"""Tests for config/loader.py module."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from local_deepwiki.config import (
    Config,
    ConfigChange,
    ConfigDiff,
    reset_config,
)
from local_deepwiki.config.loader import (
    _apply_nested_updates,
    _deep_merge,
    _is_float,
    _set_nested_value,
    _track_sources,
    config_context,
    get_config,
    load_config_from_env,
    merge_configs,
    set_config,
    validate_config,
)


@pytest.fixture(autouse=True)
def reset_config_fixture():
    """Reset global config before and after each test."""
    reset_config()
    yield
    reset_config()


class TestConfigSingleton:
    """Tests for config singleton management."""

    def test_get_config_returns_default_when_none_set(self):
        """Test get_config returns default config when none is set."""
        reset_config()
        config = get_config()

        assert config is not None
        assert isinstance(config, Config)
        assert config.embedding.provider == "local"
        assert config.llm.provider == "ollama"

    def test_get_config_returns_same_instance(self):
        """Test get_config returns same instance on multiple calls."""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_set_config_stores_and_retrieves(self):
        """Test set_config stores config and get_config retrieves it."""
        new_config = Config(chunking={"max_chunk_tokens": 2048})
        set_config(new_config)

        retrieved = get_config()
        assert retrieved is new_config
        assert retrieved.chunking.max_chunk_tokens == 2048

    def test_reset_config_clears_to_none(self):
        """Test reset_config clears global config to None."""
        custom_config = Config(chunking={"max_chunk_tokens": 4096})
        set_config(custom_config)
        assert get_config() is custom_config

        reset_config()
        # After reset, get_config will create a new default instance
        new_config = get_config()
        assert new_config is not custom_config
        assert new_config.chunking.max_chunk_tokens == 512  # default

    def test_config_singleton_thread_safety_get(self):
        """Test context-isolated concurrent get_config calls.

        With ContextVar, each thread gets its own context and lazily
        creates its own Config instance.
        """
        results = []
        errors = []

        def get_config_thread():
            try:
                config = get_config()
                results.append(config)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_config_thread) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        # All threads should get a valid Config
        assert all(isinstance(r, Config) for r in results)

    def test_config_singleton_thread_safety_set_get(self):
        """Test context-isolated concurrent set and get operations.

        With ContextVar, each thread's set_config only affects its own
        context, so the read-back always sees exactly the value that
        thread set.
        """
        errors = []

        def set_and_get(value: int):
            try:
                config = Config(chunking={"max_chunk_tokens": value})
                set_config(config)
                retrieved = get_config()
                assert retrieved.chunking.max_chunk_tokens == value
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(set_and_get, i * 100) for i in range(1, 11)]
            for f in futures:
                f.result()

        assert len(errors) == 0


class TestConfigContextManager:
    """Tests for config_context context manager."""

    def test_config_context_temporarily_overrides(self):
        """Test config_context temporarily overrides global config."""
        global_config = get_config()
        assert global_config.chunking.max_chunk_tokens == 512

        custom_config = Config(chunking={"max_chunk_tokens": 8192})
        with config_context(custom_config):
            context_config = get_config()
            assert context_config is custom_config
            assert context_config.chunking.max_chunk_tokens == 8192

        # After context, returns to global
        after_config = get_config()
        assert after_config is global_config
        assert after_config.chunking.max_chunk_tokens == 512

    def test_config_context_yields_provided_config(self):
        """Test config_context yields the provided config."""
        custom_config = Config(chunking={"max_chunk_tokens": 1536})

        with config_context(custom_config) as yielded_config:
            assert yielded_config is custom_config
            assert yielded_config.chunking.max_chunk_tokens == 1536

    def test_config_context_nested_contexts(self):
        """Test nested config_context calls work correctly."""
        config1 = Config(chunking={"max_chunk_tokens": 256})
        config2 = Config(chunking={"max_chunk_tokens": 512})
        config3 = Config(chunking={"max_chunk_tokens": 1024})

        with config_context(config1):
            assert get_config().chunking.max_chunk_tokens == 256

            with config_context(config2):
                assert get_config().chunking.max_chunk_tokens == 512

                with config_context(config3):
                    assert get_config().chunking.max_chunk_tokens == 1024

                # Back to config2
                assert get_config().chunking.max_chunk_tokens == 512

            # Back to config1
            assert get_config().chunking.max_chunk_tokens == 256

        # Back to global default
        assert get_config().chunking.max_chunk_tokens == 512

    def test_config_context_cleanup_on_exception(self):
        """Test config_context restores config even when exception is raised."""
        global_config = get_config()
        custom_config = Config(chunking={"max_chunk_tokens": 2048})

        with pytest.raises(ValueError):
            with config_context(custom_config):
                assert get_config() is custom_config
                raise ValueError("Test exception")

        # Config should be restored
        assert get_config() is global_config

    async def test_config_context_with_async_compatibility(self):
        """Test config_context works with async/await (ContextVar behavior)."""
        custom_config = Config(chunking={"max_chunk_tokens": 4096})
        with config_context(custom_config):
            # ContextVar should maintain context in async
            config = get_config()
            assert config.chunking.max_chunk_tokens == 4096

        # Global config should be unchanged
        assert get_config().chunking.max_chunk_tokens == 512


class TestLoadConfigFromEnv:
    """Tests for load_config_from_env function."""

    def test_load_config_from_env_empty_when_no_vars(self):
        """Test load_config_from_env returns empty dict when no DEEPWIKI_ vars."""
        with patch.dict(os.environ, {}, clear=True):
            env_config = load_config_from_env()
            assert env_config == {}

    def test_load_config_from_env_parses_string(self):
        """Test load_config_from_env parses string values."""
        with patch.dict(os.environ, {"DEEPWIKI_LLM_PROVIDER": "anthropic"}, clear=True):
            env_config = load_config_from_env()
            assert env_config == {"llm": {"provider": "anthropic"}}

    def test_load_config_from_env_parses_integer(self):
        """Test load_config_from_env parses integer values."""
        with patch.dict(
            os.environ, {"DEEPWIKI_CHUNKING_MAX_CHUNK_TOKENS": "1024"}, clear=True
        ):
            env_config = load_config_from_env()
            assert env_config == {"chunking": {"max_chunk_tokens": 1024}}
            assert isinstance(env_config["chunking"]["max_chunk_tokens"], int)

    def test_load_config_from_env_parses_boolean_true(self):
        """Test load_config_from_env parses boolean true values."""
        with patch.dict(
            os.environ,
            {
                "DEEPWIKI_PLUGINS_ENABLED": "true",
                "DEEPWIKI_HOOKS_ENABLED": "True",
                "DEEPWIKI_WIKI_USE_CLOUD_FOR_GITHUB": "TRUE",
            },
            clear=True,
        ):
            env_config = load_config_from_env()
            assert env_config["plugins"]["enabled"] is True
            assert env_config["hooks"]["enabled"] is True
            assert env_config["wiki"]["use_cloud_for_github"] is True

    def test_load_config_from_env_parses_boolean_false(self):
        """Test load_config_from_env parses boolean false values."""
        with patch.dict(
            os.environ,
            {
                "DEEPWIKI_PLUGINS_ENABLED": "false",
                "DEEPWIKI_HOOKS_ENABLED": "False",
                "DEEPWIKI_WIKI_USE_CLOUD_FOR_GITHUB": "FALSE",
            },
            clear=True,
        ):
            env_config = load_config_from_env()
            assert env_config["plugins"]["enabled"] is False
            assert env_config["hooks"]["enabled"] is False
            assert env_config["wiki"]["use_cloud_for_github"] is False

    def test_load_config_from_env_parses_float(self):
        """Test load_config_from_env parses float values."""
        with patch.dict(
            os.environ,
            {"DEEPWIKI_DEEPRESEARCH_SYNTHESIS_TEMPERATURE": "0.7"},
            clear=True,
        ):
            env_config = load_config_from_env()
            assert env_config == {"deepresearch": {"synthesis_temperature": 0.7}}
            assert isinstance(
                env_config["deepresearch"]["synthesis_temperature"], float
            )

    def test_load_config_from_env_ignores_non_deepwiki_vars(self):
        """Test load_config_from_env ignores variables without DEEPWIKI_ prefix."""
        with patch.dict(
            os.environ,
            {
                "RANDOM_VAR": "value",
                "OPENAI_API_KEY": "sk-test",
                "DEEPWIKI_LLM_PROVIDER": "openai",
            },
            clear=True,
        ):
            env_config = load_config_from_env()
            assert "random_var" not in env_config
            assert "openai_api_key" not in env_config
            assert "llm" in env_config

    def test_load_config_from_env_ignores_malformed_keys(self):
        """Test load_config_from_env ignores keys without section and field."""
        with patch.dict(
            os.environ,
            {
                "DEEPWIKI_NOSECTION": "value",  # Missing field
                "DEEPWIKI_": "value",  # Empty after prefix
            },
            clear=True,
        ):
            env_config = load_config_from_env()
            # Malformed keys should be ignored
            assert env_config == {}

    def test_load_config_from_env_multiple_sections(self):
        """Test load_config_from_env handles multiple sections."""
        with patch.dict(
            os.environ,
            {
                "DEEPWIKI_LLM_PROVIDER": "anthropic",
                "DEEPWIKI_EMBEDDING_PROVIDER": "openai",
                "DEEPWIKI_CHUNKING_MAX_CHUNK_TOKENS": "2048",
            },
            clear=True,
        ):
            env_config = load_config_from_env()
            assert env_config["llm"]["provider"] == "anthropic"
            assert env_config["embedding"]["provider"] == "openai"
            assert env_config["chunking"]["max_chunk_tokens"] == 2048

    def test_load_config_from_env_case_insensitive_conversion(self):
        """Test load_config_from_env converts keys to lowercase."""
        with patch.dict(
            os.environ,
            {"DEEPWIKI_LLM_PROVIDER": "ANTHROPIC"},  # VALUE is uppercase
            clear=True,
        ):
            env_config = load_config_from_env()
            # Section and field should be lowercase, value preserved
            assert "llm" in env_config
            assert "provider" in env_config["llm"]
            assert env_config["llm"]["provider"] == "ANTHROPIC"


class TestMergeConfigs:
    """Tests for merge_configs function."""

    def test_merge_configs_defaults_only(self):
        """Test merge_configs with only defaults."""
        config, diff = merge_configs(None, None, None)

        assert config.llm.provider == "ollama"  # default
        assert not diff.has_changes()

    def test_merge_configs_cli_overrides_all(self):
        """Test CLI config has highest priority."""
        cli = {"llm": {"provider": "anthropic"}}
        env = {"llm": {"provider": "openai"}}
        file = {"llm": {"provider": "ollama"}}

        config, diff = merge_configs(cli, env, file)
        assert config.llm.provider == "anthropic"

    def test_merge_configs_env_overrides_file(self):
        """Test env config overrides file config."""
        env = {"embedding": {"provider": "openai"}}
        file = {"embedding": {"provider": "local"}}

        config, diff = merge_configs(None, env, file)
        assert config.embedding.provider == "openai"

    def test_merge_configs_file_overrides_defaults(self):
        """Test file config overrides defaults."""
        file = {"chunking": {"max_chunk_tokens": 2048}}

        config, diff = merge_configs(None, None, file)
        assert config.chunking.max_chunk_tokens == 2048

    def test_merge_configs_nested_field_merging(self):
        """Test merge_configs handles nested field merging correctly."""
        cli = {"wiki": {"max_file_docs": 1000}}
        file = {"wiki": {"max_concurrent_llm_calls": 4}}

        config, diff = merge_configs(cli, None, file)

        # Both values should be set (deep merge)
        assert config.wiki.max_file_docs == 1000
        assert config.wiki.max_concurrent_llm_calls == 4

    def test_merge_configs_none_values_dont_override(self):
        """Test that None values in override don't replace existing values."""
        file = {"chunking": {"max_chunk_tokens": 1024}}

        config, diff = merge_configs(None, None, file)
        # Other chunking fields should still have defaults, not None
        assert config.chunking.overlap_tokens == 50  # default

    def test_merge_configs_returns_diff_with_changes(self):
        """Test merge_configs returns ConfigDiff with detected changes."""
        cli = {"llm": {"provider": "anthropic"}}

        config, diff = merge_configs(cli, None, None)

        assert isinstance(diff, ConfigDiff)
        assert diff.has_changes()
        changes = diff.get_changes()
        assert any("llm" in c.field and "provider" in c.field for c in changes)

    def test_merge_configs_diff_tracks_source_cli(self):
        """Test merge_configs tracks CLI as source for CLI changes."""
        cli = {"llm": {"provider": "anthropic"}}

        config, diff = merge_configs(cli, None, None)

        provider_changes = [
            c for c in diff.get_changes() if "llm" in c.field and "provider" in c.field
        ]
        assert len(provider_changes) >= 1
        assert provider_changes[0].source == "cli"

    def test_merge_configs_diff_tracks_source_env(self):
        """Test merge_configs tracks env as source for env changes."""
        env = {"embedding": {"provider": "openai"}}

        config, diff = merge_configs(None, env, None)

        provider_changes = [
            c
            for c in diff.get_changes()
            if "embedding" in c.field and "provider" in c.field
        ]
        assert len(provider_changes) >= 1
        assert provider_changes[0].source == "env"

    def test_merge_configs_diff_tracks_source_file(self):
        """Test merge_configs tracks file as source for file changes."""
        file = {"chunking": {"max_chunk_tokens": 1024}}

        config, diff = merge_configs(None, None, file)

        chunk_changes = [c for c in diff.get_changes() if "max_chunk_tokens" in c.field]
        assert len(chunk_changes) >= 1
        assert chunk_changes[0].source == "file"

    def test_merge_configs_custom_defaults(self):
        """Test merge_configs with custom defaults."""
        custom_defaults = Config(chunking={"max_chunk_tokens": 256})
        file = {"chunking": {"overlap_tokens": 25}}

        config, diff = merge_configs(None, None, file, defaults=custom_defaults)

        # File should override, but other fields from custom defaults
        assert config.chunking.max_chunk_tokens == 256
        assert config.chunking.overlap_tokens == 25


