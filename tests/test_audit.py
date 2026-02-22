"""Tests for audit logging system (Phase 3).

Tests the audit logging infrastructure for compliance and security monitoring.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from local_deepwiki.core.audit import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
    AuditSeverity,
    get_audit_logger,
    reset_audit_logger,
)


@pytest.fixture(autouse=True)
def clean_audit_logger():
    """Clean up the audit logger after each test to prevent handler leaks."""
    yield
    # Clear any handlers from the deepwiki.audit logger
    audit_logger = logging.getLogger("deepwiki.audit")
    for handler in audit_logger.handlers[:]:
        handler.close()
        audit_logger.removeHandler(handler)
    # Also reset the singleton
    reset_audit_logger()


class TestAuditEventTypeEnum:
    """Tests for AuditEventType enum values."""

    def test_access_granted_exists(self):
        """Test ACCESS_GRANTED enum value exists."""
        assert AuditEventType.ACCESS_GRANTED.value == "access_granted"

    def test_access_denied_exists(self):
        """Test ACCESS_DENIED enum value exists."""
        assert AuditEventType.ACCESS_DENIED.value == "access_denied"

    def test_index_started_exists(self):
        """Test INDEX_STARTED enum value exists."""
        assert AuditEventType.INDEX_STARTED.value == "index_started"

    def test_index_completed_exists(self):
        """Test INDEX_COMPLETED enum value exists."""
        assert AuditEventType.INDEX_COMPLETED.value == "index_completed"

    def test_index_failed_exists(self):
        """Test INDEX_FAILED enum value exists."""
        assert AuditEventType.INDEX_FAILED.value == "index_failed"

    def test_query_executed_exists(self):
        """Test QUERY_EXECUTED enum value exists."""
        assert AuditEventType.QUERY_EXECUTED.value == "query_executed"

    def test_query_failed_exists(self):
        """Test QUERY_FAILED enum value exists."""
        assert AuditEventType.QUERY_FAILED.value == "query_failed"

    def test_export_started_exists(self):
        """Test EXPORT_STARTED enum value exists."""
        assert AuditEventType.EXPORT_STARTED.value == "export_started"

    def test_export_completed_exists(self):
        """Test EXPORT_COMPLETED enum value exists."""
        assert AuditEventType.EXPORT_COMPLETED.value == "export_completed"

    def test_config_read_exists(self):
        """Test CONFIG_READ enum value exists."""
        assert AuditEventType.CONFIG_READ.value == "config_read"

    def test_config_modified_exists(self):
        """Test CONFIG_MODIFIED enum value exists."""
        assert AuditEventType.CONFIG_MODIFIED.value == "config_modified"

    def test_authentication_success_exists(self):
        """Test AUTHENTICATION_SUCCESS enum value exists."""
        assert AuditEventType.AUTHENTICATION_SUCCESS.value == "authentication_success"

    def test_authentication_failed_exists(self):
        """Test AUTHENTICATION_FAILED enum value exists."""
        assert AuditEventType.AUTHENTICATION_FAILED.value == "authentication_failed"

    def test_authorization_failed_exists(self):
        """Test AUTHORIZATION_FAILED enum value exists."""
        assert AuditEventType.AUTHORIZATION_FAILED.value == "authorization_failed"

    def test_sensitive_resource_accessed_exists(self):
        """Test SENSITIVE_RESOURCE_ACCESSED enum value exists."""
        assert (
            AuditEventType.SENSITIVE_RESOURCE_ACCESSED.value
            == "sensitive_resource_accessed"
        )

    def test_all_event_types_are_strings(self):
        """Test all event type values are strings."""
        for event_type in AuditEventType:
            assert isinstance(event_type.value, str)


class TestAuditSeverityEnum:
    """Tests for AuditSeverity enum values."""

    def test_info_exists(self):
        """Test INFO severity exists."""
        assert AuditSeverity.INFO.value == "info"

    def test_warning_exists(self):
        """Test WARNING severity exists."""
        assert AuditSeverity.WARNING.value == "warning"

    def test_critical_exists(self):
        """Test CRITICAL severity exists."""
        assert AuditSeverity.CRITICAL.value == "critical"

    def test_severity_count(self):
        """Test there are exactly 3 severity levels."""
        assert len(list(AuditSeverity)) == 3

    def test_all_severities_are_strings(self):
        """Test all severity values are strings."""
        for severity in AuditSeverity:
            assert isinstance(severity.value, str)


class TestAuditEventDataclass:
    """Tests for AuditEvent dataclass creation."""

    def test_create_minimal_event(self):
        """Test creating event with required fields."""
        event = AuditEvent(
            timestamp="2024-01-01T00:00:00Z",
            event_type=AuditEventType.ACCESS_GRANTED,
            severity=AuditSeverity.INFO,
            subject_id="user123",
            subject_role="VIEWER",
            resource_type="repository",
            resource_path="/path/to/repo",
            action="read repository",
            result="success",
        )

        assert event.timestamp == "2024-01-01T00:00:00Z"
        assert event.event_type == AuditEventType.ACCESS_GRANTED
        assert event.severity == AuditSeverity.INFO
        assert event.subject_id == "user123"
        assert event.subject_role == "VIEWER"
        assert event.resource_type == "repository"
        assert event.resource_path == "/path/to/repo"
        assert event.action == "read repository"
        assert event.result == "success"

    def test_create_event_with_reason(self):
        """Test creating event with reason field."""
        event = AuditEvent(
            timestamp="2024-01-01T00:00:00Z",
            event_type=AuditEventType.ACCESS_DENIED,
            severity=AuditSeverity.WARNING,
            subject_id="user456",
            subject_role="GUEST",
            resource_type="operation",
            resource_path="index_repository",
            action="index repository",
            result="denied",
            reason="Insufficient permissions",
        )

        assert event.reason == "Insufficient permissions"

    def test_create_event_with_details(self):
        """Test creating event with details dict."""
        event = AuditEvent(
            timestamp="2024-01-01T00:00:00Z",
            event_type=AuditEventType.QUERY_EXECUTED,
            severity=AuditSeverity.INFO,
            subject_id=None,
            subject_role=None,
            resource_type="query",
            resource_path="/repo",
            action="execute search",
            result="success",
            details={"chunks_returned": 10, "duration_ms": 150},
        )

        assert event.details == {"chunks_returned": 10, "duration_ms": 150}

    def test_default_reason_is_none(self):
        """Test reason defaults to None."""
        event = AuditEvent(
            timestamp="2024-01-01T00:00:00Z",
            event_type=AuditEventType.ACCESS_GRANTED,
            severity=AuditSeverity.INFO,
            subject_id=None,
            subject_role=None,
            resource_type="test",
            resource_path="/test",
            action="test",
            result="success",
        )

        assert event.reason is None

    def test_default_details_is_empty_dict(self):
        """Test details defaults to empty dict."""
        event = AuditEvent(
            timestamp="2024-01-01T00:00:00Z",
            event_type=AuditEventType.ACCESS_GRANTED,
            severity=AuditSeverity.INFO,
            subject_id=None,
            subject_role=None,
            resource_type="test",
            resource_path="/test",
            action="test",
            result="success",
        )

        assert event.details == {}


class TestAuditLoggerInitialization:
    """Tests for AuditLogger initialization."""

    def test_creates_log_directory(self, tmp_path):
        """Test AuditLogger creates log directory if not exists."""
        log_dir = tmp_path / "audit_logs"
        assert not log_dir.exists()

        logger = AuditLogger(log_dir=log_dir)

        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_uses_existing_directory(self, tmp_path):
        """Test AuditLogger uses existing log directory."""
        log_dir = tmp_path / "existing_logs"
        log_dir.mkdir()

        logger = AuditLogger(log_dir=log_dir)

        assert log_dir.exists()

    def test_log_dir_attribute_set(self, tmp_path):
        """Test log_dir attribute is set correctly."""
        log_dir = tmp_path / "test_logs"

        logger = AuditLogger(log_dir=log_dir)

        assert logger.log_dir == log_dir

    def test_default_log_dir_is_home_config(self):
        """Test default log directory is ~/.config/local-deepwiki/audit."""
        # Reset any existing logger first
        reset_audit_logger()

        logger = AuditLogger()

        expected = Path.home() / ".config" / "local-deepwiki" / "audit"
        assert logger.log_dir == expected


class TestAuditLoggerLogEvent:
    """Tests for AuditLogger.log_event method."""

    def test_log_event_writes_to_file(self, tmp_path):
        """Test log_event writes JSON to log file."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        event = AuditEvent(
            timestamp="2024-01-01T12:00:00Z",
            event_type=AuditEventType.ACCESS_GRANTED,
            severity=AuditSeverity.INFO,
            subject_id="test_user",
            subject_role="ADMIN",
            resource_type="repository",
            resource_path="/test/repo",
            action="test action",
            result="success",
        )

        logger.log_event(event)

        # Force flush by closing handlers
        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        assert log_file.exists()

        content = log_file.read_text()
        log_entry = json.loads(content.strip())

        assert log_entry["event_type"] == "access_granted"
        assert log_entry["severity"] == "info"
        assert log_entry["subject_id"] == "test_user"
        assert log_entry["resource_path"] == "/test/repo"

    def test_log_event_json_format(self, tmp_path):
        """Test logged event is valid JSON."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        event = AuditEvent(
            timestamp="2024-01-01T12:00:00Z",
            event_type=AuditEventType.QUERY_EXECUTED,
            severity=AuditSeverity.INFO,
            subject_id=None,
            subject_role=None,
            resource_type="query",
            resource_path="/repo",
            action="search",
            result="success",
            details={"query_length": 50},
        )

        logger.log_event(event)

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()

        # Should parse as valid JSON
        parsed = json.loads(content)
        assert "event_type" in parsed
        assert "details" in parsed
        assert parsed["details"]["query_length"] == 50

    def test_log_event_converts_enum_to_string(self, tmp_path):
        """Test enum values are converted to strings in JSON."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        event = AuditEvent(
            timestamp="2024-01-01T12:00:00Z",
            event_type=AuditEventType.INDEX_COMPLETED,
            severity=AuditSeverity.WARNING,
            subject_id=None,
            subject_role=None,
            resource_type="repository",
            resource_path="/test",
            action="index",
            result="success",
        )

        logger.log_event(event)

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        # Enums should be string values, not enum objects
        assert parsed["event_type"] == "index_completed"
        assert parsed["severity"] == "warning"


