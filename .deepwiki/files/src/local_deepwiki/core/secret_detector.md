# File Overview

This file, `src/local_deepwiki/core/secret_detector.py`, provides functionality for detecting secrets in code repositories. It defines classes and methods to scan code content for various types of secrets, such as API keys, AWS credentials, and private keys, and provides recommendations for remediation.

The module imports standard Python libraries like `re` and `pathlib`, as well as `dataclasses`, `Enum`, and `Optional` from `typing`. It also uses [`get_logger`](../logging.md) from `local_deepwiki.logging` for logging.

# Classes

## SecretType

An enumeration of secret types that can be detected by the scanner. Each secret type has a string value representing its identifier.

### Values

- `AWS_KEY`: `"aws_access_key"`
- `AWS_SECRET`: `"aws_secret_key"`
- `PRIVATE_KEY`: `"private_key"`
- `API_KEY`: `"api_key"`
- `GENERIC_TOKEN`: `"generic_token"`
- `GITHUB_TOKEN`: `"github_token"`
- `GITLAB_TOKEN`: `"gitlab_token"`
- `SLACK_TOKEN`: `"slack_token"`
- `AZURE_KEY`: `"azure_key"`
- `GOOGLE_KEY`: `"google_key"`
- `DATABASE_URL`: `"database_url"`
- `DOCKER_AUTH`: `"docker_auth"`
- `SSH_KEY`: `"ssh_key"`
- `PGP_KEY`: `"pgp_key"`

## SecretFinding

Represents a detected secret in code.

### Attributes

- `secret_type`: `SecretType` - The type of secret detected.
- `file_path`: `str` - Path to the file where the secret was found.
- `line_number`: `int` - Line number where the secret was found.
- `context`: `str` - Code snippet around the secret (truncated for safety).
- `confidence`: `float` - Confidence score between 0.0 and 1.0.
- `recommendation`: `str` - Recommendation for remediation.

## SecretDetector

Main class for scanning code for secrets.

### Methods

#### scan_content

```python
def scan_content(
    self,
    content: str,
    file_path: str,
    start_line: int = 0,
) -> list[SecretFinding]
```

Scan code content for secrets.

- **Parameters**:
  - `content`: `str` - Code content to scan.
  - `file_path`: `str` - Path to file (for reporting).
  - `start_line`: `int` - Starting line number offset (for large files).
- **Returns**:
  - `list[SecretFinding]` - List of `SecretFinding` objects for detected secrets.

#### _is_false_positive

```python
def _is_false_positive(self, match: str, full_line: str) -> bool
```

Check if match is a known false positive.

- **Parameters**:
  - `match`: `str` - The matched secret pattern.
  - `full_line`: `str` - The full line containing the match.
- **Returns**:
  - `bool` - True if this appears to be a false positive.

#### _calculate_confidence

```python
def _calculate_confidence(self, secret_type: SecretType, match: str) -> float
```

Calculate confidence score for secret detection.

- **Parameters**:
  - `secret_type`: `SecretType` - The type of secret detected.
  - `match`: `str` - The matched text.
- **Returns**:
  - `float` - Confidence score between 0.0 and 1.0.

#### _get_recommendation

```python
def _get_recommendation(self, secret_type: SecretType) -> str
```

Get remediation recommendation for secret type.

- **Parameters**:
  - `secret_type`: `SecretType` - The type of secret detected.
- **Returns**:
  - `str` - Recommendation string for remediation.

#### _create_safe_context

```python
def _create_safe_context(self, line: str, match: re.Match) -> str
```

Create a safe context string that partially masks the secret.

- **Parameters**:
  - `line`: `str` - The full line containing the match.
  - `match`: `re.Match` - The regex match object.
- **Returns**:
  - `str` - Truncated context with secret partially masked.

# Functions

## _should_skip_file

```python
def _should_skip_file(file_path: Path) -> bool
```

Check if file should be skipped from secret scanning.

- **Parameters**:
  - `file_path`: `Path` - Path to the file.
- **Returns**:
  - `bool` - True if the file should be skipped.

