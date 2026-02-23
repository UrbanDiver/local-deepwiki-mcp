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

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            pytest.param(SecretType.AWS_KEY, "aws_access_key", id="aws-key"),
            pytest.param(SecretType.AWS_SECRET, "aws_secret_key", id="aws-secret"),
            pytest.param(SecretType.PRIVATE_KEY, "private_key", id="private-key"),
            pytest.param(SecretType.API_KEY, "api_key", id="api-key"),
            pytest.param(SecretType.GENERIC_TOKEN, "generic_token", id="generic-token"),
            pytest.param(SecretType.GITHUB_TOKEN, "github_token", id="github-token"),
            pytest.param(SecretType.GITLAB_TOKEN, "gitlab_token", id="gitlab-token"),
            pytest.param(SecretType.SLACK_TOKEN, "slack_token", id="slack-token"),
            pytest.param(SecretType.AZURE_KEY, "azure_key", id="azure-key"),
            pytest.param(SecretType.GOOGLE_KEY, "google_key", id="google-key"),
            pytest.param(SecretType.DATABASE_URL, "database_url", id="database-url"),
            pytest.param(SecretType.DOCKER_AUTH, "docker_auth", id="docker-auth"),
            pytest.param(SecretType.SSH_KEY, "ssh_key", id="ssh-key"),
            pytest.param(SecretType.PGP_KEY, "pgp_key", id="pgp-key"),
        ],
    )
    def test_secret_type_exists(self, member, expected_value):
        """Test SecretType enum value exists and has correct string value."""
        assert member.value == expected_value
        assert isinstance(member.value, str)


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

    @pytest.mark.parametrize(
        "content, filename, expected_type",
        [
            pytest.param(
                'AWS_KEY = "AKIAWR5PROD9N7K2JLMN"',
                "config.py",
                SecretType.AWS_KEY,
                id="aws-access-key",
            ),
            pytest.param(
                'gh_pat = "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890"',
                "auth.py",
                SecretType.GITHUB_TOKEN,
                id="github-token",
            ),
            pytest.param(
                'DATABASE_URL = "postgres://admin:S3cr3tP4ss@localhost:5432/proddb"',
                "settings.py",
                SecretType.DATABASE_URL,
                id="database-url",
            ),
            pytest.param(
                'GITLAB_KEY = "glpat-R7k2JlmnProdWr5N91234"',
                "ci.yml",
                SecretType.GITLAB_TOKEN,
                id="gitlab-token",
            ),
            pytest.param(
                'SLACK_BOT = "xoxb-123456789012-R7k2JlmnProd"',
                "bot.py",
                SecretType.SLACK_TOKEN,
                id="slack-token",
            ),
            pytest.param(
                'GOOGLE_KEY = "AIzaSyR7k2JlmnProdWr5N9AbcdEfgHiJkL12345"',
                "config.py",
                SecretType.GOOGLE_KEY,
                id="google-api-key",
            ),
        ],
    )
    def test_finds_secret_by_type(self, content, filename, expected_type):
        """Test detecting various secret types in content."""
        detector = SecretDetector()
        findings = detector.scan_content(content, filename)

        assert len(findings) >= 1
        secret_types = [f.secret_type for f in findings]
        assert expected_type in secret_types

    def test_finds_aws_access_key_details(self):
        """Test AWS access key detection includes line number."""
        detector = SecretDetector()
        content = 'AWS_KEY = "AKIAWR5PROD9N7K2JLMN"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 1
        assert findings[0].secret_type == SecretType.AWS_KEY
        assert findings[0].line_number == 1

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

    def test_finds_api_key(self):
        """Test detecting generic API keys."""
        detector = SecretDetector()
        # Use pattern that won't trigger GitHub push protection
        content = 'api_key = "abcdefghij1234567890klmnopqrst"'

        findings = detector.scan_content(content, "config.py")

        # Should find API_KEY or GENERIC_TOKEN
        assert len(findings) >= 1


class TestFalsePositiveFiltering:
    """Tests for false positive filtering."""

    @pytest.mark.parametrize(
        "content, filename",
        [
            pytest.param(
                'test_api_key = "test_abcdefghijklmnop123456"',
                "test_config.py",
                id="test-prefix-values",
            ),
            pytest.param(
                'api_key = "example_key_abcdefghij123456"',
                "example.py",
                id="example-values",
            ),
            pytest.param(
                'mock_token = "mock_abcdefghijklmnop123456"',
                "mock.py",
                id="mock-values",
            ),
            pytest.param(
                'api_key = "placeholder_key_123456789012"',
                "config.py",
                id="placeholder-values",
            ),
            pytest.param(
                'api_key = os.environ["API_KEY"]',
                "config.py",
                id="env-var-reference",
            ),
            pytest.param(
                'api_key = "your_api_key_here"',
                "config.py",
                id="your-key-placeholder",
            ),
            pytest.param(
                "# AKIAIOSFODNN7EXAMPLE  <- this is an example",
                "readme.py",
                id="comment-lines",
            ),
            pytest.param(
                'api_key = "${API_KEY}"',
                "config.py",
                id="env-variable-syntax",
            ),
        ],
    )
    def test_skips_false_positive(self, content, filename):
        """Test that known false positive patterns are skipped."""
        detector = SecretDetector()
        findings = detector.scan_content(content, filename)
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