class TestAuditLoggerAccessDecision:
    """Tests for AuditLogger.log_access_decision method."""

    def test_log_access_granted(self, tmp_path):
        """Test logging access granted decision."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_access_decision(
            subject_id="user1",
            subject_role="ADMIN",
            resource_type="operation",
            resource_path="index_repository",
            permission_requested="execute",
            granted=True,
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        assert parsed["event_type"] == "access_granted"
        assert parsed["result"] == "granted"
        assert parsed["severity"] == "info"

    def test_log_access_denied(self, tmp_path):
        """Test logging access denied decision."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_access_decision(
            subject_id="guest_user",
            subject_role="GUEST",
            resource_type="operation",
            resource_path="export_wiki",
            permission_requested="execute",
            granted=False,
            reason="Role GUEST lacks permission to export",
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        assert parsed["event_type"] == "access_denied"
        assert parsed["result"] == "denied"
        assert parsed["severity"] == "warning"
        assert "Role GUEST" in parsed["reason"]


class TestAuditLoggerQueryExecution:
    """Tests for AuditLogger.log_query_execution method."""

    def test_log_successful_query(self, tmp_path):
        """Test logging successful query execution."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_query_execution(
            subject_id="user1",
            repo_path="/home/user/repo",
            query="How does authentication work?",
            success=True,
            query_type="search",
            chunks_returned=15,
            duration_ms=250,
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        assert parsed["event_type"] == "query_executed"
        assert parsed["result"] == "success"
        assert parsed["details"]["query_type"] == "search"
        assert parsed["details"]["chunks_returned"] == 15
        assert parsed["details"]["duration_ms"] == 250

    def test_log_failed_query(self, tmp_path):
        """Test logging failed query execution."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_query_execution(
            subject_id=None,
            repo_path="/repo",
            query="test",
            success=False,
            query_type="deep_research",
            error_message="LLM provider unavailable",
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        assert parsed["event_type"] == "query_failed"
        assert parsed["result"] == "failure"
        assert "LLM provider" in parsed["reason"]

    def test_query_truncation_for_privacy(self, tmp_path):
        """Test long queries are truncated in logs."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        long_query = "a" * 200

        logger.log_query_execution(
            subject_id=None,
            repo_path="/repo",
            query=long_query,
            success=True,
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        # The action should contain truncated query
        assert "..." in parsed["action"]
        # But full length should be in details
        assert parsed["details"]["query_length"] == 200


class TestAuditLoggerIndexOperation:
    """Tests for AuditLogger.log_index_operation method."""

    def test_log_index_started(self, tmp_path):
        """Test logging index started operation."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_index_operation(
            subject_id="system",
            repo_path="/path/to/repo",
            operation="started",
            success=True,
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        assert parsed["event_type"] == "index_started"
        assert parsed["result"] == "in_progress"

    def test_log_index_completed(self, tmp_path):
        """Test logging index completed operation."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_index_operation(
            subject_id="user",
            repo_path="/repo",
            operation="completed",
            success=True,
            files_processed=100,
            chunks_created=500,
            duration_ms=30000,
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        assert parsed["event_type"] == "index_completed"
        assert parsed["result"] == "success"
        assert parsed["details"]["files_processed"] == 100
        assert parsed["details"]["chunks_created"] == 500

    def test_log_index_failed(self, tmp_path):
        """Test logging index failed operation."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_index_operation(
            subject_id="user",
            repo_path="/repo",
            operation="failed",
            success=False,
            error_message="Repository too large",
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        assert parsed["event_type"] == "index_failed"
        assert parsed["result"] == "failure"
        assert "too large" in parsed["reason"]


