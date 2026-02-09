"""Tree-sitter code parser for multi-language support.

This package provides multi-language code parsing via tree-sitter, AST
caching for incremental indexing, and utility functions for AST inspection
and docstring extraction.

All public names are re-exported here for backward compatibility with
``from local_deepwiki.core.parser import ...``.
"""

from local_deepwiki.core.parser.ast_cache import ASTCache, ASTCacheStats, CachedAST
from local_deepwiki.core.parser.ast_utils import (
    find_nodes_by_type,
    get_node_name,
    get_node_text,
)
from local_deepwiki.core.parser.code_parser import (
    HASH_CHUNK_SIZE,
    MMAP_THRESHOLD_BYTES,
    CodeParser,
    _compute_file_hash,
    _read_file_content,
)
from local_deepwiki.core.parser.docstrings import (
    _DOCSTRING_EXTRACTORS,
    _collect_preceding_comments,
    _get_block_comment,
    _get_javadoc_or_doxygen,
    _get_jsdoc_or_line_comments,
    _get_line_comments,
    _get_python_docstring,
    _get_swift_docstring,
    _strip_line_comment_prefix,
    get_docstring,
)
from local_deepwiki.core.parser.languages import EXTENSION_MAP, LANGUAGE_MODULES

__all__ = [
    # Core classes
    "CodeParser",
    "ASTCache",
    "ASTCacheStats",
    "CachedAST",
    # AST utilities
    "get_node_text",
    "find_nodes_by_type",
    "get_node_name",
    # Docstring extraction
    "get_docstring",
    "_DOCSTRING_EXTRACTORS",
    "_collect_preceding_comments",
    "_strip_line_comment_prefix",
    "_get_python_docstring",
    "_get_jsdoc_or_line_comments",
    "_get_javadoc_or_doxygen",
    "_get_swift_docstring",
    "_get_block_comment",
    "_get_line_comments",
    # Language config
    "LANGUAGE_MODULES",
    "EXTENSION_MAP",
    # File I/O utilities
    "_read_file_content",
    "_compute_file_hash",
    "MMAP_THRESHOLD_BYTES",
    "HASH_CHUNK_SIZE",
]
