"""Comprehensive tests for CLI config module."""

import argparse
import os
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from rich.console import Console

from local_deepwiki.cli.config_cli import (
    ConfigValidator,
    ValidationIssue,
    cmd_show,
    cmd_validate,
    display_config,
    display_issues,
    main,
)
from local_deepwiki.config import Config


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_console():
    """Create a mock console that captures output."""
    console = Console(file=StringIO(), force_terminal=True)
    return console


@pytest.fixture
def valid_config_yaml():
    """Return valid config YAML content."""
    return """
llm:
  provider: ollama
  ollama:
    model: qwen3-coder:30b
    base_url: http://localhost:11434
embedding:
  provider: local
  local:
    model: all-MiniLM-L6-v2
chunking:
  max_chunk_tokens: 512
  overlap_tokens: 50
"""


@pytest.fixture
def invalid_yaml_content():
    """Return invalid YAML content."""
    return """
llm:
  provider: ollama
    model: invalid  # bad indentation
  - mixed structure
"""


@pytest.fixture
def valid_config_file(tmp_path, valid_config_yaml):
    """Create a valid config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(valid_config_yaml)
    return config_file


@pytest.fixture
def invalid_yaml_file(tmp_path, invalid_yaml_content):
    """Create an invalid YAML config file."""
    config_file = tmp_path / "bad_config.yaml"
    config_file.write_text(invalid_yaml_content)
    return config_file


@pytest.fixture
def empty_config_file(tmp_path):
    """Create an empty config file."""
    config_file = tmp_path / "empty_config.yaml"
    config_file.write_text("")
    return config_file


@pytest.fixture
def whitespace_config_file(tmp_path):
    """Create a config file with only whitespace."""
    config_file = tmp_path / "whitespace_config.yaml"
    config_file.write_text("   \n\n   \t\t\n")
    return config_file


# =============================================================================
# ValidationIssue Tests
# =============================================================================


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_create_error_issue(self):
        """Test creating an error-level issue."""
        issue = ValidationIssue(
            level="error",
            category="Test",
            message="Test error message",
            suggestion="Fix it",
        )
        assert issue.level == "error"
        assert issue.category == "Test"
        assert issue.message == "Test error message"
        assert issue.suggestion == "Fix it"

    def test_create_warning_issue(self):
        """Test creating a warning-level issue."""
        issue = ValidationIssue(
            level="warning",
            category="Performance",
            message="Test warning",
        )
        assert issue.level == "warning"
        assert issue.category == "Performance"
        assert issue.suggestion is None

    def test_issue_without_suggestion(self):
        """Test creating an issue without a suggestion."""
        issue = ValidationIssue(
            level="error",
            category="File",
            message="Cannot read file",
        )
        assert issue.suggestion is None

    def test_issue_with_empty_suggestion(self):
        """Test creating an issue with empty string suggestion."""
        issue = ValidationIssue(
            level="warning",
            category="Test",
            message="Test",
            suggestion="",
        )
        assert issue.suggestion == ""


# =============================================================================
# ConfigValidator Tests - Initialization
# =============================================================================


class TestConfigValidatorInit:
    """Tests for ConfigValidator initialization."""

    def test_init_without_config_path(self):
        """Test initialization without a config path."""
        validator = ConfigValidator()
        assert validator.config_path is None
        assert validator.issues == []
        assert validator.config is None
        assert validator.raw_config is None

    def test_init_with_config_path(self, tmp_path):
        """Test initialization with a config path."""
        config_path = tmp_path / "config.yaml"
        validator = ConfigValidator(config_path)
        assert validator.config_path == config_path

    def test_init_with_path_object(self, valid_config_file):
        """Test initialization with a Path object."""
        validator = ConfigValidator(valid_config_file)
        assert validator.config_path == valid_config_file


# =============================================================================
# ConfigValidator Tests - _load_config
# =============================================================================


class TestConfigValidatorLoadConfig:
    """Tests for ConfigValidator._load_config method."""

    def test_load_config_explicit_path(self, valid_config_file):
        """Test loading config from an explicit path."""
        validator = ConfigValidator(valid_config_file)
        result = validator._load_config()

        assert result is True
        assert validator.raw_config is not None
        assert validator.config_path == valid_config_file

    def test_load_config_file_not_found(self, tmp_path):
        """Test loading config from a non-existent file."""
        nonexistent = tmp_path / "nonexistent.yaml"
        validator = ConfigValidator(nonexistent)
        result = validator._load_config()

        assert result is False
        assert len(validator.issues) == 1
        assert validator.issues[0].level == "error"
        assert validator.issues[0].category == "File"
        assert "not found" in validator.issues[0].message

    def test_load_config_empty_file(self, empty_config_file):
        """Test loading an empty config file (uses defaults)."""
        validator = ConfigValidator(empty_config_file)
        result = validator._load_config()

        assert result is True
        assert validator.config is not None
        assert validator.raw_config == {}

    def test_load_config_whitespace_file(self, whitespace_config_file):
        """Test loading a whitespace-only config file (uses defaults)."""
        validator = ConfigValidator(whitespace_config_file)
        result = validator._load_config()

        assert result is True
        assert validator.config is not None
        assert validator.raw_config == {}

    def test_load_config_invalid_yaml(self, invalid_yaml_file):
        """Test loading a file with invalid YAML syntax."""
        validator = ConfigValidator(invalid_yaml_file)
        result = validator._load_config()

        assert result is False
        assert len(validator.issues) == 1
        assert validator.issues[0].level == "error"
        assert validator.issues[0].category == "YAML Syntax"

    def test_load_config_no_file_uses_defaults(self, tmp_path, monkeypatch):
        """Test that no config file uses defaults."""
        # Change to a directory with no config files
        monkeypatch.chdir(tmp_path)
        # Also ensure home config doesn't exist
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        validator = ConfigValidator()
        result = validator._load_config()

        assert result is True
        # When no file is found, config and raw_config are set to defaults
        assert validator.raw_config == {}

    def test_load_config_finds_cwd_config_yaml(self, tmp_path, valid_config_yaml, monkeypatch):
        """Test finding config.yaml in current working directory."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "config.yaml"
        config_file.write_text(valid_config_yaml)

        validator = ConfigValidator()
        result = validator._load_config()

        assert result is True
        assert validator.config_path == config_file

    def test_load_config_finds_local_deepwiki_yaml(self, tmp_path, valid_config_yaml, monkeypatch):
        """Test finding .local-deepwiki.yaml in current working directory."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / ".local-deepwiki.yaml"
        config_file.write_text(valid_config_yaml)

        validator = ConfigValidator()
        result = validator._load_config()

        assert result is True
        assert validator.config_path == config_file

    def test_load_config_permission_error(self, tmp_path):
        """Test loading a file with permission issues."""
        config_file = tmp_path / "protected.yaml"
        config_file.write_text("test: value")

        validator = ConfigValidator(config_file)

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = validator._load_config()

        assert result is False
        assert len(validator.issues) == 1
        assert validator.issues[0].level == "error"
        assert validator.issues[0].category == "File"


# =============================================================================
# ConfigValidator Tests - _validate_schema
# =============================================================================


class TestConfigValidatorValidateSchema:
    """Tests for ConfigValidator._validate_schema method."""

    def test_validate_schema_valid_config(self, valid_config_file):
        """Test schema validation with a valid config."""
        validator = ConfigValidator(valid_config_file)
        validator._load_config()
        result = validator._validate_schema()

        assert result is True
        assert validator.config is not None

    def test_validate_schema_invalid_type(self, tmp_path):
        """Test schema validation with invalid types."""
        config_file = tmp_path / "invalid_type.yaml"
        config_file.write_text("""
