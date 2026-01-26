# Security Remediation Guide

## Quick Start
**Target Time:** 2-3 weeks
**Priority:** 3 HIGH, 5 MEDIUM, 3 LOW findings
**Risk Score:** MEDIUM → LOW after remediation

---

## PHASE 1: CRITICAL FIXES (Week 1)

### 1.1 API Key Security Implementation

**Problem:** API keys stored in plaintext instance variables

**Solution:** Create secure credential manager

**File to Create:** `/src/local_deepwiki/providers/credentials.py`

```python
"""Secure credential management for API providers."""

import os
from typing import Optional
from dataclasses import dataclass
import hashlib

@dataclass
class CredentialManager:
    """Manages credentials securely without storing in memory."""

    @staticmethod
    def get_api_key(env_var: str, provider: str) -> Optional[str]:
        """Get API key from environment.

        Args:
            env_var: Environment variable name
            provider: Provider name for logging

        Returns:
            API key or None

        Raises:
            ValueError: If key format is invalid
        """
        key = os.environ.get(env_var)
        if not key:
            return None

        # Validate key format (basic check)
        if len(key) < 16:
            raise ValueError(f"{provider} API key appears invalid (too short)")

        # Don't store in memory, validate and return
        return key

    @staticmethod
    def validate_key_format(key: str, provider: str) -> bool:
        """Validate key format without storing."""
        if provider == "anthropic":
            # Anthropic keys start with 'sk-ant-'
            return key.startswith("sk-ant-") and len(key) > 20
        elif provider == "openai":
            # OpenAI keys start with 'sk-'
            return key.startswith("sk-") and len(key) > 20
        return len(key) >= 16
```

**Modify:** `/src/local_deepwiki/providers/llm/anthropic.py`

```python
# OLD CODE (lines 37-46)
def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
    """Initialize the Anthropic provider.

    Args:
        model: Anthropic model name.
        api_key: Optional API key. Uses ANTHROPIC_API_KEY env var if not provided.
    """
    self._model = model
    self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")  # ⚠️ REMOVED
    self._client = AsyncAnthropic(api_key=self._api_key)

# NEW CODE
from local_deepwiki.providers.credentials import CredentialManager

def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
    """Initialize the Anthropic provider."""
    self._model = model

    # Get API key without storing
    api_key = api_key or CredentialManager.get_api_key("ANTHROPIC_API_KEY", "anthropic")

    if not api_key:
        raise ProviderAuthenticationError(
            "No Anthropic API key configured. Set ANTHROPIC_API_KEY environment variable.",
            provider_name="anthropic:claude",
        )

    # Validate format
    if not CredentialManager.validate_key_format(api_key, "anthropic"):
        raise ProviderAuthenticationError(
            "Anthropic API key format appears invalid.",
            provider_name="anthropic:claude",
        )

    # Pass directly, don't store
    self._client = AsyncAnthropic(api_key=api_key)
```

**Apply same pattern to:**
- `/src/local_deepwiki/providers/llm/openai.py`
- `/src/local_deepwiki/providers/embeddings/openai.py`

---

### 1.2 Error Message Sanitization

**Problem:** Sensitive information leaked in error messages

**File to Modify:** `/src/local_deepwiki/errors.py`

Add sanitization:

```python
import re
from pathlib import Path

def sanitize_error_message(message: str, sanitize_paths: bool = True) -> str:
    """Remove sensitive information from error messages.

    Args:
        message: Original error message
        sanitize_paths: Whether to remove file paths

    Returns:
        Sanitized message
    """
    # Remove home directory paths
    home = str(Path.home())
    message = message.replace(home, "~")

    # Remove absolute paths (keep only filename)
    message = re.sub(r'/[a-zA-Z0-9/_.-]*\.py', '.py', message)

    # Remove localhost URLs
    message = re.sub(r'http://localhost:\d+', 'http://internal-service', message)
    message = re.sub(r'http://127\.0\.0\.1:\d+', 'http://internal-service', message)

    # Remove API keys (basic pattern)
    message = re.sub(r'sk-[a-zA-Z0-9]{40,}', '[REDACTED]', message)
    message = re.sub(r'Bearer [a-zA-Z0-9_-]{20,}', 'Bearer [REDACTED]', message)

    return message
```