## scan_repository_for_secrets

```python
def scan_repository_for_secrets(repo_path: Path) -> dict[str, list[SecretFinding]]
```

Scan entire repository for secrets.

- **Parameters**:
  - `repo_path`: `Path` - Path to the repository root.
- **Returns**:
  - `dict[str, list[SecretFinding]]` - Dictionary mapping file paths to lists of `SecretFinding` objects. Empty dict if no secrets found.

# Integration

This file is part of the `local_deepwiki` project and integrates with:

- `local_deepwiki.logging` for logging via [`get_logger`](../logging.md).
- The `SecretDetector` class is used to scan content for secrets.
- The `scan_repository_for_secrets` function is the [main](../export/pdf.md) entry point for scanning an entire repository.

It is closely related to:
- `src/local_deepwiki/core/__init__.py`
- `src/local_deepwiki/generators/source_refs.py`
- `src/local_deepwiki/plugins/base.py`
- `tests/test_plugins.py`

# Usage Examples

## Using `SecretDetector` to scan content

```python
detector = SecretDetector()
content = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
findings = detector.scan_content(content, "example.py")
```

## Scanning a repository

```python
from pathlib import Path
from local_deepwiki.core.secret_detector import scan_repository_for_secrets

repo_path = Path("/path/to/repo")
findings = scan_repository_for_secrets(repo_path)
```

## API Reference

### class `SecretType`

**Inherits from:** `str`, `Enum`

Types of secrets that can be detected.


<details>
<summary>View Source (lines 20-36) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L20-L36">GitHub</a></summary>

```python
class SecretType(str, Enum):
    """Types of secrets that can be detected."""

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
    SSH_KEY = "ssh_key"
    PGP_KEY = "pgp_key"
```

</details>

### class `SecretFinding`

Represents a detected secret in code.


<details>
<summary>View Source (lines 40-48) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L40-L48">GitHub</a></summary>

```python
class SecretFinding:
    """Represents a detected secret in code."""

    secret_type: SecretType
    file_path: str
    line_number: int
    context: str  # Code snippet around secret (truncated for safety)
    confidence: float  # 0.0-1.0
    recommendation: str
```

</details>

### class `SecretDetector`

Detects hardcoded secrets in code content.  Uses regex patterns to identify common secret formats including: - Cloud provider credentials (AWS, Azure, GCP) - Version control tokens (GitHub, GitLab) - Communication tokens (Slack) - Private keys (RSA, SSH, PGP) - Database connection strings - Generic API keys and tokens  False positive filtering is applied to reduce noise from test data, examples, and placeholder values.

**Methods:**


<details>
<summary>View Source (lines 51-379) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L51-L379">GitHub</a></summary>

```python
class SecretDetector:
    # Methods: scan_content, _is_false_positive, _calculate_confidence, _get_recommendation, _create_safe_context
```

</details>

#### `scan_content`

```python
def scan_content(content: str, file_path: str, start_line: int = 0) -> list[SecretFinding]
```

Scan code content for secrets.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | Code content to scan. |
| `file_path` | `str` | - | Path to file (for reporting). |
| `start_line` | `int` | `0` | Starting line number offset (for large files). |


---


<details>
<summary>View Source (lines 136-190) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L136-L190">GitHub</a></summary>

```python
def scan_content(
        self,
        content: str,
        file_path: str,
        start_line: int = 0,
    ) -> list[SecretFinding]:
        """Scan code content for secrets.

        Args:
            content: Code content to scan.
            file_path: Path to file (for reporting).
            start_line: Starting line number offset (for large files).

        Returns:
            List of SecretFinding objects for detected secrets.
        """
        findings: list[SecretFinding] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=start_line + 1):
            # Skip empty lines
            stripped = line.strip()
            if not stripped:
                continue

            # Skip single-line comments (basic heuristic)
            if stripped.startswith(("#", "//", "*", "/*")):
                continue

            # Check each pattern
            for secret_type, pattern in self.PATTERNS.items():
                matches = pattern.finditer(line)

                for match in matches:
                    matched_text = match.group()

                    # Check false positives
                    if self._is_false_positive(matched_text, line):
                        continue

                    # Create truncated context (hide actual secret)
                    context = self._create_safe_context(line, match)

                    findings.append(
                        SecretFinding(
                            secret_type=secret_type,
                            file_path=file_path,
                            line_number=line_num,
                            context=context,
                            confidence=self._calculate_confidence(secret_type, matched_text),
                            recommendation=self._get_recommendation(secret_type),
                        )
                    )

        return findings
```

