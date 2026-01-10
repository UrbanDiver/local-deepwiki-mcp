"""Tree-sitter code parser for multi-language support."""

import hashlib
from pathlib import Path
from typing import Any

import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_go
import tree_sitter_rust
import tree_sitter_java
import tree_sitter_c
import tree_sitter_cpp
from tree_sitter import Language, Parser, Node

from local_deepwiki.models import Language as LangEnum, FileInfo

# Language modules mapping
LANGUAGE_MODULES = {
    LangEnum.PYTHON: tree_sitter_python,
    LangEnum.JAVASCRIPT: tree_sitter_javascript,
    LangEnum.TYPESCRIPT: tree_sitter_typescript,
    LangEnum.GO: tree_sitter_go,
    LangEnum.RUST: tree_sitter_rust,
    LangEnum.JAVA: tree_sitter_java,
    LangEnum.C: tree_sitter_c,
    LangEnum.CPP: tree_sitter_cpp,
}

# File extension to language mapping
EXTENSION_MAP: dict[str, LangEnum] = {
    ".py": LangEnum.PYTHON,
    ".pyi": LangEnum.PYTHON,
    ".js": LangEnum.JAVASCRIPT,
    ".jsx": LangEnum.JAVASCRIPT,
    ".mjs": LangEnum.JAVASCRIPT,
    ".ts": LangEnum.TYPESCRIPT,
    ".tsx": LangEnum.TYPESCRIPT,
    ".go": LangEnum.GO,
    ".rs": LangEnum.RUST,
    ".java": LangEnum.JAVA,
    ".c": LangEnum.C,
    ".h": LangEnum.C,
    ".cpp": LangEnum.CPP,
    ".cc": LangEnum.CPP,
    ".cxx": LangEnum.CPP,
    ".hpp": LangEnum.CPP,
    ".hxx": LangEnum.CPP,
}


class CodeParser:
    """Multi-language code parser using tree-sitter."""

    def __init__(self):
        """Initialize the parser with language support."""
        self._parsers: dict[LangEnum, Parser] = {}
        self._languages: dict[LangEnum, Language] = {}

    def _get_parser(self, language: LangEnum) -> Parser:
        """Get or create a parser for the given language.

        Args:
            language: The programming language.

        Returns:
            A tree-sitter Parser configured for the language.
        """
        if language not in self._parsers:
            module = LANGUAGE_MODULES.get(language)
            if module is None:
                raise ValueError(f"Unsupported language: {language}")

            lang = Language(module.language())
            self._languages[language] = lang

            parser = Parser(lang)
            self._parsers[language] = parser

        return self._parsers[language]

    def detect_language(self, file_path: Path) -> LangEnum | None:
        """Detect the programming language from file extension.

        Args:
            file_path: Path to the source file.

        Returns:
            The detected Language enum or None if not supported.
        """
        suffix = file_path.suffix.lower()
        return EXTENSION_MAP.get(suffix)

    def parse_file(self, file_path: Path) -> tuple[Node, LangEnum, bytes] | None:
        """Parse a source file and return the AST root.

        Args:
            file_path: Path to the source file.

        Returns:
            Tuple of (AST root node, language, source bytes) or None if not supported.
        """
        language = self.detect_language(file_path)
        if language is None:
            return None

        try:
            source = file_path.read_bytes()
        except (OSError, IOError):
            return None

        parser = self._get_parser(language)
        tree = parser.parse(source)
        return tree.root_node, language, source

    def parse_source(self, source: str | bytes, language: LangEnum) -> Node:
        """Parse source code string and return the AST root.

        Args:
            source: The source code.
            language: The programming language.

        Returns:
            The AST root node.
        """
        if isinstance(source, str):
            source = source.encode("utf-8")

        parser = self._get_parser(language)
        tree = parser.parse(source)
        return tree.root_node

    def get_file_info(self, file_path: Path, repo_root: Path) -> FileInfo:
        """Get information about a source file.

        Args:
            file_path: Absolute path to the file.
            repo_root: Root directory of the repository.

        Returns:
            FileInfo with file metadata.
        """
        stat = file_path.stat()
        content = file_path.read_bytes()

        return FileInfo(
            path=str(file_path.relative_to(repo_root)),
            language=self.detect_language(file_path),
            size_bytes=stat.st_size,
            last_modified=stat.st_mtime,
            hash=hashlib.sha256(content).hexdigest(),
        )


def get_node_text(node: Node, source: bytes) -> str:
    """Extract text content from a tree-sitter node.

    Args:
        node: The tree-sitter node.
        source: The original source bytes.

    Returns:
        The text content of the node.
    """
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def find_nodes_by_type(root: Node, node_types: set[str]) -> list[Node]:
    """Find all nodes of specified types in the AST.

    Args:
        root: The root node to search from.
        node_types: Set of node type names to find.

    Returns:
        List of matching nodes.
    """
    results = []

    def walk(node: Node):
        if node.type in node_types:
            results.append(node)
        for child in node.children:
            walk(child)

    walk(root)
    return results


def get_node_name(node: Node, source: bytes, language: LangEnum) -> str | None:
    """Extract the name from a function/class/method node.

    Args:
        node: The tree-sitter node.
        source: The original source bytes.
        language: The programming language.

    Returns:
        The name or None if not found.
    """
    # Different languages have different structures
    name_field_types = {
        "name",
        "identifier",
    }

    for child in node.children:
        if child.type in name_field_types:
            return get_node_text(child, source)
        # Check named children
        if child.type == "identifier":
            return get_node_text(child, source)

    # Try field access
    name_node = node.child_by_field_name("name")
    if name_node:
        return get_node_text(name_node, source)

    return None


def get_docstring(node: Node, source: bytes, language: LangEnum) -> str | None:
    """Extract docstring from a function/class node.

    Args:
        node: The tree-sitter node.
        source: The original source bytes.
        language: The programming language.

    Returns:
        The docstring or None if not found.
    """
    if language == LangEnum.PYTHON:
        # Python docstrings are the first expression statement in the body
        body = node.child_by_field_name("body")
        if body and body.children:
            first_child = body.children[0]
            if first_child.type == "expression_statement":
                expr = first_child.children[0] if first_child.children else None
                if expr and expr.type == "string":
                    text = get_node_text(expr, source)
                    # Remove quotes
                    if text.startswith('"""') or text.startswith("'''"):
                        return text[3:-3].strip()
                    elif text.startswith('"') or text.startswith("'"):
                        return text[1:-1].strip()

    elif language in (LangEnum.JAVASCRIPT, LangEnum.TYPESCRIPT):
        # JSDoc comments precede the function
        prev = node.prev_sibling
        if prev and prev.type == "comment":
            text = get_node_text(prev, source)
            if text.startswith("/**"):
                return text[3:-2].strip()

    elif language == LangEnum.GO:
        # Go doc comments precede the function
        prev = node.prev_sibling
        if prev and prev.type == "comment":
            text = get_node_text(prev, source)
            if text.startswith("//"):
                return text[2:].strip()

    elif language in (LangEnum.JAVA, LangEnum.C, LangEnum.CPP):
        # Javadoc/Doxygen comments precede the function
        prev = node.prev_sibling
        if prev and prev.type == "comment":
            text = get_node_text(prev, source)
            if text.startswith("/**") or text.startswith("///"):
                return text.lstrip("/*").rstrip("*/").strip()

    elif language == LangEnum.RUST:
        # Rust doc comments (///)
        prev = node.prev_sibling
        if prev and prev.type == "line_comment":
            text = get_node_text(prev, source)
            if text.startswith("///"):
                return text[3:].strip()

    return None
