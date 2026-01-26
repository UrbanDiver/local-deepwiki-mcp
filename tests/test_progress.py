"""Tests for progress management module."""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.progress import (
    GetOperationProgressArgs,
    OperationProgressRegistry,
    OperationProgressResponse,
    OperationType,
    ProgressBuffer,
    ProgressManager,
    ProgressPhase,
    ProgressUpdate,
    get_progress_registry,
)


class TestProgressUpdate:
    """Tests for ProgressUpdate dataclass."""

    def test_create_progress_update(self):
        """Test creating a progress update."""
        update = ProgressUpdate(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            phase=ProgressPhase.PARSING,
            current=5,
            total=10,
            message="Processing files",
        )

        assert update.operation_id == "test-123"
        assert update.operation_type == OperationType.INDEX_REPOSITORY
        assert update.phase == ProgressPhase.PARSING
        assert update.current == 5
        assert update.total == 10
        assert update.message == "Processing files"
        assert update.timestamp > 0
        assert update.eta_seconds is None
        assert update.metadata == {}

    def test_to_dict(self):
        """Test converting progress update to dict."""
        update = ProgressUpdate(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            phase=ProgressPhase.PARSING,
            current=5,
            total=10,
            message="Processing files",
            eta_seconds=30.5,
            metadata={"files_processed": 5},
        )

        d = update.to_dict()

        assert d["operation_id"] == "test-123"
        assert d["operation_type"] == "index_repository"
        assert d["phase"] == "parsing"
        assert d["current"] == 5
        assert d["total"] == 10
        assert d["message"] == "Processing files"
        assert d["eta_seconds"] == 30.5
        assert d["percent_complete"] == 50.0
        assert d["metadata"] == {"files_processed": 5}

    def test_to_dict_no_total(self):
        """Test to_dict when total is None."""
        update = ProgressUpdate(
            operation_id="test-123",
            operation_type=OperationType.DEEP_RESEARCH,
            phase=ProgressPhase.RETRIEVAL,
            current=3,
            total=None,
            message="Retrieving context",
        )

        d = update.to_dict()

        assert d["total"] is None
        assert d["percent_complete"] is None


