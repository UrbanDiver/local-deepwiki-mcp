"""Order processing pipeline.

This module orchestrates order validation and enrichment using the core models.
"""

from __future__ import annotations

from typing import Any

from src.models import Order, User


class Processor:
    """Processes incoming orders for a given user.

    The processor validates that orders belong to the user and computes
    summary statistics.
    """

    def __init__(self, user: User) -> None:
        """Initialise the processor with a target user.

        Args:
            user: The user whose orders will be processed.
        """
        self._user = user
        self._results: list[dict[str, Any]] = []

    def process(self, orders: list[Order]) -> list[dict[str, Any]]:
        """Process a batch of orders for the user.

        Only orders matching the user's ID are included.  Each accepted
        order is transformed into a summary dictionary.

        Args:
            orders: Orders to evaluate.

        Returns:
            List of summary dictionaries for accepted orders.
        """
        self._results = []
        for order in orders:
            if order.user_id != self._user.user_id:
                continue
            self._results.append(
                {
                    "order_id": order.order_id,
                    "items": order.item_count(),
                    "total": order.total,
                }
            )
        return list(self._results)