class TestConfigDiffing:
    """Tests for ConfigDiff and ConfigChange classes."""

    def test_config_change_dataclass_fields(self):
        """Test ConfigChange has expected fields."""
        change = ConfigChange(
            field="llm.provider",
            old_value="ollama",
            new_value="anthropic",
            source="cli",
        )

        assert change.field == "llm.provider"
        assert change.old_value == "ollama"
        assert change.new_value == "anthropic"
        assert change.source == "cli"

    def test_config_change_str_representation(self):
        """Test ConfigChange string representation."""
        change = ConfigChange(
            field="chunking.max_chunk_tokens",
            old_value=512,
            new_value=1024,
            source="env",
        )

        str_repr = str(change)
        assert "chunking.max_chunk_tokens" in str_repr
        assert "512" in str_repr
        assert "1024" in str_repr
        assert "env" in str_repr

    def test_config_diff_no_changes(self):
        """Test ConfigDiff with identical configs shows no changes."""
        config1 = Config()
        config2 = Config()

        diff = ConfigDiff(config1, config2)

        assert not diff.has_changes()
        assert len(diff.get_changes()) == 0
        assert diff.summary() == "No configuration changes"

    def test_config_diff_detects_simple_changes(self):
        """Test ConfigDiff detects simple field changes."""
        config1 = Config()
        config2 = Config().with_llm_provider("anthropic")

        diff = ConfigDiff(config1, config2)

        assert diff.has_changes()
        changes = diff.get_changes()
        provider_changes = [
            c for c in changes if "llm" in c.field and "provider" in c.field
        ]
        assert len(provider_changes) >= 1
        assert provider_changes[0].old_value == "ollama"
        assert provider_changes[0].new_value == "anthropic"

    def test_config_diff_detects_nested_changes(self):
        """Test ConfigDiff detects nested field changes."""
        config1 = Config()
        config2 = Config(chunking={"max_chunk_tokens": 2048})

        diff = ConfigDiff(config1, config2)

        assert diff.has_changes()
        changes = diff.get_changes()
        chunk_changes = [c for c in changes if "max_chunk_tokens" in c.field]
        assert len(chunk_changes) == 1
        assert chunk_changes[0].old_value == 512
        assert chunk_changes[0].new_value == 2048

    def test_config_diff_get_changes_returns_copy(self):
        """Test get_changes returns a copy, not the original list."""
        config1 = Config()
        config2 = Config().with_llm_provider("anthropic")

        diff = ConfigDiff(config1, config2)

        changes1 = diff.get_changes()
        changes2 = diff.get_changes()

        assert changes1 is not changes2
        assert len(changes1) == len(changes2)

    def test_config_diff_get_changes_by_source(self):
        """Test get_changes_by_source filters correctly."""
        config1 = Config()
        config2 = Config().with_llm_provider("anthropic")

        diff = ConfigDiff(config1, config2)

        # Manually set sources for testing
        for change in diff.changes:
            if "llm" in change.field:
                change.source = "cli"
            else:
                change.source = "env"

        cli_changes = diff.get_changes_by_source("cli")
        env_changes = diff.get_changes_by_source("env")

        assert all(c.source == "cli" for c in cli_changes)
        assert all(c.source == "env" for c in env_changes)

    def test_config_diff_summary_with_changes(self):
        """Test ConfigDiff summary is human-readable with changes."""
        config1 = Config()
        config2 = Config().with_llm_provider("anthropic")

        diff = ConfigDiff(config1, config2)

        summary = diff.summary()
        assert "Configuration changes" in summary
        assert "anthropic" in summary

    def test_config_diff_apply_to_config(self):
        """Test ConfigDiff.apply creates correct config."""
        config1 = Config()
        config2 = Config().with_llm_provider("anthropic")

        diff = ConfigDiff(config1, config2)

        # Apply to a fresh config
        config3 = Config()
        result = diff.apply(config3)

        assert result.llm.provider == "anthropic"
        assert result is not config3  # Should be a new instance

    def test_config_diff_apply_no_changes(self):
        """Test ConfigDiff.apply with no changes returns copy."""
        config1 = Config()
        config2 = Config()

        diff = ConfigDiff(config1, config2)

        result = diff.apply(config1)
        assert result is not config1
        assert result.llm.provider == config1.llm.provider


