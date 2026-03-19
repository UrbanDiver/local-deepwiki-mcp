"""Request-level rate limiting for web API endpoints (CWE-770).

Provides a simple per-IP rate limiter decorator that can be applied to
Flask route functions. Uses an in-memory time-window approach.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from functools import wraps
from time import time
from typing import Any

from flask import Response, jsonify, request


_request_times: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()

# Default requests per minute for API endpoints
DEFAULT_REQUESTS_PER_MINUTE = 30


def rate_limit(
    requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
) -> Any:
    """Rate limit decorator for Flask routes.

    Args:
        requests_per_minute: Maximum requests allowed per IP per minute.

    Returns:
        Decorator function.
    """

    def decorator(f: Any) -> Any:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Response | tuple[Response, int]:
            key = request.remote_addr or "unknown"
            now = time()
            with _rate_limit_lock:
                times = _request_times[key]
                # Remove entries older than 1 minute
                times[:] = [t for t in times if now - t < 60]
                if len(times) >= requests_per_minute:
                    return jsonify({"error": "Rate limit exceeded"}), 429
                times.append(now)
            return f(*args, **kwargs)

        return wrapper

    return decorator


def reset_rate_limits() -> None:
    """Clear all rate limit state. Used in tests."""
    with _rate_limit_lock:
        _request_times.clear()
