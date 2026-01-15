"""Tree-sitter code parser for multi-language support."""

import hashlib
import mmap
from pathlib import Path
from typing import Any

import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_cpp
import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_kotlin
import tree_sitter_php
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_swift
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from local_deepwiki.logging import get_logger
from local_deepwiki.models import FileInfo
from local_deepwiki.models import Language as LangEnum

logger = get_logger(__name__)

# Threshold for using memory-mapped files (1 MB)
MMAP_THRESHOLD_BYTES = 1 * 1024 * 1024

# Chunk size for computing file hashes (64 KB)
HASH_CHUNK_SIZE = 64 * 1024


def _read_file_content(file_path: Path) -> bytes:
    """Read file content, using memory-mapping for large files.

    For files larger than MMAP_THRESHOLD_BYTES, uses memory mapping
    which allows the OS to manage memory more efficiently.

    Args:
        file_path: Path to the file to read.

    Returns:
        The file content as bytes.
    """
    file_size = file_path.stat().st_size

    if file_size <= MMAP_THRESHOLD_BYTES:
        # Small files: direct read is faster
        return file_path.read_bytes()

    # Large files: use memory mapping
    logger.debug(f"Using mmap for large file ({file_size} bytes): {file_path.name}")
    with open(file_path, "rb") as f:
        # Memory-map the file (read-only)
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            # Return a copy as bytes since mmap is closed after context
            return bytes(mm)


def _compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file using chunked reading.

    This is more memory-efficient for large files as it doesn't
    require loading the entire file into memory at once.

    Args:
        file_path: Path to the file to hash.

    Returns:
        Hexadecimal SHA-256 hash string.
    """
    file_size = file_path.stat().st_size

    if file_size <= MMAP_THRESHOLD_BYTES:
        # Small files: direct read is fine
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

    # Large files: read in chunks
    logger.debug(f"Using chunked hashing for large file ({file_size} bytes): {file_path.name}")
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


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
    LangEnum.SWIFT: tree_sitter_swift,
    LangEnum.RUBY: tree_sitter_ruby,
    LangEnum.PHP: tree_sitter_php,
    LangEnum.KOTLIN: tree_sitter_kotlin,
    LangEnum.CSHARP: tree_sitter_c_sharp,
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
    ".swift": LangEnum.SWIFT,
    ".rb": LangEnum.RUBY,
    ".rake": LangEnum.RUBY,
    ".gemspec": LangEnum.RUBY,
    ".php": LangEnum.PHP,
    ".phtml": LangEnum.PHP,
    ".kt": LangEnum.KOTLIN,
    ".kts": LangEnum.KOTLIN,
    ".cs": LangEnum.CSHARP,
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

            # PHP module uses language_php() instead of language()
            if language == LangEnum.PHP:
                lang = Language(module.language_php())
            else:
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
            logger.debug(f"Unsupported file type: {file_path}")
            return None

        try:
            source = _read_file_content(file_path)
        except (OSError, IOError) as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return None

        logger.debug(f"Parsing {file_path.name} as {language.value}")
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

        Uses chunked reading for large files to avoid loading
        the entire file into memory just for hash computation.

        Args:
            file_path: Absolute path to the file.
            repo_root: Root directory of the repository.

        Returns:
            FileInfo with file metadata.
        """
        stat = file_path.stat()

        return FileInfo(
            path=str(file_path.relative_to(repo_root)),
            language=self.detect_language(file_path),
            size_bytes=stat.st_size,
            last_modified=stat.st_mtime,
            hash=_compute_file_hash(file_path),
        )


def get_node_text(node: Node, source: bytes) -> str:
    """Extract text content from a tree-sitter node.

    Args:
        node: The tree-sitter node.
        source: The original source bytes.

    Returns:
        The text content of the node.
    """
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


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
    comments = []
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


def _get_line_comments(node: Node, source: bytes, comment_type: str, prefix: str) -> str | None:
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
        return extractor(node, source)
    return None
