"""Language-specific docstring extraction from tree-sitter AST nodes."""

from __future__ import annotations

from typing import Any, cast

from tree_sitter import Node

from local_deepwiki.core.parser.ast_utils import get_node_text
from local_deepwiki.models import Language as LangEnum


def _collect_preceding_comments(
    node: Node,
    source: bytes,
    comment_types: set[str],
    prefix: str | None = None,
) -> list[str]:
    """Collect all consecutive preceding comment lines.

    Args:
        node: The tree-sitter node to look before.
        source: The original source bytes.
        comment_types: Set of comment node type names (e.g., {"comment", "line_comment"}).
        prefix: Optional prefix that comments must start with (e.g., "///" for doc comments).

    Returns:
        List of comment text lines in order (first comment first).
    """
    comments: list[str] = []
    prev = node.prev_sibling

    while prev and prev.type in comment_types:
        text = get_node_text(prev, source)
        if prefix is None or text.startswith(prefix):
            comments.insert(0, text)
            prev = prev.prev_sibling
        else:
            # Stop at non-matching comment (e.g., regular // after ///)
            break

    return comments


def _strip_line_comment_prefix(lines: list[str], prefix: str) -> str:
    """Strip prefix from comment lines and join them.

    Args:
        lines: List of comment lines.
        prefix: The prefix to strip (e.g., "//", "///", "#").

    Returns:
        Joined docstring with prefixes removed.
    """
    stripped = []
    for line in lines:
        # Remove the prefix and optional leading space
        content = line[len(prefix) :]
        if content.startswith(" "):
            content = content[1:]
        stripped.append(content)
    return "\n".join(stripped).strip()


def _get_python_docstring(node: Node, source: bytes) -> str | None:
    """Extract Python docstring from function/class body."""
    body = node.child_by_field_name("body")
    if not body or not body.children:
        return None

    first_child = body.children[0]
    if first_child.type != "expression_statement":
        return None

    expr = first_child.children[0] if first_child.children else None
    if not expr or expr.type != "string":
        return None

    text = get_node_text(expr, source)
    if text.startswith('"""') or text.startswith("'''"):
        return text[3:-3].strip()
    if text.startswith('"') or text.startswith("'"):
        return text[1:-1].strip()
    return None


def _get_jsdoc_or_line_comments(node: Node, source: bytes) -> str | None:
    """Extract JSDoc (/** */) or multi-line // comments."""
    prev = node.prev_sibling
    if prev and prev.type == "comment":
        text = get_node_text(prev, source)
        if text.startswith("/**"):
            return text[3:-2].strip()

    comments = _collect_preceding_comments(node, source, {"comment"}, "//")
    if comments:
        return _strip_line_comment_prefix(comments, "//")
    return None


def _get_line_comments(
    node: Node, source: bytes, comment_type: str, prefix: str
) -> str | None:
    """Extract multi-line comments with a specific prefix."""
    comments = _collect_preceding_comments(node, source, {comment_type}, prefix)
    if comments:
        return _strip_line_comment_prefix(comments, prefix)
    return None


def _get_javadoc_or_doxygen(node: Node, source: bytes) -> str | None:
    """Extract Javadoc/Doxygen (/** */) or /// comments."""
    prev = node.prev_sibling
    if prev and prev.type in ("comment", "block_comment"):
        text = get_node_text(prev, source)
        if text.startswith("/**"):
            return text[3:-2].strip()

    comments = _collect_preceding_comments(node, source, {"comment"}, "///")
    if comments:
        return _strip_line_comment_prefix(comments, "///")
    return None


def _get_swift_docstring(node: Node, source: bytes) -> str | None:
    """Extract Swift /// comments or /** */ block."""
    comments = _collect_preceding_comments(node, source, {"comment"}, "///")
    if comments:
        return _strip_line_comment_prefix(comments, "///")

    prev = node.prev_sibling
    if prev and prev.type == "comment":
        text = get_node_text(prev, source)
        if text.startswith("/**"):
            return text[3:-2].strip()
    return None


def _get_block_comment(node: Node, source: bytes, comment_type: str) -> str | None:
    """Extract /** */ block comment of specified type."""
    prev = node.prev_sibling
    if prev and prev.type == comment_type:
        text = get_node_text(prev, source)
        if text.startswith("/**"):
            return text[3:-2].strip()
    return None


# Docstring extraction dispatch - maps languages to their extraction functions
_DOCSTRING_EXTRACTORS: dict[LangEnum, Any] = {
    LangEnum.PYTHON: lambda n, s: _get_python_docstring(n, s),
    LangEnum.JAVASCRIPT: lambda n, s: _get_jsdoc_or_line_comments(n, s),
    LangEnum.TYPESCRIPT: lambda n, s: _get_jsdoc_or_line_comments(n, s),
    LangEnum.TSX: lambda n, s: _get_jsdoc_or_line_comments(n, s),
    LangEnum.GO: lambda n, s: _get_line_comments(n, s, "comment", "//"),
    LangEnum.JAVA: lambda n, s: _get_javadoc_or_doxygen(n, s),
    LangEnum.C: lambda n, s: _get_javadoc_or_doxygen(n, s),
    LangEnum.CPP: lambda n, s: _get_javadoc_or_doxygen(n, s),
    LangEnum.RUST: lambda n, s: _get_line_comments(n, s, "line_comment", "///"),
    LangEnum.SWIFT: lambda n, s: _get_swift_docstring(n, s),
    LangEnum.RUBY: lambda n, s: _get_line_comments(n, s, "comment", "#"),
    LangEnum.PHP: lambda n, s: _get_block_comment(n, s, "comment"),
    LangEnum.KOTLIN: lambda n, s: _get_block_comment(n, s, "multiline_comment"),
    LangEnum.CSHARP: lambda n, s: _get_line_comments(n, s, "comment", "///"),
}


def get_docstring(node: Node, source: bytes, language: LangEnum) -> str | None:
    """Extract docstring from a function/class node.

    Args:
        node: The tree-sitter node.
        source: The original source bytes.
        language: The programming language.

    Returns:
        The docstring or None if not found.
    """
    extractor = _DOCSTRING_EXTRACTORS.get(language)
    if extractor:
        return cast(str | None, extractor(node, source))
    return None
