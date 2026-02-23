"""Structured error system with actionable guidance for users.

This module provides a hierarchy of exception classes that include:
- Clear error messages explaining what went wrong
- Actionable hints on how to fix the issue
- Optional context for debugging

Example usage:
    from local_deepwiki.errors import provider_error, validation_error

    # Create a provider error from an exception
    try:
        result = await llm_provider.generate(prompt)
    except Exception as e:
        raise provider_error("anthropic", e)

    # Create a validation error
    if not repo_path.exists():
        raise validation_error(
            field="repo_path",
            value=str(repo_path),
            expected="an existing directory path"
        )
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

__all__ = [
    "BaseProviderError",
    "DeepWikiError",
    "EnvironmentSetupError",
    "EXCEPTION_HINTS",
    "ExportError",
    "IndexingError",
    "ResearchError",
    "ValidationError",
    "environment_error",
    "export_error",
    "format_error_response",
    "indexing_error",
    "map_exception_to_deepwiki_error",
    "not_indexed_error",
    "path_not_found_error",
    "provider_error",
    "research_error",
    "sanitize_error_message",
    "validation_error",
]


class DeepWikiError(Exception):
    """Base exception for all DeepWiki errors.

    All DeepWiki errors include:
    - message: What happened
    - hint: How to fix it (optional)
    - context: Additional debug info (optional)

    Attributes:
        message: A human-readable description of the error.
        hint: Actionable guidance on how to resolve the error.
        context: Additional context for debugging.
    """

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: What happened.
            hint: How to fix it.
            context: Additional debug info.
            retryable: Whether the operation can be retried.
            retry_after_seconds: Suggested wait before retrying.
        """
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.context = context or {}
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds

    def __str__(self) -> str:
        """Format the error message with hint if available."""
        parts = [self.message]
        if self.hint:
            parts.append(f"\nHint: {self.hint}")
        return "".join(parts)

    def __repr__(self) -> str:
        """Return a detailed representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"hint={self.hint!r}, "
            f"context={self.context!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the error to a dictionary for JSON serialization.

        Returns:
            Dictionary containing error details.
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "hint": self.hint,
            "context": self.context,
        }


class ValidationError(DeepWikiError):
    """Error raised when input validation fails.

    This error indicates that user-provided input is invalid,
    such as missing required fields, invalid formats, or
    values outside acceptable ranges.

    Examples:
        - Invalid repository path
        - Invalid language filter
        - Invalid configuration values
    """

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        field: str | None = None,
        value: Any = None,
    ) -> None:
        """Initialize the validation error.

        Args:
            message: What validation failed.
            hint: How to fix it.
            context: Additional debug info.
            field: The name of the invalid field.
            value: The invalid value that was provided.
        """
        super().__init__(message, hint, context)
        self.field = field
        self.value = value
        if field:
            self.context["field"] = field
        if value is not None:
            self.context["value"] = value


class EnvironmentSetupError(DeepWikiError):
    """Error raised when environment setup is incomplete.

    This error indicates that required dependencies, configuration,
    or system resources are missing or misconfigured.

    Examples:
        - Missing API keys
        - Required tools not installed
        - Configuration file not found
    """

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        missing_component: str | None = None,
    ) -> None:
        """Initialize the environment error.

        Args:
            message: What component is missing/misconfigured.
            hint: How to set it up.
            context: Additional debug info.
            missing_component: Name of the missing component.
        """
        super().__init__(message, hint, context)
        self.missing_component = missing_component
        if missing_component:
            self.context["missing_component"] = missing_component


class BaseProviderError(DeepWikiError):
    """Error raised when an LLM or embedding provider fails.

    This error wraps failures from external AI providers like
    Anthropic, OpenAI, or Ollama. It includes the original
    exception for debugging.

    Examples:
        - API key invalid or expired
        - Network connectivity issues
        - Rate limiting
        - Model not available
    """

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        provider_name: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize the provider error.

        Args:
            message: What provider operation failed.
            hint: How to fix it.
            context: Additional debug info.
            provider_name: Name of the failing provider.
            original_error: The original exception from the provider.
        """
        super().__init__(message, hint, context)
        self.provider_name = provider_name
        self.original_error = original_error
        if provider_name:
            self.context["provider"] = provider_name
        if original_error:
            self.context["original_error"] = str(original_error)
            self.context["original_error_type"] = type(original_error).__name__


