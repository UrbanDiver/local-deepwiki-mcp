"""Tests for secret detection system (Phase 3).

Tests CWE-798 prevention: detection of hardcoded credentials in code.
"""

from pathlib import Path

import pytest

from local_deepwiki.core.secret_detector import (
    SecretDetector,
    SecretFinding,
    SecretType,
    _should_skip_file,
    scan_repository_for_secrets,
)


class TestSecretTypeEnum:
    """Tests for SecretType enum values."""

    def test_aws_key_exists(self):
        """Test AWS_KEY enum value exists."""
        assert SecretType.AWS_KEY.value == "aws_access_key"

    def test_aws_secret_exists(self):
        """Test AWS_SECRET enum value exists."""
        assert SecretType.AWS_SECRET.value == "aws_secret_key"

    def test_private_key_exists(self):
        """Test PRIVATE_KEY enum value exists."""
        assert SecretType.PRIVATE_KEY.value == "private_key"

    def test_api_key_exists(self):
        """Test API_KEY enum value exists."""
        assert SecretType.API_KEY.value == "api_key"

    def test_generic_token_exists(self):
        """Test GENERIC_TOKEN enum value exists."""
        assert SecretType.GENERIC_TOKEN.value == "generic_token"

    def test_github_token_exists(self):
        """Test GITHUB_TOKEN enum value exists."""
        assert SecretType.GITHUB_TOKEN.value == "github_token"

    def test_gitlab_token_exists(self):
        """Test GITLAB_TOKEN enum value exists."""
        assert SecretType.GITLAB_TOKEN.value == "gitlab_token"

    def test_slack_token_exists(self):
        """Test SLACK_TOKEN enum value exists."""
        assert SecretType.SLACK_TOKEN.value == "slack_token"

    def test_azure_key_exists(self):
        """Test AZURE_KEY enum value exists."""
        assert SecretType.AZURE_KEY.value == "azure_key"

    def test_google_key_exists(self):
        """Test GOOGLE_KEY enum value exists."""
        assert SecretType.GOOGLE_KEY.value == "google_key"

    def test_database_url_exists(self):
        """Test DATABASE_URL enum value exists."""
        assert SecretType.DATABASE_URL.value == "database_url"

    def test_docker_auth_exists(self):
        """Test DOCKER_AUTH enum value exists."""
        assert SecretType.DOCKER_AUTH.value == "docker_auth"

    def test_ssh_key_exists(self):
        """Test SSH_KEY enum value exists."""
        assert SecretType.SSH_KEY.value == "ssh_key"

    def test_pgp_key_exists(self):
        """Test PGP_KEY enum value exists."""
        assert SecretType.PGP_KEY.value == "pgp_key"

    def test_all_types_are_strings(self):
        """Test all secret type values are strings."""
        for secret_type in SecretType:
            assert isinstance(secret_type.value, str)


class TestSecretFindingDataclass:
    """Tests for SecretFinding dataclass creation."""

    def test_create_finding(self):
        """Test creating a SecretFinding."""
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
        assert finding.line_number == 42
        assert finding.confidence == 0.95

    def test_finding_all_fields(self):
        """Test all fields are accessible."""
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
        assert finding.line_number is not None
        assert finding.context is not None
        assert finding.confidence is not None
        assert finding.recommendation is not None


class TestSecretDetectorScanContent:
    """Tests for SecretDetector.scan_content method."""

    def test_finds_aws_access_key(self):
        """Test detecting AWS access key (AKIA...)."""
        detector = SecretDetector()
        # Use a realistic-looking but clearly fake key (not containing "example", "test", etc.)
        content = 'AWS_KEY = "AKIAWR5PROD9N7K2JLMN"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 1
        assert findings[0].secret_type == SecretType.AWS_KEY
        assert findings[0].line_number == 1

    def test_finds_github_token(self):
        """Test detecting GitHub personal access token (ghp_...)."""
        detector = SecretDetector()
        # Token must have exactly 36 characters after ghp_ prefix
        # Use a variable name that doesn't trigger GENERIC_TOKEN pattern
        content = 'gh_pat = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890"'

        findings = detector.scan_content(content, "auth.py")

        assert len(findings) >= 1
        # Check that GitHub token was found
        github_findings = [
            f for f in findings if f.secret_type == SecretType.GITHUB_TOKEN
        ]
        assert len(github_findings) == 1

    def test_finds_private_key(self):
        """Test detecting private key header (-----BEGIN...)."""
        detector = SecretDetector()
        content = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA1234...
