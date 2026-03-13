"""Data parsing utilities.

This module provides classes and functions for parsing structured data
from various configuration formats.
"""

from __future__ import annotations

from typing import Any

from src.models import User


class DataParser:
    """A parser that converts raw dictionaries into domain objects.

    The parser validates required fields before constructing model instances.
    """

    def __init__(self, strict: bool = False) -> None:
        """Initialise the parser.

        Args:
            strict: When True, raise on unexpected keys instead of ignoring them.
        """
        self._strict = strict

    def parse(self, raw: dict[str, Any]) -> User:
        """Parse a raw dictionary into a User object.

        Args:
            raw: Dictionary with at least 'user_id', 'name', and 'email' keys.

        Returns:
            A validated User instance.

        Raises:
            KeyError: If a required field is missing.
            TypeError: If a field has the wrong type.
        """
        if self._strict:
            allowed = {"user_id", "name", "email", "created_at"}
            extra = set(raw) - allowed
            if extra:
                raise KeyError(f"Unexpected keys: {extra}")

        return User(
            user_id=int(raw["user_id"]),
            name=str(raw["name"]),
            email=str(raw["email"]),
        )


def parse_config(path: str) -> dict[str, Any]:
    """Read and parse a JSON configuration file.

    Args:
        path: Filesystem path to the JSON config file.

    Returns:
        Parsed configuration as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file contains invalid JSON.
    """
    import json
    from pathlib import Path

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    text = config_path.read_text(encoding="utf-8")
    try:
        return dict(json.loads(text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}") from exc