class IndexingError(DeepWikiError):
    """Error raised when repository indexing fails.

    This error indicates problems during the indexing process,
    such as permission issues, unsupported files, or resource
    exhaustion.

    Examples:
        - Repository path doesn't exist
        - Permission denied on files
        - Parsing errors
        - Vector store failures
    """

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        repo_path: str | None = None,
        file_path: str | None = None,
    ) -> None:
        """Initialize the indexing error.

        Args:
            message: What indexing operation failed.
            hint: How to fix it.
            context: Additional debug info.
            repo_path: Path to the repository being indexed.
            file_path: Specific file that caused the error.
        """
        super().__init__(message, hint, context)
        self.repo_path = repo_path
        self.file_path = file_path
        if repo_path:
            self.context["repo_path"] = repo_path
        if file_path:
            self.context["file_path"] = file_path


class ExportError(DeepWikiError):
    """Error raised when wiki export fails.

    This error indicates problems during HTML or PDF export,
    such as missing dependencies, permission issues, or
    invalid output paths.

    Examples:
        - Output directory not writable
        - WeasyPrint/mermaid-cli not installed
        - Corrupted wiki content
    """

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        export_format: str | None = None,
        output_path: str | None = None,
    ) -> None:
        """Initialize the export error.

        Args:
            message: What export operation failed.
            hint: How to fix it.
            context: Additional debug info.
            export_format: The export format (html, pdf).
            output_path: The target output path.
        """
        super().__init__(message, hint, context)
        self.export_format = export_format
        self.output_path = output_path
        if export_format:
            self.context["format"] = export_format
        if output_path:
            self.context["output_path"] = output_path


class ResearchError(DeepWikiError):
    """Error raised when deep research fails.

    This error indicates problems during the deep research
    pipeline, such as LLM failures, timeout, or cancellation.

    Examples:
        - LLM generation failed
        - Research timeout
        - Vector search failures
    """

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
        step: str | None = None,
        question: str | None = None,
    ) -> None:
        """Initialize the research error.

        Args:
            message: What research operation failed.
            hint: How to fix it.
            context: Additional debug info.
            step: The research step that failed.
            question: The research question being processed.
        """
        super().__init__(message, hint, context)
        self.step = step
        self.question = question
        if step:
            self.context["step"] = step
        if question:
            self.context["question"] = question[:100]  # Truncate long questions


# -----------------------------------------------------------------------------
# Error Factory Functions
# -----------------------------------------------------------------------------


def validation_error(
    field: str,
    value: Any,
    expected: str,
    *,
    context: dict[str, Any] | None = None,
) -> ValidationError:
    """Create a validation error with actionable hints.

    Args:
        field: The name of the invalid field.
        value: The invalid value provided.
        expected: Description of what was expected.
        context: Additional context for debugging.

    Returns:
        A ValidationError with formatted message and hint.

    Example:
        raise validation_error(
            field="repo_path",
            value="/nonexistent/path",
            expected="an existing directory"
        )
    """
    # Truncate long values for readability
    value_str = str(value)
    if len(value_str) > 100:
        value_str = value_str[:100] + "..."

    return ValidationError(
        message=f"Invalid value for '{field}': {value_str}",
        hint=f"Expected {expected}",
        context=context,
        field=field,
        value=value,
    )


