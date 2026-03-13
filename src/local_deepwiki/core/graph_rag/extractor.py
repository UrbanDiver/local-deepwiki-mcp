"""Entity and relationship extraction from tree-sitter ASTs.

Walks a parsed AST to discover functions, classes, methods and the
relationships between them (calls, imports, inheritance, containment).
Results are returned as immutable ``FileGraphData`` objects.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from local_deepwiki.core.chunk_extractors import (
    CLASS_NODE_TYPES,
    FUNCTION_NODE_TYPES,
    IMPORT_NODE_TYPES,
    get_parent_classes,
)
from local_deepwiki.core.parser import find_nodes_by_type, get_node_name, get_node_text
from local_deepwiki.core.graph_rag.models import (
    EntityType,
    FileGraphData,
    GraphEntity,
    GraphRelationship,
    RelationshipType,
    entity_id,
    relationship_id,
)
from local_deepwiki.generators.analysis.callgraph import (
    CALL_NODE_TYPES,
    extract_call_name,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import CodeChunk, Language

logger = get_logger(__name__)


class GraphRelationshipExtractor:
    """Extract entities and relationships from a tree-sitter AST.

    Walks the AST once for each extraction phase (entities, calls,
    imports, inheritance, containment) and aggregates the results into
    a single ``FileGraphData``.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_from_ast(
        self,
        root_node: Any,
        source_bytes: bytes,
        language: Language,
        file_path: str,
    ) -> FileGraphData:
        """Extract entities and relationships from a parsed AST.

        Args:
            root_node: tree-sitter root ``Node``.
            source_bytes: Original source bytes used for text extraction.
            language: The ``Language`` enum value for this file.
            file_path: Repository-relative path for deterministic IDs.

        Returns:
            ``FileGraphData`` with extracted entities and relationships.
        """
        entities = self._extract_entities(root_node, source_bytes, language, file_path)

        # Build a lookup for quick entity resolution by name
        entity_map: dict[str, GraphEntity] = {e.name: e for e in entities}
        qualified_map: dict[str, GraphEntity] = {e.qualified_name: e for e in entities}

        calls = self._extract_calls(
            root_node,
            source_bytes,
            language,
            file_path,
            entity_map,
            qualified_map,
        )
        imports = self._extract_imports(
            root_node,
            source_bytes,
            language,
            file_path,
        )
        inheritance = self._extract_inheritance(
            root_node,
            source_bytes,
            language,
            file_path,
            entity_map,
        )
        containment = self._extract_containment(entities, file_path)

        all_relationships = (*calls, *imports, *inheritance, *containment)

        return FileGraphData(
            file_path=file_path,
            entities=tuple(entities),
            relationships=all_relationships,
        )

    @staticmethod
    def link_entities_to_chunks(
        entities: list[GraphEntity],
        chunks: list[CodeChunk],
    ) -> list[GraphEntity]:
        """Match entities to ``CodeChunk`` objects by file path, name, and start line.

        Returns new ``GraphEntity`` instances with ``chunk_id`` set for every
        entity that could be matched.  Entities without a matching chunk are
        returned unchanged.

        Args:
            entities: Entities to link.
            chunks: Available code chunks.

        Returns:
            New list of entities with ``chunk_id`` populated where possible.
        """
        # Index chunks by (file_path, name) for O(1) lookups
        chunk_index: dict[tuple[str, str | None], list[CodeChunk]] = {}
        for chunk in chunks:
            key = (chunk.file_path, chunk.name)
            chunk_index.setdefault(key, []).append(chunk)

        result: list[GraphEntity] = []
        for ent in entities:
            matched_chunk_id = _find_matching_chunk_id(ent, chunk_index)
            if matched_chunk_id:
                result.append(replace(ent, chunk_id=matched_chunk_id))
            else:
                result.append(ent)
        return result

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    def _extract_entities(
        self,
        root_node: Any,
        source_bytes: bytes,
        language: Language,
        file_path: str,
    ) -> list[GraphEntity]:
        """Extract function, class, and method entities from the AST."""
        entities: list[GraphEntity] = []

        func_types = FUNCTION_NODE_TYPES.get(language, set())
        class_types = CLASS_NODE_TYPES.get(language, set())

        try:
            # --- Classes ---
            for class_node in find_nodes_by_type(root_node, class_types):
                class_name = get_node_name(class_node, source_bytes, language)
                if not class_name:
                    continue
                entities.append(
                    GraphEntity(
                        id=entity_id(file_path, class_name),
                        name=class_name,
                        qualified_name=class_name,
                        entity_type=EntityType.CLASS,
                        file_path=file_path,
                        start_line=class_node.start_point[0] + 1,
                        end_line=class_node.end_point[0] + 1,
                    )
                )

                # --- Methods (functions nested inside this class) ---
                for method_node in find_nodes_by_type(class_node, func_types):
                    method_name = get_node_name(method_node, source_bytes, language)
                    if not method_name:
                        continue
                    qualified = f"{class_name}.{method_name}"
                    entities.append(
                        GraphEntity(
                            id=entity_id(file_path, qualified),
                            name=method_name,
                            qualified_name=qualified,
                            entity_type=EntityType.METHOD,
                            file_path=file_path,
                            start_line=method_node.start_point[0] + 1,
                            end_line=method_node.end_point[0] + 1,
                            metadata={"parent_name": class_name},
                        )
                    )

            # --- Top-level functions (not inside a class) ---
            for func_node in find_nodes_by_type(root_node, func_types):
                if _is_inside_class(func_node, class_types):
                    continue
                func_name = get_node_name(func_node, source_bytes, language)
                if not func_name:
                    continue
                entities.append(
                    GraphEntity(
                        id=entity_id(file_path, func_name),
                        name=func_name,
                        qualified_name=func_name,
                        entity_type=EntityType.FUNCTION,
                        file_path=file_path,
                        start_line=func_node.start_point[0] + 1,
                        end_line=func_node.end_point[0] + 1,
                    )
                )
        except Exception:
            logger.exception("Failed to extract entities from %s", file_path)

        return entities

    def _extract_calls(
        self,
        root_node: Any,
        source_bytes: bytes,
        language: Language,
        file_path: str,
        entity_map: dict[str, GraphEntity],
        qualified_map: dict[str, GraphEntity],
    ) -> tuple[GraphRelationship, ...]:
        """Extract *calls* relationships from function/method bodies."""
        relationships: list[GraphRelationship] = []

        func_types = FUNCTION_NODE_TYPES.get(language, set())
        class_types = CLASS_NODE_TYPES.get(language, set())
        call_types = CALL_NODE_TYPES.get(language, set())
        if not call_types:
            return ()

        try:
            all_func_nodes = find_nodes_by_type(root_node, func_types)
            for func_node in all_func_nodes:
                caller_name = get_node_name(func_node, source_bytes, language)
                if not caller_name:
                    continue

                # Determine qualified name
                parent_class = _get_enclosing_class_name(
                    func_node,
                    class_types,
                    source_bytes,
                    language,
                )
                qualified_caller = (
                    f"{parent_class}.{caller_name}" if parent_class else caller_name
                )

                source_entity = qualified_map.get(qualified_caller)
                if source_entity is None:
                    continue

                # Find calls within this function
                call_nodes = find_nodes_by_type(func_node, call_types)
                seen: set[str] = set()
                for call_node in call_nodes:
                    callee_name = extract_call_name(call_node, source_bytes, language)
                    if not callee_name or callee_name in seen:
                        continue
                    seen.add(callee_name)

                    # Resolve the target entity (try qualified first, then simple)
                    target_entity = _resolve_callee(
                        callee_name,
                        parent_class,
                        entity_map,
                        qualified_map,
                    )
                    target_id_str = (
                        target_entity.id
                        if target_entity
                        else entity_id(file_path, callee_name)
                    )

                    rel_id = relationship_id(
                        source_entity.id,
                        RelationshipType.CALLS,
                        target_id_str,
                    )
                    relationships.append(
                        GraphRelationship(
                            id=rel_id,
                            source_id=source_entity.id,
                            target_id=target_id_str,
                            relationship=RelationshipType.CALLS,
                            file_path=file_path,
                        )
                    )
        except Exception:
            logger.exception("Failed to extract calls from %s", file_path)

        return tuple(relationships)

    def _extract_imports(
        self,
        root_node: Any,
        source_bytes: bytes,
        language: Language,
        file_path: str,
    ) -> tuple[GraphRelationship, ...]:
        """Extract *imports* relationships from import statements."""
        relationships: list[GraphRelationship] = []

        import_types = IMPORT_NODE_TYPES.get(language, set())
        if not import_types:
            return ()

        try:
            file_entity_id = entity_id(file_path, file_path)

            for import_node in find_nodes_by_type(root_node, import_types):
                module_name = _extract_import_module(
                    import_node,
                    source_bytes,
                    language,
                )
                if not module_name:
                    continue

                target_id_str = entity_id(module_name, module_name)
                rel_id = relationship_id(
                    file_entity_id,
                    RelationshipType.IMPORTS,
                    target_id_str,
                )
                relationships.append(
                    GraphRelationship(
                        id=rel_id,
                        source_id=file_entity_id,
                        target_id=target_id_str,
                        relationship=RelationshipType.IMPORTS,
                        file_path=file_path,
                    )
                )
        except Exception:
            logger.exception("Failed to extract imports from %s", file_path)

        return tuple(relationships)

    def _extract_inheritance(
        self,
        root_node: Any,
        source_bytes: bytes,
        language: Language,
        file_path: str,
        entity_map: dict[str, GraphEntity],
    ) -> tuple[GraphRelationship, ...]:
        """Extract *inherits_from* relationships from class definitions."""
        relationships: list[GraphRelationship] = []
        class_types = CLASS_NODE_TYPES.get(language, set())

        try:
            for class_node in find_nodes_by_type(root_node, class_types):
                class_name = get_node_name(class_node, source_bytes, language)
                if not class_name:
                    continue

                parents = get_parent_classes(class_node, source_bytes, language)
                child_entity = entity_map.get(class_name)
                if child_entity is None:
                    continue

                for parent_name in parents:
                    parent_entity = entity_map.get(parent_name)
                    target_id_str = (
                        parent_entity.id
                        if parent_entity
                        else entity_id(file_path, parent_name)
                    )
                    rel_id = relationship_id(
                        child_entity.id,
                        RelationshipType.INHERITS_FROM,
                        target_id_str,
                    )
                    relationships.append(
                        GraphRelationship(
                            id=rel_id,
                            source_id=child_entity.id,
                            target_id=target_id_str,
                            relationship=RelationshipType.INHERITS_FROM,
                            file_path=file_path,
                        )
                    )
        except Exception:
            logger.exception("Failed to extract inheritance from %s", file_path)

        return tuple(relationships)

    def _extract_containment(
        self,
        entities: list[GraphEntity],
        file_path: str,
    ) -> tuple[GraphRelationship, ...]:
        """Extract *contains* relationships for methods inside classes."""
        relationships: list[GraphRelationship] = []

        # Build a set of class entity ids for quick lookup
        class_entities: dict[str, GraphEntity] = {
            e.name: e for e in entities if e.entity_type == EntityType.CLASS
        }

        try:
            for ent in entities:
                if ent.entity_type != EntityType.METHOD:
                    continue
                parent_name = ent.metadata.get("parent_name", "")
                parent_entity = class_entities.get(parent_name)
                if parent_entity is None:
                    continue

                rel_id = relationship_id(
                    parent_entity.id,
                    RelationshipType.CONTAINS,
                    ent.id,
                )
                relationships.append(
                    GraphRelationship(
                        id=rel_id,
                        source_id=parent_entity.id,
                        target_id=ent.id,
                        relationship=RelationshipType.CONTAINS,
                        file_path=file_path,
                    )
                )
        except Exception:
            logger.exception("Failed to extract containment from %s", file_path)

        return tuple(relationships)


