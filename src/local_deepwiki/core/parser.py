"""Tree-sitter code parser for multi-language support."""

import hashlib
import mmap
import sys
import threading
import time
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

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


@dataclass
class CachedAST:
    """A cached AST entry with metadata for validation and eviction.

    Attributes:
        tree: The tree-sitter Tree object (stored as weak reference internally).
        file_hash: SHA256 hash of the file content when parsed.
        created_at: Unix timestamp when the entry was created.
        language: The programming language of the parsed file.
        last_accessed: Unix timestamp of last access (for LRU eviction).
        estimated_size_bytes: Estimated memory size of the tree.
    """

    tree: Any  # tree_sitter.Tree - using Any to avoid import issues
    file_hash: str
    created_at: float
    language: str
    last_accessed: float = field(default_factory=time.time)
    estimated_size_bytes: int = 0


@dataclass
class ASTCacheStats:
    """Statistics for AST cache operations.

    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        evictions: Number of entries evicted due to max size.
        expirations: Number of entries expired due to TTL.
        invalidations: Number of explicit invalidations.
        total_entries: Current number of entries in cache.
        estimated_memory_bytes: Estimated total memory usage.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    invalidations: int = 0
    total_entries: int = 0
    estimated_memory_bytes: int = 0

    def to_dict(self) -> dict[str, int | float]:
        """Convert stats to a dictionary.

        Returns:
            Dictionary with all statistics.
        """
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "invalidations": self.invalidations,
            "total_entries": self.total_entries,
            "estimated_memory_bytes": self.estimated_memory_bytes,
        }


class ASTCache:
    """Thread-safe LRU cache for parsed ASTs with TTL support.

    Caches tree-sitter ASTs to avoid re-parsing unchanged files during
    incremental indexing. Uses file path + content hash as the cache key
    to ensure cache validity.

    Features:
    - TTL-based expiration
    - LRU eviction when max_entries is exceeded
    - Memory usage estimation
    - Thread-safe operations
    - Cache statistics tracking

    Example:
        cache = ASTCache(max_entries=1000, ttl_seconds=3600)

        # Try to get cached AST
        tree = cache.get(file_path, file_hash)
        if tree is None:
            # Parse the file
            tree = parser.parse(source)
            cache.set(file_path, file_hash, tree, "python")

        # Check statistics
        stats = cache.get_stats()
        print(f"Cache hit rate: {stats['hit_rate']:.2%}")
    """

    def __init__(self, max_entries: int = 1000, ttl_seconds: int = 3600):
        """Initialize the AST cache.

        Args:
            max_entries: Maximum number of entries before LRU eviction.
            ttl_seconds: Time-to-live for cache entries in seconds.
        """
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, CachedAST] = {}
        self._lock = threading.RLock()
        self._stats = ASTCacheStats()

    def _make_key(self, file_path: str, file_hash: str) -> str:
        """Create a cache key from file path and hash.

        Args:
            file_path: Path to the file.
            file_hash: SHA256 hash of file content.

        Returns:
            Combined cache key string.
        """
        return f"{file_path}:{file_hash}"

    def _is_expired(self, entry: CachedAST) -> bool:
        """Check if a cache entry has expired.

        Args:
            entry: The cache entry to check.

        Returns:
            True if the entry has expired, False otherwise.
        """
        return time.time() - entry.created_at > self._ttl_seconds

    def _estimate_tree_size(self, tree: Any) -> int:
        """Estimate memory size of a tree-sitter Tree.

        This is a rough estimate based on the tree structure. Tree-sitter
        trees can be large for complex files.

        Args:
            tree: The tree-sitter Tree object.

        Returns:
            Estimated size in bytes.
        """
        try:
            # Base size for the Tree object itself
            base_size = sys.getsizeof(tree)

            # Estimate node count from root - traverse a sample
            root = tree.root_node
            if root is None:
                return base_size

            # Count nodes in a limited traversal (avoid full tree walk for performance)
            node_count = 0
            stack = [root]
            max_nodes = 10000  # Limit traversal for large trees

            while stack and node_count < max_nodes:
                node = stack.pop()
                node_count += 1
                stack.extend(node.children)

            # Estimate ~100 bytes per node (node object + text references)
            estimated_node_size = node_count * 100

            return base_size + estimated_node_size
        except Exception:
            # If estimation fails, return a reasonable default
            return 10000  # 10 KB default

    def _evict_lru(self) -> None:
        """Evict least recently used entries until under max_entries.

        Must be called with lock held.
        """
        while len(self._cache) >= self._max_entries:
            if not self._cache:
                break

            # Find LRU entry
            lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
            evicted = self._cache.pop(lru_key)
            self._stats.evictions += 1
            self._stats.estimated_memory_bytes -= evicted.estimated_size_bytes

    def get(self, file_path: str, file_hash: str) -> Any | None:
        """Get a cached AST if valid (hash matches and not expired).

        Args:
            file_path: Path to the file (used as part of cache key).
            file_hash: SHA256 hash of the file content.

        Returns:
            The cached tree-sitter Tree if found and valid, None otherwise.
        """
        key = self._make_key(file_path, file_hash)

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            # Check expiration
            if self._is_expired(entry):
                self._cache.pop(key, None)
                self._stats.expirations += 1
                self._stats.misses += 1
                self._stats.estimated_memory_bytes -= entry.estimated_size_bytes
                return None

            # Update access time for LRU
            entry.last_accessed = time.time()
            self._stats.hits += 1
            return entry.tree

    def set(
        self, file_path: str, file_hash: str, tree: Any, language: str
    ) -> None:
        """Cache a parsed AST.

        Args:
            file_path: Path to the file.
            file_hash: SHA256 hash of the file content.
            tree: The tree-sitter Tree object to cache.
            language: The programming language of the file.
        """
        key = self._make_key(file_path, file_hash)
        estimated_size = self._estimate_tree_size(tree)
        current_time = time.time()

        entry = CachedAST(
            tree=tree,
            file_hash=file_hash,
            created_at=current_time,
            language=language,
            last_accessed=current_time,
            estimated_size_bytes=estimated_size,
        )

        with self._lock:
            # Check if we need to evict before adding
            if key not in self._cache:
                self._evict_lru()

            # If updating existing entry, subtract old size
            old_entry = self._cache.get(key)
            if old_entry:
                self._stats.estimated_memory_bytes -= old_entry.estimated_size_bytes

            self._cache[key] = entry
            self._stats.estimated_memory_bytes += estimated_size

    def invalidate(self, file_path: str) -> None:
        """Remove all entries for a specific file from cache.

        This removes entries regardless of their hash, useful when a file
        is known to have been modified.

        Args:
            file_path: Path to the file to invalidate.
        """
        with self._lock:
            # Find all keys that start with this file path
            keys_to_remove = [
                k for k in self._cache.keys() if k.startswith(f"{file_path}:")
            ]
            for key in keys_to_remove:
                entry = self._cache.pop(key, None)
                if entry:
                    self._stats.invalidations += 1
                    self._stats.estimated_memory_bytes -= entry.estimated_size_bytes

    def clear(self) -> None:
        """Clear all cached ASTs."""
        with self._lock:
            self._cache.clear()
            self._stats.estimated_memory_bytes = 0

    def get_stats(self) -> dict[str, int | float]:
        """Return cache statistics.

        Returns:
            Dictionary with cache statistics including hits, misses,
            hit rate, evictions, expirations, invalidations, total entries,
            and estimated memory usage.
        """
        with self._lock:
            self._stats.total_entries = len(self._cache)
            return self._stats.to_dict()

    def cleanup_expired(self) -> int:
        """Remove all expired entries from the cache.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items() if self._is_expired(v)
            ]
            for key in expired_keys:
                entry = self._cache.pop(key, None)
                if entry:
                    self._stats.expirations += 1
                    self._stats.estimated_memory_bytes -= entry.estimated_size_bytes
            return len(expired_keys)

    @property
    def size(self) -> int:
        """Return current number of entries in cache."""
        with self._lock:
            return len(self._cache)


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
    LangEnum.TSX: tree_sitter_typescript,
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
    ".tsx": LangEnum.TSX,
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
    """Multi-language code parser using tree-sitter.

    Supports optional AST caching to speed up incremental indexing by
    avoiding re-parsing of unchanged files.

    Args:
        cache: Optional ASTCache instance for caching parsed ASTs.
            If provided, parse_file will check the cache before parsing
            and store results after parsing.

    Example:
        # Without cache
        parser = CodeParser()

        # With cache
        cache = ASTCache(max_entries=1000, ttl_seconds=3600)
        parser = CodeParser(cache=cache)

        # Parse a file (cache hit if unchanged)
        result = parser.parse_file(Path("example.py"))
    """

    def __init__(self, cache: ASTCache | None = None):
        """Initialize the parser with language support.

        Args:
            cache: Optional ASTCache instance for caching parsed ASTs.
        """
        self._parsers: dict[LangEnum, Parser] = {}
        self._languages: dict[LangEnum, Language] = {}
        self._cache = cache

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

            # Some modules have different function names
            if language == LangEnum.PHP:
                lang = Language(module.language_php())
            elif language == LangEnum.TYPESCRIPT:
                lang = Language(module.language_typescript())
            elif language == LangEnum.TSX:
                lang = Language(module.language_tsx())
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

        If a cache is configured, checks the cache before parsing and
        stores the result after parsing.

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

        # Compute file hash for cache lookup
        file_hash = hashlib.sha256(source).hexdigest()
        file_path_str = str(file_path)

        # Check cache if available
        if self._cache is not None:
            cached_tree = self._cache.get(file_path_str, file_hash)
            if cached_tree is not None:
                logger.debug(f"Cache hit for {file_path.name}")
                return cached_tree.root_node, language, source

        # Parse the file
        logger.debug(f"Parsing {file_path.name} as {language.value}")
        parser = self._get_parser(language)
        tree = parser.parse(source)

        # Store in cache if available
        if self._cache is not None:
            self._cache.set(file_path_str, file_hash, tree, language.value)

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

    @property
    def cache(self) -> ASTCache | None:
        """Get the AST cache instance if configured.

        Returns:
            The ASTCache instance or None if caching is not enabled.
        """
        return self._cache

    def get_cache_stats(self) -> dict[str, int | float] | None:
        """Get cache statistics if caching is enabled.

        Returns:
            Dictionary with cache statistics or None if caching is disabled.
        """
        if self._cache is None:
            return None
        return self._cache.get_stats()


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