**Modify error handler:** `/src/local_deepwiki/handlers.py:131-135`

```python
# OLD CODE
except Exception as e:
    logger.exception(f"Unexpected error in {func.__name__}: {e}")
    error = DeepWikiError(
        message=f"An unexpected error occurred: {e}",  # ⚠️ EXPOSED
        hint="Check the logs for more details. If this persists, please report the issue.",
    )

# NEW CODE
except Exception as e:
    logger.exception(f"Unexpected error in {func.__name__}: {e}")

    # Sanitize before returning to user
    from local_deepwiki.errors import sanitize_error_message
    safe_message = sanitize_error_message(str(e))

    error = DeepWikiError(
        message=f"An error occurred: {safe_message if safe_message else 'please try again'}",
        hint="Check the logs for details if you need troubleshooting.",
    )
```

---

## PHASE 2: HIGH-PRIORITY FIXES (Week 2)

### 2.1 Access Control Implementation

**Create file:** `/src/local_deepwiki/access_control.py`

```python
"""Access control and authorization for tools."""

import os
from pathlib import Path
from typing import Optional, Set
import logging

logger = logging.getLogger(__name__)

class AccessController:
    """Manages access to repositories and paths."""

    # Environment variable to control allowed paths
    ALLOWED_PATHS_ENV = "DEEPWIKI_ALLOWED_PATHS"
    DENIED_PATHS_ENV = "DEEPWIKI_DENIED_PATHS"

    # Dangerous patterns that should require explicit allowlist
    SENSITIVE_PATTERNS = {
        "/.ssh/",
        "/.aws/",
        "/.config/",
        "/root/",
        "/etc/",
        "/.env",
        "/credentials",
        "/secrets",
        "/password",
        "/private_key",
    }

    @staticmethod
    def is_path_allowed(path: Path) -> tuple[bool, Optional[str]]:
        """Check if path is allowed for indexing.

        Args:
            path: Path to check

        Returns:
            Tuple of (allowed, reason)
        """
        path = path.resolve()

        # Check denied list
        denied_paths = os.environ.get(AccessController.DENIED_PATHS_ENV, "").split(":")
        for denied in denied_paths:
            if denied and path.is_relative_to(Path(denied)):
                return False, f"Path in denied list: {denied}"

        # Check allowed list (if set, only these paths allowed)
        allowed_paths = os.environ.get(AccessController.ALLOWED_PATHS_ENV, "").split(":")
        if allowed_paths and allowed_paths[0]:  # If allowlist set
            found = False
            for allowed in allowed_paths:
                if allowed and path.is_relative_to(Path(allowed)):
                    found = True
                    break
            if not found:
                return False, "Path not in allowed list"

        # Warn about sensitive patterns
        path_str = str(path).lower()
        for pattern in AccessController.SENSITIVE_PATTERNS:
            if pattern in path_str:
                logger.warning(f"Indexing path containing '{pattern}': {path}")
                break

        return True, None

    @staticmethod
    def get_access_info() -> dict:
        """Get current access configuration."""
        return {
            "allowed_paths": os.environ.get(AccessController.ALLOWED_PATHS_ENV, "").split(":") or None,
            "denied_paths": os.environ.get(AccessController.DENIED_PATHS_ENV, "").split(":") or None,
            "sensitive_patterns": list(AccessController.SENSITIVE_PATTERNS),
        }
```

**Modify handlers:** `/src/local_deepwiki/handlers.py`

```python
# Add to imports
from local_deepwiki.access_control import AccessController

# In handle_index_repository, after line 177
async def _handle_index_repository_impl(...):
    repo_path = Path(validated.repo_path).resolve()

    # ADD THIS:
    allowed, reason = AccessController.is_path_allowed(repo_path)
    if not allowed:
        raise ValidationError(
            message=f"Path access denied: {reason}",
            hint="Check DEEPWIKI_ALLOWED_PATHS or DEEPWIKI_DENIED_PATHS environment variables",
            field="repo_path",
            value=str(repo_path),
        )

    logger.info(f"Indexing repository: {repo_path}")
    # ... continue
```