# ------------------------------------------------------------------
# Module-level helpers (private)
# ------------------------------------------------------------------


def _is_inside_class(node: Any, class_types: set[str]) -> bool:
    """Return ``True`` if *node* is nested inside a class node."""
    parent = node.parent
    while parent:
        if parent.type in class_types:
            return True
        parent = parent.parent
    return False


def _get_enclosing_class_name(
    node: Any,
    class_types: set[str],
    source_bytes: bytes,
    language: Language,
) -> str | None:
    """Return the name of the class enclosing *node*, or ``None``."""
    parent = node.parent
    while parent:
        if parent.type in class_types:
            return get_node_name(parent, source_bytes, language)
        parent = parent.parent
    return None


def _resolve_callee(
    callee_name: str,
    parent_class: str | None,
    entity_map: dict[str, GraphEntity],
    qualified_map: dict[str, GraphEntity],
) -> GraphEntity | None:
    """Try to resolve a callee name to a known entity."""
    # Try qualified name within same class first
    if parent_class:
        qualified = f"{parent_class}.{callee_name}"
        if qualified in qualified_map:
            return qualified_map[qualified]

    # Try as a qualified name directly
    if callee_name in qualified_map:
        return qualified_map[callee_name]

    # Try simple name
    if callee_name in entity_map:
        return entity_map[callee_name]

    return None