def _classify_hint(
    msg_lower: str,
    classifiers: tuple[tuple[tuple[str, ...], str], ...],
    default: str,
) -> str:
    """Match the first classifier whose keywords appear in the message.

    Args:
        msg_lower: Lowercased error message to classify.
        classifiers: Tuple of ((keywords...), hint) pairs checked in order.
        default: Hint returned when no classifier matches.

    Returns:
        The matching hint string, or *default*.
    """
    for keywords, hint in classifiers:
        if any(kw in msg_lower for kw in keywords):
            return hint
    return default


# Sentinel values replaced by callables in _classify_provider_error
_AUTH_SENTINEL = "__auth__"
_CONNECTION_SENTINEL = "__connection__"

_PROVIDER_HINT_CLASSIFIERS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        ("api key", "authentication", "401"),
        _AUTH_SENTINEL,
        "{title} API authentication failed",
    ),
    (
        ("rate limit", "429"),
        "You've hit the API rate limit. Wait a few minutes and try again, "
        "or consider upgrading your API plan.",
        "{title} rate limit exceeded",
    ),
    (
        ("connection", "timeout", "network"),
        _CONNECTION_SENTINEL,
        "Failed to connect to {title}",
    ),
    (
        ("overloaded", "503", "502"),
        "The provider's servers are temporarily overloaded. "
        "Wait a few minutes and try again.",
        "{title} service temporarily unavailable",
    ),
)

# "model" + "not found" requires both keywords — handled separately
_PROVIDER_MODEL_NOT_FOUND_HINT = (
    "The requested model is not available. Check the model name "
    "and ensure it's accessible in your {title} account."
)


def _classify_provider_error(
    provider_name: str,
    original_error: Exception,
) -> tuple[str, str]:
    """Return (hint, message) for a provider error.

    Handles special sentinel values that delegate to callable hint builders.
    """
    error_str = str(original_error).lower()
    title = provider_name.title()

    for keywords, hint_or_sentinel, message_template in _PROVIDER_HINT_CLASSIFIERS:
        if any(kw in error_str for kw in keywords):
            if hint_or_sentinel == _AUTH_SENTINEL:
                hint = _get_api_key_hint(provider_name)
            elif hint_or_sentinel == _CONNECTION_SENTINEL:
                hint = _get_connection_hint(provider_name)
            else:
                hint = hint_or_sentinel
            return hint, message_template.format(title=title)

    # Two-keyword check: both "model" and "not found" must be present
    if "model" in error_str and "not found" in error_str:
        return (
            _PROVIDER_MODEL_NOT_FOUND_HINT.format(title=title),
            f"{title} model not found",
        )

    return (
        f"Check your {title} configuration and API status. "
        f"See provider documentation for details.",
        f"{title} provider error: {original_error}",
    )


def provider_error(
    provider_name: str,
    original_error: Exception,
    *,
    context: dict[str, Any] | None = None,
) -> BaseProviderError:
    """Create a provider error from an exception with actionable hints.

    This function analyzes the original exception to provide
    context-specific hints for common provider issues.

    Args:
        provider_name: Name of the provider (e.g., "anthropic", "ollama").
        original_error: The original exception from the provider.
        context: Additional context for debugging.

    Returns:
        A BaseProviderError with formatted message and hint.

    Example:
        try:
            result = await llm.generate(prompt)
        except Exception as e:
            raise provider_error("anthropic", e)
    """
    hint, message = _classify_provider_error(provider_name, original_error)

    return BaseProviderError(
        message=message,
        hint=hint,
        context=context,
        provider_name=provider_name,
        original_error=original_error,
    )


def _get_api_key_hint(provider_name: str) -> str:
    """Get API key setup hint for a specific provider."""
    hints = {
        "anthropic": (
            "Set your Anthropic API key:\n"
            "  export ANTHROPIC_API_KEY='your-key-here'\n"
            "Get a key at: https://console.anthropic.com/settings/keys"
        ),
        "openai": (
            "Set your OpenAI API key:\n"
            "  export OPENAI_API_KEY='your-key-here'\n"
            "Get a key at: https://platform.openai.com/api-keys"
        ),
        "ollama": (
            "Ollama runs locally and doesn't require an API key.\n"
            "Make sure Ollama is running: ollama serve"
        ),
    }
    return hints.get(
        provider_name.lower(),
        f"Check your {provider_name} API key configuration.",
    )