</details>

### Functions

#### `scan_repository_for_secrets`

```python
def scan_repository_for_secrets(repo_path: Path) -> dict[str, list[SecretFinding]]
```

Scan entire repository for secrets.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `Path` | - | Path to the repository root. |

**Returns:** `dict[str, list[SecretFinding]]`




<details>
<summary>View Source (lines 515-568) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L515-L568">GitHub</a></summary>

```python
def scan_repository_for_secrets(repo_path: Path) -> dict[str, list[SecretFinding]]:
    """Scan entire repository for secrets.

    Args:
        repo_path: Path to the repository root.

    Returns:
        Dictionary mapping file paths to lists of SecretFinding objects.
        Empty dict if no secrets found.
    """
    detector = SecretDetector()
    findings_by_file: dict[str, list[SecretFinding]] = {}
    files_scanned = 0
    files_skipped = 0

    logger.debug(f"Starting secret scan of repository: {repo_path}")

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        # Skip binary files and common non-source files
        if _should_skip_file(file_path):
            files_skipped += 1
            continue

        try:
            # Read file content
            content = file_path.read_text(errors="ignore")
            files_scanned += 1

            # Get relative path for reporting
            try:
                rel_path = str(file_path.relative_to(repo_path))
            except ValueError:
                rel_path = str(file_path)

            # Scan content
            findings = detector.scan_content(content, rel_path)

            if findings:
                findings_by_file[str(file_path)] = findings

        except (OSError, PermissionError) as e:
            logger.debug(f"Could not read file for secret scanning: {file_path}: {e}")
            continue

    logger.debug(
        f"Secret scan complete: scanned {files_scanned} files, "
        f"skipped {files_skipped} files, "
        f"found secrets in {len(findings_by_file)} files"
    )

    return findings_by_file
```

</details>

## Class Diagram

```mermaid
classDiagram
    class SecretDetector {
        +scan_content(content: str, file_path: str, start_line: int) list[SecretFinding]
        -_is_false_positive(match: str, full_line: str) bool
        -_calculate_confidence(secret_type: SecretType, match: str) float
        -_get_recommendation(secret_type: SecretType) str
        -_create_safe_context(line: str, match: re.Match) str
    }
    class SecretFinding {
        +secret_type: SecretType
        +file_path: str
        +line_number: int
        +context: str  # Code snippet around secret (truncated for safety)
        +confidence: float  # 0.0-1.0
        +recommendation: str
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[SecretDetector]
    N1[SecretDetector._create_safe...]
    N2[SecretDetector._is_false_po...]
    N3[SecretDetector.scan_content]
    N4[SecretFinding]
    N5[_calculate_confidence]
    N6[_create_safe_context]
    N7[_get_recommendation]
    N8[_is_false_positive]
    N9[_should_skip_file]
    N10[end]
    N11[finditer]
    N12[group]
    N13[is_file]
    N14[read_text]
    N15[relative_to]
    N16[rglob]
    N17[scan_content]
    N18[scan_repository_for_secrets]
    N19[search]
    N20[start]
    N18 --> N0
    N18 --> N16
    N18 --> N13
    N18 --> N9
    N18 --> N14
    N18 --> N15
    N18 --> N17
    N3 --> N11
    N3 --> N12
    N3 --> N8
    N3 --> N6
    N3 --> N4
    N3 --> N5
    N3 --> N7
    N2 --> N19
    N1 --> N12
    N1 --> N20
    N1 --> N10
    classDef func fill:#e1f5fe
    class N0,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20 func
    classDef method fill:#fff3e0
    class N1,N2,N3 method
```