class TestAuditLoggerExportOperation:
    """Tests for AuditLogger.log_export_operation method."""

    def test_log_export_started(self, tmp_path):
        """Test logging export started operation."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_export_operation(
            subject_id="user1",
            wiki_path="/repo/.deepwiki",
            output_path="/tmp/export",
            export_type="html",
            operation="started",
            success=True,
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        assert parsed["event_type"] == "export_started"
        assert parsed["details"]["export_type"] == "html"

    def test_log_export_completed(self, tmp_path):
        """Test logging export completed operation."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_export_operation(
            subject_id="user1",
            wiki_path="/repo/.deepwiki",
            output_path="/output.pdf",
            export_type="pdf",
            operation="completed",
            success=True,
            pages_exported=50,
            duration_ms=5000,
        )

        for handler in logger._logger.handlers:
            handler.flush()

        log_file = log_dir / "audit.log"
        content = log_file.read_text().strip()
        parsed = json.loads(content)

        assert parsed["event_type"] == "export_completed"
        assert parsed["details"]["pages_exported"] == 50
        assert parsed["details"]["duration_ms"] == 5000


class TestGetAuditLoggerSingleton:
    """Tests for get_audit_logger singleton function."""

    def test_returns_audit_logger_instance(self):
        """Test get_audit_logger returns an AuditLogger."""
        reset_audit_logger()  # Start fresh

        logger = get_audit_logger()

        assert isinstance(logger, AuditLogger)

    def test_returns_same_instance(self):
        """Test get_audit_logger returns the same instance."""
        reset_audit_logger()

        logger1 = get_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is logger2

    def test_context_isolation(self):
        """Test get_audit_logger provides per-context isolation via ContextVar."""
        import threading

        reset_audit_logger()
        instances = []

        def get_instance():
            instances.append(get_audit_logger())

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread has its own ContextVar context, so each creates its own instance
        assert len(instances) == 10
        assert all(isinstance(inst, AuditLogger) for inst in instances)