class TestCompoundVariableFalsePositives:
    """Tests for false positives on compound variable names and type annotations.

    Ensures the detector does not flag legitimate variable names like
    progress_token, token_config, or function call values like
    api_key=credentials(...).
    """

    @pytest.mark.parametrize(
        "content, filename",
        [
            pytest.param(
                "progress_token = token",
                "handler.py",
                id="progress-token-assignment",
            ),
            pytest.param(
                "self.progress_token: str | int | None = None",
                "handler.py",
                id="self-progress-token-annotation",
            ),
            pytest.param(
                'api_key=credentials("service_name")',
                "config.py",
                id="api-key-credentials-call",
            ),
            pytest.param(
                "token_config.set(config)",
                "settings.py",
                id="token-config-method-call",
            ),
            pytest.param(
                'access_token_url = "https://oauth.provider.com/token"',
                "oauth.py",
                id="access-token-url",
            ),
            pytest.param(
                "secret_manager = SecretManager()",
                "app.py",
                id="secret-manager-variable",
            ),
            pytest.param(
                "password_hash = bcrypt.hash(raw_input)",
                "auth.py",
                id="password-hash-variable",
            ),
            pytest.param(
                "token: Optional[str] = None",
                "models.py",
                id="token-optional-annotation",
            ),
        ],
    )
    def test_compound_variable_not_flagged(self, content, filename):
        """Test that compound variable names and type annotations are NOT flagged."""
        detector = SecretDetector()
        findings = detector.scan_content(content, filename)
        assert len(findings) == 0

    def test_real_generic_token_still_triggers(self):
        """Test that a real hardcoded token STILL triggers detection."""
        detector = SecretDetector()
        content = 'token = "sk-proj-abc123def456ghi789"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) >= 1
        secret_types = [f.secret_type for f in findings]
        assert SecretType.GENERIC_TOKEN in secret_types

    def test_real_api_key_still_triggers(self):
        """Test that a real hardcoded API key STILL triggers detection."""
        detector = SecretDetector()
        content = 'api_key = "sk-proj-abc123def456ghi789jkl012"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) >= 1
        secret_types = [f.secret_type for f in findings]
        assert SecretType.API_KEY in secret_types

    def test_real_token_with_quotes_still_triggers(self):
        """Test that token = 'long_literal_value' STILL triggers."""
        detector = SecretDetector()
        content = "token = 'a1b2c3d4e5f6g7h8i9j0k1l2'"

        findings = detector.scan_content(content, "config.py")

        assert len(findings) >= 1

    def test_password_with_literal_value_still_triggers(self):
        """Test that password = 'hardcoded_value' STILL triggers."""
        detector = SecretDetector()
        content = "password = 'Sup3rS3cur3P4ssw0rd!'"

        findings = detector.scan_content(content, "settings.py")

        assert len(findings) >= 1
        secret_types = [f.secret_type for f in findings]
        assert SecretType.GENERIC_TOKEN in secret_types

    def test_dummy_key_with_customkey_not_flagged(self):
        """Test that keys containing 'customkey' are filtered as dummy values."""
        detector = SecretDetector()
        content = 'api_key = "sk-customkey1234567890abcdef"'

        findings = detector.scan_content(content, "config.py")

        assert len(findings) == 0

    def test_test_file_skips_low_confidence_api_key(self):
        """Test that API_KEY pattern is skipped in test files."""
        detector = SecretDetector()
        content = 'api_key="sk-ant-api03-realkey9876543210wxyz"'

        # In a non-test file, this should trigger
        findings_prod = detector.scan_content(content, "src/config.py")
        assert len(findings_prod) >= 1

        # In a test file, low-confidence types are suppressed
        findings_test = detector.scan_content(content, "tests/test_provider.py")
        assert len(findings_test) == 0

    def test_test_file_still_detects_high_confidence_secrets(self):
        """Test that high-confidence patterns (AWS, private keys) still trigger in test files."""
        detector = SecretDetector()
        content = 'key = "AKIAWR5PROD9N7K2JLMN"'

        findings = detector.scan_content(content, "tests/test_aws.py")

        assert len(findings) >= 1
        assert any(f.secret_type == SecretType.AWS_KEY for f in findings)

    def test_is_test_file_detection(self):
        """Test _is_test_file correctly identifies test files."""
        assert SecretDetector._is_test_file("tests/test_provider.py")
        assert SecretDetector._is_test_file("test/test_api.py")
        assert SecretDetector._is_test_file("test_something.py")
        assert SecretDetector._is_test_file("src/tests/test_util.py")
        assert not SecretDetector._is_test_file("src/config.py")
        assert not SecretDetector._is_test_file("src/provider.py")
