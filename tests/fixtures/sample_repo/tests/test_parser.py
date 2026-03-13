"""Tests for the parser module."""

from __future__ import annotations

import pytest

from src.models import User
from src.parser import DataParser


def test_parse_valid_dict() -> None:
    """DataParser.parse returns a User for valid input."""
    parser = DataParser()
    result = parser.parse({"user_id": 1, "name": "Bob", "email": "bob@example.com"})
    assert isinstance(result, User)
    assert result.name == "Bob"


def test_parse_missing_field() -> None:
    """DataParser.parse raises KeyError for missing required fields."""
    parser = DataParser()
    with pytest.raises(KeyError):
        parser.parse({"user_id": 1})
