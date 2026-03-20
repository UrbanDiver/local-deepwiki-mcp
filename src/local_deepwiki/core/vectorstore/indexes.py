"""Index creation and management for LanceDB tables."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from lancedb.table import Table

    from .maintenance import LazyIndexManager

logger = get_logger(__name__)


def _get_index_type(idx: object) -> str:
    """Safely extract the index_type string from a LanceDB index object."""
    idx_type = getattr(idx, "index_type", None) or (
        idx.get("index_type", "") if isinstance(idx, dict) else ""  # type: ignore[union-attr]
    )
    return str(idx_type).lower() if idx_type else ""


def _inspect_existing_indexes(
    table: Table,
) -> tuple[list[object], set[str], bool]:
    """List table indexes and classify them.

    Returns:
        Tuple of (indices, existing_index_names, has_vector_index).
    """
    try:
        indices = table.list_indices()
        existing_indexes: set[str] = set()
        has_vector_index = False
        for idx in indices:
            name = getattr(idx, "name", None) or (
                idx.get("name") if isinstance(idx, dict) else None  # type: ignore[union-attr]
            )
            if name:
                existing_indexes.add(name)
            if "ivf" in _get_index_type(idx):
                has_vector_index = True
        return indices, existing_indexes, has_vector_index
    except (KeyError, TypeError, RuntimeError, AttributeError) as e:
        logger.debug("Could not list existing indexes: %s", e)
        return [], set(), False


def _has_fts_index(indices: list[object]) -> bool:
    """Return True if any of the listed indexes is a full-text search index."""
    return bool(indices) and any("fts" in _get_index_type(idx) for idx in indices)


def _create_fts_index(table: Table, indices: list[object]) -> None:
    """Create the FTS index on 'content' if it does not already exist."""
    if not _has_fts_index(indices):
        create_fts_index_safe(table, "content")


def _create_vector_index_if_needed(
    table: Table,
    lazy_index_manager: LazyIndexManager,
) -> None:
    """Create or defer creation of the vector index."""
    try:
        num_rows = table.count_rows()
        if lazy_index_manager.config.enabled:
            if num_rows >= lazy_index_manager.config.min_rows:
                lazy_index_manager.mark_index_pending()
                logger.debug(
                    "Vector index creation deferred (lazy mode): %d rows", num_rows
                )
        else:
            create_vector_index(table, num_rows, lazy_index_manager)
    except (RuntimeError, OSError) as e:
        logger.debug("Could not check row count for vector indexing: %s", e)


def ensure_indexes(table: Table, lazy_index_manager: LazyIndexManager) -> None:
    """Ensure all indexes exist on a table, creating them if needed.

    Called when opening an existing table to ensure indexes are present
    even if the table was created by an older version. Creates both
    scalar indexes (for lookups) and vector indexes (for search).

    Args:
        table: The LanceDB table to check/create indexes on.
        lazy_index_manager: Manager for lazy vector index creation.
    """
    indices, existing_indexes, has_vector_index = _inspect_existing_indexes(table)

    if "id_idx" not in existing_indexes:
        create_index_safe(table, "id")
    if "file_path_idx" not in existing_indexes:
        create_index_safe(table, "file_path")

    _create_fts_index(table, indices)

    if not has_vector_index:
        _create_vector_index_if_needed(table, lazy_index_manager)
    else:
        lazy_index_manager.mark_index_created()


def create_fts_index_safe(table: Table, column: str) -> None:
    """Safely create a full-text search (BM25) index on a text column.

    Args:
        table: The LanceDB table.
        column: The text column name to index.
    """
    try:
        table.create_fts_index(column, replace=True)
        logger.debug("Created FTS index on '%s' column", column)
    except (ValueError, RuntimeError, OSError, TypeError, AttributeError) as e:
        # TypeError/AttributeError: older LanceDB versions without FTS support
        logger.debug("Could not create FTS index on '%s': %s", column, e)


def create_index_safe(table: Table, column: str) -> None:
    """Safely create a scalar index on a column.

    Args:
        table: The LanceDB table.
        column: The column name to index.
    """
    try:
        table.create_scalar_index(column)
        logger.debug("Created scalar index on '%s' column", column)
    except (ValueError, RuntimeError, OSError) as e:
        logger.debug("Could not create index on '%s': %s", column, e)


def create_scalar_indexes(table: Table) -> None:
    """Create scalar indexes for efficient lookups.

    Creates indexes on 'id' and 'file_path' columns to optimize
    get_chunk_by_id() and get_chunks_by_file() operations.
    Also creates a full-text search index on 'content' for BM25 keyword search.

    Args:
        table: The LanceDB table.
    """
    create_index_safe(table, "id")
    create_index_safe(table, "file_path")
    create_fts_index_safe(table, "content")


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
            "Skipping vector index creation: %d rows < %d threshold",
            num_rows,
            min_rows_for_index,
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
            "Created vector index with %d partitions for %d vectors",
            num_partitions,
            num_rows,
        )

        lazy_index_manager.mark_index_created()

    except (ValueError, RuntimeError, OSError) as e:
        logger.debug("Could not create vector index: %s", e)