## Used By

Functions and methods in this file and their callers:

- **`SecretDetector`**: called by `scan_repository_for_secrets`
- **`SecretFinding`**: called by `SecretDetector.scan_content`
- **`_calculate_confidence`**: called by `SecretDetector.scan_content`
- **`_create_safe_context`**: called by `SecretDetector.scan_content`
- **`_get_recommendation`**: called by `SecretDetector.scan_content`
- **`_is_false_positive`**: called by `SecretDetector.scan_content`
- **`_should_skip_file`**: called by `scan_repository_for_secrets`
- **`end`**: called by `SecretDetector._create_safe_context`
- **`finditer`**: called by `SecretDetector.scan_content`
- **`group`**: called by `SecretDetector._create_safe_context`, `SecretDetector.scan_content`
- **`is_file`**: called by `scan_repository_for_secrets`
- **`read_text`**: called by `scan_repository_for_secrets`
- **`relative_to`**: called by `scan_repository_for_secrets`
- **`rglob`**: called by `scan_repository_for_secrets`
- **`scan_content`**: called by `scan_repository_for_secrets`
- **`search`**: called by `SecretDetector._is_false_positive`
- **`start`**: called by `SecretDetector._create_safe_context`

## Usage Examples

*Examples extracted from test files*

### Test AWS_KEY enum value exists

From `test_secret_detector.py::TestSecretTypeEnum::test_aws_key_exists`:

```python
assert SecretType.AWS_KEY.value == "aws_access_key"
```

### Test AWS_SECRET enum value exists

From `test_secret_detector.py::TestSecretTypeEnum::test_aws_secret_exists`:

```python
assert SecretType.AWS_SECRET.value == "aws_secret_key"
```

### Test creating a SecretFinding

From `test_secret_detector.py::TestSecretFindingDataclass::test_create_finding`:

```python
finding = SecretFinding(
    secret_type=SecretType.AWS_KEY,
    file_path="config.py",
    line_number=42,
    context="AWS_ACCESS_KEY_ID = AKIA****1234",
    confidence=0.95,
    recommendation="Rotate AWS access key immediately.",
)

assert finding.secret_type == SecretType.AWS_KEY
assert finding.file_path == "config.py"
```

### Test all fields are accessible

From `test_secret_detector.py::TestSecretFindingDataclass::test_finding_all_fields`:

```python
finding = SecretFinding(
    secret_type=SecretType.GITHUB_TOKEN,
    file_path="auth.py",
    line_number=10,
    context="token = ghp_****abcd",
    confidence=0.95,
    recommendation="Revoke token",
)

assert finding.secret_type is not None
assert finding.file_path is not None
```

### Test detecting AWS access key (AKIA...)

From `test_secret_detector.py::TestSecretDetectorScanContent::test_finds_aws_access_key`:

```python
detector = SecretDetector()
# Use a realistic-looking but clearly fake key (not containing "example", "test", etc.)
content = 'AWS_KEY = "AKIAWR5PROD9N7K2JLMN"'

findings = detector.scan_content(content, "config.py")

assert len(findings) == 1
assert findings[0].secret_type == SecretType.AWS_KEY
```


## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `SecretType` | class | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |
| `SecretFinding` | class | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |
| `SecretDetector` | class | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |
| `scan_content` | method | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |
| `_is_false_positive` | method | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |
| `_calculate_confidence` | method | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |
| `_get_recommendation` | method | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |
| `_create_safe_context` | method | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |
| `_should_skip_file` | function | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |
| `scan_repository_for_secrets` | function | Brian Breidenbach | 1 week ago | `9844731` Phase 3: Implement input va... |

## Additional Source Code

Source code for functions and methods not listed in the API Reference above.

#### `_is_false_positive`

<details>
<summary>View Source (lines 192-212) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L192-L212">GitHub</a></summary>

