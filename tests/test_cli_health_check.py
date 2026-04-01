"""Tests for the deepwiki-config health-check command."""

import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml

# Import config_cli directly without going through package __init__
config_cli_path = (
    Path(__file__).parent.parent / "src" / "local_deepwiki" / "cli" / "config_cli.py"
)
spec = importlib.util.spec_from_file_location("config_cli", config_cli_path)
config_cli = importlib.util.module_from_spec(spec)
sys.modules["config_cli"] = config_cli
spec.loader.exec_module(config_cli)

cmd_health_check = config_cli.cmd_health_check


@pytest.fixture
def mock_console():
    """Mock rich Console."""
    with mock.patch("config_cli.Console") as MockConsole:
        console = mock.MagicMock()
        MockConsole.return_value = console
        yield console


@pytest.fixture
def mock_args():
    """Create mock args namespace."""
    args = mock.MagicMock()
    args.config = None
    return args


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file."""
    config_file = tmp_path / "config.yaml"
    config_data = {
        "llm": {"provider": "ollama"},
        "embedding": {"provider": "local"},
        "output": {"wiki_dir": str(tmp_path / ".deepwiki")},
    }
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return config_file


class TestHealthCheckBasic:
    """Basic health check functionality tests."""

    def test_health_check_runs_successfully(self, mock_console, mock_args):
        """Test health check runs and produces output."""
        result = cmd_health_check(mock_args)

        # Should complete successfully with all packages installed
        assert result == 0
        # Verify output was generated
        assert mock_console.print.called
        assert mock_console.print.call_count >= 3  # Header, table, summary

    def test_health_check_with_valid_config(
        self, mock_console, mock_args, temp_config_file
    ):
        """Test health check with valid config file."""
        mock_args.config = str(temp_config_file)

        result = cmd_health_check(mock_args)

        # Should pass with ollama/local config
        assert result == 0
        assert mock_console.print.called


class TestHealthCheckFailures:
    """Tests for failure scenarios."""

    def test_missing_required_package(self, mock_console, mock_args):
        """Test failure when a required package is missing."""
        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "lancedb":
                raise ImportError("No module named 'lancedb'")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=mock_import):
            result = cmd_health_check(mock_args)

            # Should fail due to missing package
            assert result == 1
            assert mock_console.print.called

    def test_anthropic_without_api_key(self, mock_console, mock_args, tmp_path):
        """Test Anthropic provider requires API key."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: anthropic\n")
        mock_args.config = str(config_file)

        with mock.patch.dict("os.environ", {}, clear=True):
            result = cmd_health_check(mock_args)

            # Should fail without API key
            assert result == 1
            assert mock_console.print.called

    def test_openai_without_api_key(self, mock_console, mock_args, tmp_path):
        """Test OpenAI provider requires API key."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: openai\n")
        mock_args.config = str(config_file)

        with mock.patch.dict("os.environ", {}, clear=True):
            result = cmd_health_check(mock_args)

            # Should fail without API key
            assert result == 1
            assert mock_console.print.called

    def test_invalid_yaml_config(self, mock_console, mock_args, tmp_path):
        """Test invalid YAML in config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: syntax:\n  - broken")
        mock_args.config = str(config_file)

        result = cmd_health_check(mock_args)

        # Should fail with invalid YAML
        assert result == 1
        assert mock_console.print.called

    def test_unwritable_wiki_directory(self, mock_console, mock_args, tmp_path):
        """Test unwritable wiki output directory."""
        config_file = tmp_path / "config.yaml"
        wiki_dir = tmp_path / ".deepwiki"
        config_file.write_text(f"output:\n  wiki_dir: {wiki_dir}\n")
        mock_args.config = str(config_file)

        with mock.patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
            result = cmd_health_check(mock_args)

            # Should fail with permission error
            assert result == 1
            assert mock_console.print.called


class TestHealthCheckConfigOptions:
    """Tests for different config file options."""

    @pytest.fixture(autouse=True)
    def _set_api_key(self, monkeypatch):
        """Default provider is OpenAI, which requires an API key."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")

    def test_empty_config_file(self, mock_console, mock_args, tmp_path):
        """Test empty config file uses defaults."""
        config_file = tmp_path / "config.yaml"
        wiki_dir = tmp_path / ".deepwiki"
        # Write minimal config with writable output directory
        config_file.write_text(f"output:\n  wiki_dir: {wiki_dir}\n")
        mock_args.config = str(config_file)

        result = cmd_health_check(mock_args)

        # Should pass with defaults
        assert result == 0
        assert mock_console.print.called

    def test_no_config_file(self, mock_console, mock_args):
        """Test no config file uses defaults."""
        mock_args.config = None

        result = cmd_health_check(mock_args)

        # Should pass with defaults
        assert result == 0
        assert mock_console.print.called

    def test_ollama_provider(self, mock_console, mock_args, tmp_path):
        """Test Ollama provider (no API key required)."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: ollama\n")
        mock_args.config = str(config_file)

        result = cmd_health_check(mock_args)

        # Should pass without API key for ollama
        assert result == 0
        assert mock_console.print.called

    def test_writable_wiki_directory(self, mock_console, mock_args, tmp_path):
        """Test writable wiki output directory."""
        config_file = tmp_path / "config.yaml"
        wiki_dir = tmp_path / ".deepwiki"
        config_file.write_text(f"output:\n  wiki_dir: {wiki_dir}\n")
        mock_args.config = str(config_file)

        result = cmd_health_check(mock_args)

        # Should pass with writable directory
        assert result == 0
        assert mock_console.print.called
        # Verify test file was cleaned up
        test_file = wiki_dir / ".deepwiki_health_check"
        assert not test_file.exists()


class TestHealthCheckMultipleIssues:
    """Tests for multiple concurrent issues."""

    def test_multiple_failures(self, mock_console, mock_args, tmp_path):
        """Test multiple health check failures at once."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("llm:\n  provider: anthropic\n")
        mock_args.config = str(config_file)

        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "lancedb":
                raise ImportError("No module named 'lancedb'")
            return original_import(name, *args, **kwargs)

        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch("builtins.__import__", side_effect=mock_import):
                result = cmd_health_check(mock_args)

                # Should fail with multiple issues
                assert result == 1
                assert mock_console.print.called
                # Verify multiple checks were reported
                assert mock_console.print.call_count >= 3
