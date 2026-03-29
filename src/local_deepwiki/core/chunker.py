"""AST-based code chunking for semantic extraction."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from tree_sitter import Node

from local_deepwiki.config import ChunkingConfig, get_config
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

# Re-export extracted names for backward compatibility
__all__ = [
    "FUNCTION_NODE_TYPES",
    "CLASS_NODE_TYPES",
    "IMPORT_NODE_TYPES",
    "get_parent_classes",
    "extract_python_parameter_types",
    "extract_python_parameter_defaults",
    "extract_python_return_type",
    "extract_python_decorators",
    "is_async_function",
    "extract_python_raised_exceptions",
    "extract_function_type_metadata",
    "CodeChunker",
]

logger = get_logger(__name__)


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
        yield self._create_module_chunk(root, source, language, rel_path)

        # For __init__.py files, yield a MODULE_SUMMARY chunk
        if file_path.name == "__init__.py":
            yield self._create_module_summary_chunk(
                root, source, language, rel_path, file_path
            )

        # Extract imports
        import_types = IMPORT_NODE_TYPES.get(language, set())
        import_nodes = find_nodes_by_type(root, import_types)
        if import_nodes:
            yield self._create_imports_chunk(import_nodes, source, language, rel_path)

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
            if not self._is_inside_class(func_node, class_types):
                yield self._create_function_chunk(func_node, source, language, rel_path)

        # Yield FILE_SUMMARY as the last chunk for RAG retrieval on broad questions
        yield self._create_file_summary_chunk(root, source, language, rel_path)

    def _create_module_chunk(
        self,
        root: Node,
        source: bytes,
        language: Language,
        file_path: str,
    ) -> CodeChunk:
        """Create a chunk for the module/file overview.

        Args:
            root: AST root node.
            source: Source bytes.
            language: Programming language.
            file_path: Relative file path.

        Returns:
            A CodeChunk for the module.
        """
        # Get module docstring if present
        docstring = None
        if language == Language.PYTHON:
            # Python module docstring is first expression
            if root.children and root.children[0].type == "expression_statement":
                expr = root.children[0]
                if expr.children and expr.children[0].type == "string":
                    docstring = get_node_text(expr.children[0], source)
                    if docstring.startswith('"""') or docstring.startswith("'''"):
                        docstring = docstring[3:-3].strip()

        # Create a summary of the file structure
        content = self._create_file_summary(root, source, language)

        chunk_id = self._generate_id(file_path, "module", 0)
        return CodeChunk(
            id=chunk_id,
            file_path=file_path,
            language=language,
            chunk_type=ChunkType.MODULE,
            name=Path(file_path).stem,
            content=content,
            start_line=1,
            end_line=source.count(b"\n") + 1,
            docstring=docstring,
            metadata={"is_overview": True},
        )

    def _create_file_summary(
        self, root: Node, source: bytes, language: Language
    ) -> str:
        """Create a summary of file structure for the module chunk.

        Args:
            root: AST root node.
            source: Source bytes.
            language: Programming language.

        Returns:
            A summary string of file contents.
        """
        parts = []

        # List imports
        import_types = IMPORT_NODE_TYPES.get(language, set())
        imports = find_nodes_by_type(root, import_types)
        if imports:
            import_text = "\n".join(get_node_text(n, source) for n in imports[:10])
            if len(imports) > 10:
                import_text += f"\n# ... and {len(imports) - 10} more imports"
            parts.append(f"# Imports:\n{import_text}")

        # List classes
        class_types = CLASS_NODE_TYPES.get(language, set())
        classes = find_nodes_by_type(root, class_types)
        if classes:
            class_names = [
                get_node_name(c, source, language) or "anonymous" for c in classes
            ]
            parts.append(f"# Classes: {', '.join(class_names)}")

        # List functions
        function_types = FUNCTION_NODE_TYPES.get(language, set())
        functions = [
            f
            for f in find_nodes_by_type(root, function_types)
            if not self._is_inside_class(f, class_types)
        ]
        if functions:
            func_names = [
                get_node_name(f, source, language) or "anonymous" for f in functions
            ]
            parts.append(f"# Functions: {', '.join(func_names)}")

        return "\n\n".join(parts) if parts else "# Empty file"

    def _create_imports_chunk(
        self,
        import_nodes: list[Node],
        source: bytes,
        language: Language,
        file_path: str,
    ) -> CodeChunk:
        """Create a chunk for import statements.

        Args:
            import_nodes: List of import nodes.
            source: Source bytes.
            language: Programming language.
            file_path: Relative file path.

        Returns:
            A CodeChunk for imports.
        """
        content = "\n".join(get_node_text(n, source) for n in import_nodes)
        start_line = min(n.start_point[0] + 1 for n in import_nodes)
        end_line = max(n.end_point[0] + 1 for n in import_nodes)

        chunk_id = self._generate_id(file_path, "imports", start_line)
        return CodeChunk(
            id=chunk_id,
            file_path=file_path,
            language=language,
            chunk_type=ChunkType.IMPORT,
            name="imports",
            content=content,
            start_line=start_line,
            end_line=end_line,
            metadata={"import_count": len(import_nodes)},
        )

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
                class_node,
                source,
                language,
                file_path,
                class_name,
                docstring,
                parent_classes,
            )

            # Extract methods separately
            function_types = FUNCTION_NODE_TYPES.get(language, set())
            for method_node in find_nodes_by_type(class_node, function_types):
                yield self._create_method_chunk(
                    method_node, source, language, file_path, class_name
                )
        else:
            # Small class - include everything in one chunk
            chunk_id = self._generate_id(
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
        class_node: Node,
        source: bytes,
        language: Language,
        file_path: str,
        class_name: str,
        docstring: str | None,
        parent_classes: list[str] | None = None,
    ) -> CodeChunk:
        """Create a summary chunk for a large class.

        Args:
            class_node: The class AST node.
            source: Source bytes.
            language: Programming language.
            file_path: Relative file path.
            class_name: Name of the class.
            docstring: Class docstring if any.
            parent_classes: List of parent class names.

        Returns:
            A summary CodeChunk for the class.
        """
        # Get class signature and method list
        function_types = FUNCTION_NODE_TYPES.get(language, set())
        methods = find_nodes_by_type(class_node, function_types)
        method_names = [
            get_node_name(m, source, language) or "anonymous" for m in methods
        ]

        # Build summary content
        signature_end = class_node.start_byte
        for child in class_node.children:
            if child.type in ("block", "class_body", "declaration_list"):
                signature_end = child.start_byte
                break

        signature = (
            source[class_node.start_byte : signature_end]
            .decode("utf-8", errors="replace")
            .strip()
        )
        content = f"{signature}\n    # Methods: {', '.join(method_names)}"

        chunk_id = self._generate_id(
            file_path, f"class_{class_name}", class_node.start_point[0]
        )
        metadata: dict[str, bool | int | list[str]] = {
            "is_summary": True,
            "method_count": len(methods),
        }
        if parent_classes:
            metadata["parent_classes"] = parent_classes
        return CodeChunk(
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

        chunk_id = self._generate_id(
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

        chunk_id = self._generate_id(
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

    def _extract_module_docstring(
        self,
        root: Node,
        source: bytes,
        language: Language,
    ) -> str | None:
        """Extract the module-level docstring from a Python AST root.

        Returns:
            The stripped docstring text, or None if not present or not Python.
        """
        if language != Language.PYTHON:
            return None
        if not root.children or root.children[0].type != "expression_statement":
            return None
        expr = root.children[0]
        if not expr.children or expr.children[0].type != "string":
            return None
        docstring = get_node_text(expr.children[0], source)
        if docstring.startswith('"""') or docstring.startswith("'''"):
            return docstring[3:-3].strip()
        return docstring

    def _build_import_summary(
        self,
        root: Node,
        source: bytes,
        language: Language,
    ) -> str | None:
        """Build a compact import summary string (at most 10 shown).

        Returns:
            An "Imports: ..." string, or None if no imports found.
        """
        import_types = IMPORT_NODE_TYPES.get(language, set())
        imports = find_nodes_by_type(root, import_types)
        if not imports:
            return None
        import_lines = [get_node_text(n, source) for n in imports[:10]]
        import_text = ", ".join(import_lines)
        if len(imports) > 10:
            import_text += f" ... and {len(imports) - 10} more imports"
        return f"Imports: {import_text}"

    def _build_class_summary(
        self,
        root: Node,
        source: bytes,
        language: Language,
    ) -> str | None:
        """Build a comma-separated list of class names defined in the file.

        Returns:
            A "Classes: ..." string, or None if no classes found.
        """
        class_types = CLASS_NODE_TYPES.get(language, set())
        classes = find_nodes_by_type(root, class_types)
        if not classes:
            return None
        class_names = [
            get_node_name(c, source, language) or "anonymous" for c in classes
        ]
        return f"Classes: {', '.join(class_names)}"

    def _build_function_summary(
        self,
        root: Node,
        source: bytes,
        language: Language,
    ) -> str | None:
        """Build a comma-separated list of top-level function names.

        Returns:
            A "Functions: ..." string, or None if no top-level functions found.
        """
        class_types = CLASS_NODE_TYPES.get(language, set())
        function_types = FUNCTION_NODE_TYPES.get(language, set())
        functions = [
            f
            for f in find_nodes_by_type(root, function_types)
            if not self._is_inside_class(f, class_types)
        ]
        if not functions:
            return None
        func_names = [
            get_node_name(f, source, language) or "anonymous" for f in functions
        ]
        return f"Functions: {', '.join(func_names)}"

    def _create_file_summary_chunk(
        self,
        root: Node,
        source: bytes,
        language: Language,
        file_path: str,
    ) -> CodeChunk:
        """Create a FILE_SUMMARY chunk for document-level RAG retrieval.

        Builds a structured summary containing the file path, module docstring,
        imports (first 10), all classes, and all top-level functions.

        Args:
            root: AST root node.
            source: Source bytes.
            language: Programming language.
            file_path: Relative file path.

        Returns:
            A CodeChunk with chunk_type FILE_SUMMARY.
        """
        parts: list[str] = [f"File: {file_path}"]

        docstring = self._extract_module_docstring(root, source, language)
        if docstring:
            parts.append(f"Description: {docstring}")

        for section in (
            self._build_import_summary(root, source, language),
            self._build_class_summary(root, source, language),
            self._build_function_summary(root, source, language),
        ):
            if section:
                parts.append(section)

        content = "\n".join(parts)
        chunk_id = self._generate_id(file_path, "file_summary", 0)
        return CodeChunk(
            id=chunk_id,
            file_path=file_path,
            language=language,
            chunk_type=ChunkType.FILE_SUMMARY,
            name=Path(file_path).stem,
            content=content,
            start_line=1,
            end_line=source.count(b"\n") + 1,
            metadata={"is_file_summary": True},
        )

    def _create_module_summary_chunk(
        self,
        root: Node,
        source: bytes,
        language: Language,
        file_path: str,
        abs_path: Path,
    ) -> CodeChunk:
        """Create a MODULE_SUMMARY chunk for ``__init__.py`` package files.

        Content includes the package name, docstring, and re-export lines.

        Args:
            root: AST root node.
            source: Source bytes.
            language: Programming language.
            file_path: Relative file path.
            abs_path: Absolute path to the file.

        Returns:
            A CodeChunk with chunk_type MODULE_SUMMARY.
        """
        package_name = abs_path.parent.name
        parts: list[str] = [f"Package: {package_name}"]

        # Extract package docstring (Python only)
        if language == Language.PYTHON:
            if root.children and root.children[0].type == "expression_statement":
                expr = root.children[0]
                if expr.children and expr.children[0].type == "string":
                    docstring = get_node_text(expr.children[0], source)
                    if docstring.startswith('"""') or docstring.startswith("'''"):
                        docstring = docstring[3:-3].strip()
                    parts.append(f"Description: {docstring}")

        # Collect re-export lines (from .X import Y)
        import_types = IMPORT_NODE_TYPES.get(language, set())
        imports = find_nodes_by_type(root, import_types)
        if imports:
            re_exports: list[str] = []
            for node in imports:
                text = get_node_text(node, source)
                re_exports.append(text)
            if re_exports:
                parts.append(f"Re-exports: {', '.join(re_exports)}")

        content = "\n".join(parts)
        chunk_id = self._generate_id(file_path, "module_summary", 0)
        return CodeChunk(
            id=chunk_id,
            file_path=file_path,
            language=language,
            chunk_type=ChunkType.MODULE_SUMMARY,
            name=package_name,
            content=content,
            start_line=1,
            end_line=source.count(b"\n") + 1,
            metadata={"is_module_summary": True, "package_name": package_name},
        )

    @staticmethod
    def _is_inside_class(node: Node, class_types: set[str]) -> bool:
        """Check if a node is inside a class definition.

        Args:
            node: The node to check.
            class_types: Set of class node type names.

        Returns:
            True if the node is inside a class.
        """
        parent = node.parent
        while parent:
            if parent.type in class_types:
                return True
            parent = parent.parent
        return False

    @staticmethod
    def _generate_id(file_path: str, name: str, line: int) -> str:
        """Generate a unique chunk ID.

        Args:
            file_path: File path.
            name: Chunk name.
            line: Line number.

        Returns:
            A unique ID string.
        """
        key = f"{file_path}:{name}:{line}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