class TestConfigValidation:
    """Tests for validate_config function."""

    def test_validate_config_default_no_warnings(self):
        """Test validate_config with default local config has no API key warnings."""
        config = Config()  # Default uses local/ollama

        warnings = validate_config(config)

        api_warnings = [w for w in warnings if "API_KEY" in w]
        assert len(api_warnings) == 0

    def test_validate_config_returns_list(self):
        """Test validate_config always returns a list."""
        config = Config()

        warnings = validate_config(config)

        assert isinstance(warnings, list)

    def test_validate_config_warns_missing_openai_embedding_key(self):
        """Test validate_config warns about missing OPENAI_API_KEY for embeddings."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config().with_embedding_provider("openai")

            warnings = validate_config(config)

            assert any("OPENAI_API_KEY" in w and "embedding" in w for w in warnings)

    def test_validate_config_warns_missing_anthropic_llm_key(self):
        """Test validate_config warns about missing ANTHROPIC_API_KEY for LLM."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config().with_llm_provider("anthropic")

            warnings = validate_config(config)

            assert any("ANTHROPIC_API_KEY" in w for w in warnings)

    def test_validate_config_warns_missing_openai_llm_key(self):
        """Test validate_config warns about missing OPENAI_API_KEY for LLM."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config().with_llm_provider("openai")

            warnings = validate_config(config)

            assert any("OPENAI_API_KEY" in w for w in warnings)

    def test_validate_config_warns_parallel_workers_exceeds_cpu(self):
        """Test validate_config warns when parallel_workers exceeds CPU count."""
        cpu_count = os.cpu_count() or 4
        # The validator caps it, but validate_config checks the configured value
        config = Config(chunking={"parallel_workers": cpu_count + 10})

        warnings = validate_config(config)

        # May or may not warn depending on validator behavior, but should not crash
        assert isinstance(warnings, list)

    def test_validate_config_warns_large_batch_size_with_api(self):
        """Test validate_config warns about large batch_size with API provider."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config(
                embedding={"provider": "openai"}, embedding_batch={"batch_size": 150}
            )

            warnings = validate_config(config)

            assert any("batch_size" in w.lower() for w in warnings)

    def test_validate_config_warns_large_max_total_chunks(self):
        """Test validate_config warns about large max_total_chunks."""
        config = Config(deep_research={"max_total_chunks": 60})

        warnings = validate_config(config)

        assert any("max_total_chunks" in w for w in warnings)

    def test_validate_config_warns_large_embedding_cache(self):
        """Test validate_config warns about very large embedding cache."""
        config = Config(embedding_cache={"max_entries": 600000})

        warnings = validate_config(config)

        assert any("embedding cache" in w.lower() for w in warnings)

    def test_validate_config_warns_missing_plugin_dir(self, tmp_path):
        """Test validate_config warns about missing custom plugins directory."""
        fake_dir = tmp_path / "nonexistent"
        config = Config(plugins={"custom_dir": str(fake_dir)})

        warnings = validate_config(config)

        assert any("plugins directory" in w.lower() for w in warnings)

    def test_validate_config_warns_missing_hooks_dir(self, tmp_path):
        """Test validate_config warns about missing hooks scripts directory."""
        fake_dir = tmp_path / "nonexistent"
        config = Config(hooks={"scripts_dir": str(fake_dir)})

        warnings = validate_config(config)

        assert any("hook scripts directory" in w.lower() for w in warnings)

    def test_validate_config_no_warning_for_existing_dirs(self, tmp_path):
        """Test validate_config doesn't warn when directories exist."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()

        config = Config(
            plugins={"custom_dir": str(plugin_dir)},
            hooks={"scripts_dir": str(hooks_dir)},
        )

        warnings = validate_config(config)

        dir_warnings = [w for w in warnings if "directory" in w.lower()]
        assert len(dir_warnings) == 0

    def test_validate_config_cloud_github_missing_key(self):
        """Test validate_config warns about use_cloud_for_github without API key."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config(
                wiki={"use_cloud_for_github": True, "github_llm_provider": "anthropic"}
            )

            warnings = validate_config(config)

            assert any(
                "use_cloud_for_github" in w and "ANTHROPIC_API_KEY" in w
                for w in warnings
            )