-----END RSA PRIVATE KEY-----"""

        findings = detector.scan_content(content, "key.pem")

        # May find both PRIVATE_KEY and SSH_KEY due to overlapping patterns
        assert len(findings) >= 1
        secret_types = [f.secret_type for f in findings]
        assert (
            SecretType.PRIVATE_KEY in secret_types or SecretType.SSH_KEY in secret_types
        )

    def test_finds_database_url(self):
        """Test detecting database URLs with credentials."""
        detector = SecretDetector()
        content = 'DATABASE_URL = "postgres://admin:S3cr3tP4ss@localhost:5432/proddb"'

        findings = detector.scan_content(content, "settings.py")

        assert len(findings) >= 1
        secret_types = [f.secret_type for f in findings]
        assert SecretType.DATABASE_URL in secret_types

    def test_finds_api_key(self):
        """Test detecting generic API keys."""
        detector = SecretDetector()
        # Use pattern that won't trigger GitHub push protection
        content = 'api_key = "abcdefghij1234567890klmnopqrst"'

        findings = detector.scan_content(content, "config.py")

        # Should find API_KEY or GENERIC_TOKEN
        assert len(findings) >= 1

    def test_finds_gitlab_token(self):
        """Test detecting GitLab token."""
        detector = SecretDetector()
        content = 'GITLAB_KEY = "glpat-R7k2JlmnProdWr5N91234"'

        findings = detector.scan_content(content, "ci.yml")

        assert len(findings) >= 1
        secret_types = [f.secret_type for f in findings]
        assert SecretType.GITLAB_TOKEN in secret_types

    def test_finds_slack_token(self):
        """Test detecting Slack tokens."""
        detector = SecretDetector()
        content = 'SLACK_BOT = "xoxb-123456789012-R7k2JlmnProd"'

        findings = detector.scan_content(content, "bot.py")

        assert len(findings) >= 1
        secret_types = [f.secret_type for f in findings]
        assert SecretType.SLACK_TOKEN in secret_types

    def test_finds_google_api_key(self):
        """Test detecting Google API keys."""
        detector = SecretDetector()
        content = 'GOOGLE_KEY = "AIzaSyR7k2JlmnProdWr5N9AbcdEfgHiJkL12345"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) >= 1
        secret_types = [f.secret_type for f in findings]
        assert SecretType.GOOGLE_KEY in secret_types


class TestFalsePositiveFiltering:
    """Tests for false positive filtering."""

    def test_skips_test_values(self):
        """Test that test_ prefixed values are skipped."""
        detector = SecretDetector()
        content = 'test_api_key = "test_abcdefghijklmnop123456"'

        findings = detector.scan_content(content, "test_config.py")

        # Should be filtered as false positive
        assert len(findings) == 0

    def test_skips_example_values(self):
        """Test that example values are skipped."""
        detector = SecretDetector()
        content = 'api_key = "example_key_abcdefghij123456"'

        findings = detector.scan_content(content, "example.py")

        assert len(findings) == 0

    def test_skips_mock_values(self):
        """Test that mock values are skipped."""
        detector = SecretDetector()
        content = 'mock_token = "mock_abcdefghijklmnop123456"'

        findings = detector.scan_content(content, "mock.py")

        assert len(findings) == 0

    def test_skips_placeholder_values(self):
        """Test that placeholder values are skipped."""
        detector = SecretDetector()
        content = 'api_key = "placeholder_key_123456789012"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 0

    def test_skips_environment_variable_reference(self):
        """Test that env var references are skipped."""
        detector = SecretDetector()
        content = 'api_key = os.environ["API_KEY"]'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 0

    def test_skips_your_key_placeholder(self):
        """Test that 'your_key' placeholders are skipped."""
        detector = SecretDetector()
        content = 'api_key = "your_api_key_here"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 0

    def test_skips_comment_lines(self):
        """Test that comment lines are skipped."""
        detector = SecretDetector()
        content = "# AKIAIOSFODNN7EXAMPLE  <- this is an example"

        findings = detector.scan_content(content, "readme.py")

        assert len(findings) == 0

    def test_skips_env_variable_syntax(self):
        """Test that ${ENV_VAR} syntax is skipped."""
        detector = SecretDetector()
        content = 'api_key = "${API_KEY}"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 0


class TestConfidenceScoring:
    """Tests for confidence score calculation."""

    def test_aws_key_high_confidence(self):
        """Test AWS keys have high confidence (0.95)."""
        detector = SecretDetector()
        content = 'key = "AKIAWR5PROD9N7K2JLMN"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 1
        assert findings[0].confidence == 0.95

    def test_github_token_high_confidence(self):
        """Test GitHub tokens have high confidence (0.95)."""
        detector = SecretDetector()
        # Token must have exactly 36 characters after ghp_ prefix
        # Use a variable name that doesn't trigger GENERIC_TOKEN pattern
        content = 'gh_pat = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890"'

        findings = detector.scan_content(content, "auth.py")

        assert len(findings) >= 1
        github_findings = [
            f for f in findings if f.secret_type == SecretType.GITHUB_TOKEN
        ]
        assert len(github_findings) == 1
        assert github_findings[0].confidence == 0.95

    def test_private_key_very_high_confidence(self):
        """Test private keys have very high confidence (0.98)."""
        detector = SecretDetector()
        content = "-----BEGIN RSA PRIVATE KEY-----"

        findings = detector.scan_content(content, "key.pem")

        assert len(findings) >= 1
        # Private keys should have 0.98 confidence
        for f in findings:
            if f.secret_type in (SecretType.PRIVATE_KEY, SecretType.SSH_KEY):
                assert f.confidence == 0.98

    def test_database_url_high_confidence(self):
        """Test database URLs have high confidence (0.90)."""
        detector = SecretDetector()
        content = 'url = "postgres://admin:S3cr3tP4ss@prodhost:5432/maindb"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) >= 1
        db_findings = [f for f in findings if f.secret_type == SecretType.DATABASE_URL]
        assert len(db_findings) == 1
        assert db_findings[0].confidence == 0.90


class TestRecommendations:
    """Tests for remediation recommendations."""

    def test_aws_key_recommendation(self):
        """Test AWS key has appropriate recommendation."""
        detector = SecretDetector()
        content = 'key = "AKIAWR5PROD9N7K2JLMN"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 1
        assert (
            "IAM" in findings[0].recommendation or "AWS" in findings[0].recommendation
        )

    def test_github_token_recommendation(self):
        """Test GitHub token has appropriate recommendation."""
        detector = SecretDetector()
        # Token must have exactly 36 characters after ghp_ prefix
        # Use a variable name that doesn't trigger GENERIC_TOKEN pattern
        content = 'gh_pat = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890"'

        findings = detector.scan_content(content, "auth.py")

        assert len(findings) >= 1
        github_findings = [
            f for f in findings if f.secret_type == SecretType.GITHUB_TOKEN
        ]
        assert len(github_findings) == 1
        assert (
            "GitHub" in github_findings[0].recommendation
            or "token" in github_findings[0].recommendation
        )

    def test_private_key_recommendation(self):
        """Test private key has appropriate recommendation."""
        detector = SecretDetector()
        content = "-----BEGIN RSA PRIVATE KEY-----"

        findings = detector.scan_content(content, "key.pem")

        assert len(findings) >= 1
        for f in findings:
            if f.secret_type == SecretType.PRIVATE_KEY:
                assert (
                    "private key" in f.recommendation.lower()
                    or "rotate" in f.recommendation.lower()
                )

    def test_all_secret_types_have_recommendations(self):
        """Test all secret types have non-empty recommendations."""
        detector = SecretDetector()

        for secret_type in SecretType:
            rec = detector._get_recommendation(secret_type)
            assert rec is not None
            assert len(rec) > 0


class TestShouldSkipFile:
    """Tests for _should_skip_file function."""

    def test_skips_git_directory(self, tmp_path):
        """Test .git directory is skipped."""
        git_file = tmp_path / ".git" / "config"
        assert _should_skip_file(git_file)

    def test_skips_node_modules(self, tmp_path):
        """Test node_modules directory is skipped."""
        node_file = tmp_path / "node_modules" / "package" / "index.js"
        assert _should_skip_file(node_file)

    def test_skips_binary_extensions(self, tmp_path):
        """Test binary file extensions are skipped."""
        assert _should_skip_file(Path("image.png"))
        assert _should_skip_file(Path("image.jpg"))
        assert _should_skip_file(Path("archive.zip"))
        assert _should_skip_file(Path("binary.exe"))
        assert _should_skip_file(Path("compiled.pyc"))

    def test_skips_pycache(self, tmp_path):
        """Test __pycache__ directory is skipped."""
        cache_file = tmp_path / "__pycache__" / "module.cpython-311.pyc"
        assert _should_skip_file(cache_file)

    def test_skips_venv(self, tmp_path):
        """Test venv/virtual environment directories are skipped."""
        venv_file = tmp_path / "venv" / "lib" / "python3.11" / "site.py"
        assert _should_skip_file(venv_file)

    def test_skips_lock_files(self, tmp_path):
        """Test lock files are skipped."""
        assert _should_skip_file(Path("package-lock.json"))
        assert _should_skip_file(Path("yarn.lock"))
        assert _should_skip_file(Path("poetry.lock"))

    def test_allows_source_files(self, tmp_path):
        """Test source files are not skipped."""
        assert not _should_skip_file(Path("main.py"))
        assert not _should_skip_file(Path("src/app.js"))
        assert not _should_skip_file(Path("config.yaml"))

    def test_skips_secret_detector_self(self):
        """Test secret_detector.py is skipped (self-detection false positives)."""
        assert _should_skip_file(Path("src/core/secret_detector.py"))
        assert _should_skip_file(Path("secret_detector.py"))

    def test_skips_documentation_files(self):
        """Test markdown and rst files are skipped."""
        assert _should_skip_file(Path("README.md"))
        assert _should_skip_file(Path("docs/guide.md"))
        assert _should_skip_file(Path("CHANGELOG.rst"))
        # .txt files should NOT be skipped (may contain real config secrets)
        assert not _should_skip_file(Path("config.txt"))

    def test_skips_secret_detector_test(self):
        """Test test_secret_detector.py is skipped (contains test patterns)."""
        assert _should_skip_file(Path("tests/test_secret_detector.py"))

    def test_skips_build_directory(self, tmp_path):
        """Test build directories are skipped."""
        build_file = tmp_path / "build" / "output.js"
        assert _should_skip_file(build_file)

    def test_skips_dist_directory(self, tmp_path):
        """Test dist directories are skipped."""
        dist_file = tmp_path / "dist" / "bundle.js"
        assert _should_skip_file(dist_file)


class TestScanRepositoryForSecrets:
    """Tests for scan_repository_for_secrets function."""

    def test_scans_directory_recursively(self, tmp_path):
        """Test scanning scans all files recursively."""
        # Create nested structure with secrets (avoiding false positive keywords)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "config.py").write_text('AWS_KEY = "AKIAWR5PROD9N7K2JLMN"')
        (tmp_path / "src" / "nested").mkdir()
        # Use a second AWS key to avoid triggering multiple pattern types
        (tmp_path / "src" / "nested" / "auth.py").write_text(
            'AWS_KEY2 = "AKIA1234567890ABCDEF"'
        )

        findings = scan_repository_for_secrets(tmp_path)

        # Should find secrets in both files
        assert len(findings) == 2

    def test_no_findings_for_clean_code(self, tmp_path):
        """Test no findings for code without secrets."""
        (tmp_path / "clean.py").write_text("""