**Usage:**
```bash
# Allow only specific paths
export DEEPWIKI_ALLOWED_PATHS="/projects:/work:/home/user/code"

# Or deny sensitive paths
export DEEPWIKI_DENIED_PATHS="/etc:/root:/.ssh"
```

---

### 2.2 Dependency Pinning

**Modify:** `/pyproject.toml`

```toml
# OLD (Line 30-37)
pyyaml >= 6.0
rich >= 13.0
flask >= 3.0
markdown >= 3.0
watchdog >= 4.0
weasyprint >= 68.0
psutil >= 5.0

# NEW - Add upper bounds
pyyaml >= 6.0, < 7.0
rich >= 13.0, < 14.0
flask >= 3.0, < 4.0
markdown >= 3.0, < 4.0
watchdog >= 4.0, < 5.0
weasyprint >= 68.0, < 69.0
psutil >= 5.0, < 6.0
```

---

## PHASE 3: MEDIUM-PRIORITY FIXES (Week 2-3)

### 3.1 Verify YAML Safe Loading

**Check file:** `/src/local_deepwiki/config.py`

Search for all YAML loading:
```bash
grep -n "yaml.load" src/local_deepwiki/config.py
```

**Should only find:**
```python
yaml.safe_load()  # ✓ SECURE
```

**NOT find:**
```python
yaml.load()       # ⚠️ VULNERABLE
```

If `yaml.load()` found, change to `yaml.safe_load()` everywhere.

---

### 3.2 Input Size Validation

**Modify:** `/src/local_deepwiki/validation.py`

Add:
```python
# Add constants (around line 8)
MAX_QUESTION_LENGTH = 2000  # characters
MAX_SEARCH_QUERY_LENGTH = 500

def validate_question(question: str, name: str = "question") -> str:
    """Validate question/prompt length."""
    if not isinstance(question, str):
        raise ValueError(f"{name} must be a string")

    if len(question) == 0:
        raise ValueError(f"{name} cannot be empty")

    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError(
            f"{name} too long ({len(question)} chars, max {MAX_QUESTION_LENGTH})"
        )

    return question
```

**Use in handlers:**
```python
from local_deepwiki.validation import validate_question

# In handle_ask_question
question = validate_question(validated.question)
```

---

### 3.3 Secret Detection in Indexer

**Create:** `/src/local_deepwiki/core/secret_detector.py`

```python
"""Detect and warn about secrets in indexed code."""

import re
from pathlib import Path

class SecretDetector:
    """Detects common secrets in code."""

    PATTERNS = {
        "AWS_KEY": r"AKIA[0-9A-Z]{16}",
        "PRIVATE_KEY": r"-----BEGIN RSA PRIVATE KEY-----",
        "API_KEY": r"['\"]?(api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"][a-zA-Z0-9]{32,}['\"]",
        "PASSWORD": r"['\"]?(password|passwd|pwd)['\"]?\s*[:=]\s*['\"][^'\"]{8,}['\"]",
        "DATABASE_URL": r"(postgres|mysql|mongodb)://[^\s]+",
    }

    @staticmethod
    def check_content(content: str, file_path: str) -> list[str]:
        """Detect secrets in content.

        Returns list of warnings.
        """
        warnings = []

        for secret_type, pattern in SecretDetector.PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                warnings.append(
                    f"⚠️  Possible {secret_type} detected in {file_path}"
                )

        return warnings
```

Use in indexer:
```python
from local_deepwiki.core.secret_detector import SecretDetector

def _parse_single_file(self, file_path: Path) -> ParseResult:
    """Parse file and detect secrets."""
    # ... existing code ...

    # Check for secrets
    warnings = SecretDetector.check_content(content, str(file_path))
    for warning in warnings:
        logger.warning(warning)
```

---

### 3.4 Audit Logging

**Create:** `/src/local_deepwiki/audit.py`