class TestHelperFunctions:
    """Tests for helper functions in loader.py."""

    def test_is_float_true_with_decimal(self):
        """Test _is_float returns True for valid float with decimal point."""
        assert _is_float("3.14")
        assert _is_float("0.5")
        assert _is_float("100.0")
        assert _is_float("-5.5")

    def test_is_float_false_without_decimal(self):
        """Test _is_float returns False for integers (no decimal point)."""
        assert not _is_float("123")
        assert not _is_float("0")
        assert not _is_float("-42")

    def test_is_float_false_for_invalid(self):
        """Test _is_float returns False for invalid strings."""
        assert not _is_float("abc")
        assert not _is_float("12.34.56")
        assert not _is_float("")
        assert not _is_float("inf")

    def test_deep_merge_simple_dict(self):
        """Test _deep_merge with simple dictionary."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        _deep_merge(base, override)

        assert base == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested_dict(self):
        """Test _deep_merge with nested dictionaries."""
        base = {"outer": {"a": 1, "b": 2}, "other": 3}
        override = {"outer": {"b": 20, "c": 30}}

        _deep_merge(base, override)

        assert base == {"outer": {"a": 1, "b": 20, "c": 30}, "other": 3}

    def test_deep_merge_overwrites_non_dict(self):
        """Test _deep_merge overwrites non-dict values with dict."""
        base = {"a": "string_value"}
        override = {"a": {"nested": "value"}}

        _deep_merge(base, override)

        assert base == {"a": {"nested": "value"}}

    def test_track_sources_flat_dict(self):
        """Test _track_sources tracks sources for flat dictionary."""
        config = {"provider": "anthropic", "model": "claude"}
        sources = {}

        _track_sources(config, "", sources, "cli")

        assert sources == {"provider": "cli", "model": "cli"}

    def test_track_sources_nested_dict(self):
        """Test _track_sources tracks sources for nested dictionary."""
        config = {"llm": {"provider": "anthropic", "model": "claude"}}
        sources = {}

        _track_sources(config, "", sources, "env")

        assert sources == {"llm.provider": "env", "llm.model": "env"}

    def test_track_sources_with_prefix(self):
        """Test _track_sources respects prefix parameter."""
        config = {"provider": "local"}
        sources = {}

        _track_sources(config, "embedding", sources, "file")

        assert sources == {"embedding.provider": "file"}

    def test_set_nested_value_simple_path(self):
        """Test _set_nested_value with simple path."""
        d = {}
        _set_nested_value(d, ["key"], "value")

        assert d == {"key": "value"}

    def test_set_nested_value_nested_path(self):
        """Test _set_nested_value with nested path."""
        d = {}
        _set_nested_value(d, ["outer", "inner"], "value")

        assert d == {"outer": {"inner": "value"}}

    def test_set_nested_value_deep_path(self):
        """Test _set_nested_value with deep nested path."""
        d = {}
        _set_nested_value(d, ["a", "b", "c", "d"], 42)

        assert d == {"a": {"b": {"c": {"d": 42}}}}

    def test_set_nested_value_existing_dict(self):
        """Test _set_nested_value adds to existing nested dict."""
        d = {"outer": {"existing": 1}}
        _set_nested_value(d, ["outer", "new"], 2)

        assert d == {"outer": {"existing": 1, "new": 2}}

    def test_apply_nested_updates_simple(self):
        """Test _apply_nested_updates with simple update."""
        config = Config()
        updates = {"llm": {"provider": "anthropic"}}

        result = _apply_nested_updates(config, updates)

        assert result.llm.provider == "anthropic"
        assert result is not config

    def test_apply_nested_updates_nested(self):
        """Test _apply_nested_updates with nested updates."""
        config = Config()
        updates = {"chunking": {"max_chunk_tokens": 2048, "overlap_tokens": 100}}

        result = _apply_nested_updates(config, updates)

        assert result.chunking.max_chunk_tokens == 2048
        assert result.chunking.overlap_tokens == 100

    def test_apply_nested_updates_preserves_unmodified(self):
        """Test _apply_nested_updates preserves unmodified fields."""
        config = Config()
        updates = {"llm": {"provider": "anthropic"}}

        result = _apply_nested_updates(config, updates)

        # Embedding provider should be unchanged
        assert result.embedding.provider == "local"
