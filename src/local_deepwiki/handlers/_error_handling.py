"""Decorator for consistent error handling in tool handlers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeAlias

from mcp.types import TextContent

from local_deepwiki.core.rate_limiter import RateLimitExceeded
from local_deepwiki.errors import (
    DeepWikiError,
    ValidationError,
    format_error_response,
    map_exception_to_deepwiki_error,
)
from local_deepwiki.logging import get_logger
from local_deepwiki.security import AccessDeniedException, AuthenticationException

logger = get_logger(__name__)

# Type alias for tool handler functions
ToolHandler: TypeAlias = Callable[..., Awaitable[list[TextContent]]]


def handle_tool_errors(func: ToolHandler) -> ToolHandler:
    """Decorator for consistent error handling in tool handlers.

    Catches exceptions and returns properly formatted error responses with
    actionable hints when available:

    - DeepWikiError subclasses: Format with message and hint
    - ValueError: Input validation errors (logged at ERROR level)
    - Common exceptions: Map to DeepWikiError with appropriate hints
    - Other exceptions: Log with traceback and return generic error

    Args:
        func: The async tool handler function to wrap.

    Returns:
        Wrapped function with consistent error handling.
    """

    @wraps(func)
    async def wrapper(
        args: dict[str, Any], **kwargs: dict[str, Any]
    ) -> list[TextContent]:
        try:
            return await func(args, **kwargs)
        except AccessDeniedException as e:
            # RBAC: User lacks required permission
            logger.warning("Access denied in %s: %s", func.__name__, e)
            error = DeepWikiError(
                message=f"Access denied: {e}",
                hint="You don't have permission for this operation. Contact an administrator to request access.",
            )
            return [TextContent(type="text", text=format_error_response(error))]
        except AuthenticationException as e:
            # RBAC: No authenticated subject
            logger.warning("Authentication required in %s: %s", func.__name__, e)
            error = DeepWikiError(
                message=f"Authentication required: {e}",
                hint="Please authenticate before performing this operation.",
            )
            return [TextContent(type="text", text=format_error_response(error))]
        except DeepWikiError as e:
            # Our custom errors already have good messages and hints
            logger.error("DeepWiki error in %s: %s", func.__name__, e.message)
            if e.context:
                logger.debug("Error context: %s", e.context)
            return [TextContent(type="text", text=format_error_response(e))]
        except ValueError as e:
            # Wrap ValueError in ValidationError for better hints
            error = ValidationError(
                message=str(e),
                hint="Check that all input parameters are valid.",
            )
            logger.error("Validation error in %s: %s", func.__name__, e)
            return [TextContent(type="text", text=format_error_response(error))]
        except (FileNotFoundError, PermissionError) as e:
            # Map common file system errors
            error = map_exception_to_deepwiki_error(e)
            logger.error("File system error in %s: %s", func.__name__, e)
            return [TextContent(type="text", text=format_error_response(error))]
        except (ConnectionError, TimeoutError) as e:
            # Map common network errors — retryable
            error = map_exception_to_deepwiki_error(e)
            error.retryable = True
            error.retry_after_seconds = 5
            logger.error("Network error in %s: %s", func.__name__, e)
            return [TextContent(type="text", text=format_error_response(error))]
        except RateLimitExceeded as e:
            # Rate limit exceeded — retryable after cooldown
            logger.warning("Rate limit exceeded in %s: %s", func.__name__, e)
            error = DeepWikiError(
                message=str(e),
                hint="Wait for the rate limit to reset, or reduce the frequency of requests.",
                retryable=True,
                retry_after_seconds=60,
            )
            return [TextContent(type="text", text=format_error_response(error))]
        except asyncio.CancelledError:
            # Re-raise cancellation to propagate properly
            raise
        except Exception as e:  # noqa: BLE001
            # Broad catch is intentional: top-level error handler for MCP tools
            # that converts any unhandled exception to a user-friendly error message
            logger.exception("Unexpected error in %s: %s", func.__name__, e)
            error = DeepWikiError(
                message=f"An unexpected error occurred: {e}",
                hint="Check the logs for more details. If this persists, please report the issue.",
            )
            return [TextContent(type="text", text=format_error_response(error))]

    return wrapper