class TestProgressManager:
    """Tests for ProgressManager class."""

    def test_init(self):
        """Test initializing a progress manager."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        assert manager.operation_id == "test-123"
        assert manager.operation_type == OperationType.INDEX_REPOSITORY
        assert manager.total == 100
        assert manager.current == 0
        assert manager.phase == ProgressPhase.PROCESSING
        assert manager.started_at > 0

    def test_update_progress(self):
        """Test updating progress."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        update = manager.update(
            current=25,
            message="Processing files",
            phase=ProgressPhase.PARSING,
        )

        assert manager.current == 25
        assert manager.message == "Processing files"
        assert manager.phase == ProgressPhase.PARSING
        assert update.current == 25
        assert update.message == "Processing files"

    def test_update_with_callback(self):
        """Test that callbacks are called on update."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=10,
        )

        callback_updates = []
        manager.add_callback(callback_updates.append)

        manager.update(current=5, message="Halfway there")

        assert len(callback_updates) == 1
        assert callback_updates[0].current == 5

    def test_remove_callback(self):
        """Test removing a callback."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=10,
        )

        callback_updates = []
        manager.add_callback(callback_updates.append)
        manager.update(current=1)

        manager.remove_callback(callback_updates.append)
        manager.update(current=2)

        # Only one update should have been recorded
        assert len(callback_updates) == 1

    def test_get_eta_no_progress(self):
        """Test ETA when no progress has been made."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        # No progress updates yet, ETA should be None
        eta = manager.get_eta()
        assert eta is None

    def test_get_eta_with_progress(self):
        """Test ETA calculation with progress."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        # Simulate progress over time
        manager.update(current=10)
        time.sleep(0.1)
        manager.update(current=20)

        eta = manager.get_eta()

        # Should have an ETA estimate now
        # With 20% done in 0.1s, ETA should be around 0.4s for remaining 80%
        assert eta is not None
        assert eta > 0

    def test_get_eta_with_historical_data(self):
        """Test ETA uses historical data."""
        historical = {"index_repository_rate": 10.0}  # 10 items/second

        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
            historical_data=historical,
        )

        # First update, no current rate yet
        manager.update(current=10)
        eta = manager.get_eta()

        # Should use historical rate: 90 remaining / 10 per second = ~9 seconds
        assert eta is not None
        # Allow some tolerance
        assert 5 < eta < 15

    def test_get_progress_dict(self):
        """Test getting progress as dict."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        manager.update(current=50, phase=ProgressPhase.EMBEDDING, message="Embedding chunks")

        progress = manager.get_progress_dict()

        assert progress["operation_id"] == "test-123"
        assert progress["operation_type"] == "index_repository"
        assert progress["phase"] == "embedding"
        assert progress["current"] == 50
        assert progress["total"] == 100
        assert progress["percent_complete"] == 50.0
        assert progress["message"] == "Embedding chunks"
        assert "elapsed_seconds" in progress
        assert "started_at" in progress

    def test_complete(self):
        """Test marking operation as complete."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        manager.update(current=50)
        update = manager.complete("Done!")

        assert manager.current == 100
        assert manager.phase == ProgressPhase.COMPLETE
        assert update.phase == ProgressPhase.COMPLETE

    def test_phase_transitions_track_durations(self):
        """Test that phase transitions track durations."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        manager.update(current=10, phase=ProgressPhase.SCANNING)
        time.sleep(0.05)
        manager.update(current=50, phase=ProgressPhase.PARSING)
        time.sleep(0.05)
        manager.update(current=100, phase=ProgressPhase.COMPLETE)

        progress = manager.get_progress_dict()

        # Should have duration for scanning phase
        assert "scanning" in progress["phase_durations"]
        assert progress["phase_durations"]["scanning"] > 0.04

    def test_callback_error_handling(self):
        """Test that callback errors don't crash updates."""
        manager = ProgressManager(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=10,
        )

        def bad_callback(update):
            raise ValueError("Callback error")

        manager.add_callback(bad_callback)

        # Should not raise
        update = manager.update(current=5, message="Test")
        assert update.current == 5


class TestProgressBuffer:
    """Tests for ProgressBuffer class."""

    def test_init(self):
        """Test initializing a progress buffer."""
        buffer = ProgressBuffer(flush_interval=0.5, max_buffer_size=50)
        assert buffer._flush_interval == 0.5
        assert buffer._max_buffer_size == 50
        assert buffer.buffered_count == 0

    def test_add_no_flush(self):
        """Test adding updates without triggering flush."""
        buffer = ProgressBuffer(flush_interval=10.0)  # Long interval

        update = ProgressUpdate(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            phase=ProgressPhase.PARSING,
            current=1,
            total=10,
            message="Test",
        )

        result = buffer.add(update)

        assert result is None
        assert buffer.buffered_count == 1

    def test_add_triggers_time_flush(self):
        """Test that time interval triggers flush."""
        buffer = ProgressBuffer(flush_interval=0.05)

        update1 = ProgressUpdate(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            phase=ProgressPhase.PARSING,
            current=1,
            total=10,
            message="Test 1",
        )
        buffer.add(update1)

        time.sleep(0.06)

        update2 = ProgressUpdate(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            phase=ProgressPhase.PARSING,
            current=2,
            total=10,
            message="Test 2",
        )
        result = buffer.add(update2)

        assert result is not None
        assert len(result) == 2
        assert buffer.buffered_count == 0

    def test_add_triggers_size_flush(self):
        """Test that max buffer size triggers flush."""
        buffer = ProgressBuffer(flush_interval=100.0, max_buffer_size=3)

        for i in range(2):
            result = buffer.add(
                ProgressUpdate(
                    operation_id="test-123",
                    operation_type=OperationType.INDEX_REPOSITORY,
                    phase=ProgressPhase.PARSING,
                    current=i,
                    total=10,
                    message=f"Test {i}",
                )
            )
            assert result is None

        # Third add should trigger flush
        result = buffer.add(
            ProgressUpdate(
                operation_id="test-123",
                operation_type=OperationType.INDEX_REPOSITORY,
                phase=ProgressPhase.PARSING,
                current=3,
                total=10,
                message="Test 3",
            )
        )

        assert result is not None
        assert len(result) == 3

    def test_complete_phase_triggers_flush(self):
        """Test that COMPLETE phase always triggers flush."""
        buffer = ProgressBuffer(flush_interval=100.0, max_buffer_size=100)

        buffer.add(
            ProgressUpdate(
                operation_id="test-123",
                operation_type=OperationType.INDEX_REPOSITORY,
                phase=ProgressPhase.PARSING,
                current=1,
                total=10,
                message="Test",
            )
        )

        result = buffer.add(
            ProgressUpdate(
                operation_id="test-123",
                operation_type=OperationType.INDEX_REPOSITORY,
                phase=ProgressPhase.COMPLETE,
                current=10,
                total=10,
                message="Complete",
            )
        )

        assert result is not None
        assert len(result) == 2

    def test_flush_empty_buffer(self):
        """Test flushing an empty buffer."""
        buffer = ProgressBuffer()

        result = buffer.flush()

        assert result == []

    def test_flush_clears_buffer(self):
        """Test that flush clears the buffer."""
        buffer = ProgressBuffer(flush_interval=100.0)

        buffer.add(
            ProgressUpdate(
                operation_id="test-123",
                operation_type=OperationType.INDEX_REPOSITORY,
                phase=ProgressPhase.PARSING,
                current=1,
                total=10,
                message="Test",
            )
        )

        assert buffer.buffered_count == 1

        buffer.flush()

        assert buffer.buffered_count == 0