def _extract_import_module(
    import_node: Any,
    source_bytes: bytes,
    language: Language,
) -> str | None:
    """Extract the module/package name from an import AST node.

    Returns the top-level module name (e.g. ``os`` from ``import os.path``
    or ``flask`` from ``from flask import Flask``).
    """
    try:
        if language == Language.PYTHON:
            return _extract_python_import(import_node, source_bytes)
        if language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            return _extract_js_import(import_node, source_bytes)
        if language == Language.GO:
            return _extract_go_import(import_node, source_bytes)
        if language == Language.RUST:
            return _extract_rust_import(import_node, source_bytes)
        if language == Language.JAVA:
            return _extract_java_import(import_node, source_bytes)
        # Fallback: extract raw text from the node
        text = get_node_text(import_node, source_bytes).strip()
        return text if text else None
    except Exception:
        logger.debug("Failed to extract import module from node", exc_info=True)
        return None


def _extract_python_import(node: Any, source_bytes: bytes) -> str | None:
    """Handle ``import X`` and ``from X import Y``."""
    if node.type == "import_from_statement":
        # from X import Y  -> module_name child is typically "dotted_name"
        module_node = node.child_by_field_name("module_name")
        if module_node:
            return get_node_text(module_node, source_bytes)
        # Fallback: look for dotted_name child
        for child in node.children:
            if child.type == "dotted_name":
                return get_node_text(child, source_bytes)
    elif node.type == "import_statement":
        # import X  or  import X.Y
        for child in node.children:
            if child.type == "dotted_name":
                return get_node_text(child, source_bytes)
            if child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                if name_node:
                    return get_node_text(name_node, source_bytes)
    return None