def _get_connection_hint(provider_name: str) -> str:
    """Get connection troubleshooting hint for a specific provider."""
    if provider_name.lower() == "ollama":
        return (
            "Cannot connect to Ollama. Make sure:\n"
            "  1. Ollama is installed: https://ollama.ai/download\n"
            "  2. Ollama is running: ollama serve\n"
            "  3. The model is available: ollama list"
        )
    return (
        f"Check your network connection and verify {provider_name.title()} "
        f"services are operational. You can check status at the provider's "
        f"status page."
    )


def environment_error(
    missing_component: str,
    purpose: str,
    setup_instructions: str,
    *,
    context: dict[str, Any] | None = None,
) -> EnvironmentSetupError:
    """Create an environment error with setup instructions.

    Args:
        missing_component: Name of the missing component.
        purpose: What the component is needed for.
        setup_instructions: How to install/configure it.
        context: Additional context for debugging.

    Returns:
        An EnvironmentSetupError with formatted message and hint.

    Example:
        raise environment_error(
            missing_component="weasyprint",
            purpose="PDF export",
            setup_instructions="pip install weasyprint"
        )
    """
    return EnvironmentSetupError(
        message=f"Missing required component: {missing_component}",
        hint=f"Required for {purpose}.\nTo set up:\n{setup_instructions}",
        context=context,
        missing_component=missing_component,
    )


_INDEXING_HINT_CLASSIFIERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("not exist", "not found"),
        "Check that the repository path is correct and accessible.",
    ),
    (
        ("permission",),
        "Check file permissions. You may need to run with elevated privileges or fix ownership.",
    ),
    (
        ("empty",),
        "The repository appears to be empty or contain no supported files. Check that source files exist.",
    ),
    (
        ("parse", "syntax"),
        "There was a problem parsing source files. Check for syntax errors in the affected files.",
    ),
)


def indexing_error(
    message: str,
    *,
    repo_path: str | None = None,
    file_path: str | None = None,
    context: dict[str, Any] | None = None,
) -> IndexingError:
    """Create an indexing error with actionable hints.

    Args:
        message: Description of what failed.
        repo_path: Path to the repository being indexed.
        file_path: Specific file that caused the error.
        context: Additional context for debugging.

    Returns:
        An IndexingError with formatted message and hint.
    """
    hint = _classify_hint(
        message.lower(),
        _INDEXING_HINT_CLASSIFIERS,
        "Check the repository path, file permissions, and ensure source files are readable.",
    )

    return IndexingError(
        message=message,
        hint=hint,
        context=context,
        repo_path=repo_path,
        file_path=file_path,
    )


_EXPORT_PDF_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("weasyprint", "cairo"),
        "PDF export requires WeasyPrint. Install it with:\n"
        "  pip install weasyprint\n"
        "On macOS, you may also need: brew install pango",
    ),
    (
        ("mermaid", "mmdc"),
        "Mermaid diagram rendering requires mermaid-cli. Install it with:\n"
        "  npm install -g @mermaid-js/mermaid-cli",
    ),
)

_EXPORT_HTML_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("permission",),
        "Check that the output directory is writable.",
    ),
)


