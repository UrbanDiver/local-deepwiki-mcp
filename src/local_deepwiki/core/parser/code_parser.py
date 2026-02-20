"""Main CodeParser class for multi-language tree-sitter parsing."""

from __future__ import annotations

import hashlib
import mmap
from pathlib import Path
from typing import Any

from tree_sitter import Language, Node, Parser

from local_deepwiki.core.parser.ast_cache import ASTCache
from local_deepwiki.core.parser.languages import EXTENSION_MAP, LANGUAGE_MODULES
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
    logger.debug("Using mmap for large file (%s bytes): %s", file_size, file_path.name)
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
    logger.debug(
        "Using chunked hashing for large file (%d bytes): %s",
        file_size,
        file_path.name,
    )
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


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
            logger.debug("Unsupported file type: %s", file_path)
            return None

        try:
            source = _read_file_content(file_path)
        except (OSError, IOError) as e:
            logger.warning("Failed to read file %s: %s", file_path, e)
            return None

        # Compute file hash for cache lookup
        file_hash = hashlib.sha256(source).hexdigest()
        file_path_str = str(file_path)

        # Check cache if available
        if self._cache is not None:
            cached_tree = self._cache.get(file_path_str, file_hash)
            if cached_tree is not None:
                logger.debug("Cache hit for %s", file_path.name)
                return cached_tree.root_node, language, source

        # Parse the file
        logger.debug("Parsing %s as %s", file_path.name, language.value)
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