class TestOperationProgressRegistry:
    """Tests for OperationProgressRegistry class."""

    def test_start_operation(self):
        """Test starting a new operation."""
        registry = OperationProgressRegistry()

        manager = registry.start_operation(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        assert manager is not None
        assert manager.operation_id == "test-123"
        assert manager.total == 100

    def test_get_operation(self):
        """Test getting an operation."""
        registry = OperationProgressRegistry()

        registry.start_operation(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        manager = registry.get_operation("test-123")
        assert manager is not None

        # Non-existent operation
        assert registry.get_operation("not-found") is None

    def test_complete_operation(self):
        """Test completing an operation."""
        registry = OperationProgressRegistry()

        manager = registry.start_operation(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )
        manager.update(current=100)

        result = registry.complete_operation("test-123", record_timing=True)

        assert result is not None
        assert result["current"] == 100

        # Should be removed from registry
        assert registry.get_operation("test-123") is None

    def test_complete_nonexistent_operation(self):
        """Test completing a non-existent operation."""
        registry = OperationProgressRegistry()

        result = registry.complete_operation("not-found")

        assert result is None

    def test_list_operations(self):
        """Test listing all operations."""
        registry = OperationProgressRegistry()

        registry.start_operation("op-1", OperationType.INDEX_REPOSITORY, total=10)
        registry.start_operation("op-2", OperationType.DEEP_RESEARCH, total=5)

        operations = registry.list_operations()

        assert len(operations) == 2
        operation_ids = {op["operation_id"] for op in operations}
        assert operation_ids == {"op-1", "op-2"}

    def test_get_operation_progress(self):
        """Test getting progress for a specific operation."""
        registry = OperationProgressRegistry()

        manager = registry.start_operation(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )
        manager.update(current=50, message="Halfway")

        progress = registry.get_operation_progress("test-123")

        assert progress is not None
        assert progress["current"] == 50
        assert progress["message"] == "Halfway"

        # Non-existent
        assert registry.get_operation_progress("not-found") is None

    def test_historical_data_persistence(self, tmp_path: Path):
        """Test that historical data is persisted and loaded."""
        data_path = tmp_path / "progress_history.json"

        # Create registry and complete an operation
        registry1 = OperationProgressRegistry()
        registry1.set_data_path(data_path)

        manager = registry1.start_operation(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )
        manager.update(current=100)
        registry1.complete_operation("test-123", record_timing=True)

        # Verify file was created
        assert data_path.exists()

        # Create new registry and load historical data
        registry2 = OperationProgressRegistry()
        registry2.set_data_path(data_path)

        # Should have loaded historical data
        assert "index_repository" in registry2._historical_data

    def test_historical_rate_used_for_eta(self, tmp_path: Path):
        """Test that historical rate is used for ETA prediction."""
        data_path = tmp_path / "progress_history.json"

        # Seed with historical data
        data_path.write_text(json.dumps({
            "index_repository": {
                "index_repository_rate": 10.0,  # 10 items/sec
            }
        }))

        registry = OperationProgressRegistry()
        registry.set_data_path(data_path)

        manager = registry.start_operation(
            operation_id="test-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )

        # First update, should use historical rate
        manager.update(current=10)
        eta = manager.get_eta()

        # With 90 remaining at 10/sec, ETA should be ~9 seconds
        assert eta is not None
        assert 5 < eta < 15


class TestGetProgressRegistry:
    """Tests for the global registry."""

    def test_get_progress_registry_returns_same_instance(self):
        """Test that get_progress_registry returns the same instance."""
        registry1 = get_progress_registry()
        registry2 = get_progress_registry()

        assert registry1 is registry2


class TestPydanticModels:
    """Tests for Pydantic models."""

    def test_get_operation_progress_args_with_id(self):
        """Test GetOperationProgressArgs with operation_id."""
        args = GetOperationProgressArgs(operation_id="test-123")
        assert args.operation_id == "test-123"

    def test_get_operation_progress_args_without_id(self):
        """Test GetOperationProgressArgs without operation_id."""
        args = GetOperationProgressArgs()
        assert args.operation_id is None

    def test_operation_progress_response(self):
        """Test OperationProgressResponse model."""
        response = OperationProgressResponse(
            operation_id="test-123",
            operation_type="index_repository",
            phase="parsing",
            current=50,
            total=100,
            percent_complete=50.0,
            message="Processing files",
            elapsed_seconds=5.5,
            eta_seconds=5.5,
            phase_durations={"scanning": 1.5},
        )

        assert response.operation_id == "test-123"
        assert response.percent_complete == 50.0
        assert response.eta_seconds == 5.5


class TestHandlerIntegration:
    """Integration tests for handler progress integration."""

    @pytest.fixture
    def skip_if_no_handlers(self):
        """Skip test if handlers cannot be imported (missing dependencies)."""
        try:
            from local_deepwiki.handlers import handle_get_operation_progress  # noqa: F401
        except ImportError as e:
            pytest.skip(f"Could not import handlers: {e}")

    async def test_handle_get_operation_progress_no_operations(self, skip_if_no_handlers):
        """Test get_operation_progress when no operations are active."""
        from local_deepwiki.handlers import handle_get_operation_progress

        # Clear the registry
        registry = get_progress_registry()
        registry._operations.clear()

        result = await handle_get_operation_progress({})

        assert len(result) == 1
        response = json.loads(result[0].text)
        assert response["status"] == "success"
        assert response["active_operations"] == 0
        assert response["operations"] == []

    async def test_handle_get_operation_progress_with_operation(self, skip_if_no_handlers):
        """Test get_operation_progress with an active operation."""
        from local_deepwiki.handlers import handle_get_operation_progress

        registry = get_progress_registry()
        registry._operations.clear()

        # Start an operation
        manager = registry.start_operation(
            operation_id="test-op-123",
            operation_type=OperationType.INDEX_REPOSITORY,
            total=100,
        )
        manager.update(current=50, message="Halfway there")

        # Get progress for specific operation
        result = await handle_get_operation_progress({"operation_id": "test-op-123"})

        assert len(result) == 1
        response = json.loads(result[0].text)
        assert response["current"] == 50
        assert response["message"] == "Halfway there"

        # Cleanup
        registry._operations.clear()

    async def test_handle_get_operation_progress_not_found(self, skip_if_no_handlers):
        """Test get_operation_progress for non-existent operation."""
        from local_deepwiki.handlers import handle_get_operation_progress

        registry = get_progress_registry()
        registry._operations.clear()

        result = await handle_get_operation_progress({"operation_id": "not-found"})

        assert len(result) == 1
        response = json.loads(result[0].text)
        assert response["status"] == "not_found"
