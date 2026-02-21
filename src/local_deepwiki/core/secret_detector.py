"""Secret detection for hardcoded credentials in code.

Detects common secret patterns like API keys, tokens, and credentials
to warn users about potential security issues during repository indexing.

Addresses CWE-798: Use of Hard-Coded Credentials
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Minimum length for a secret match to be partially masked
MIN_SECRET_MASK_LENGTH = 10

# Maximum length for the safe context snippet around a secret
MAX_SECRET_CONTEXT_LENGTH = 100


class SecretType(StrEnum):
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


_CONFIDENCE_SCORES: dict[SecretType, float] = {
    SecretType.PRIVATE_KEY: 0.98,
    SecretType.SSH_KEY: 0.98,
    SecretType.PGP_KEY: 0.98,
    SecretType.AWS_KEY: 0.95,
    SecretType.GITHUB_TOKEN: 0.95,
    SecretType.GITLAB_TOKEN: 0.92,
    SecretType.SLACK_TOKEN: 0.92,
    SecretType.DATABASE_URL: 0.90,
    SecretType.GOOGLE_KEY: 0.90,
    SecretType.AWS_SECRET: 0.85,
    SecretType.AZURE_KEY: 0.80,
    SecretType.DOCKER_AUTH: 0.75,
    SecretType.API_KEY: 0.70,
    SecretType.GENERIC_TOKEN: 0.70,
}


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """Represents a detected secret in code."""

    secret_type: SecretType
    file_path: str
    line_number: int
    context: str  # Code snippet around secret (truncated for safety)
    confidence: float  # 0.0-1.0
    recommendation: str


class SecretDetector:
    """Detects hardcoded secrets in code content.

    Uses regex patterns to identify common secret formats including:
    - Cloud provider credentials (AWS, Azure, GCP)
    - Version control tokens (GitHub, GitLab)
    - Communication tokens (Slack)
    - Private keys (RSA, SSH, PGP)
    - Database connection strings
    - Generic API keys and tokens

    False positive filtering is applied to reduce noise from test
    data, examples, and placeholder values.
    """

    # Secret patterns (high-confidence patterns)
    PATTERNS: dict[SecretType, re.Pattern] = {
        # AWS Access Key ID - always starts with AKIA
        SecretType.AWS_KEY: re.compile(r"AKIA[0-9A-Z]{16}"),
        # AWS Secret Access Key - 40 character base64
        SecretType.AWS_SECRET: re.compile(
            r"(?i)aws_secret_access_key\s*[:=]\s*[\"']?[a-zA-Z0-9/+]{40}[\"']?"
        ),
        # GitHub Personal Access Token (classic and fine-grained)
        SecretType.GITHUB_TOKEN: re.compile(r"ghp_[a-zA-Z0-9]{36}"),
        # GitLab Personal Access Token
        SecretType.GITLAB_TOKEN: re.compile(r"glpat-[a-zA-Z0-9\-_]{20,}"),
        # Slack tokens (bot, app, user, etc.)
        SecretType.SLACK_TOKEN: re.compile(r"xox[baprs]-[a-zA-Z0-9]{10,48}"),
        # Private key headers (RSA, EC, DSA, OPENSSH)
        SecretType.PRIVATE_KEY: re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
        ),
        # SSH private keys
        SecretType.SSH_KEY: re.compile(
            r"-----BEGIN (?:OPENSSH |RSA )?PRIVATE KEY-----"
        ),
        # PGP private keys
        SecretType.PGP_KEY: re.compile(r"-----BEGIN PGP PRIVATE KEY BLOCK-----"),
        # Generic API key patterns
        # Negative lookbehind rejects compound names (e.g. old_api_key_manager)
        # Value must not start with a function call (parenthesis)
        SecretType.API_KEY: re.compile(
            r"(?i)(?<![a-zA-Z_])api[_-]?key\s*[:=]\s*[\"']?(?![a-zA-Z0-9_]*\()[a-zA-Z0-9_\-]{20,}[\"']?"
        ),
        # Database connection URLs with credentials
        SecretType.DATABASE_URL: re.compile(
            r"(?i)(?:postgres|mysql|mongodb|redis|amqp)://[a-zA-Z0-9_\-]+:[^@\s]+@"
        ),
        # Azure storage/API keys
        SecretType.AZURE_KEY: re.compile(
            r"(?i)(?:azure|storage)[_-]?(?:key|account)[_-]?(?:key)?\s*[:=]\s*[\"']?[a-zA-Z0-9/+=]{20,}[\"']?"
        ),
        # Google API keys
        SecretType.GOOGLE_KEY: re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        # Docker auth tokens
        SecretType.DOCKER_AUTH: re.compile(
            r"(?i)docker[_-]?(?:auth|password|token)\s*[:=]\s*[\"']?[a-zA-Z0-9_\-]{20,}[\"']?"
        ),
        # Generic tokens and secrets
        # Negative lookbehind rejects compound names (e.g. progress_token, token_config)
        # Value must not start with a function call (parenthesis)
        SecretType.GENERIC_TOKEN: re.compile(
            r"(?i)(?<![a-zA-Z_])(?:secret|token|password|passwd|pwd)\s*[:=]\s*[\"']?(?![a-zA-Z0-9_]*\()[a-zA-Z0-9_\-!@#$%^&*]{12,}[\"']?"
        ),
    }

    # False positive patterns to exclude
    FALSE_POSITIVES: list[re.Pattern] = [
        # Test/example/placeholder values
        re.compile(r"(?i)example|test|demo|mock|fake|placeholder|dummy|sample"),
        # Common placeholder patterns
        re.compile(r"(?i)your[-_]?(?:key|token|secret|password)"),
        # Test key prefixes (like Stripe test keys)
        re.compile(r"(?i)sk[-_]?test[-_]?[a-z]+"),
        re.compile(r"(?i)pk[-_]?test[-_]?[a-z]+"),
        # Documentation placeholders
        re.compile(r"(?i)xxx+|yyy+|zzz+"),
        re.compile(r"<[^>]+>"),  # <YOUR_API_KEY>
        re.compile(r"\{[^}]+\}"),  # {your_api_key}
        # Common dummy values
        re.compile(r"(?i)changeme|replace[-_]?me|insert[-_]?here|customkey"),
        # Environment variable references
        re.compile(r"\$\{?[A-Z_]+\}?"),  # $API_KEY or ${API_KEY}
        re.compile(r"(?i)process\.env\.[A-Z_]+"),  # process.env.API_KEY
        re.compile(r"(?i)os\.environ"),  # os.environ
        re.compile(r"(?i)getenv\("),  # getenv()
        # Compound variable names where keyword is a suffix (progress_token, auth_secret)
        re.compile(r"(?i)[a-zA-Z_]+_(?:token|secret|password|passwd|pwd|api_key)\b"),
        # Compound variable names where keyword is a prefix (token_config, secret_manager)
        re.compile(r"(?i)\b(?:token|secret|password|passwd|pwd)_[a-zA-Z_]+\b"),
        # Type annotations (: str, : int, : Optional[, : str | None, etc.)
        re.compile(
            r":\s*(?:str|int|float|bool|bytes|None|Optional\[|Union\[|list\[|dict\[|str\s*\|)"
        ),
        # Function/method calls as values (credentials(...), get_token(...), etc.)
        re.compile(r"[:=]\s*[a-zA-Z_][a-zA-Z0-9_.]*\("),
    ]

    # Low-confidence secret types that should be suppressed in test files
    _LOW_CONFIDENCE_TYPES: frozenset[SecretType] = frozenset(
        {SecretType.API_KEY, SecretType.GENERIC_TOKEN}
    )

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
        is_test_file = self._is_test_file(file_path)

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
                # Skip low-confidence patterns in test files — test files
                # routinely use dummy keys that look real but aren't.
                if is_test_file and secret_type in self._LOW_CONFIDENCE_TYPES:
                    continue

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
                            confidence=self._calculate_confidence(
                                secret_type, matched_text
                            ),
                            recommendation=self._get_recommendation(secret_type),
                        )
                    )

        return findings

    @staticmethod
    def _is_test_file(file_path: str) -> bool:
        """Check if the file path indicates a test file.

        Args:
            file_path: Relative or absolute file path.

        Returns:
            True if the file appears to be a test file.
        """
        parts = file_path.replace("\\", "/").split("/")
        filename = parts[-1] if parts else file_path
        return (
            "tests/" in file_path
            or "test/" in file_path
            or filename.startswith("test_")
            or filename.endswith("_test.py")
        )

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

    @staticmethod
    def _calculate_confidence(secret_type: SecretType, match: str) -> float:
        """Calculate confidence score for secret detection.

        Args:
            secret_type: The type of secret detected.
            match: The matched text.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        return _CONFIDENCE_SCORES.get(secret_type, 0.75)

    @staticmethod
    def _get_recommendation(secret_type: SecretType) -> str:
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

    @staticmethod
    def _create_safe_context(line: str, match: re.Match) -> str:
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
        if len(matched_text) > MIN_SECRET_MASK_LENGTH:
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
        if len(context) > MAX_SECRET_CONTEXT_LENGTH:
            context = context[:MAX_SECRET_CONTEXT_LENGTH] + "..."

        return context


def _should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped from secret scanning.

    Args:
        file_path: Path to the file.

    Returns:
        True if the file should be skipped.
    """
    # Skip the secret detector itself (self-detection false positives)
    if file_path.name == "secret_detector.py":
        return True

    # Skip documentation files (contain example key formats, not real secrets)
    if file_path.suffix.lower() in {".md", ".rst"}:
        return True

    # Skip test files for secret detector (contain test patterns)
    if file_path.name == "test_secret_detector.py":
        return True

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

    logger.debug("Starting secret scan of repository: %s", repo_path)

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
            logger.debug(
                "Could not read file for secret scanning: %s: %s", file_path, e
            )
            continue

    logger.debug(
        "Secret scan complete: scanned %d files, skipped %d files, found secrets in %d files",
        files_scanned,
        files_skipped,
        len(findings_by_file),
    )

    return findings_by_file