```python
def _is_false_positive(self, match: str, full_line: str) -> bool:
        """Check if match is a known false positive.

        Args:
            match: The matched secret pattern.
            full_line: The full line containing the match.

        Returns:
            True if this appears to be a false positive.
        """
        # Check the match itself
        for pattern in self.FALSE_POSITIVES:
            if pattern.search(match):
                return True

        # Also check surrounding context in the line
        for pattern in self.FALSE_POSITIVES:
            if pattern.search(full_line):
                return True

        return False
```

</details>


#### `_calculate_confidence`

<details>
<summary>View Source (lines 214-268) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L214-L268">GitHub</a></summary>

```python
def _calculate_confidence(self, secret_type: SecretType, match: str) -> float:
        """Calculate confidence score for secret detection.

        Args:
            secret_type: The type of secret detected.
            match: The matched text.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        # AWS keys have very specific format - high confidence
        if secret_type == SecretType.AWS_KEY:
            return 0.95

        # GitHub tokens have specific prefix - high confidence
        if secret_type == SecretType.GITHUB_TOKEN:
            return 0.95

        # GitLab tokens have specific prefix - high confidence
        if secret_type == SecretType.GITLAB_TOKEN:
            return 0.92

        # Slack tokens have specific prefix - high confidence
        if secret_type == SecretType.SLACK_TOKEN:
            return 0.92

        # Private keys are very distinctive - very high confidence
        if secret_type in (SecretType.PRIVATE_KEY, SecretType.SSH_KEY, SecretType.PGP_KEY):
            return 0.98

        # Database URLs with credentials - high confidence
        if secret_type == SecretType.DATABASE_URL:
            return 0.90

        # Google API keys have specific format
        if secret_type == SecretType.GOOGLE_KEY:
            return 0.90

        # AWS secret requires context - moderate-high confidence
        if secret_type == SecretType.AWS_SECRET:
            return 0.85

        # Azure keys depend on context
        if secret_type == SecretType.AZURE_KEY:
            return 0.80

        # Docker auth
        if secret_type == SecretType.DOCKER_AUTH:
            return 0.75

        # Generic patterns are lower confidence due to false positive potential
        if secret_type in (SecretType.API_KEY, SecretType.GENERIC_TOKEN):
            return 0.70

        return 0.75
```

</details>


#### `_get_recommendation`

<details>
<summary>View Source (lines 270-340) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L270-L340">GitHub</a></summary>

```python
def _get_recommendation(self, secret_type: SecretType) -> str:
        """Get remediation recommendation for secret type.

        Args:
            secret_type: The type of secret detected.

        Returns:
            Recommendation string for remediation.
        """
        recommendations = {
            SecretType.AWS_KEY: (
                "Rotate AWS access key immediately via IAM console. "
                "Check CloudTrail for unauthorized access. Use IAM roles or environment variables instead."
            ),
            SecretType.AWS_SECRET: (
                "Rotate AWS secret access key immediately. "
                "Use AWS Secrets Manager or environment variables."
            ),
            SecretType.PRIVATE_KEY: (
                "Rotate private key immediately and revoke associated certificate. "
                "Never commit private keys to version control."
            ),
            SecretType.SSH_KEY: (
                "Generate new SSH key pair and update authorized_keys. "
                "Remove compromised key from all servers."
            ),
            SecretType.PGP_KEY: (
                "Revoke PGP key and generate new key pair. "
                "Update key servers with revocation certificate."
            ),
            SecretType.GITHUB_TOKEN: (
                "Revoke GitHub token immediately in Settings > Developer settings > Personal access tokens. "
                "Generate new token with minimal required scopes."
            ),
            SecretType.GITLAB_TOKEN: (
                "Revoke GitLab token in User Settings > Access Tokens. "
                "Create new token with appropriate expiration."
            ),
            SecretType.SLACK_TOKEN: (
                "Revoke Slack token in your Slack app settings. "
                "Regenerate token and update configuration."
            ),
            SecretType.DATABASE_URL: (
                "Change database password immediately. "
                "Update connection strings in all environments. Use secrets management."
            ),
            SecretType.AZURE_KEY: (
                "Rotate Azure key in Azure Portal. "
                "Use Azure Key Vault for secret management."
            ),
            SecretType.GOOGLE_KEY: (
                "Regenerate Google API key in Google Cloud Console. "
                "Apply API key restrictions for security."
            ),
            SecretType.DOCKER_AUTH: (
                "Rotate Docker credentials. "
                "Use Docker credential helpers or secrets management."
            ),
            SecretType.API_KEY: (
                "Rotate API key with the service provider. "
                "Use environment variables or secrets manager instead of hardcoding."
            ),
            SecretType.GENERIC_TOKEN: (
                "Review and rotate this credential if it's a real secret. "
                "Move to environment variables or secrets manager."
            ),
        }
        return recommendations.get(
            secret_type,
            f"Review and rotate {secret_type.value} if genuine. Use environment variables or secrets manager.",
        )
```