def _extract_js_import(node: Any, source_bytes: bytes) -> str | None:
    """Handle JS/TS import statements."""
    # import ... from "module"
    source_node = node.child_by_field_name("source")
    if source_node:
        raw = get_node_text(source_node, source_bytes)
        return raw.strip("\"'")
    # Fallback: look for string children
    for child in node.children:
        if child.type == "string":
            raw = get_node_text(child, source_bytes)
            return raw.strip("\"'")
    return None


def _extract_go_import(node: Any, source_bytes: bytes) -> str | None:
    """Handle Go import declarations."""
    for child in node.children:
        if child.type == "import_spec":
            path_node = child.child_by_field_name("path")
            if path_node:
                raw = get_node_text(path_node, source_bytes)
                return raw.strip('"')
        if child.type == "import_spec_list":
            # First spec in a grouped import
            for spec in child.children:
                if spec.type == "import_spec":
                    path_node = spec.child_by_field_name("path")
                    if path_node:
                        raw = get_node_text(path_node, source_bytes)
                        return raw.strip('"')
    return None


def _extract_rust_import(node: Any, source_bytes: bytes) -> str | None:
    """Handle Rust ``use`` declarations."""
    # use crate_name::module::item;
    for child in node.children:
        if child.type in ("scoped_identifier", "identifier", "use_wildcard"):
            text = get_node_text(child, source_bytes)
            # Return the top-level crate/module
            return text.split("::")[0] if "::" in text else text
        if child.type == "scoped_use_list":
            text = get_node_text(child, source_bytes)
            return text.split("::")[0] if "::" in text else text
    return None


def _extract_java_import(node: Any, source_bytes: bytes) -> str | None:
    """Handle Java ``import`` declarations."""
    for child in node.children:
        if child.type == "scoped_identifier":
            text = get_node_text(child, source_bytes)
            # Return the full dotted path
            return text
    return None


def _find_matching_chunk_id(
    entity: GraphEntity,
    chunk_index: dict[tuple[str, str | None], list[CodeChunk]],
) -> str | None:
    """Find a matching chunk ID for an entity, preferring exact line match."""
    candidates = chunk_index.get((entity.file_path, entity.name), [])
    if not candidates:
        return None

    # Prefer a chunk whose start_line matches exactly
    for chunk in candidates:
        if chunk.start_line == entity.start_line:
            return chunk.id

    # Fall back to the first candidate
    return candidates[0].id