class TestResetAuditLogger:
    """Tests for reset_audit_logger function."""

    def test_clears_instance(self):
        """Test reset_audit_logger clears the global instance."""
        logger1 = get_audit_logger()

        reset_audit_logger()

        logger2 = get_audit_logger()

        # After reset, should get a new instance
        assert logger1 is not logger2

    def test_allows_new_initialization(self):
        """Test reset allows fresh initialization."""
        reset_audit_logger()
        logger = get_audit_logger()

        assert isinstance(logger, AuditLogger)


class TestLogRotationConfiguration:
    """Tests for log rotation configuration."""

    def test_handler_is_timed_rotating(self, tmp_path):
        """Test logger uses TimedRotatingFileHandler."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        # Check handler type
        handlers = logger._logger.handlers
        assert len(handlers) > 0

        handler = handlers[0]
        assert isinstance(handler, logging.handlers.TimedRotatingFileHandler)

    def test_rotation_interval_is_midnight(self, tmp_path):
        """Test rotation happens at midnight."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        handler = logger._logger.handlers[0]
        assert handler.when == "MIDNIGHT"

    def test_backup_count_is_30(self, tmp_path):
        """Test 30 days of logs are retained."""
        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        handler = logger._logger.handlers[0]
        assert handler.backupCount == 30


