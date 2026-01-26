# Phase 3 Implementation Plan - Medium-Priority Security Fixes

## Overview

Phase 3 focuses on preventing resource exhaustion attacks, establishing security audit trails, and detecting secrets in analyzed code.

**Estimated Effort**: 8-10 hours
**Target Completion**: Week 3-4
**Priority Level**: MEDIUM (High impact but lower critical severity)

---

## Phase 3 Objectives

1. **Prevent Denial of Service via Resource Exhaustion** (CWE-400)
   - Input size validation on all MCP tool parameters
   - Query complexity limits for deep research
   - Index size limits for repositories

2. **Establish Security Audit Trail** (CWE-778)
   - Log all access to sensitive operations
   - Track who (subject) accessed what (resource) when and how
   - Enable compliance reporting (SOC2, GDPR, HIPAA)

3. **Detect Hardcoded Secrets** (CWE-798)
   - Scan indexed code for API keys, credentials, tokens
   - Provide warnings during indexing
   - Support common secret patterns

---

## Implementation Details

### Task 1: Input Size Validation

**Files to Create**:
- `/src/local_deepwiki/core/validation.py` (NEW)

**Files to Modify**:
- `/src/local_deepwiki/handlers.py` (add validation checks)
- `/src/local_deepwiki/core/indexer.py` (index size checks)

**Effort**: 1-2 hours | **Tests**: 15-20 new tests

**Implementation**:

```python
# /src/local_deepwiki/core/validation.py

class ResourceLimits:
    """Resource consumption limits for security."""

    # Query parameters
    MAX_QUERY_LENGTH = 5000  # Characters
    MAX_QUESTION_LENGTH = 2000  # Characters
    MAX_QUERY_HISTORY = 100  # Previous queries

    # Repository indexing
    MAX_REPO_SIZE = 1_000_000_000  # 1GB
    MAX_FILES_PER_REPO = 50_000  # Files
    MAX_FILE_SIZE = 50_000_000  # 50MB per file
    MAX_TOTAL_CHUNK_SIZE = 500_000_000  # 500MB total chunks

    # Deep research
    MAX_SUB_QUESTIONS = 20  # Sub-questions in decomposition
    MAX_RESEARCH_DEPTH = 5  # Recursion depth
    MAX_CONTEXT_CHUNKS = 500  # Chunks to consider

    # Export operations
    MAX_PDF_PAGES = 10_000  # Pages in PDF
    MAX_HTML_SIZE = 100_000_000  # 100MB HTML

def validate_query_parameters(
    query: str,
    repo_path: str,
    max_results: int
) -> None:
    """Validate query parameters against resource limits."""
    if len(query) > ResourceLimits.MAX_QUERY_LENGTH:
        raise ValueError(f"Query exceeds max length ({ResourceLimits.MAX_QUERY_LENGTH})")

    if len(query) < 1:
        raise ValueError("Query cannot be empty")

    if max_results < 1 or max_results > ResourceLimits.MAX_CONTEXT_CHUNKS:
        raise ValueError(f"max_results must be 1-{ResourceLimits.MAX_CONTEXT_CHUNKS}")

    repo_path_obj = Path(repo_path)
    if not repo_path_obj.exists():
        raise ValueError(f"Repository path does not exist: {repo_path}")

    if not repo_path_obj.is_dir():
        raise ValueError(f"Repository path is not a directory: {repo_path}")

def validate_index_parameters(
    repo_path: str,
    output_dir: str
) -> tuple[int, int]:
    """
    Validate repository indexing parameters.

    Returns:
        (total_size, file_count)

    Raises:
        ValueError: If repository exceeds limits
    """
    repo_path_obj = Path(repo_path)
    total_size = 0
    file_count = 0

    for file_path in repo_path_obj.rglob("*"):
        if file_path.is_file():
            file_size = file_path.stat().st_size

            # Check individual file size
            if file_size > ResourceLimits.MAX_FILE_SIZE:
                raise ValueError(
                    f"File too large: {file_path} ({file_size} bytes, "
                    f"max {ResourceLimits.MAX_FILE_SIZE})"
                )

            total_size += file_size
            file_count += 1

            # Check total repository size
            if total_size > ResourceLimits.MAX_REPO_SIZE:
                raise ValueError(
                    f"Repository exceeds max size ({ResourceLimits.MAX_REPO_SIZE} bytes)"
                )

            # Check file count
            if file_count > ResourceLimits.MAX_FILES_PER_REPO:
                raise ValueError(
                    f"Repository exceeds max files ({ResourceLimits.MAX_FILES_PER_REPO})"
                )

    return total_size, file_count

def validate_deep_research_parameters(
    question: str,
    preset: str,
    max_chunks: int
) -> None:
    """Validate deep research parameters."""
    if len(question) > ResourceLimits.MAX_QUESTION_LENGTH:
        raise ValueError(
            f"Question exceeds max length ({ResourceLimits.MAX_QUESTION_LENGTH})"
        )

    if preset not in ("quick", "default", "thorough"):
        raise ValueError(f"Invalid preset: {preset}")

    if max_chunks < 1 or max_chunks > ResourceLimits.MAX_CONTEXT_CHUNKS:
        raise ValueError(
            f"max_chunks must be 1-{ResourceLimits.MAX_CONTEXT_CHUNKS}"
        )
```

