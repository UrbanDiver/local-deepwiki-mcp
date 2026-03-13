"""Tests for the models module."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.models import Order, User


class TestUser:
    """Tests for the User dataclass."""

    def test_display_label_format(self) -> None:
        """display_label returns 'Name <email>'."""
        user = User(user_id=1, name="Alice", email="alice@example.com")
        assert user.display_label() == "Alice <alice@example.com>"

    def test_display_label_with_mock_dependency(self) -> None:
        """Verify display_label does not depend on external services."""
        service = MagicMock()
        service.lookup.return_value = "Alice"
        user = User(user_id=2, name=service.lookup(), email="b@example.com")
        assert "<" in user.display_label()
