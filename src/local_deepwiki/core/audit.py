"""Audit logging system for local-deepwiki.

This module provides comprehensive audit logging for security-relevant operations,
supporting compliance requirements (SOC2, GDPR, HIPAA) and security incident investigation.

The audit system logs:
- Access control decisions (granted/denied)
- Operation lifecycle events (index, query, export)
- Configuration changes
- Security events (authentication, authorization failures)
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from local_deepwiki.logging import get_logger

# Module logger for non-audit operational messages
logger = get_logger(__name__)


class AuditEventType(StrEnum):
    """Types of audit events.

    Categorized by operation type for easier filtering and analysis.
    """

    # Access control events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"

    # Repository indexing events
    INDEX_STARTED = "index_started"
    INDEX_COMPLETED = "index_completed"
    INDEX_FAILED = "index_failed"

    # Query operation events
    QUERY_EXECUTED = "query_executed"
    QUERY_FAILED = "query_failed"

    # Export operation events
    EXPORT_STARTED = "export_started"
    EXPORT_COMPLETED = "export_completed"

    # Configuration events
    CONFIG_READ = "config_read"
    CONFIG_MODIFIED = "config_modified"

    # Security events
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    SENSITIVE_RESOURCE_ACCESSED = "sensitive_resource_accessed"


class AuditSeverity(StrEnum):
    """Severity levels for audit events.

    Used to categorize events for alerting and log rotation policies.
    """

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents an audit event for logging.

    All fields are designed to support compliance reporting and
    security incident investigation.

    Attributes:
        timestamp: ISO8601 formatted timestamp with timezone.
        event_type: Type of audit event.
        severity: Severity level of the event.
        subject_id: Identifier of the user/service performing the action.
        subject_role: Role of the subject (ADMIN, EDITOR, VIEWER, GUEST).
        resource_type: Type of resource being accessed (repository, config, query, etc.).
        resource_path: Path or identifier of the specific resource.
        action: Description of the action being performed.
        result: Outcome of the action (success/failure).
        reason: Explanation for failures or denials.
        details: Additional context as key-value pairs.
    """

    timestamp: str
    event_type: AuditEventType
    severity: AuditSeverity
    subject_id: str | None
    subject_role: str | None
    resource_type: str
    resource_path: str
    action: str
    result: str
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    """Manages audit logging for security events.

    Provides structured logging of security-relevant events to file,
    with automatic daily rotation and 30-day retention.

    The audit logger uses a separate logging hierarchy from the application
    logger to ensure audit events are never accidentally filtered or lost.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        """Initialize the audit logger.

        Args:
            log_dir: Directory to store audit logs. Defaults to
                     ~/.config/local-deepwiki/audit
        """
        self.log_dir = log_dir or Path.home() / ".config" / "local-deepwiki" / "audit"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Set up the audit logger with file rotation.

        Creates a dedicated logger with:
        - TimedRotatingFileHandler for daily rotation
        - 30-day retention (backupCount=30)
        - JSON-compatible format for log analysis tools

        Returns:
            Configured logging.Logger instance.
        """
        # Use a unique logger name to avoid conflicts
        audit_logger = logging.getLogger("deepwiki.audit")

        # Prevent duplicate handlers if logger is reinitialized
        if audit_logger.handlers:
            return audit_logger

        audit_logger.setLevel(logging.DEBUG)

        # Prevent propagation to root logger to avoid duplicate messages
        audit_logger.propagate = False

        # File handler with daily rotation
        log_file = self.log_dir / "audit.log"
        handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_file),
            when="midnight",
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding="utf-8",
        )
        handler.setLevel(logging.DEBUG)

        # Simple format - the message itself is JSON
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)

        audit_logger.addHandler(handler)

        return audit_logger

    def log_event(self, event: AuditEvent) -> None:
        """Log an audit event.

        The event is serialized to JSON and written to the audit log file.
        Critical events are also logged to the application logger for
        immediate visibility.

        Args:
            event: The audit event to log.
        """
        # Convert event to dictionary
        event_dict = asdict(event)

        # Convert enum values to strings for JSON serialization
        event_dict["event_type"] = event.event_type.value
        event_dict["severity"] = event.severity.value

        # Use provided timestamp or generate current UTC time in ISO8601 format
        if not event_dict.get("timestamp"):
            event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Log to audit file as JSON
        self._logger.info(json.dumps(event_dict, default=str))

        # Log critical events to application logger for visibility
        if event.severity == AuditSeverity.CRITICAL:
            logger.warning(
                "AUDIT[CRITICAL]: %s on %s by %s - %s",
                event.action,
                event.resource_type,
                event.subject_id or "anonymous",
                event.result,
            )

    def log_access_decision(
        self,
        subject_id: str | None,
        subject_role: str | None,
        resource_type: str,
        resource_path: str,
        permission_requested: str,
        granted: bool,
        reason: str | None = None,
    ) -> None:
        """Log an access control decision.

        Convenience method for logging permission checks from RBAC system.

        Args:
            subject_id: Identifier of the subject requesting access.
            subject_role: Role of the subject.
            resource_type: Type of resource (operation, file, etc.).
            resource_path: Path or identifier of the resource.
            permission_requested: The permission being requested.
            granted: Whether access was granted.
            reason: Explanation for the decision (especially for denials).
        """
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=AuditEventType.ACCESS_GRANTED
            if granted
            else AuditEventType.ACCESS_DENIED,
            severity=AuditSeverity.INFO if granted else AuditSeverity.WARNING,
            subject_id=subject_id,
            subject_role=subject_role,
            resource_type=resource_type,
            resource_path=resource_path,
            action=f"Request permission: {permission_requested}",
            result="granted" if granted else "denied",
            reason=reason,
            details={
                "permission": permission_requested,
            },
        )
        self.log_event(event)

    def log_query_execution(
        self,
        subject_id: str | None,
        repo_path: str,
        query: str,
        success: bool,
        query_type: str = "search",
        error_message: str | None = None,
        chunks_returned: int | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Log a query execution.

        Convenience method for logging query operations (search, deep research).

        Args:
            subject_id: Identifier of the subject executing the query.
            repo_path: Path to the repository being queried.
            query: The query string (truncated for privacy).
            success: Whether the query succeeded.
            query_type: Type of query (search, deep_research).
            error_message: Error message if query failed.
            chunks_returned: Number of result chunks returned.
            duration_ms: Query duration in milliseconds.
        """
        # Truncate query for logging (privacy)
        query_preview = query[:100] + "..." if len(query) > 100 else query

        details: dict[str, Any] = {
            "query_length": len(query),
            "query_type": query_type,
            "repo_path": repo_path,
        }

        if chunks_returned is not None:
            details["chunks_returned"] = chunks_returned
        if duration_ms is not None:
            details["duration_ms"] = duration_ms

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=AuditEventType.QUERY_EXECUTED
            if success
            else AuditEventType.QUERY_FAILED,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            subject_id=subject_id,
            subject_role=None,  # Populated from context if available
            resource_type="query",
            resource_path=repo_path,
            action=f"Execute {query_type}: {query_preview}",
            result="success" if success else "failure",
            reason=error_message,
            details=details,
        )
        self.log_event(event)

    def log_index_operation(
        self,
        subject_id: str | None,
        repo_path: str,
        operation: str,
        success: bool,
        files_processed: int | None = None,
        chunks_created: int | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log an indexing operation.

        Convenience method for logging repository indexing lifecycle events.

        Args:
            subject_id: Identifier of the subject performing the operation.
            repo_path: Path to the repository being indexed.
            operation: Operation type (started, completed, failed).
            success: Whether the operation succeeded (for completed/failed).
            files_processed: Number of files processed.
            chunks_created: Number of chunks created.
            duration_ms: Operation duration in milliseconds.
            error_message: Error message if operation failed.
        """
        # Determine event type based on operation
        if operation == "started":
            event_type = AuditEventType.INDEX_STARTED
            severity = AuditSeverity.INFO
            result = "in_progress"
        elif operation == "completed" and success:
            event_type = AuditEventType.INDEX_COMPLETED
            severity = AuditSeverity.INFO
            result = "success"
        else:
            event_type = AuditEventType.INDEX_FAILED
            severity = AuditSeverity.WARNING
            result = "failure"

        details: dict[str, Any] = {
            "operation": operation,
            "repo_path": repo_path,
        }

        if files_processed is not None:
            details["files_processed"] = files_processed
        if chunks_created is not None:
            details["chunks_created"] = chunks_created
        if duration_ms is not None:
            details["duration_ms"] = duration_ms

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            severity=severity,
            subject_id=subject_id,
            subject_role=None,
            resource_type="repository",
            resource_path=repo_path,
            action=f"Index repository: {operation}",
            result=result,
            reason=error_message,
            details=details,
        )
        self.log_event(event)

    def log_export_operation(
        self,
        subject_id: str | None,
        wiki_path: str,
        output_path: str,
        export_type: str,
        operation: str,
        success: bool,
        pages_exported: int | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log an export operation.

        Convenience method for logging wiki export lifecycle events.

        Args:
            subject_id: Identifier of the subject performing the export.
            wiki_path: Path to the wiki being exported.
            output_path: Destination path for the export.
            export_type: Type of export (html, pdf).
            operation: Operation type (started, completed).
            success: Whether the operation succeeded.
            pages_exported: Number of pages exported.
            duration_ms: Operation duration in milliseconds.
            error_message: Error message if operation failed.
        """
        event_type = (
            AuditEventType.EXPORT_STARTED
            if operation == "started"
            else AuditEventType.EXPORT_COMPLETED
        )
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        result = (
            "in_progress"
            if operation == "started"
            else ("success" if success else "failure")
        )

        details: dict[str, Any] = {
            "export_type": export_type,
            "wiki_path": wiki_path,
            "output_path": output_path,
        }

        if pages_exported is not None:
            details["pages_exported"] = pages_exported
        if duration_ms is not None:
            details["duration_ms"] = duration_ms

        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            severity=severity,
            subject_id=subject_id,
            subject_role=None,
            resource_type="wiki_export",
            resource_path=wiki_path,
            action=f"Export wiki to {export_type}: {operation}",
            result=result,
            reason=error_message,
            details=details,
        )
        self.log_event(event)


# Global audit logger instance
_audit_logger_var: ContextVar[AuditLogger | None] = ContextVar(
    "audit_logger", default=None
)


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance.

    Returns:
        The global AuditLogger instance.
    """
    val = _audit_logger_var.get()
    if val is None:
        val = AuditLogger()
        _audit_logger_var.set(val)
    return val


def reset_audit_logger() -> None:
    """Reset the global audit logger (for testing only).

    This clears the global instance, allowing a fresh logger
    to be created on the next call to get_audit_logger().
    """
    _audit_logger_var.set(None)