**Integration in Handlers**:

```python
# /src/local_deepwiki/handlers.py

from local_deepwiki.core.validation import (
    validate_query_parameters,
    validate_index_parameters,
    validate_deep_research_parameters,
    ResourceLimits
)

async def handle_ask_question(question: str, repo_path: str, max_results: int = 5):
    """Ask question about indexed repository."""
    # Validate inputs FIRST
    validate_query_parameters(question, repo_path, max_results)

    # Then proceed with actual work
    ...

async def handle_index_repository(repo_path: str, full_rebuild: bool = False):
    """Index repository for search."""
    # Validate inputs FIRST
    total_size, file_count = validate_index_parameters(repo_path, output_dir)

    # Log validation success
    logger.info(
        f"Indexing repository: {repo_path} "
        f"({total_size} bytes, {file_count} files)"
    )

    # Proceed with indexing
    ...
```

**Benefits**:
- Prevents DoS attacks via large queries
- Prevents disk exhaustion from huge repositories
- Prevents memory exhaustion from massive chunks
- Provides clear feedback to users about limits

**Vulnerabilities Addressed**:
- CWE-400: Uncontrolled Resource Consumption (via HTTP Request)
- CWE-770: Allocation of Resources Without Limits or Throttling
- CWE-774: Allocation of File Descriptors or Handles Without Limits or Throttling

---

### Task 2: Audit Logging System

**Files to Create**:
- `/src/local_deepwiki/core/audit.py` (NEW)
- `/src/local_deepwiki/core/audit_logger.py` (NEW)

**Files to Modify**:
- `/src/local_deepwiki/handlers.py` (integrate audit logging)
- `/src/local_deepwiki/security/access_control.py` (log access decisions)

**Effort**: 2-3 hours | **Tests**: 20-25 new tests

**Implementation**:

```python
# /src/local_deepwiki/core/audit.py

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

class AuditEventType(str, Enum):
    """Types of audit events."""
    # Access events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"

    # Operation events
    INDEX_STARTED = "index_started"
    INDEX_COMPLETED = "index_completed"
    INDEX_FAILED = "index_failed"

    QUERY_EXECUTED = "query_executed"
    QUERY_FAILED = "query_failed"

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

class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class AuditEvent:
    """Represents an audit event."""
    timestamp: str  # ISO8601
    event_type: AuditEventType
    severity: AuditSeverity
    subject_id: Optional[str]  # User or service performing action
    subject_role: Optional[str]  # ADMIN, EDITOR, VIEWER, GUEST
    resource_type: str  # "repository", "config", "query", etc.
    resource_path: str  # Path or identifier of resource
    action: str  # What was attempted
    result: str  # "success" or "failure"
    reason: Optional[str]  # Why it failed (if applicable)
    details: dict  # Additional context

class AuditLogger:
    """Manages audit logging for security events."""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path.home() / ".config" / "local-deepwiki" / "audit"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup audit logger with file and console handlers."""
        logger = logging.getLogger("deepwiki.audit")
        logger.setLevel(logging.DEBUG)

        # File handler (daily rotation)
        handler = logging.handlers.TimedRotatingFileHandler(
            self.log_dir / "audit.log",
            when="midnight",
            interval=1,
            backupCount=30  # Keep 30 days of logs
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        logger.addHandler(handler)

        return logger

    def log_event(self, event: AuditEvent) -> None:
        """Log an audit event."""
        event_dict = asdict(event)

        # Ensure ISO8601 timestamp
        event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Log to file
        self.logger.info(json.dumps(event_dict))

        # Log critical events to console as well
        if event.severity == AuditSeverity.CRITICAL:
            logger.warning(
                f"AUDIT[CRITICAL]: {event.action} on {event.resource_type} "
                f"by {event.subject_id} - {event.result}"
            )

    def log_access_decision(
        self,
        subject_id: str,
        subject_role: str,
        resource_type: str,
        resource_path: str,
        permission_requested: str,
        granted: bool,
        reason: Optional[str] = None
    ) -> None:
        """Log an access control decision."""
        event = AuditEvent(
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=AuditEventType.ACCESS_GRANTED if granted else AuditEventType.ACCESS_DENIED,
            severity=AuditSeverity.WARNING if not granted else AuditSeverity.INFO,
            subject_id=subject_id,
            subject_role=subject_role,
            resource_type=resource_type,
            resource_path=resource_path,
            action=f"Request permission: {permission_requested}",
            result="success" if granted else "failure",
            reason=reason,
            details={
                "permission": permission_requested,
            }
        )
        self.log_event(event)

    def log_query_execution(
        self,
        subject_id: str,
        repo_path: str,
        query: str,
        success: bool,
        error_message: Optional[str] = None
    ) -> None:
        """Log query execution."""
        event = AuditEvent(
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=AuditEventType.QUERY_EXECUTED if success else AuditEventType.QUERY_FAILED,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            subject_id=subject_id,
            subject_role=None,  # Would be populated from subject
            resource_type="query",
            resource_path=repo_path,
            action=f"Execute query: {query[:100]}...",
            result="success" if success else "failure",
            reason=error_message,
            details={
                "query_length": len(query),
                "repo_path": repo_path,
            }
        )
        self.log_event(event)

# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None

def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
```

**Integration in Handlers**:

```python
# /src/local_deepwiki/handlers.py

from local_deepwiki.core.audit import get_audit_logger, AuditEventType

async def handle_ask_question(question: str, repo_path: str):
    """Ask question about indexed repository."""
    audit_logger = get_audit_logger()
    subject_id = get_current_subject()?.identifier or "anonymous"

    try:
        # Log query attempt
        audit_logger.log_query_execution(
            subject_id=subject_id,
            repo_path=repo_path,
            query=question,
            success=False,  # Initial state
            error_message=None
        )

        # Execute query
        result = await query_engine.search(question, repo_path)

        # Log success
        audit_logger.log_query_execution(
            subject_id=subject_id,
            repo_path=repo_path,
            query=question,
            success=True
        )

        return result

    except Exception as e:
        # Log failure
        audit_logger.log_query_execution(
            subject_id=subject_id,
            repo_path=repo_path,
            query=question,
            success=False,
            error_message=str(e)
        )
        raise
```

**Integration in Access Control**:

