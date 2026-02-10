"""Tests for VectorStore lifecycle management (close, context manager, __del__)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.core.vectorstore.store import VectorStore


def _make_store(tmp_path: Path) -> VectorStore:
    """Create a VectorStore with mocked embedding provider and fake DB."""
    provider = MagicMock()
    provider.name = "local:test"
    provider.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    store = VectorStore(
        db_path=tmp_path / "test.lance",
        embedding_provider=provider,
    )
    return store


# -- close() basics ----------------------------------------------------------


def test_close_clears_internal_state(tmp_path: Path) -> None:
    """close() should set _db, _table, and _fuzzy_search_helper to None."""
    store = _make_store(tmp_path)

    # Simulate that some state has been populated
    store._db = MagicMock()
    store._table = MagicMock()
    store._fuzzy_search_helper = MagicMock()

    store.close()

    assert store._db is None
    assert store._table is None
    assert store._fuzzy_search_helper is None


def test_close_invalidates_search_cache(tmp_path: Path) -> None:
    """close() should call invalidate() on the search cache."""
    store = _make_store(tmp_path)

    # Spy on the cache invalidate method
    original_invalidate = store._search_cache.invalidate
    call_count = 0

    def counting_invalidate() -> int:
        nonlocal call_count
        call_count += 1
        return original_invalidate()

    store._search_cache.invalidate = counting_invalidate

    store.close()

    assert call_count == 1


def test_close_resets_adaptive_searcher(tmp_path: Path) -> None:
    """close() should clear adaptive searcher history and caches."""
    store = _make_store(tmp_path)

    # Populate adaptive searcher state
    store._adaptive_searcher._query_history.append(("test query", 0.9, 5, 20))
    store._adaptive_searcher._feedback_history.append(MagicMock())
    store._adaptive_searcher._complexity_cache["test"] = 0.5

    store.close()

    assert len(store._adaptive_searcher._query_history) == 0
    assert len(store._adaptive_searcher._feedback_history) == 0
    assert len(store._adaptive_searcher._complexity_cache) == 0


def test_close_is_idempotent(tmp_path: Path) -> None:
    """Calling close() multiple times should not raise."""
    store = _make_store(tmp_path)
    store._db = MagicMock()
    store._table = MagicMock()

    store.close()
    store.close()
    store.close()

    assert store._db is None
    assert store._table is None


# -- __del__ safety net -------------------------------------------------------


def test_del_calls_close(tmp_path: Path) -> None:
    """__del__ should invoke close() without raising."""
    store = _make_store(tmp_path)
    store._db = MagicMock()

    # Should not raise
    store.__del__()

    assert store._db is None


def test_del_suppresses_exceptions(tmp_path: Path) -> None:
    """__del__ should suppress any exception raised by close()."""
    store = _make_store(tmp_path)

    # Force close() to raise
    with patch.object(store, "close", side_effect=RuntimeError("boom")):
        # __del__ must swallow the error
        store.__del__()  # no exception expected


# -- async context manager ----------------------------------------------------


async def test_async_context_manager_returns_self(tmp_path: Path) -> None:
    """async with VectorStore(...) as vs: should yield the same instance."""
    store = _make_store(tmp_path)

    async with store as vs:
        assert vs is store


async def test_async_context_manager_calls_close(tmp_path: Path) -> None:
    """Exiting the async context manager should call close()."""
    store = _make_store(tmp_path)
    store._db = MagicMock()
    store._table = MagicMock()
    store._fuzzy_search_helper = MagicMock()

    async with store:
        # State is still alive inside the block
        assert store._db is not None

    # After the block, close() has been called
    assert store._db is None
    assert store._table is None
    assert store._fuzzy_search_helper is None


async def test_async_context_manager_calls_close_on_exception(
    tmp_path: Path,
) -> None:
    """close() should still be called when the body raises an exception."""
    store = _make_store(tmp_path)
    store._db = MagicMock()

    with pytest.raises(ValueError, match="intentional"):
        async with store:
            raise ValueError("intentional")

    assert store._db is None


# -- lazy reconnect after close -----------------------------------------------


def test_connect_works_after_close(tmp_path: Path) -> None:
    """After close(), _connect() should re-establish the connection."""
    store = _make_store(tmp_path)

    fake_db = MagicMock()
    with patch("local_deepwiki.core.vectorstore.store.lancedb") as mock_lance:
        mock_lance.connect.return_value = fake_db

        store.close()
        assert store._db is None

        # _connect() should lazily reconnect
        db = store._connect()

        assert db is fake_db
        assert store._db is fake_db
        mock_lance.connect.assert_called_once()
