"""Data models for the sample project.

This module defines the core domain objects used throughout the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class User:
    """A registered user of the system.

    Attributes:
        user_id: Unique identifier for the user.
        name: Full display name.
        email: Contact email address.
        created_at: Timestamp when the user was created.
    """

    user_id: int
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)

    def display_label(self) -> str:
        """Return a human-readable label for UI display.

        Returns:
            A string in the format 'Name <email>'.
        """
        return f"{self.name} <{self.email}>"


@dataclass(frozen=True, slots=True)
class Order:
    """A purchase order placed by a user.

    Attributes:
        order_id: Unique identifier for the order.
        user_id: The ID of the user who placed the order.
        items: List of item names in the order.
        total: Total price in dollars.
    """

    order_id: int
    user_id: int
    items: list[str] = field(default_factory=list)
    total: float = 0.0

    def item_count(self) -> int:
        """Return the number of items in the order.

        Returns:
            Integer count of items.
        """
        return len(self.items)