```python
# /src/local_deepwiki/security/access_control.py

class AccessController:
    def require_permission(self, permission: Permission) -> None:
        """Check that current subject has the required permission."""
        if not self._current_subject:
            raise AuthenticationException("No subject authenticated")

        if not self._current_subject.has_permission(permission):
            # Log access denial
            audit_logger = get_audit_logger()
            audit_logger.log_access_decision(
                subject_id=self._current_subject.identifier,
                subject_role=next(iter(self._current_subject.roles)).value,
                resource_type="operation",
                resource_path=permission.value,
                permission_requested=permission.value,
                granted=False,
                reason=f"Subject lacks required permission"
            )

            raise AccessDeniedException(
                f"Subject '{self._current_subject.identifier}' lacks permission: {permission}"
            )

        # Log successful permission check
        audit_logger.log_access_decision(
            subject_id=self._current_subject.identifier,
            subject_role=next(iter(self._current_subject.roles)).value,
            resource_type="operation",
            resource_path=permission.value,
            permission_requested=permission.value,
            granted=True
        )
```

**Benefits**:
- Complete audit trail for compliance (SOC2, GDPR, HIPAA)
- Security incident investigation capability
- User activity tracking
- Authentication/authorization logging

**Vulnerabilities Addressed**:
- CWE-778: Insufficient Logging

---

### Task 3: Secret Detection

**Files to Create**:
- `/src/local_deepwiki/core/secret_detector.py` (NEW)

**Files to Modify**:
- `/src/local_deepwiki/core/indexer.py` (integrate secret detection)

**Effort**: 1-2 hours | **Tests**: 15-20 new tests

**Implementation**:

