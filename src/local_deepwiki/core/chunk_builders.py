"""Module-level chunk builder functions extracted from CodeChunker.

These functions create summary and overview chunks (MODULE, FILE_SUMMARY,
MODULE_SUMMARY, IMPORT) and are called by :class:`CodeChunker` but live
outside the class to keep its method count manageable.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from tree_sitter import Node

from local_deepwiki.core.chunk_extractors import (
    CLASS_NODE_TYPES,
    FUNCTION_NODE_TYPES,
    IMPORT_NODE_TYPES,
)
from local_deepwiki.core.parser import (
    find_nodes_by_type,
    get_node_name,
    get_node_text,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language


# ---------------------------------------------------------------------------
# Shared helpers (also used by CodeChunker for remaining methods)
# ---------------------------------------------------------------------------


def generate_chunk_id(file_path: str, name: str, line: int) -> str:
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


def is_inside_class(node: Node, class_types: set[str]) -> bool:
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


# ---------------------------------------------------------------------------
# Private helpers for file / module summary content
# ---------------------------------------------------------------------------


def _extract_module_docstring(
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
    class_names = [get_node_name(c, source, language) or "anonymous" for c in classes]
    return f"Classes: {', '.join(class_names)}"


def _build_function_summary(
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
        if not is_inside_class(f, class_types)
    ]
    if not functions:
        return None
    func_names = [get_node_name(f, source, language) or "anonymous" for f in functions]
    return f"Functions: {', '.join(func_names)}"


# ---------------------------------------------------------------------------
# Public chunk builder functions
# ---------------------------------------------------------------------------


def create_file_summary(root: Node, source: bytes, language: Language) -> str:
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
        if not is_inside_class(f, class_types)
    ]
    if functions:
        func_names = [
            get_node_name(f, source, language) or "anonymous" for f in functions
        ]
        parts.append(f"# Functions: {', '.join(func_names)}")

    return "\n\n".join(parts) if parts else "# Empty file"


def create_module_chunk(
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
    content = create_file_summary(root, source, language)

    chunk_id = generate_chunk_id(file_path, "module", 0)
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


def create_imports_chunk(
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

    chunk_id = generate_chunk_id(file_path, "imports", start_line)
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


def create_file_summary_chunk(
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

    docstring = _extract_module_docstring(root, source, language)
    if docstring:
        parts.append(f"Description: {docstring}")

    for section in (
        _build_import_summary(root, source, language),
        _build_class_summary(root, source, language),
        _build_function_summary(root, source, language),
    ):
        if section:
            parts.append(section)

    content = "\n".join(parts)
    chunk_id = generate_chunk_id(file_path, "file_summary", 0)
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


def create_module_summary_chunk(
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
    chunk_id = generate_chunk_id(file_path, "module_summary", 0)
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