```python
"""Audit logging for security-relevant events."""

import logging
import json
from datetime import datetime
from typing import Any, Optional

class AuditLogger:
    """Logs security-relevant events."""

    def __init__(self):
        self.logger = logging.getLogger("local_deepwiki.audit")

    def log_access(
        self,
        action: str,
        resource: str,
        result: str,
        details: Optional[dict] = None
    ):
        """Log security access event.

        Args:
            action: Action performed (index, search, read, export)
            resource: Resource accessed (repo path)
            result: Result (success, denied, error)
            details: Additional context
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "resource": resource,
            "result": result,
            "details": details or {},
        }

        self.logger.info(json.dumps(event))
```

Use in handlers:
```python
from local_deepwiki.audit import AuditLogger

audit = AuditLogger()

async def handle_ask_question(args: dict[str, Any]) -> list[TextContent]:
    try:
        # ... existing code ...
        audit.log_access(
            action="ask_question",
            resource=str(repo_path),
            result="success",
            details={"question_length": len(question)}
        )
    except Exception as e:
        audit.log_access(
            action="ask_question",
            resource=str(repo_path),
            result="error",
            details={"error": str(e)}
        )
        raise
```

---

## PHASE 4: TESTING (All Phases)

### Security Testing Checklist

```bash
# 1. SAST Analysis
bandit -r src/local_deepwiki/ -v

# 2. Dependency Checking
pip-audit
safety check

# 3. Type Checking
mypy src/local_deepwiki/ --strict

# 4. Path Traversal Tests
python -m pytest tests/security/test_path_traversal.py

# 5. Error Message Tests
python -m pytest tests/security/test_error_messages.py

# 6. API Key Tests
python -m pytest tests/security/test_api_keys.py
```

### Test File to Create: `/tests/security/test_path_traversal.py`

```python
"""Security tests for path traversal."""

import pytest
from pathlib import Path
from local_deepwiki.handlers import handle_read_wiki_page
from local_deepwiki.errors import ValidationError

@pytest.mark.asyncio
async def test_path_traversal_blocked():
    """Verify path traversal attacks are blocked."""

    # Create test wiki path
    wiki_path = Path("/tmp/test_wiki")
    wiki_path.mkdir(exist_ok=True)

    args = {
        "wiki_path": str(wiki_path),
        "page": "../../../../etc/passwd"  # Attack payload
    }

    result = await handle_read_wiki_page(args)

    # Should return error, not the file
    assert "Invalid page path" in str(result)
```

---

## VERIFICATION CHECKLIST

After implementing all fixes:

- [ ] API keys not stored in instance variables
- [ ] Error messages don't leak paths or URLs
- [ ] Access control checks in all tool handlers
- [ ] Dependencies have upper version bounds
- [ ] YAML only uses safe_load()
- [ ] Audit logging captures access
- [ ] Secret detector warns on sensitive patterns
- [ ] Input validation enforces size limits
- [ ] Config files checked for permissions
- [ ] All tests pass
- [ ] No secrets in git history

---

## DEPLOYMENT STRATEGY

### 1. Pre-Deployment
```bash
# Run all security tests
pytest tests/security/ -v

# SAST analysis
bandit -r src/

# Dependency audit
pip-audit
```

### 2. Deployment
- [ ] Deploy to staging first
- [ ] Run penetration testing
- [ ] Test with real API keys (in secure environment)
- [ ] Monitor logs for errors
- [ ] Deploy to production

### 3. Post-Deployment
- [ ] Monitor audit logs
- [ ] Check error rates
- [ ] Verify no key leakage in logs
- [ ] Document access control configuration

---

## ROLLBACK PLAN

If critical issues found:

1. Revert to previous version
2. Keep audit logs for investigation
3. Run post-incident security review
4. Address issues before re-deployment

---

## Success Criteria

- [ ] No high-severity vulnerabilities
- [ ] All findings remediated or documented
- [ ] Security tests passing
- [ ] SAST tools report no issues
- [ ] Dependency audit clean
- [ ] Access control working
- [ ] Audit logging functional
- [ ] Error messages sanitized
