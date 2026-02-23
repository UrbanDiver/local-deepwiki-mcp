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


# Re-export factory functions and utilities from error_factories for backward
# compatibility.  Every public symbol that was previously defined in this file
# remains importable via ``from local_deepwiki.errors import <name>``.
from local_deepwiki.error_factories import (  # noqa: E402
    EXCEPTION_HINTS as EXCEPTION_HINTS,
    environment_error as environment_error,
    export_error as export_error,
    format_error_response as format_error_response,
    indexing_error as indexing_error,
    map_exception_to_deepwiki_error as map_exception_to_deepwiki_error,
    not_indexed_error as not_indexed_error,
    path_not_found_error as path_not_found_error,
    provider_error as provider_error,
    research_error as research_error,
    sanitize_error_message as sanitize_error_message,
    validation_error as validation_error,
)