</details>


#### `_create_safe_context`

<details>
<summary>View Source (lines 342-379) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L342-L379">GitHub</a></summary>

```python
def _create_safe_context(self, line: str, match: re.Match) -> str:
        """Create a safe context string that partially masks the secret.

        Args:
            line: The full line containing the match.
            match: The regex match object.

        Returns:
            Truncated context with secret partially masked.
        """
        # Get the matched text
        matched_text = match.group()

        # For private keys, just show the header
        if "PRIVATE KEY" in matched_text:
            return matched_text[:50] + "..."

        # For other secrets, show first few and last few characters
        if len(matched_text) > 10:
            visible_start = min(6, len(matched_text) // 4)
            visible_end = min(4, len(matched_text) // 4)
            masked = matched_text[:visible_start] + "****" + matched_text[-visible_end:]
        else:
            masked = matched_text[:2] + "****"

        # Replace the secret in the line context
        line_start = max(0, match.start() - 20)
        line_end = min(len(line), match.end() + 20)
        context = line[line_start:line_end].strip()

        # Replace actual secret with masked version in context
        context = context.replace(matched_text, masked)

        # Truncate if too long
        if len(context) > 100:
            context = context[:100] + "..."

        return context
```

</details>


#### `_should_skip_file`

<details>
<summary>View Source (lines 382-512) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/core/secret_detector.py#L382-L512">GitHub</a></summary>

```python
def _should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped from secret scanning.

    Args:
        file_path: Path to the file.

    Returns:
        True if the file should be skipped.
    """
    # Binary and compiled file extensions to skip
    skip_extensions = {
        # Images
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".svg",
        ".webp",
        # Compiled/binary
        ".pyc",
        ".pyo",
        ".so",
        ".o",
        ".a",
        ".lib",
        ".dll",
        ".exe",
        ".bin",
        ".class",
        ".jar",
        # Archives
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        # Documents (often binary)
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        # Media
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".wav",
        ".flac",
        # Fonts
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
        # Other binary
        ".db",
        ".sqlite",
        ".sqlite3",
        ".pkl",
        ".pickle",
        ".npy",
        ".npz",
        # Lock files (often auto-generated)
        ".lock",
    }

    # Directory names to skip
    skip_dirs = {
        ".git",
        ".svn",
        ".hg",
        ".venv",
        "venv",
        ".env",
        "env",
        "__pycache__",
        "node_modules",
        ".deepwiki",
        "dist",
        "build",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "coverage",
        ".coverage",
        "htmlcov",
        ".eggs",
        "*.egg-info",
        ".nox",
        ".cache",
        "vendor",
        "third_party",
        "external",
    }

    # File names to skip
    skip_names = {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "Cargo.lock",
        "Gemfile.lock",
        "composer.lock",
    }

    # Check extension
    if file_path.suffix.lower() in skip_extensions:
        return True

    # Check file name
    if file_path.name in skip_names:
        return True

    # Check if any parent directory should be skipped
    for part in file_path.parts:
        if part in skip_dirs:
            return True
        # Handle wildcard patterns like *.egg-info
        if part.endswith(".egg-info"):
            return True

    return False
```

</details>

## Relevant Source Files

- `src/local_deepwiki/core/secret_detector.py:20-36`
