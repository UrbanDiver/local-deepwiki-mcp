"""Input validation utilities for MCP tool handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.models import ChunkType, Language

# Input validation constants
MIN_CONTEXT_CHUNKS = 1
MAX_CONTEXT_CHUNKS = 50
MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 100
VALID_LANGUAGES = frozenset(lang.value for lang in Language)
VALID_CHUNK_TYPES = frozenset(ct.value for ct in ChunkType)
VALID_LLM_PROVIDERS = frozenset({"ollama", "anthropic", "openai"})
VALID_EMBEDDING_PROVIDERS = frozenset({"local", "openai"})

# Deep research validation constants
MIN_DEEP_RESEARCH_CHUNKS = 10
MAX_DEEP_RESEARCH_CHUNKS = 50
DEFAULT_DEEP_RESEARCH_CHUNKS = 30

# File size limits (in bytes)
MAX_WIKI_PAGE_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_positive_int(
    value: int | None, name: str, min_val: int, max_val: int, default: int
) -> int:
    """Validate and bound an integer parameter.

    Args:
        value: The value to validate.
        name: Parameter name for error messages.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.
        default: Default value if None.

    Returns:
        Validated and bounded integer.

    Raises:
        ValueError: If value is not a valid integer.
    """
    if value is None:
        return default
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {type(value).__name__}")
    return max(min_val, min(max_val, value))


def validate_non_empty_string(value: str | None, name: str) -> str:
    """Validate that a string is non-empty.

    Args:
        value: The value to validate.
        name: Parameter name for error messages.

    Returns:
        The validated string.

    Raises:
        ValueError: If value is not a non-empty string.
    """
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{name} cannot be empty")
    return value


def validate_language(language: str | None) -> str | None:
    """Validate a language filter value.

    Args:
        language: The language to validate.

    Returns:
        The validated language or None.

    Raises:
        ValueError: If language is invalid.
    """
    if language is None:
        return None
    if language not in VALID_LANGUAGES:
        raise ValueError(
            f"Invalid language: '{language}'. Valid options: {sorted(VALID_LANGUAGES)}"
        )
    return language


def validate_languages_list(languages: list[str] | None) -> list[str] | None:
    """Validate a list of languages.

    Args:
        languages: List of languages to validate.

    Returns:
        The validated list or None.

    Raises:
        ValueError: If any language is invalid.
    """
    if languages is None:
        return None
    if not isinstance(languages, list):
        raise ValueError(f"languages must be a list, got {type(languages).__name__}")

    invalid = [lang for lang in languages if lang not in VALID_LANGUAGES]
    if invalid:
        raise ValueError(
            f"Invalid languages: {invalid}. Valid options: {sorted(VALID_LANGUAGES)}"
        )
    return languages


def validate_provider(
    provider: str | None, valid_providers: set[str], name: str
) -> str | None:
    """Validate a provider value.

    Args:
        provider: The provider to validate.
        valid_providers: Set of valid provider names.
        name: Parameter name for error messages.

    Returns:
        The validated provider or None.

    Raises:
        ValueError: If provider is invalid.
    """
    if provider is None:
        return None
    if provider not in valid_providers:
        raise ValueError(
            f"Invalid {name}: '{provider}'. Valid options: {sorted(valid_providers)}"
        )
    return provider


def validate_chunk_type(chunk_type: str | None) -> str | None:
    """Validate a chunk type filter value.

    Args:
        chunk_type: The chunk type to validate.

    Returns:
        The validated chunk type or None.

    Raises:
        ValueError: If chunk type is invalid.
    """
    if chunk_type is None:
        return None
    if chunk_type not in VALID_CHUNK_TYPES:
        raise ValueError(
            f"Invalid chunk_type: '{chunk_type}'. Valid options: {sorted(VALID_CHUNK_TYPES)}"
        )
    return chunk_type


def validate_path_pattern(path_pattern: str | None) -> str | None:
    """Validate a file path pattern.

    Accepts glob-like patterns for file path filtering.

    Args:
        path_pattern: The path pattern to validate.

    Returns:
        The validated path pattern or None.

    Raises:
        ValueError: If path pattern is invalid.
    """
    if path_pattern is None:
        return None
    if not isinstance(path_pattern, str):
        raise ValueError(f"path must be a string, got {type(path_pattern).__name__}")
    # Basic validation - pattern should not be empty if provided
    if path_pattern.strip() == "":
        return None
    # Check for dangerous patterns
    if ".." in path_pattern:
        raise ValueError("path pattern cannot contain '..'")
    return path_pattern


def validate_fuzzy_weight(weight: float | None) -> float:
    """Validate fuzzy weight parameter.

    Args:
        weight: The fuzzy weight (0.0-1.0).

    Returns:
        Validated weight, default 0.3.

    Raises:
        ValueError: If weight is out of range.
    """
    if weight is None:
        return 0.3
    if not isinstance(weight, (int, float)):
        raise ValueError(f"fuzzy_weight must be a number, got {type(weight).__name__}")
    if weight < 0.0 or weight > 1.0:
        raise ValueError(f"fuzzy_weight must be between 0.0 and 1.0, got {weight}")
    return float(weight)


# =============================================================================
# Phase 3: Resource Limits and Input Size Validation (CWE-400 Prevention)
# =============================================================================


class ResourceLimits:
    """Resource consumption limits for security (CWE-400 prevention).

    These limits prevent denial of service attacks via resource exhaustion.
    All limits are intentionally conservative to protect system resources.
    """

    # Query parameters
    MAX_QUERY_LENGTH = 5000  # Characters
    MAX_QUESTION_LENGTH = 2000  # Characters

    # Repository indexing
    MAX_REPO_SIZE = 1_000_000_000  # 1GB
    MAX_FILES_PER_REPO = 50_000
    MAX_FILE_SIZE = 50_000_000  # 50MB per file

    # Deep research
    MAX_SUB_QUESTIONS = 20
    MAX_RESEARCH_DEPTH = 5
    MAX_CONTEXT_CHUNKS = 500

    # Export operations
    MAX_PDF_PAGES = 10_000
    MAX_HTML_SIZE = 100_000_000  # 100MB


# Valid deep research presets
VALID_RESEARCH_PRESETS = frozenset({"quick", "default", "thorough"})


def validate_query_parameters(
    query: str,
    repo_path: str,
    max_results: int,
) -> None:
    """Validate query parameters against resource limits.

    Ensures query string length, repository path validity, and result
    count are within acceptable bounds to prevent resource exhaustion.

    Args:
        query: The search query string.
        repo_path: Path to the repository.
        max_results: Maximum number of results to return.

    Raises:
        ValueError: If any parameter violates resource limits.
    """
    # Validate query length
    if len(query) > ResourceLimits.MAX_QUERY_LENGTH:
        raise ValueError(
            f"Query exceeds maximum length ({ResourceLimits.MAX_QUERY_LENGTH} characters)"
        )

    if len(query) < 1:
        raise ValueError("Query cannot be empty")

    # Validate repo_path exists and is a directory
    repo_path_obj = Path(repo_path)
    if not repo_path_obj.exists():
        raise ValueError(f"Repository path does not exist: {repo_path}")

    if not repo_path_obj.is_dir():
        raise ValueError(f"Repository path is not a directory: {repo_path}")

    # Validate max_results is in acceptable range
    if max_results < 1 or max_results > ResourceLimits.MAX_CONTEXT_CHUNKS:
        raise ValueError(
            f"max_results must be between 1 and {ResourceLimits.MAX_CONTEXT_CHUNKS}"
        )


def validate_index_parameters(
    repo_path: str,
) -> tuple[int, int]:
    """Validate repository indexing parameters.

    Scans the repository to ensure it doesn't exceed size limits.
    Checks total repository size, file count, and individual file sizes.
    Skips directories that the indexer would also skip (hidden dirs,
    virtual envs, node_modules, etc.) to avoid false rejections.

    Args:
        repo_path: Path to the repository to index.

    Returns:
        Tuple of (total_size, file_count) for the repository.

    Raises:
        ValueError: If repository exceeds any resource limits.
    """
    import os

    from local_deepwiki.config import get_config

    repo_path_obj = Path(repo_path)
    total_size = 0
    file_count = 0

    config = get_config()
    skip_dirs = set()
    for pattern in config.parsing.exclude_patterns:
        if pattern.endswith("/**"):
            skip_dirs.add(pattern[:-3])

    for root, dirs, filenames in os.walk(repo_path_obj):
        root_path = Path(root)
        rel_root = root_path.relative_to(repo_path_obj)

        dirs[:] = [
            d
            for d in dirs
            if d not in skip_dirs
            and str(rel_root / d) not in skip_dirs
            and not d.startswith(".")
        ]

        for filename in filenames:
            file_path = root_path / filename
            try:
                file_size = file_path.stat().st_size
            except OSError:
                continue

            if file_size > ResourceLimits.MAX_FILE_SIZE:
                raise ValueError(
                    f"File too large: {file_path} ({file_size:,} bytes, "
                    f"max {ResourceLimits.MAX_FILE_SIZE:,})"
                )

            total_size += file_size
            file_count += 1

            if total_size > ResourceLimits.MAX_REPO_SIZE:
                raise ValueError(
                    f"Repository exceeds maximum size "
                    f"({ResourceLimits.MAX_REPO_SIZE:,} bytes)"
                )

            if file_count > ResourceLimits.MAX_FILES_PER_REPO:
                raise ValueError(
                    f"Repository exceeds maximum file count "
                    f"({ResourceLimits.MAX_FILES_PER_REPO:,} files)"
                )

    return total_size, file_count


def validate_deep_research_parameters(
    question: str,
    preset: str | None,
    max_chunks: int,
) -> None:
    """Validate deep research parameters.

    Ensures question length, preset validity, and chunk count are
    within acceptable bounds for deep research operations.

    Args:
        question: The research question.
        preset: Research preset (quick/default/thorough) or None.
        max_chunks: Maximum number of context chunks to use.

    Raises:
        ValueError: If any parameter violates resource limits.
    """
    # Validate question length
    if len(question) > ResourceLimits.MAX_QUESTION_LENGTH:
        raise ValueError(
            f"Question exceeds maximum length "
            f"({ResourceLimits.MAX_QUESTION_LENGTH} characters)"
        )

    if len(question) < 1:
        raise ValueError("Question cannot be empty")

    # Validate preset if provided
    if preset is not None and preset not in VALID_RESEARCH_PRESETS:
        raise ValueError(
            f"Invalid preset: '{preset}'. "
            f"Valid options: {sorted(VALID_RESEARCH_PRESETS)}"
        )

    # Validate max_chunks is in acceptable range
    if max_chunks < 1 or max_chunks > ResourceLimits.MAX_CONTEXT_CHUNKS:
        raise ValueError(
            f"max_chunks must be between 1 and {ResourceLimits.MAX_CONTEXT_CHUNKS}"
        )
