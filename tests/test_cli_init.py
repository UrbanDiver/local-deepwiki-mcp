"""Tests for the deepwiki init wizard (cli/init_cli.py)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from local_deepwiki.cli.init_cli import (
    _DEFAULT_CONFIG_PATH,
    build_config,
    config_to_minimal_dict,
    detect_api_key,
    detect_languages,
    detect_ollama,
    detect_providers,
    find_existing_config,
    main,
    run_wizard,
    write_config,
)
from local_deepwiki.config import Config


# ── detect_languages ─────────────────────────────────────────────────


class TestDetectLanguages:
    """Scan a temp directory tree and count files per language."""

    def test_empty_directory(self, tmp_path: Path):
        assert detect_languages(tmp_path) == {}

    def test_single_python_file(self, tmp_path: Path):
        (tmp_path / "app.py").write_text("print('hi')")
        result = detect_languages(tmp_path)
        assert result == {"python": 1}

    def test_multiple_languages(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("")
        (tmp_path / "utils.py").write_text("")
        (tmp_path / "index.ts").write_text("")
        (tmp_path / "lib.go").write_text("")
        result = detect_languages(tmp_path)
        assert result["python"] == 2
        assert result["typescript"] == 1
        assert result["go"] == 1

    def test_skips_node_modules(self, tmp_path: Path):
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("")
        (tmp_path / "app.js").write_text("")
        result = detect_languages(tmp_path)
        assert result == {"javascript": 1}

    def test_skips_git_directory(self, tmp_path: Path):
        git_dir = tmp_path / ".git" / "objects"
        git_dir.mkdir(parents=True)
        (git_dir / "script.py").write_text("")
        assert detect_languages(tmp_path) == {}

    def test_skips_venv(self, tmp_path: Path):
        venv = tmp_path / "venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "module.py").write_text("")
        assert detect_languages(tmp_path) == {}

    def test_unknown_extension_ignored(self, tmp_path: Path):
        (tmp_path / "data.csv").write_text("")
        (tmp_path / "readme.md").write_text("")
        assert detect_languages(tmp_path) == {}

    def test_returns_sorted_by_count(self, tmp_path: Path):
        for i in range(3):
            (tmp_path / f"mod{i}.go").write_text("")
        (tmp_path / "app.py").write_text("")
        result = detect_languages(tmp_path)
        langs = list(result.keys())
        assert langs[0] == "go"
        assert langs[1] == "python"

    def test_case_insensitive_extension(self, tmp_path: Path):
        (tmp_path / "Main.PY").write_text("")
        # .PY is lowered to .py in the scan
        result = detect_languages(tmp_path)
        assert result.get("python") == 1


# ── detect_providers ─────────────────────────────────────────────────


class TestDetectProviders:
    """Provider auto-detection via HTTP and env vars."""

    def test_detect_ollama_success(self):
        with patch("local_deepwiki.cli.init_cli.urllib.request.urlopen"):
            assert detect_ollama() is True

    def test_detect_ollama_failure(self):
        with patch(
            "local_deepwiki.cli.init_cli.urllib.request.urlopen",
            side_effect=Exception("connection refused"),
        ):
            assert detect_ollama() is False

    def test_detect_api_key_present(self):
        with patch.dict("os.environ", {"MY_KEY": "sk-test-value"}):
            assert detect_api_key("MY_KEY") is True

    def test_detect_api_key_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            assert detect_api_key("MISSING_KEY") is False

    def test_detect_api_key_empty(self):
        with patch.dict("os.environ", {"MY_KEY": ""}):
            assert detect_api_key("MY_KEY") is False

    def test_detect_providers_all(self):
        with (
            patch("local_deepwiki.cli.init_cli.detect_ollama", return_value=True),
            patch.dict(
                "os.environ",
                {"ANTHROPIC_API_KEY": "sk-ant-test", "OPENAI_API_KEY": "sk-test"},
            ),
        ):
            result = detect_providers()
            assert result == {"ollama": True, "anthropic": True, "openai": True}

    def test_detect_providers_none(self):
        with (
            patch("local_deepwiki.cli.init_cli.detect_ollama", return_value=False),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = detect_providers()
            assert result == {"ollama": False, "anthropic": False, "openai": False}


# ── build_config ─────────────────────────────────────────────────────


class TestBuildConfig:
    """Verify config object has correct provider settings."""

    def test_ollama_local(self):
        config = build_config("ollama", "local", ["python", "go"])
        assert config.llm.provider == "ollama"
        assert config.embedding.provider == "local"
        assert "python" in config.parsing.languages
        assert "go" in config.parsing.languages

    def test_anthropic_openai_embedding(self):
        config = build_config("anthropic", "openai", ["typescript"])
        assert config.llm.provider == "anthropic"
        assert config.embedding.provider == "openai"
        assert config.parsing.languages == ["typescript"]

    def test_default_languages_unchanged(self):
        defaults = Config()
        config = build_config("ollama", "local", list(defaults.parsing.languages))
        # When languages match defaults, parsing config should equal defaults
        assert config.parsing.languages == list(defaults.parsing.languages)

    def test_returns_immutable_config(self):
        config = build_config("ollama", "local", ["python"])
        assert config.model_config.get("frozen") is True


# ── config_to_minimal_dict ───────────────────────────────────────────


class TestMinimalYaml:
    """Verify only non-default fields are written."""

    def test_all_defaults_returns_empty(self):
        config = Config()
        minimal = config_to_minimal_dict(config)
        assert minimal == {}

    def test_changed_provider_included(self):
        config = Config().with_llm_provider("anthropic")
        minimal = config_to_minimal_dict(config)
        assert minimal["llm"]["provider"] == "anthropic"

    def test_default_fields_excluded(self):
        config = Config().with_llm_provider("anthropic")
        minimal = config_to_minimal_dict(config)
        # Embedding should not appear since it's still the default
        assert "embedding" not in minimal

    def test_changed_embedding_included(self):
        config = Config().with_embedding_provider("openai")
        minimal = config_to_minimal_dict(config)
        assert minimal["embedding"]["provider"] == "openai"


# ── write_config ─────────────────────────────────────────────────────


class TestWriteConfig:
    """Write YAML to disk and read it back."""

    def test_writes_valid_yaml(self, tmp_path: Path):
        dest = tmp_path / "sub" / "config.yaml"
        data = {"llm": {"provider": "anthropic"}}
        write_config(data, dest)

        loaded = yaml.safe_load(dest.read_text())
        assert loaded == data

    def test_creates_parent_directories(self, tmp_path: Path):
        dest = tmp_path / "a" / "b" / "c" / "config.yaml"
        write_config({"llm": {"provider": "ollama"}}, dest)
        assert dest.exists()

    def test_roundtrip_with_build(self, tmp_path: Path):
        config = build_config("openai", "openai", ["python", "rust"])
        minimal = config_to_minimal_dict(config)
        dest = tmp_path / "config.yaml"
        write_config(minimal, dest)

        loaded = yaml.safe_load(dest.read_text())
        # Merging loaded data with defaults should produce valid Config
        restored = Config.model_validate(loaded)
        assert restored.llm.provider == "openai"
        assert restored.embedding.provider == "openai"


# ── find_existing_config ─────────────────────────────────────────────


class TestExistingConfig:
    """Verify detection of existing config files."""

    def test_no_config_returns_none(self):
        with patch(
            "local_deepwiki.cli.init_cli._CONFIG_SEARCH_PATHS",
            [Path("/nonexistent/config.yaml")],
        ):
            assert find_existing_config() is None

    def test_existing_config_returned(self, tmp_path: Path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("llm:\n  provider: ollama\n")
        with patch(
            "local_deepwiki.cli.init_cli._CONFIG_SEARCH_PATHS",
            [cfg],
        ):
            assert find_existing_config() == cfg


# ── Non-interactive mode ─────────────────────────────────────────────


class TestNonInteractiveMode:
    """Full flow with --non-interactive flags."""

    def test_non_interactive_writes_config(self, tmp_path: Path):
        dest = tmp_path / "config.yaml"
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("")

        console = MagicMock()
        # Mock: no existing config, ollama available (non-default provider)
        with (
            patch(
                "local_deepwiki.cli.init_cli.find_existing_config", return_value=None
            ),
            patch(
                "local_deepwiki.cli.init_cli.detect_providers",
                return_value={
                    "ollama": True,
                    "anthropic": True,
                    "openai": False,
                },
            ),
        ):
            result = run_wizard(
                repo,
                console,
                non_interactive=True,
                provider_flag="ollama",
                embedding_flag="local",
                config_dest=dest,
            )

        assert result == 0
        assert dest.exists()
        loaded = yaml.safe_load(dest.read_text())
        assert loaded["llm"]["provider"] == "ollama"
        # Config roundtrip should produce valid Config
        restored = Config.model_validate(loaded)
        assert restored.llm.provider == "ollama"

    def test_non_interactive_aborts_on_existing(self, tmp_path: Path):
        existing = tmp_path / "existing.yaml"
        existing.write_text("llm:\n  provider: ollama\n")

        console = MagicMock()
        with patch(
            "local_deepwiki.cli.init_cli.find_existing_config",
            return_value=existing,
        ):
            result = run_wizard(
                tmp_path,
                console,
                non_interactive=True,
                config_dest=tmp_path / "config.yaml",
            )

        assert result == 1

    def test_non_interactive_auto_selects_provider(self, tmp_path: Path):
        dest = tmp_path / "config.yaml"
        console = MagicMock()

        with (
            patch(
                "local_deepwiki.cli.init_cli.find_existing_config", return_value=None
            ),
            patch(
                "local_deepwiki.cli.init_cli.detect_providers",
                return_value={
                    "ollama": False,
                    "anthropic": True,
                    "openai": False,
                },
            ),
        ):
            result = run_wizard(
                tmp_path,
                console,
                non_interactive=True,
                provider_flag=None,
                embedding_flag=None,
                config_dest=dest,
            )

        assert result == 0
        loaded = yaml.safe_load(dest.read_text())
        assert loaded["llm"]["provider"] == "anthropic"

    def test_non_interactive_force_overwrites_existing(self, tmp_path: Path):
        existing = tmp_path / "existing.yaml"
        existing.write_text("llm:\n  provider: ollama\n")
        dest = tmp_path / "config.yaml"

        console = MagicMock()
        with (
            patch(
                "local_deepwiki.cli.init_cli.find_existing_config",
                return_value=existing,
            ),
            patch(
                "local_deepwiki.cli.init_cli.detect_providers",
                return_value={
                    "ollama": True,
                    "anthropic": False,
                    "openai": False,
                },
            ),
        ):
            result = run_wizard(
                tmp_path,
                console,
                non_interactive=True,
                force=True,
                config_dest=dest,
            )

        assert result == 0
        assert dest.exists()
        loaded = yaml.safe_load(dest.read_text())
        assert loaded["llm"]["provider"] == "ollama"

    def test_non_interactive_force_via_main(self, tmp_path: Path):
        dest = tmp_path / "config.yaml"
        existing = tmp_path / "existing.yaml"
        existing.write_text("llm:\n  provider: ollama\n")

        with (
            patch.object(
                sys,
                "argv",
                [
                    "deepwiki init",
                    str(tmp_path),
                    "--non-interactive",
                    "--force",
                    "--provider",
                    "anthropic",
                    "--config",
                    str(dest),
                ],
            ),
            patch(
                "local_deepwiki.cli.init_cli.find_existing_config",
                return_value=existing,
            ),
            patch(
                "local_deepwiki.cli.init_cli.detect_providers",
                return_value={
                    "ollama": False,
                    "anthropic": True,
                    "openai": False,
                },
            ),
        ):
            result = main()

        assert result == 0
        assert dest.exists()
        loaded = yaml.safe_load(dest.read_text())
        assert loaded["llm"]["provider"] == "anthropic"

    def test_non_interactive_fallback_to_default(self, tmp_path: Path):
        dest = tmp_path / "config.yaml"
        console = MagicMock()

        with (
            patch(
                "local_deepwiki.cli.init_cli.find_existing_config", return_value=None
            ),
            patch(
                "local_deepwiki.cli.init_cli.detect_providers",
                return_value={
                    "ollama": False,
                    "anthropic": False,
                    "openai": False,
                },
            ),
        ):
            result = run_wizard(
                tmp_path,
                console,
                non_interactive=True,
                config_dest=dest,
            )

        assert result == 0
        # Fallback is openai (the default), so minimal YAML may omit it
        restored = Config.load(dest)
        assert restored.llm.provider == "openai"


# ── main() dispatch ──────────────────────────────────────────────────


class TestMainDispatch:
    """Verify deepwiki init routes correctly."""

    def test_help_flag(self, capsys):
        with patch.object(sys, "argv", ["deepwiki init", "--help"]):
            try:
                main()
            except SystemExit:
                pass
        captured = capsys.readouterr()
        assert "deepwiki init" in captured.out

    def test_invalid_repo_path(self, capsys):
        with patch.object(sys, "argv", ["deepwiki init", "/nonexistent/path"]):
            result = main()
        assert result == 1

    def test_dispatches_to_run_wizard(self, tmp_path: Path):
        with (
            patch.object(
                sys,
                "argv",
                [
                    "deepwiki init",
                    str(tmp_path),
                    "--non-interactive",
                    "--provider",
                    "ollama",
                    "--config",
                    str(tmp_path / "config.yaml"),
                ],
            ),
            patch(
                "local_deepwiki.cli.init_cli.find_existing_config", return_value=None
            ),
            patch(
                "local_deepwiki.cli.init_cli.detect_providers",
                return_value={
                    "ollama": True,
                    "anthropic": False,
                    "openai": False,
                },
            ),
        ):
            result = main()
        assert result == 0
        assert (tmp_path / "config.yaml").exists()
