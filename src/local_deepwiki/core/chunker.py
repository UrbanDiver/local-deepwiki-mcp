"""AST-based code chunking for semantic extraction."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node

from local_deepwiki.config import ChunkingConfig, get_config
from local_deepwiki.core.chunk_builders import (
    create_file_summary_chunk,
    create_imports_chunk,
    create_module_chunk,
    create_module_summary_chunk,
    generate_chunk_id,
    is_inside_class,
)
from local_deepwiki.core.chunk_extractors import (
    CLASS_NODE_TYPES,
    FUNCTION_NODE_TYPES,
    IMPORT_NODE_TYPES,
    extract_function_type_metadata,
    extract_python_decorators,
    extract_python_parameter_defaults,
    extract_python_parameter_types,
    extract_python_raised_exceptions,
    extract_python_return_type,
    get_parent_classes,
    is_async_function,
)
from local_deepwiki.core.parser import (
    CodeParser,
    find_nodes_by_type,
    get_docstring,
    get_node_name,
    get_node_text,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, CodeChunk, Language
from local_deepwiki.plugins.registry import get_plugin_registry

__all__ = ["CodeChunker"]

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ClassChunkContext:
    """Immutable context for creating a class summary chunk.

    Bundles the data extracted from the AST that
    :meth:`CodeChunker._create_class_summary_chunk` needs.
    """

    class_node: Node
    source: bytes
    language: Language
    file_path: str
    class_name: str
    docstring: str | None = None
    parent_classes: list[str] | None = None


class CodeChunker:
    """Extract semantic code chunks from source files using AST analysis."""

    def __init__(self, config: ChunkingConfig | None = None):
        """Initialize the chunker.

        Args:
            config: Optional chunking configuration.
        """
        base_config = config or get_config().chunking
        # Store a defensive copy to prevent external mutation
        self.config = base_config.model_copy(deep=True)
        self.parser = CodeParser()

    def chunk_file(self, file_path: Path, repo_root: Path) -> Iterator[CodeChunk]:
        """Extract code chunks from a source file.

        Checks for registered language parser plugins first. If a plugin
        handles the file extension, uses the plugin's parse_file method.
        Otherwise falls back to the built-in tree-sitter parser.

        Args:
            file_path: Path to the source file.
            repo_root: Root directory of the repository.

        Yields:
            CodeChunk objects for each semantic unit found.
        """
        # Check for plugin parser first
        registry = get_plugin_registry()
        plugin_parser = registry.get_parser_for_extension(file_path.suffix)

        if plugin_parser is not None:
            # Use plugin parser - it returns CodeChunk objects directly
            logger.debug(
                "Using plugin parser '%s' for %s",
                plugin_parser.language_name,
                file_path.name,
            )
            try:
                source = file_path.read_bytes()
                chunks = plugin_parser.parse_file(file_path, source)
                yield from chunks
                return
            except (OSError, ValueError, LookupError, TypeError, RuntimeError) as e:
                logger.warning(
                    "Plugin parser failed for %s: %s, falling back to built-in",
                    file_path,
                    e,
                )

        # Fall back to built-in tree-sitter parser
        result = self.parser.parse_file(file_path)
        if result is None:
            logger.debug("Skipping unsupported file: %s", file_path)
            return

        root, language, source = result
        rel_path = str(file_path.relative_to(repo_root))
        logger.debug("Chunking %s (%s)", rel_path, language.value)

        # Extract module-level chunk (file overview)
        yield create_module_chunk(root, source, language, rel_path)

        # For __init__.py files, yield a MODULE_SUMMARY chunk
        if file_path.name == "__init__.py":
            yield create_module_summary_chunk(
                root, source, language, rel_path, file_path
            )

        # Extract imports
        import_types = IMPORT_NODE_TYPES.get(language, set())
        import_nodes = find_nodes_by_type(root, import_types)
        if import_nodes:
            yield create_imports_chunk(import_nodes, source, language, rel_path)

        # Extract classes and their methods
        class_types = CLASS_NODE_TYPES.get(language, set())
        for class_node in find_nodes_by_type(root, class_types):
            yield from self._extract_class_chunks(
                class_node, source, language, rel_path
            )

        # Extract top-level functions (not inside classes)
        function_types = FUNCTION_NODE_TYPES.get(language, set())
        for func_node in find_nodes_by_type(root, function_types):
            # Skip if inside a class (already processed)
            if not is_inside_class(func_node, class_types):
                yield self._create_function_chunk(func_node, source, language, rel_path)

        # Yield FILE_SUMMARY as the last chunk for RAG retrieval on broad questions
        yield create_file_summary_chunk(root, source, language, rel_path)

    def _extract_class_chunks(
        self,
        class_node: Node,
        source: bytes,
        language: Language,
        file_path: str,
    ) -> Iterator[CodeChunk]:
        """Extract chunks from a class definition.

        Args:
            class_node: The class AST node.
            source: Source bytes.
            language: Programming language.
            file_path: Relative file path.

        Yields:
            CodeChunks for the class and its methods.
        """
        class_name = get_node_name(class_node, source, language) or "anonymous"
        docstring = get_docstring(class_node, source, language)
        content = get_node_text(class_node, source)

        # Extract parent classes for inheritance
        parent_classes = get_parent_classes(class_node, source, language)

        # Check if class is too large and needs to be split
        lines = content.count("\n") + 1
        if lines > self.config.class_split_threshold:
            # For large classes, create a summary chunk and method chunks
            yield self._create_class_summary_chunk(
                ClassChunkContext(
                    class_node=class_node,
                    source=source,
                    language=language,
                    file_path=file_path,
                    class_name=class_name,
                    docstring=docstring,
                    parent_classes=parent_classes,
                )
            )

            # Extract methods separately
            function_types = FUNCTION_NODE_TYPES.get(language, set())
            for method_node in find_nodes_by_type(class_node, function_types):
                yield self._create_method_chunk(
                    method_node, source, language, file_path, class_name
                )
        else:
            # Small class - include everything in one chunk
            chunk_id = generate_chunk_id(
                file_path, f"class_{class_name}", class_node.start_point[0]
            )
            metadata: dict[str, int | list[str]] = {"line_count": lines}
            if parent_classes:
                metadata["parent_classes"] = parent_classes
            yield CodeChunk(
                id=chunk_id,
                file_path=file_path,
                language=language,
                chunk_type=ChunkType.CLASS,
                name=class_name,
                content=content,
                start_line=class_node.start_point[0] + 1,
                end_line=class_node.end_point[0] + 1,
                docstring=docstring,
                metadata=metadata,
            )

    def _create_class_summary_chunk(
        self,
        ctx: ClassChunkContext,
    ) -> CodeChunk:
        """Create a summary chunk for a large class.

        Args:
            ctx: Immutable context with class node, source, language,
                file path, class name, docstring, and parent classes.

        Returns:
            A summary CodeChunk for the class.
        """
        # Get class signature and method list
        function_types = FUNCTION_NODE_TYPES.get(ctx.language, set())
        methods = find_nodes_by_type(ctx.class_node, function_types)
        method_names = [
            get_node_name(m, ctx.source, ctx.language) or "anonymous" for m in methods
        ]

        # Build summary content
        signature_end = ctx.class_node.start_byte
        for child in ctx.class_node.children:
            if child.type in ("block", "class_body", "declaration_list"):
                signature_end = child.start_byte
                break

        signature = (
            ctx.source[ctx.class_node.start_byte : signature_end]
            .decode("utf-8", errors="replace")
            .strip()
        )
        content = f"{signature}\n    # Methods: {', '.join(method_names)}"

        chunk_id = generate_chunk_id(
            ctx.file_path, f"class_{ctx.class_name}", ctx.class_node.start_point[0]
        )
        metadata: dict[str, bool | int | list[str]] = {
            "is_summary": True,
            "method_count": len(methods),
        }
        if ctx.parent_classes:
            metadata["parent_classes"] = ctx.parent_classes
        return CodeChunk(
            id=chunk_id,
            file_path=ctx.file_path,
            language=ctx.language,
            chunk_type=ChunkType.CLASS,
            name=ctx.class_name,
            content=content,
            start_line=ctx.class_node.start_point[0] + 1,
            end_line=ctx.class_node.end_point[0] + 1,
            docstring=ctx.docstring,
            metadata=metadata,
        )

    def _create_method_chunk(
        self,
        method_node: Node,
        source: bytes,
        language: Language,
        file_path: str,
        class_name: str,
    ) -> CodeChunk:
        """Create a chunk for a class method.

        Args:
            method_node: The method AST node.
            source: Source bytes.
            language: Programming language.
            file_path: Relative file path.
            class_name: Name of the parent class.

        Returns:
            A CodeChunk for the method.
        """
        method_name = get_node_name(method_node, source, language) or "anonymous"
        content = get_node_text(method_node, source)
        docstring = get_docstring(method_node, source, language)

        # Extract type annotation metadata
        metadata = extract_function_type_metadata(method_node, source, language)

        chunk_id = generate_chunk_id(
            file_path, f"{class_name}.{method_name}", method_node.start_point[0]
        )
        return CodeChunk(
            id=chunk_id,
            file_path=file_path,
            language=language,
            chunk_type=ChunkType.METHOD,
            name=method_name,
            content=content,
            start_line=method_node.start_point[0] + 1,
            end_line=method_node.end_point[0] + 1,
            docstring=docstring,
            parent_name=class_name,
            metadata=metadata,
        )

    def _create_function_chunk(
        self,
        func_node: Node,
        source: bytes,
        language: Language,
        file_path: str,
    ) -> CodeChunk:
        """Create a chunk for a top-level function.

        Args:
            func_node: The function AST node.
            source: Source bytes.
            language: Programming language.
            file_path: Relative file path.

        Returns:
            A CodeChunk for the function.
        """
        func_name = get_node_name(func_node, source, language) or "anonymous"
        content = get_node_text(func_node, source)
        docstring = get_docstring(func_node, source, language)

        # Extract type annotation metadata
        metadata = extract_function_type_metadata(func_node, source, language)

        chunk_id = generate_chunk_id(
            file_path, f"func_{func_name}", func_node.start_point[0]
        )
        return CodeChunk(
            id=chunk_id,
            file_path=file_path,
            language=language,
            chunk_type=ChunkType.FUNCTION,
            name=func_name,
            content=content,
            start_line=func_node.start_point[0] + 1,
            end_line=func_node.end_point[0] + 1,
            docstring=docstring,
            metadata=metadata,
        )
