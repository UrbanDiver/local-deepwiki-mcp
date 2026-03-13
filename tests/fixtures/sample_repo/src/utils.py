"""General-purpose utility functions.

This module contains small, reusable helper functions used across the project.
"""

from __future__ import annotations

import hashlib
import re


def format_name(first: str, last: str) -> str:
    """Format a full name from first and last components.

    Args:
        first: Given name.
        last: Family name.

    Returns:
        A properly capitalised full name string.
    """
    return f"{first.strip().title()} {last.strip().title()}"


def validate_email(email: str) -> bool:
    """Check whether an email address has a valid format.

    Args:
        email: The email address to validate.

    Returns:
        True if the format is valid, False otherwise.
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def hash_password(password: str, salt: str = "default_salt") -> str:
    """Produce a SHA-256 hash of a password with a salt.

    Args:
        password: The plaintext password.
        salt: A salt string to prepend before hashing.

    Returns:
        Hex-encoded hash digest.
    """
    salted = f"{salt}{password}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()