```python
# /src/local_deepwiki/core/secret_detector.py

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

class SecretType(str, Enum):
    """Types of secrets to detect."""
    AWS_KEY = "aws_access_key"
    AWS_SECRET = "aws_secret_key"
    PRIVATE_KEY = "private_key"
    API_KEY = "api_key"
    GENERIC_TOKEN = "generic_token"
    GITHUB_TOKEN = "github_token"
    GITLAB_TOKEN = "gitlab_token"
    SLACK_TOKEN = "slack_token"
    AZURE_KEY = "azure_key"
    GOOGLE_KEY = "google_key"
    DATABASE_URL = "database_url"
    DOCKER_AUTH = "docker_auth"
    JAVA_KEYSTORE = "java_keystore"
    SSH_KEY = "ssh_key"
    PGP_KEY = "pgp_key"

@dataclass
class SecretFinding:
    """Represents a detected secret in code."""
    secret_type: SecretType
    file_path: str
    line_number: int
    context: str  # Code snippet around secret
    confidence: float  # 0.0-1.0
    recommendation: str

class SecretDetector:
    """Detects hardcoded secrets in code."""

    # Secret patterns (high-confidence patterns only)
    PATTERNS = {
        SecretType.AWS_KEY: re.compile(r'AKIA[0-9A-Z]{16}'),
        SecretType.AWS_SECRET: re.compile(
            r'(?i)aws_secret_access_key\s*[:=]\s*["\']?[a-zA-Z0-9/+]{40}["\']?'
        ),
        SecretType.GITHUB_TOKEN: re.compile(r'ghp_[a-zA-Z0-9]{36}'),
        SecretType.GITLAB_TOKEN: re.compile(r'glpat-[a-zA-Z0-9\-_]{20,}'),
        SecretType.SLACK_TOKEN: re.compile(r'xox[baprs]-[a-zA-Z0-9]{10,48}'),
        SecretType.PRIVATE_KEY: re.compile(
            r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'
        ),
        SecretType.API_KEY: re.compile(
            r'(?i)api[_-]?key\s*[:=]\s*["\']?[a-zA-Z0-9_\-]{20,}["\']?'
        ),
        SecretType.DATABASE_URL: re.compile(
            r'(?i)(?:postgres|mysql|mongodb)://[a-zA-Z0-9_-]+:[a-zA-Z0-9_@!#$%^&*()-]+@'
        ),
    }

    # False positive patterns to exclude
    FALSE_POSITIVES = [
        re.compile(r'example|test|demo|mock|fake|placeholder|your[-_]?key'),
        re.compile(r'sk[-_]?test[-_]?[a-z]+'),  # Test keys
    ]

    def scan_content(
        self,
        content: str,
        file_path: str,
        start_line: int = 0
    ) -> list[SecretFinding]:
        """
        Scan code content for secrets.

        Args:
            content: Code content to scan
            file_path: Path to file (for reporting)
            start_line: Starting line number (for large files)

        Returns:
            List of SecretFinding objects
        """
        findings = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=start_line + 1):
            # Skip comments and empty lines
            if line.strip().startswith('#') or not line.strip():
                continue

            # Check each pattern
            for secret_type, pattern in self.PATTERNS.items():
                matches = pattern.finditer(line)

                for match in matches:
                    # Check false positives
                    if self._is_false_positive(match.group()):
                        continue

                    findings.append(
                        SecretFinding(
                            secret_type=secret_type,
                            file_path=file_path,
                            line_number=line_num,
                            context=line.strip(),
                            confidence=self._calculate_confidence(secret_type, match.group()),
                            recommendation=self._get_recommendation(secret_type)
                        )
                    )

        return findings

    def _is_false_positive(self, match: str) -> bool:
        """Check if match is a known false positive."""
        for pattern in self.FALSE_POSITIVES:
            if pattern.search(match):
                return True
        return False

    def _calculate_confidence(self, secret_type: SecretType, match: str) -> float:
        """Calculate confidence score for secret detection."""
        # AWS keys have very high confidence
        if secret_type in (SecretType.AWS_KEY, SecretType.GITHUB_TOKEN):
            return 0.95

        # Database URLs have high confidence
        if secret_type == SecretType.DATABASE_URL:
            return 0.9

        # Private keys have very high confidence
        if secret_type == SecretType.PRIVATE_KEY:
            return 0.98

        # Generic API keys are lower confidence
        if secret_type == SecretType.API_KEY:
            return 0.7

        return 0.8

    def _get_recommendation(self, secret_type: SecretType) -> str:
        """Get remediation recommendation for secret type."""
        recommendations = {
            SecretType.AWS_KEY: "Rotate AWS access key immediately. Check CloudTrail for unauthorized access.",
            SecretType.PRIVATE_KEY: "Rotate private key immediately. Revoke old certificate.",
            SecretType.GITHUB_TOKEN: "Revoke GitHub token in settings. Generate new token if needed.",
            SecretType.DATABASE_URL: "Update database password. Change connection string in all environments.",
            SecretType.API_KEY: "Rotate API key in provider console. Update configuration.",
        }
        return recommendations.get(
            secret_type,
            f"Review and rotate {secret_type.value} immediately."
        )

def scan_repository_for_secrets(repo_path: Path) -> dict[str, list[SecretFinding]]:
    """
    Scan entire repository for secrets.

    Returns:
        Dictionary mapping file paths to findings
    """
    detector = SecretDetector()
    findings_by_file = {}

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip binary files and common non-source files
        if _should_skip_file(file_path):
            continue

        try:
            content = file_path.read_text(errors='ignore')
            findings = detector.scan_content(
                content,
                str(file_path.relative_to(repo_path))
            )

            if findings:
                findings_by_file[str(file_path)] = findings

        except Exception:
            # Skip files that can't be read
            pass

    return findings_by_file

def _should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped from secret scanning."""
    skip_extensions = {
        '.png', '.jpg', '.jpeg', '.gif', '.bin', '.pyc',
        '.so', '.o', '.a', '.lib', '.zip', '.tar', '.gz'
    }

    skip_names = {
        '.git', '.venv', '__pycache__', 'node_modules',
        '.deepwiki', 'dist', 'build', '.tox'
    }

    if file_path.suffix.lower() in skip_extensions:
        return True

    if file_path.name in skip_names:
        return True

    if any(part in skip_names for part in file_path.parts):
        return True

    return False
```

**Integration in Indexer**:

```python
# /src/local_deepwiki/core/indexer.py

from local_deepwiki.core.secret_detector import scan_repository_for_secrets

async def index_repository(repo_path: Path, ...) -> IndexResult:
    """Index repository with secret detection."""

    # Scan for secrets before indexing
    logger.info("Scanning for hardcoded secrets...")
    secret_findings = scan_repository_for_secrets(repo_path)

    if secret_findings:
        logger.warning(
            f"Found {sum(len(f) for f in secret_findings.values())} "
            f"potential secrets in {len(secret_findings)} files"
        )

        # Log each finding with recommendations
        for file_path, findings in secret_findings.items():
            for finding in findings:
                logger.warning(
                    f"[{finding.secret_type.value}] {file_path}:{finding.line_number} - "
                    f"{finding.recommendation}"
                )

    # Continue with normal indexing
    # Secrets are now detected but indexing can proceed
    # (users should remediate, but indexing doesn't fail)

    return result
```

**Benefits**:
- Detects accidental secret commits before they're indexed
- Provides automatic remediation guidance
- Prevents secret exposure via search results
- Helps enforce secret management practices

**Vulnerabilities Addressed**:
- CWE-798: Use of Hard-Coded Credentials (detection)
- CWE-359: Exposure of Private Information

---

## Implementation Timeline

### Week 1 (Days 1-2)
- Day 1: Implement input size validation (4 hours)
  - Create validation.py with limits and check functions
  - Update handlers.py to call validation
  - Write 15-20 tests

- Day 2: Implement audit logging (5 hours)
  - Create audit.py and audit_logger.py
  - Integrate with handlers.py
  - Integrate with access_control.py
  - Write 20-25 tests

### Week 2 (Day 3)
- Day 3: Implement secret detection (4 hours)
  - Create secret_detector.py
  - Integrate with indexer.py
  - Write 15-20 tests
  - Run full test suite (2988+ tests)

### Week 2-3 (Days 4-5)
- Day 4: Complete testing and integration
- Day 5: Documentation and staging deployment

---

## Testing Strategy

### Unit Tests (50-65 new tests)
- Input validation limits and edge cases
- Audit event logging and retrieval
- Secret pattern detection (true/false positives)
- Resource limit enforcement

### Integration Tests
- End-to-end audit trail for query operations
- Secret detection during indexing
- Resource limits during large operations

### Performance Tests
- Audit logging overhead (<5% impact)
- Secret scanning overhead (<10% for indexing)
- Validation check performance (<1ms per check)

---

## Success Criteria

- [ ] All 2988+ existing tests pass
- [ ] 50-65 new tests added (all passing)
- [ ] Input validation prevents all resource exhaustion scenarios
- [ ] Audit logs record all security-relevant operations
- [ ] Secret detection finds 90%+ of common secret patterns
- [ ] <5ms overhead per operation for validation
- [ ] <10ms overhead for audit logging
- [ ] No false positives in RBAC enforcement

---

## Known Limitations & Future Work

1. **Secret Detection**
   - Limited to regex patterns (no ML-based detection)
   - May have false positives on test/example credentials
   - Doesn't scan inside binary files

2. **Audit Logging**
   - Local file storage (could integrate with central syslog)
   - No encryption of audit logs (filesystem permissions assumed)
   - No built-in log analysis/alerting

3. **Resource Limits**
   - Static limits (could be made configurable per role)
   - No per-user quota tracking
   - No rate limiting on API calls

---

## Integration with Phase 1 & 2

- **Phase 1**: API key security + error sanitization
  - Phase 3 audit logs will record access to sensitive operations without exposing keys

- **Phase 2**: RBAC + dependency pinning
  - Phase 3 audit logs integrate with RBAC to track who accessed what
  - Resource limits prevent privilege escalation via resource exhaustion

---

## Post-Phase 3 Work (Phase 4)

After Phase 3 completion, recommended follow-up work:

1. **Integrate Access Control with Handlers**
   - Apply @require_permission decorators to all tool functions
   - Implement allowlist/denylist for repositories

2. **Configure Role Assignments**
   - Define how users are assigned to roles
   - Set up initial admin accounts

3. **Deploy and Monitor**
   - Deploy to staging environment
   - Run security regression tests
   - Monitor logs for issues
   - Deploy to production