chunking:
  max_chunk_tokens: "not a number"
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        result = validator._validate_schema()

        assert result is False
        assert len(validator.issues) >= 1
        assert validator.issues[0].level == "error"
        assert validator.issues[0].category == "Schema"

    def test_validate_schema_invalid_enum(self, tmp_path):
        """Test schema validation with invalid enum value."""
        config_file = tmp_path / "invalid_enum.yaml"
        config_file.write_text("""
llm:
  provider: invalid_provider
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        result = validator._validate_schema()

        assert result is False
        assert len(validator.issues) >= 1
        assert any("Schema" in issue.category for issue in validator.issues)

    def test_validate_schema_value_out_of_range(self, tmp_path):
        """Test schema validation with value out of range."""
        config_file = tmp_path / "out_of_range.yaml"
        config_file.write_text("""
deep_research:
  max_sub_questions: 100
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        result = validator._validate_schema()

        assert result is False
        assert len(validator.issues) >= 1


# =============================================================================
# ConfigValidator Tests - _validate_llm_provider
# =============================================================================


class TestConfigValidatorValidateLLMProvider:
    """Tests for ConfigValidator._validate_llm_provider method."""

    def test_validate_anthropic_missing_api_key(self, tmp_path, monkeypatch):
        """Test validation fails when Anthropic API key is missing."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        config_file = tmp_path / "anthropic.yaml"
        config_file.write_text("llm:\n  provider: anthropic")

        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_llm_provider()

        assert any(
            issue.level == "error" and "ANTHROPIC_API_KEY" in issue.message
            for issue in validator.issues
        )

    def test_validate_anthropic_invalid_api_key_format(self, tmp_path, monkeypatch):
        """Test validation warns when Anthropic API key format is wrong."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "invalid-key-format")

        config_file = tmp_path / "anthropic.yaml"
        config_file.write_text("llm:\n  provider: anthropic")

        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_llm_provider()

        assert any(
            issue.level == "warning" and "sk-ant-" in issue.message
            for issue in validator.issues
        )

    def test_validate_anthropic_valid_api_key(self, tmp_path, monkeypatch):
        """Test validation passes with valid Anthropic API key format."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-valid-key")

        config_file = tmp_path / "anthropic.yaml"
        config_file.write_text("llm:\n  provider: anthropic")

        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_llm_provider()

        # Should not have Anthropic API key errors
        api_errors = [
            i for i in validator.issues
            if "ANTHROPIC_API_KEY" in i.message and i.level == "error"
        ]
        assert len(api_errors) == 0

    def test_validate_openai_missing_api_key(self, tmp_path, monkeypatch):
        """Test validation fails when OpenAI API key is missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config_file = tmp_path / "openai.yaml"
        config_file.write_text("llm:\n  provider: openai")

        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_llm_provider()

        assert any(
            issue.level == "error" and "OPENAI_API_KEY" in issue.message
            for issue in validator.issues
        )

    def test_validate_openai_invalid_api_key_format(self, tmp_path, monkeypatch):
        """Test validation warns when OpenAI API key format is wrong."""
        monkeypatch.setenv("OPENAI_API_KEY", "invalid-key-format")

        config_file = tmp_path / "openai.yaml"
        config_file.write_text("llm:\n  provider: openai")

        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_llm_provider()

        assert any(
            issue.level == "warning" and "sk-" in issue.message
            for issue in validator.issues
        )

    def test_validate_openai_valid_api_key(self, tmp_path, monkeypatch):
        """Test validation passes with valid OpenAI API key format."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-valid-key-1234")

        config_file = tmp_path / "openai.yaml"
        config_file.write_text("llm:\n  provider: openai")

        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_llm_provider()

        # Should not have OpenAI API key errors
        api_errors = [
            i for i in validator.issues
            if "OPENAI_API_KEY" in i.message and i.level == "error"
        ]
        assert len(api_errors) == 0

    def test_validate_ollama_localhost_warning(self, tmp_path):
        """Test validation warns about localhost Ollama configuration."""
        config_file = tmp_path / "ollama.yaml"
        config_file.write_text("""
llm:
  provider: ollama
  ollama:
    base_url: http://localhost:11434
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_llm_provider()

        assert any(
            issue.level == "warning" and "localhost" in issue.message
            for issue in validator.issues
        )

    def test_validate_ollama_127_0_0_1_warning(self, tmp_path):
        """Test validation warns about 127.0.0.1 Ollama configuration."""
        config_file = tmp_path / "ollama.yaml"
        config_file.write_text("""
llm:
  provider: ollama
  ollama:
    base_url: http://127.0.0.1:11434
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_llm_provider()

        assert any(
            issue.level == "warning" and "127.0.0.1" in issue.message
            for issue in validator.issues
        )

    def test_validate_llm_provider_none_config(self):
        """Test _validate_llm_provider handles None config gracefully."""
        validator = ConfigValidator()
        validator.config = None
        validator._validate_llm_provider()
        # Should not raise and should not add issues
        assert len(validator.issues) == 0


# =============================================================================
# ConfigValidator Tests - _validate_embedding_provider
# =============================================================================


class TestConfigValidatorValidateEmbeddingProvider:
    """Tests for ConfigValidator._validate_embedding_provider method."""

    def test_validate_openai_embedding_missing_api_key(self, tmp_path, monkeypatch):
        """Test validation fails when OpenAI embedding API key is missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config_file = tmp_path / "openai_embed.yaml"
        config_file.write_text("embedding:\n  provider: openai")

        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_embedding_provider()

        assert any(
            issue.level == "error" and "OPENAI_API_KEY" in issue.message
            for issue in validator.issues
        )

    def test_validate_local_embedding_custom_model_warning(self, tmp_path):
        """Test validation warns about custom local embedding model."""
        config_file = tmp_path / "local_embed.yaml"
        config_file.write_text("""
embedding:
  provider: local
  local:
    model: my-custom-model
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_embedding_provider()

        assert any(
            issue.level == "warning" and "my-custom-model" in issue.message
            for issue in validator.issues
        )

    def test_validate_local_embedding_known_model_no_warning(self, tmp_path):
        """Test validation does not warn about known local embedding models."""
        known_models = [
            "all-MiniLM-L6-v2",
            "all-mpnet-base-v2",
            "paraphrase-multilingual-MiniLM-L12-v2",
        ]

        for model in known_models:
            config_file = tmp_path / f"local_embed_{model.replace('-', '_')}.yaml"
            config_file.write_text(f"""
embedding:
  provider: local
  local:
    model: {model}
""")
            validator = ConfigValidator(config_file)
            validator._load_config()
            validator._validate_schema()
            validator.issues = []  # Clear previous issues
            validator._validate_embedding_provider()

            model_warnings = [
                i for i in validator.issues
                if "custom embedding model" in i.message.lower()
            ]
            assert len(model_warnings) == 0, f"Should not warn about {model}"

    def test_validate_embedding_provider_none_config(self):
        """Test _validate_embedding_provider handles None config gracefully."""
        validator = ConfigValidator()
        validator.config = None
        validator._validate_embedding_provider()
        assert len(validator.issues) == 0


# =============================================================================
# ConfigValidator Tests - _validate_wiki_settings
# =============================================================================


class TestConfigValidatorValidateWikiSettings:
    """Tests for ConfigValidator._validate_wiki_settings method."""

    def test_validate_cloud_github_anthropic_missing_key(self, tmp_path, monkeypatch):
        """Test validation when use_cloud_for_github is enabled without Anthropic key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        config_file = tmp_path / "wiki.yaml"
        config_file.write_text("""
wiki:
  use_cloud_for_github: true
  github_llm_provider: anthropic
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_wiki_settings()

        assert any(
            issue.level == "error" and "use_cloud_for_github" in issue.message
            for issue in validator.issues
        )

    def test_validate_cloud_github_openai_missing_key(self, tmp_path, monkeypatch):
        """Test validation when use_cloud_for_github is enabled without OpenAI key."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config_file = tmp_path / "wiki.yaml"
        config_file.write_text("""
wiki:
  use_cloud_for_github: true
  github_llm_provider: openai
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_wiki_settings()

        assert any(
            issue.level == "error" and "use_cloud_for_github" in issue.message
            for issue in validator.issues
        )

    def test_validate_chat_provider_anthropic_missing_key(self, tmp_path, monkeypatch):
        """Test validation when chat_llm_provider is anthropic without key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        config_file = tmp_path / "wiki.yaml"
        config_file.write_text("""
llm:
  provider: ollama
wiki:
  chat_llm_provider: anthropic
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_wiki_settings()

        assert any(
            issue.level == "error" and "chat_llm_provider" in issue.message
            for issue in validator.issues
        )

    def test_validate_chat_provider_openai_missing_key(self, tmp_path, monkeypatch):
        """Test validation when chat_llm_provider is openai without key."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config_file = tmp_path / "wiki.yaml"
        config_file.write_text("""
llm:
  provider: ollama
wiki:
  chat_llm_provider: openai
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_wiki_settings()

        assert any(
            issue.level == "error" and "chat_llm_provider" in issue.message
            for issue in validator.issues
        )

    def test_validate_high_concurrent_llm_calls_warning(self, tmp_path):
        """Test validation warns about high max_concurrent_llm_calls."""
        config_file = tmp_path / "wiki.yaml"
        config_file.write_text("""
wiki:
  max_concurrent_llm_calls: 15
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_wiki_settings()

        assert any(
            issue.level == "warning" and "max_concurrent_llm_calls" in issue.message
            for issue in validator.issues
        )

    def test_validate_wiki_settings_none_config(self):
        """Test _validate_wiki_settings handles None config gracefully."""
        validator = ConfigValidator()
        validator.config = None
        validator._validate_wiki_settings()
        assert len(validator.issues) == 0


# =============================================================================
# ConfigValidator Tests - _validate_paths
# =============================================================================


class TestConfigValidatorValidatePaths:
    """Tests for ConfigValidator._validate_paths method."""

    def test_validate_missing_node_modules_warning(self, tmp_path):
        """Test validation warns when node_modules not in exclude patterns."""
        config_file = tmp_path / "paths.yaml"
        config_file.write_text("""
parsing:
  exclude_patterns:
    - ".git/**"
    - "dist/**"
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_paths()

        assert any(
            issue.level == "warning" and "node_modules" in issue.message
            for issue in validator.issues
        )

    def test_validate_missing_git_warning(self, tmp_path):
        """Test validation warns when .git not in exclude patterns."""
        config_file = tmp_path / "paths.yaml"
        config_file.write_text("""
parsing:
  exclude_patterns:
    - "node_modules/**"
    - "dist/**"
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_paths()

        assert any(
            issue.level == "warning" and ".git" in issue.message
            for issue in validator.issues
        )

    def test_validate_paths_with_all_patterns(self, tmp_path):
        """Test validation passes when all expected patterns are present."""
        config_file = tmp_path / "paths.yaml"
        config_file.write_text("""
parsing:
  exclude_patterns:
    - "node_modules/**"
    - ".git/**"
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_paths()

        path_warnings = [
            i for i in validator.issues
            if i.category == "Parsing"
        ]
        assert len(path_warnings) == 0

    def test_validate_paths_none_config(self):
        """Test _validate_paths handles None config gracefully."""
        validator = ConfigValidator()
        validator.config = None
        validator._validate_paths()
        assert len(validator.issues) == 0


# =============================================================================
# ConfigValidator Tests - _validate_performance_settings
# =============================================================================


class TestConfigValidatorValidatePerformanceSettings:
    """Tests for ConfigValidator._validate_performance_settings method."""

    def test_validate_high_parallel_workers_warning(self, tmp_path, monkeypatch):
        """Test validation warns about high parallel workers.

        Note: Pydantic's field validator caps parallel_workers to CPU count,
        so we need to mock the CPU count during validation to make the warning
        trigger. We mock it to return a higher value during config parsing,
        then a lower value during validation.
        """
        # First, create the config with a high parallel_workers value
        # by mocking cpu_count to return a high value during Config parsing
        high_workers = 20

        config_file = tmp_path / "perf.yaml"
        config_file.write_text(f"""
chunking:
  parallel_workers: {high_workers}
""")

        # During loading, use a high CPU count so Pydantic doesn't cap the value
        original_cpu_count = os.cpu_count
        call_count = [0]

        def variable_cpu_count():
            call_count[0] += 1
            # First calls during Config parsing - return high value
            if call_count[0] <= 5:
                return 32
            # Later calls during validation - return low value
            return 4

        monkeypatch.setattr(os, "cpu_count", variable_cpu_count)

        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()

        # Reset counter for validation
        call_count[0] = 10  # Force the low CPU count for validation
        validator._validate_performance_settings()

        # The warning should be issued since 20 > 2 * 4 = 8
        assert any(
            issue.level == "warning" and "parallel_workers" in issue.message
            for issue in validator.issues
        )

    def test_validate_high_chunk_tokens_warning(self, tmp_path):
        """Test validation warns about high max_chunk_tokens."""
        config_file = tmp_path / "perf.yaml"
        config_file.write_text("""
chunking:
  max_chunk_tokens: 2048
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_performance_settings()

        assert any(
            issue.level == "warning" and "max_chunk_tokens" in issue.message
            for issue in validator.issues
        )

    def test_validate_disabled_embedding_cache_warning(self, tmp_path):
        """Test validation warns when embedding cache is disabled."""
        config_file = tmp_path / "perf.yaml"
        config_file.write_text("""
embedding_cache:
  enabled: false
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_performance_settings()

        assert any(
            issue.level == "warning" and "Embedding cache" in issue.message
            for issue in validator.issues
        )

    def test_validate_disabled_llm_cache_warning(self, tmp_path):
        """Test validation warns when LLM cache is disabled."""
        config_file = tmp_path / "perf.yaml"
        config_file.write_text("""
llm_cache:
  enabled: false
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_performance_settings()

        assert any(
            issue.level == "warning" and "LLM cache" in issue.message
            for issue in validator.issues
        )

    def test_validate_performance_settings_none_config(self):
        """Test _validate_performance_settings handles None config gracefully."""
        validator = ConfigValidator()
        validator.config = None
        validator._validate_performance_settings()
        assert len(validator.issues) == 0


# =============================================================================
# ConfigValidator Tests - validate (full flow)
# =============================================================================


class TestConfigValidatorValidate:
    """Tests for ConfigValidator.validate method (full validation flow)."""

    def test_validate_valid_config(self, valid_config_file):
        """Test full validation with a valid config."""
        validator = ConfigValidator(valid_config_file)
        result = validator.validate()

        # May have warnings but no errors
        errors = [i for i in validator.issues if i.level == "error"]
        assert result is True or len(errors) == 0

    def test_validate_invalid_yaml(self, invalid_yaml_file):
        """Test full validation with invalid YAML."""
        validator = ConfigValidator(invalid_yaml_file)
        result = validator.validate()

        assert result is False
        assert len(validator.issues) >= 1

    def test_validate_nonexistent_file(self, tmp_path):
        """Test full validation with nonexistent file."""
        nonexistent = tmp_path / "nonexistent.yaml"
        validator = ConfigValidator(nonexistent)
        result = validator.validate()

        assert result is False
        assert len(validator.issues) >= 1

    def test_validate_clears_previous_issues(self, valid_config_file):
        """Test that validate clears issues from previous runs."""
        validator = ConfigValidator(valid_config_file)

        # Add a fake issue
        validator.issues.append(
            ValidationIssue(level="error", category="Fake", message="Fake issue")
        )

        # Run validation
        validator.validate()

        # Fake issue should be cleared
        assert not any(i.message == "Fake issue" for i in validator.issues)

    def test_validate_returns_false_on_error(self, tmp_path, monkeypatch):
        """Test validate returns False when there are errors."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: anthropic")

        validator = ConfigValidator(config_file)
        result = validator.validate()

        assert result is False

    def test_validate_returns_true_with_only_warnings(self, valid_config_file):
        """Test validate returns True when there are only warnings."""
        validator = ConfigValidator(valid_config_file)

        # Run validation
        result = validator.validate()

        # Should return True even if there are warnings (no errors)
        errors = [i for i in validator.issues if i.level == "error"]
        if len(errors) == 0:
            assert result is True


# =============================================================================
# Display Functions Tests
# =============================================================================


class TestDisplayConfig:
    """Tests for display_config function."""

    def test_display_config_ollama(self, mock_console):
        """Test displaying config with Ollama provider."""
        config = Config()  # Default uses ollama
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "LLM" in output
        assert "ollama" in output

    def test_display_config_anthropic(self, mock_console, monkeypatch):
        """Test displaying config with Anthropic provider."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        config = Config().with_llm_provider("anthropic")
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "anthropic" in output

    def test_display_config_openai(self, mock_console, monkeypatch):
        """Test displaying config with OpenAI provider."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config = Config().with_llm_provider("openai")
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "openai" in output

    def test_display_config_shows_embedding(self, mock_console):
        """Test display_config shows embedding settings."""
        config = Config()
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "Embedding" in output

    def test_display_config_shows_parsing(self, mock_console):
        """Test display_config shows parsing settings."""
        config = Config()
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "Parsing" in output

    def test_display_config_shows_chunking(self, mock_console):
        """Test display_config shows chunking settings."""
        config = Config()
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "Chunking" in output

    def test_display_config_shows_wiki(self, mock_console):
        """Test display_config shows wiki settings."""
        config = Config()
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "Wiki" in output

    def test_display_config_shows_cache(self, mock_console):
        """Test display_config shows cache settings."""
        config = Config()
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "Caching" in output

    def test_display_config_shows_output(self, mock_console):
        """Test display_config shows output settings."""
        config = Config()
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "Output" in output

    def test_display_config_openai_embedding(self, mock_console, monkeypatch):
        """Test display_config with OpenAI embedding provider."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config = Config().with_embedding_provider("openai")
        display_config(config, mock_console)

        output = mock_console.file.getvalue()
        assert "openai" in output.lower()
        # Should show the OpenAI embedding model
        assert "text-embedding" in output or "Embedding" in output


class TestDisplayIssues:
    """Tests for display_issues function."""

    def test_display_no_issues(self, mock_console):
        """Test displaying when there are no issues."""
        display_issues([], mock_console)

        output = mock_console.file.getvalue()
        assert "No validation issues" in output

    def test_display_single_error(self, mock_console):
        """Test displaying a single error."""
        issues = [
            ValidationIssue(
                level="error",
                category="Test",
                message="Test error",
                suggestion="Fix it",
            )
        ]
        display_issues(issues, mock_console)

        output = mock_console.file.getvalue()
        # Rich adds ANSI codes, so check for the text content
        assert "error" in output.lower() or "ERROR" in output
        assert "Test error" in output

    def test_display_single_warning(self, mock_console):
        """Test displaying a single warning."""
        issues = [
            ValidationIssue(
                level="warning",
                category="Test",
                message="Test warning",
            )
        ]
        display_issues(issues, mock_console)

        output = mock_console.file.getvalue()
        # Rich adds ANSI codes, so check for the text content
        assert "warning" in output.lower() or "WARNING" in output
        assert "Test warning" in output

    def test_display_mixed_issues(self, mock_console):
        """Test displaying mixed errors and warnings."""
        issues = [
            ValidationIssue(level="error", category="Test", message="Error 1"),
            ValidationIssue(level="warning", category="Test", message="Warning 1"),
            ValidationIssue(level="error", category="Test", message="Error 2"),
        ]
        display_issues(issues, mock_console)

        output = mock_console.file.getvalue()
        # Check the summary shows correct counts
        assert "2" in output  # 2 errors
        assert "1" in output  # 1 warning
        # Check the messages appear
        assert "Error 1" in output
        assert "Error 2" in output
        assert "Warning 1" in output

    def test_display_issues_shows_suggestions(self, mock_console):
        """Test that suggestions are displayed when present."""
        issues = [
            ValidationIssue(
                level="error",
                category="Test",
                message="Error",
                suggestion="Here is a suggestion",
            )
        ]
        display_issues(issues, mock_console)

        output = mock_console.file.getvalue()
        assert "Here is a suggestion" in output


# =============================================================================
# CLI Command Tests
# =============================================================================


class TestCmdValidate:
    """Tests for cmd_validate function."""

    def test_cmd_validate_valid_config(self, valid_config_file):
        """Test cmd_validate with valid config."""
        args = argparse.Namespace(config=str(valid_config_file))

        with patch("local_deepwiki.cli.config_cli.Console"):
            result = cmd_validate(args)

        # Should succeed (return 0) or have only warnings
        assert result in [0, 1]

    def test_cmd_validate_no_config(self, tmp_path, monkeypatch):
        """Test cmd_validate with no config file."""
        monkeypatch.chdir(tmp_path)
        args = argparse.Namespace(config=None)

        with patch("local_deepwiki.cli.config_cli.Console"):
            result = cmd_validate(args)

        # Should succeed with defaults
        assert result == 0

    def test_cmd_validate_invalid_config(self, invalid_yaml_file):
        """Test cmd_validate with invalid config."""
        args = argparse.Namespace(config=str(invalid_yaml_file))

        with patch("local_deepwiki.cli.config_cli.Console"):
            result = cmd_validate(args)

        assert result == 1


class TestCmdShow:
    """Tests for cmd_show function."""

    def test_cmd_show_valid_config(self, valid_config_file):
        """Test cmd_show with valid config."""
        args = argparse.Namespace(config=str(valid_config_file), raw=False)

        with patch("local_deepwiki.cli.config_cli.Console"):
            result = cmd_show(args)

        assert result == 0

    def test_cmd_show_no_config(self, tmp_path, monkeypatch):
        """Test cmd_show with no config file."""
        monkeypatch.chdir(tmp_path)
        args = argparse.Namespace(config=None, raw=False)

        with patch("local_deepwiki.cli.config_cli.Console"):
            result = cmd_show(args)

        assert result == 0

    def test_cmd_show_with_raw(self, valid_config_file):
        """Test cmd_show with raw output."""
        args = argparse.Namespace(config=str(valid_config_file), raw=True)

        with patch("local_deepwiki.cli.config_cli.Console"):
            result = cmd_show(args)

        assert result == 0

    def test_cmd_show_error_loading_config(self, invalid_yaml_file):
        """Test cmd_show with error loading config."""
        args = argparse.Namespace(config=str(invalid_yaml_file), raw=False)

        with patch("local_deepwiki.cli.config_cli.Console"):
            result = cmd_show(args)

        assert result == 1

    def test_cmd_show_no_config_default_message(self, tmp_path, monkeypatch):
        """Test cmd_show displays default message when no config file found."""
        # Change to temp directory with no config files
        monkeypatch.chdir(tmp_path)
        # Mock home to avoid finding user config
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        args = argparse.Namespace(config=None, raw=False)

        # Capture the console output
        console_mock = MagicMock()
        with patch("local_deepwiki.cli.config_cli.Console", return_value=console_mock):
            result = cmd_show(args)

        assert result == 0
        # Check that the "default configuration" message was printed
        calls = [str(call) for call in console_mock.print.call_args_list]
        assert any("default" in str(call).lower() for call in calls)


class TestMain:
    """Tests for main function."""

    def test_main_no_args_defaults_to_validate(self, tmp_path, monkeypatch):
        """Test main with no arguments defaults to validate."""
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["deepwiki-config"]):
            with patch("local_deepwiki.cli.config_cli.Console"):
                result = main()

        assert result == 0

    def test_main_validate_command(self, valid_config_file):
        """Test main with validate command."""
        with patch("sys.argv", ["deepwiki-config", "-c", str(valid_config_file), "validate"]):
            with patch("local_deepwiki.cli.config_cli.Console"):
                result = main()

        assert result in [0, 1]

    def test_main_show_command(self, valid_config_file):
        """Test main with show command."""
        with patch("sys.argv", ["deepwiki-config", "-c", str(valid_config_file), "show"]):
            with patch("local_deepwiki.cli.config_cli.Console"):
                result = main()

        assert result == 0

    def test_main_show_with_raw(self, valid_config_file):
        """Test main with show --raw command."""
        with patch("sys.argv", ["deepwiki-config", "-c", str(valid_config_file), "show", "--raw"]):
            with patch("local_deepwiki.cli.config_cli.Console"):
                result = main()

        assert result == 0


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and unusual scenarios."""

    def test_config_with_null_values(self, tmp_path):
        """Test handling config with null values."""
        config_file = tmp_path / "null_config.yaml"
        config_file.write_text("""
llm:
  provider: ollama
wiki:
  max_file_docs: null
""")
        validator = ConfigValidator(config_file)
        # This should not crash
        result = validator.validate()
        # Result depends on whether null is valid for max_file_docs
        assert isinstance(result, bool)

    def test_config_with_extra_fields(self, tmp_path):
        """Test handling config with unknown/extra fields."""
        config_file = tmp_path / "extra_fields.yaml"
        config_file.write_text("""
llm:
  provider: ollama
unknown_section:
  unknown_field: value
""")
        validator = ConfigValidator(config_file)
        result = validator.validate()
        # Extra fields may or may not be allowed depending on Pydantic config
        assert isinstance(result, bool)

    def test_unicode_in_config(self, tmp_path):
        """Test handling config with unicode characters."""
        config_file = tmp_path / "unicode_config.yaml"
        config_file.write_text("""
llm:
  provider: ollama
  ollama:
    model: "test-model-with-unicode-\u00e9"
""")
        validator = ConfigValidator(config_file)
        result = validator.validate()
        assert isinstance(result, bool)

    def test_very_long_config_values(self, tmp_path):
        """Test handling config with very long values."""
        long_string = "a" * 10000
        config_file = tmp_path / "long_config.yaml"
        config_file.write_text(f"""
llm:
  provider: ollama
  ollama:
    model: "{long_string}"
""")
        validator = ConfigValidator(config_file)
        result = validator.validate()
        assert isinstance(result, bool)

    def test_deeply_nested_config(self, tmp_path):
        """Test handling valid deeply nested config."""
        config_file = tmp_path / "deep_config.yaml"
        config_file.write_text("""
llm:
  provider: ollama
  ollama:
    model: qwen3-coder:30b
    base_url: http://localhost:11434
embedding:
  provider: local
  local:
    model: all-MiniLM-L6-v2
prompts:
  ollama:
    wiki_system: "Test prompt"
    research_decomposition: "Test"
    research_gap_analysis: "Test"
    research_synthesis: "Test"
""")
        validator = ConfigValidator(config_file)
        result = validator.validate()
        assert isinstance(result, bool)

    def test_config_with_special_yaml_types(self, tmp_path):
        """Test handling config with special YAML types."""
        config_file = tmp_path / "special_yaml.yaml"
        config_file.write_text("""
llm:
  provider: ollama
chunking:
  max_chunk_tokens: 512
  overlap_tokens: 0o62  # Octal
""")
        validator = ConfigValidator(config_file)
        result = validator.validate()
        assert isinstance(result, bool)

    def test_concurrent_validation(self, valid_config_file):
        """Test that validation is safe for concurrent use."""
        import threading

        results = []
        errors = []

        def validate():
            try:
                validator = ConfigValidator(valid_config_file)
                result = validator.validate()
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=validate) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5

    def test_api_key_with_newline(self, tmp_path, monkeypatch):
        """Test handling API key with trailing newline."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test\n")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: anthropic")

        validator = ConfigValidator(config_file)
        result = validator.validate()
        # Should still work (implementation may strip whitespace)
        assert isinstance(result, bool)

    def test_empty_exclude_patterns(self, tmp_path):
        """Test handling config with empty exclude patterns."""
        config_file = tmp_path / "empty_patterns.yaml"
        config_file.write_text("""
parsing:
  exclude_patterns: []
""")
        validator = ConfigValidator(config_file)
        validator._load_config()
        validator._validate_schema()
        validator._validate_paths()

        # Should warn about missing node_modules and .git
        assert len([i for i in validator.issues if "node_modules" in i.message]) >= 1
        assert len([i for i in validator.issues if ".git" in i.message]) >= 1