def hello():
    print("Hello, world!")

class Calculator:
    def add(self, a, b):
        return a + b
""")

        findings = scan_repository_for_secrets(tmp_path)

        assert len(findings) == 0

    def test_multiple_findings_in_same_file(self, tmp_path):
        """Test multiple secrets in same file are all found."""
        # Use two AWS keys to avoid multiple pattern types matching
        (tmp_path / "secrets.py").write_text("""
AWS_KEY1 = "AKIAWR5PROD9N7K2JLMN"
AWS_KEY2 = "AKIA1234567890ABCDEF"
""")

        findings = scan_repository_for_secrets(tmp_path)

        assert len(findings) == 1  # One file
        # Check the file has multiple findings
        all_findings = list(findings.values())[0]
        assert len(all_findings) == 2

    def test_line_numbers_are_correct(self, tmp_path):
        """Test line numbers are accurately reported."""
        (tmp_path / "conf.py").write_text("""# Line 1
# Line 2
AWS_KEY = "AKIAWR5PROD9N7K2JLMN"
# Line 4
""")

        findings = scan_repository_for_secrets(tmp_path)

        assert len(findings) == 1
        file_findings = list(findings.values())[0]
        assert file_findings[0].line_number == 3

    def test_skips_binary_files(self, tmp_path):
        """Test binary files are skipped."""
        # Create a binary-looking file
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\nAKIAWR5PROD9N7K2JLMN")

        findings = scan_repository_for_secrets(tmp_path)

        assert len(findings) == 0

    def test_skips_git_directory(self, tmp_path):
        """Test .git directory is skipped."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text('AWS_KEY = "AKIAWR5PROD9N7K2JLMN"')

        findings = scan_repository_for_secrets(tmp_path)

        assert len(findings) == 0

    def test_returns_empty_dict_for_empty_repo(self, tmp_path):
        """Test empty repo returns empty dict."""
        findings = scan_repository_for_secrets(tmp_path)

        assert findings == {}

    def test_returns_dict_with_file_paths(self, tmp_path):
        """Test return value maps file paths to findings."""
        (tmp_path / "config.py").write_text('key = "AKIAWR5PROD9N7K2JLMN"')

        findings = scan_repository_for_secrets(tmp_path)

        assert isinstance(findings, dict)
        for key in findings:
            assert isinstance(key, str)
            # Should be full path
            assert tmp_path.name in key or str(tmp_path) in key

    def test_findings_have_relative_file_path_in_context(self, tmp_path):
        """Test SecretFinding file_path uses relative path."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "config.py").write_text('key = "AKIAWR5PROD9N7K2JLMN"')

        findings = scan_repository_for_secrets(tmp_path)

        assert len(findings) == 1
        file_findings = list(findings.values())[0]
        # The file_path in the finding should be relative
        assert file_findings[0].file_path == "src/config.py"


class TestContextCreation:
    """Tests for safe context creation in findings."""

    def test_context_masks_secret(self):
        """Test secret is partially masked in context."""
        detector = SecretDetector()
        content = 'AWS_KEY = "AKIAWR5PROD9N7K2JLMN"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 1
        # Should contain masked version
        assert "****" in findings[0].context

    def test_context_truncates_long_lines(self):
        """Test very long lines are truncated in context."""
        detector = SecretDetector()
        # Use padding that doesn't trigger false positive patterns
        prefix = "data = " + "v" * 93  # 100 chars total prefix
        content = f"{prefix}AKIAWR5PROD9N7K2JLMN" + "w" * 100

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 1
        # Context should be reasonably short
        assert len(findings[0].context) <= 120  # Allow for "..." suffix

    def test_private_key_context_shows_header(self):
        """Test private key context shows just header."""
        detector = SecretDetector()
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA1234..."

        findings = detector.scan_content(content, "key.pem")

        assert len(findings) >= 1
        for f in findings:
            if f.secret_type in (SecretType.PRIVATE_KEY, SecretType.SSH_KEY):
                assert "BEGIN" in f.context
                assert "..." in f.context


class TestEdgeCases:
    """Tests for edge cases in secret detection."""

    def test_empty_content(self):
        """Test scanning empty content."""
        detector = SecretDetector()
        findings = detector.scan_content("", "empty.py")
        assert findings == []

    def test_whitespace_only_content(self):
        """Test scanning whitespace-only content."""
        detector = SecretDetector()
        findings = detector.scan_content("   \n\n   \t", "whitespace.py")
        assert findings == []

    def test_unicode_content(self):
        """Test scanning content with unicode characters."""
        detector = SecretDetector()
        content = '# Comment with unicode: cafe\nkey = "AKIAWR5PROD9N7K2JLMN"'
        findings = detector.scan_content(content, "unicode.py")
        assert len(findings) == 1

    def test_start_line_offset(self):
        """Test start_line parameter affects line numbers."""
        detector = SecretDetector()
        content = 'key = "AKIAWR5PROD9N7K2JLMN"'

        findings = detector.scan_content(content, "config.py", start_line=100)

        assert len(findings) == 1
        assert findings[0].line_number == 101  # 100 + 1

    def test_mixed_content_types(self, tmp_path):
        """Test scanning repo with mixed file types."""
        # Create various file types (avoid false positive keywords)
        # Use AWS keys in both files for consistent detection
        # Note: JSON with braces triggers false positive filter, so use a text file instead
        (tmp_path / "script.py").write_text('aws_cred = "AKIAWR5PROD9N7K2JLMN"')
        (tmp_path / "config.txt").write_text("aws_cred = AKIA1234567890ABCDEF")
        (tmp_path / "readme.md").write_text("# Readme\nNo secrets here")

        findings = scan_repository_for_secrets(tmp_path)

        # Should find secrets in py and txt but not md
        assert len(findings) == 2