class TestCriticalEventLogging:
    """Tests for critical event handling."""

    def test_critical_events_logged_to_app_logger(self, tmp_path):
        """Test critical events trigger the app logger code path."""
        import io
        import sys

        log_dir = tmp_path / "audit"
        audit_logger = AuditLogger(log_dir=log_dir)

        # Set up a custom stream handler to capture the module logger output
        module_logger = logging.getLogger("local_deepwiki.core.audit")
        original_level = module_logger.level
        original_handlers = module_logger.handlers[:]

        capture_stream = io.StringIO()
        handler = logging.StreamHandler(capture_stream)
        handler.setLevel(logging.WARNING)
        module_logger.addHandler(handler)
        module_logger.setLevel(logging.WARNING)

        try:
            event = AuditEvent(
                timestamp="2024-01-01T00:00:00Z",
                event_type=AuditEventType.AUTHORIZATION_FAILED,
                severity=AuditSeverity.CRITICAL,
                subject_id="attacker",
                subject_role="GUEST",
                resource_type="operation",
                resource_path="delete_all",
                action="Attempt to delete all data",
                result="denied",
            )

            audit_logger.log_event(event)

            # Check that the critical event was logged to the module logger
            captured = capture_stream.getvalue()
            assert "AUDIT[CRITICAL]" in captured
        finally:
            # Restore original state
            module_logger.removeHandler(handler)
            module_logger.setLevel(original_level)

    def test_non_critical_events_not_logged_to_app_logger(self, tmp_path):
        """Test non-critical events don't trigger app logger WARNING."""
        import io

        log_dir = tmp_path / "audit"
        audit_logger = AuditLogger(log_dir=log_dir)

        # Set up a custom stream handler
        module_logger = logging.getLogger("local_deepwiki.core.audit")
        original_level = module_logger.level
        original_handlers = module_logger.handlers[:]

        capture_stream = io.StringIO()
        handler = logging.StreamHandler(capture_stream)
        handler.setLevel(logging.WARNING)
        module_logger.addHandler(handler)
        module_logger.setLevel(logging.WARNING)

        try:
            event = AuditEvent(
                timestamp="2024-01-01T00:00:00Z",
                event_type=AuditEventType.ACCESS_GRANTED,
                severity=AuditSeverity.INFO,
                subject_id="user",
                subject_role="VIEWER",
                resource_type="query",
                resource_path="/repo",
                action="search",
                result="success",
            )

            audit_logger.log_event(event)

            # Check that no CRITICAL log was emitted
            captured = capture_stream.getvalue()
            assert "AUDIT[CRITICAL]" not in captured
        finally:
            # Restore original state
            module_logger.removeHandler(handler)
            module_logger.setLevel(original_level)
