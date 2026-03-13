"""Shared fixtures for the sample project test suite."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.models import User


@pytest.fixture
def sample_user() -> User:
    """Create a User instance for testing."""
    return User(user_id=1, name="Alice", email="alice@example.com")