def export_error(
    message: str,
    export_format: str,
    *,
    output_path: str | None = None,
    context: dict[str, Any] | None = None,
) -> ExportError:
    """Create an export error with actionable hints.

    Args:
        message: Description of what failed.
        export_format: The export format (html, pdf).
        output_path: The target output path.
        context: Additional context for debugging.

    Returns:
        An ExportError with formatted message and hint.
    """
    msg_lower = message.lower()

    if export_format == "pdf":
        hint = _classify_hint(
            msg_lower,
            _EXPORT_PDF_HINTS,
            "Check that the output path is writable and you have the required dependencies installed.",
        )
    else:
        hint = _classify_hint(
            msg_lower,
            _EXPORT_HTML_HINTS,
            "Check that the wiki path exists and contains valid markdown files.",
        )

    return ExportError(
        message=message,
        hint=hint,
        context=context,
        export_format=export_format,
        output_path=output_path,
    )


_RESEARCH_HINT_CLASSIFIERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("timeout", "timed out", "cancelled"),
        "The research took too long. Try a simpler question or reduce the max_chunks parameter.",
    ),
    (
        ("llm", "provider"),
        "The LLM provider failed. Check your API key and network connection.",
    ),
    (
        ("vector", "search"),
        "Vector search failed. Make sure the repository is indexed first with index_repository.",
    ),
)


def research_error(
    message: str,
    *,
    step: str | None = None,
    question: str | None = None,
    context: dict[str, Any] | None = None,
) -> ResearchError:
    """Create a research error with actionable hints.

    Args:
        message: Description of what failed.
        step: The research step that failed.
        question: The research question being processed.
        context: Additional context for debugging.

    Returns:
        A ResearchError with formatted message and hint.
    """
    hint = _classify_hint(
        message.lower(),
        _RESEARCH_HINT_CLASSIFIERS,
        "Check that the repository is indexed and the LLM provider is configured correctly.",
    )

    return ResearchError(
        message=message,
        hint=hint,
        context=context,
        step=step,
        question=question,
    )


def not_indexed_error(repo_path: str) -> ValidationError:
    """Create an error for when a repository hasn't been indexed yet.

    Args:
        repo_path: Path to the repository that needs indexing.

    Returns:
        A ValidationError with instructions to index first.
    """
    return ValidationError(
        message=f"Repository not indexed: {repo_path}",
        hint=(
            "Run index_repository first to create the search index:\n"
            f'  index_repository(repo_path="{repo_path}")'
        ),
        field="repo_path",
        value=repo_path,
    )


def path_not_found_error(
    path: str,
    path_type: str = "path",
) -> ValidationError:
    """Create an error for when a path doesn't exist.

    Args:
        path: The path that doesn't exist.
        path_type: Type of path (e.g., "repository", "wiki", "file").

    Returns:
        A ValidationError with hint about the path.
    """
    return ValidationError(
        message=f"{path_type.title()} does not exist: {path}",
        hint=f"Check that the {path_type} path is correct and accessible.",
        field=path_type,
        value=path,
    )


# -----------------------------------------------------------------------------
# Error Mapping for Exception Translation
# -----------------------------------------------------------------------------

# Map common exception types to DeepWikiError factories
EXCEPTION_HINTS: dict[type, tuple[str, str]] = {
    FileNotFoundError: (
        "The requested file or directory was not found.",
        "Check that the path exists and is spelled correctly.",
    ),
    PermissionError: (
        "Permission denied.",
        "Check file permissions or run with appropriate privileges.",
    ),
    ConnectionError: (
        "Network connection failed.",
        "Check your internet connection and verify the service is accessible.",
    ),
    TimeoutError: (
        "Operation timed out.",
        "The operation took too long. Try again or simplify your request.",
    ),
}


