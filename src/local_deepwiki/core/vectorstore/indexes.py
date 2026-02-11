"""Index creation and management for LanceDB tables."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from lancedb.table import Table

    from .maintenance import LazyIndexManager

logger = get_logger(__name__)


def ensure_indexes(table: Table, lazy_index_manager: LazyIndexManager) -> None:
    """Ensure all indexes exist on a table, creating them if needed.

    Called when opening an existing table to ensure indexes are present
    even if the table was created by an older version. Creates both
    scalar indexes (for lookups) and vector indexes (for search).

    Args:
        table: The LanceDB table to check/create indexes on.
        lazy_index_manager: Manager for lazy vector index creation.
    """
    # Check existing indexes
    try:
        indices = table.list_indices()
        existing_indexes: set[str] = set()
        has_vector_index = False
        for idx in indices:
            name = getattr(idx, "name", None) or (
                idx.get("name") if isinstance(idx, dict) else None
            )
            if name:
                existing_indexes.add(name)
            idx_type = getattr(idx, "index_type", None) or (
                idx.get("index_type") if isinstance(idx, dict) else None
            )
            if idx_type and "ivf" in str(idx_type).lower():
                has_vector_index = True
    except (KeyError, TypeError, RuntimeError, AttributeError) as e:
        logger.debug(f"Could not list existing indexes: {e}")
        existing_indexes = set()
        has_vector_index = False

    # Create missing scalar indexes
    if "id_idx" not in existing_indexes:
        create_index_safe(table, "id")
    if "file_path_idx" not in existing_indexes:
        create_index_safe(table, "file_path")

    # Handle vector index
    if not has_vector_index:
        try:
            num_rows = table.count_rows()
            if lazy_index_manager.config.enabled:
                if num_rows >= lazy_index_manager.config.min_rows:
                    lazy_index_manager.mark_index_pending()
                    logger.debug(
                        f"Vector index creation deferred (lazy mode): {num_rows} rows"
                    )
            else:
                create_vector_index(table, num_rows, lazy_index_manager)
        except (RuntimeError, OSError) as e:
            logger.debug(f"Could not check row count for vector indexing: {e}")
    else:
        lazy_index_manager.mark_index_created()


def create_index_safe(table: Table, column: str) -> None:
    """Safely create a scalar index on a column.

    Args:
        table: The LanceDB table.
        column: The column name to index.
    """
    try:
        table.create_scalar_index(column)
        logger.debug(f"Created scalar index on '{column}' column")
    except (ValueError, RuntimeError, OSError) as e:
        logger.debug(f"Could not create index on '{column}': {e}")


def create_scalar_indexes(table: Table) -> None:
    """Create scalar indexes for efficient lookups.

    Creates indexes on 'id' and 'file_path' columns to optimize
    get_chunk_by_id() and get_chunks_by_file() operations.

    Args:
        table: The LanceDB table.
    """
    create_index_safe(table, "id")
    create_index_safe(table, "file_path")


def create_vector_index(
    table: Table,
    num_rows: int,
    lazy_index_manager: LazyIndexManager,
) -> None:
    """Create a vector index for faster semantic search.

    Uses IVF-PQ index for approximate nearest neighbor search,
    which provides 5-10x speedup on large datasets (10k+ vectors).

    Args:
        table: The LanceDB table.
        num_rows: Number of rows in the table.
        lazy_index_manager: Manager for tracking index state.
    """
    min_rows_for_index = lazy_index_manager.config.min_rows

    if num_rows < min_rows_for_index:
        logger.debug(
            f"Skipping vector index creation: {num_rows} rows < {min_rows_for_index} threshold"
        )
        return

    try:
        num_partitions = min(max(int(math.sqrt(num_rows)), 16), 256)

        table.create_index(
            metric="L2",
            num_partitions=num_partitions,
            num_sub_vectors=16,
        )
        logger.info(
            f"Created vector index with {num_partitions} partitions for {num_rows} vectors"
        )

        lazy_index_manager.mark_index_created()

    except (ValueError, RuntimeError, OSError) as e:
        logger.debug(f"Could not create vector index: {e}")