def map_exception_to_deepwiki_error(
    exc: Exception,
    *,
    context: dict[str, Any] | None = None,
) -> DeepWikiError:
    """Map a standard exception to an appropriate DeepWikiError.

    This function converts common Python exceptions into DeepWikiError
    subclasses with helpful hints.

    Args:
        exc: The exception to convert.
        context: Additional context for debugging.

    Returns:
        A DeepWikiError subclass with appropriate message and hint.
    """
    # Check if it's already a DeepWikiError
    if isinstance(exc, DeepWikiError):
        return exc

    # Look up hint for exception type
    for exc_type, (message_prefix, hint) in EXCEPTION_HINTS.items():
        if isinstance(exc, exc_type):
            return DeepWikiError(
                message=f"{message_prefix} {exc}",
                hint=hint,
                context=context,
            )

    # Default handling for unknown exceptions
    return DeepWikiError(
        message=str(exc),
        hint="An unexpected error occurred. Please check the logs for details.",
        context=context,
    )


_PATH_SANITIZATION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"/[a-zA-Z0-9/_.-]*\.py", ".py"),
    (r"/[a-zA-Z0-9/_.-]*\.yml", ".yml"),
    (r"/[a-zA-Z0-9/_.-]*\.yaml", ".yaml"),
    # Remove absolute paths (3+ segments like /foo/bar/baz, not short URL paths)
    (r"/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+){2,}", "<path>"),
)

_GENERAL_SANITIZATION_PATTERNS: tuple[tuple[str, str], ...] = (
    # Localhost URLs (prevents revealing local service configuration)
    (r"http://localhost:\d+", "http://internal-service"),
    (r"http://127\.0\.0\.1:\d+", "http://internal-service"),
    (r"localhost:\d+", "internal-service"),
    (r"127\.0\.0\.1:\d+", "internal-service"),
    # API keys
    (r"sk-[a-zA-Z0-9]{40,}", "[REDACTED_KEY]"),
    (r"Bearer [a-zA-Z0-9_-]{20,}", "Bearer [REDACTED_TOKEN]"),
    (r"token [a-zA-Z0-9_-]{20,}", "token [REDACTED_TOKEN]"),
    # Database connection strings
    (
        r"(postgres|mysql|mongodb)://[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+@[^/\s]+",
        r"\1://[REDACTED]@[REDACTED]",
    ),
    # AWS credentials
    (r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]"),
)


def _apply_sanitization_patterns(
    text: str,
    patterns: tuple[tuple[str, str], ...],
) -> str:
    """Apply a sequence of regex substitution patterns to *text*."""
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text


def sanitize_error_message(message: str, sanitize_paths: bool = True) -> str:
    """Remove sensitive information from error messages.

    This function sanitizes error messages before returning them to users
    to prevent information disclosure about internal paths, URLs, API
    configuration, and other sensitive details.

    Args:
        message: Original error message potentially containing sensitive info.
        sanitize_paths: Whether to remove file paths (default: True).

    Returns:
        Sanitized message safe for user display.

    Examples:
        >>> sanitize_error_message("/home/user/.config/app/config.yaml: File not found")
        "~/.config/app/config.yaml: File not found"

        >>> sanitize_error_message("Connection refused to http://localhost:11434")
        "Connection refused to internal-service"
    """
    if not isinstance(message, str):
        return str(message)

    result = message

    if sanitize_paths:
        home = str(Path.home())
        result = result.replace(home, "~")
        result = _apply_sanitization_patterns(result, _PATH_SANITIZATION_PATTERNS)

    result = _apply_sanitization_patterns(result, _GENERAL_SANITIZATION_PATTERNS)

    return result


def format_error_response(error: DeepWikiError) -> str:
    """Format an error for display to users.

    Args:
        error: The DeepWikiError to format.

    Returns:
        A formatted string suitable for display.
    """
    # Sanitize the message to remove sensitive information
    safe_message = sanitize_error_message(error.message)
    if error.hint:
        safe_hint = sanitize_error_message(error.hint)
    else:
        safe_hint = None

    result: dict[str, Any] = {
        "status": "error",
        "error": safe_message,
    }
    if safe_hint:
        result["hint"] = safe_hint
    if error.retryable:
        result["retryable"] = True
        if error.retry_after_seconds is not None:
            result["retry_after_seconds"] = error.retry_after_seconds
    return json.dumps(result, indent=2)
