"""Tests for configuration."""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from local_deepwiki.config import (
    Config,
    DeepResearchConfig,
    RESEARCH_PRESETS,
    ResearchPreset,
    config_context,
    get_config,
    reset_config,
    set_config,
)


@pytest.fixture(autouse=True)
def reset_global_config():
    """Reset global config before and after each test."""
    reset_config()
    yield
    reset_config()


class TestConfig:
    """Test suite for Config."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()

        assert config.embedding.provider == "local"
        assert config.llm.provider == "ollama"
        assert "python" in config.parsing.languages
        assert config.chunking.max_chunk_tokens == 512

    def test_embedding_config(self):
        """Test embedding configuration."""
        config = Config()

        assert config.embedding.local.model == "all-MiniLM-L6-v2"
        assert config.embedding.openai.model == "text-embedding-3-small"

    def test_llm_config(self):
        """Test LLM configuration."""
        config = Config()

        assert config.llm.ollama.model == "qwen3-coder:30b"
        assert config.llm.ollama.base_url == "http://localhost:11434"
        assert config.llm.anthropic.model == "claude-sonnet-4-20250514"
        assert config.llm.openai.model == "gpt-4o"

    def test_parsing_config(self):
        """Test parsing configuration."""
        config = Config()

        assert "node_modules/**" in config.parsing.exclude_patterns
        assert config.parsing.max_file_size == 1048576

    def test_chunking_config(self):
        """Test chunking configuration."""
        config = Config()

        assert config.chunking.max_chunk_tokens == 512
        assert config.chunking.overlap_tokens == 50
        assert config.chunking.batch_size == 500
        assert config.chunking.class_split_threshold == 100

    def test_wiki_config(self):
        """Test wiki generation configuration."""
        config = Config()

        assert config.wiki.max_file_docs == 20
        assert config.wiki.import_search_limit == 200
        assert config.wiki.context_search_limit == 50
        assert config.wiki.fallback_search_limit == 30

    def test_deep_research_config(self):
        """Test deep research configuration."""
        config = Config()

        assert config.deep_research.max_sub_questions == 4
        assert config.deep_research.chunks_per_subquestion == 5
        assert config.deep_research.max_total_chunks == 30
        assert config.deep_research.max_follow_up_queries == 3
        assert config.deep_research.synthesis_temperature == 0.5
        assert config.deep_research.synthesis_max_tokens == 4096

    def test_deep_research_config_validation(self):
        """Test deep research config validation bounds."""
        from pydantic import ValidationError

        # Test max_sub_questions bounds
        with pytest.raises(ValidationError):
            Config(deep_research={"max_sub_questions": 0})  # Below min

        with pytest.raises(ValidationError):
            Config(deep_research={"max_sub_questions": 11})  # Above max

        # Test temperature bounds
        with pytest.raises(ValidationError):
            Config(deep_research={"synthesis_temperature": -0.1})  # Below min

        with pytest.raises(ValidationError):
            Config(deep_research={"synthesis_temperature": 2.5})  # Above max

    def test_get_wiki_path(self, tmp_path):
        """Test wiki path generation."""
        config = Config()
        wiki_path = config.get_wiki_path(tmp_path)

        assert wiki_path == tmp_path / ".deepwiki"

    def test_get_vector_db_path(self, tmp_path):
        """Test vector database path generation."""
        config = Config()
        db_path = config.get_vector_db_path(tmp_path)

        assert db_path == tmp_path / ".deepwiki" / "vectors.lance"

    def test_global_config(self):
        """Test global config singleton."""
        config1 = get_config()
        config2 = get_config()

        # Should return the same instance
        assert config1 is config2

    def test_set_config(self):
        """Test setting global config."""
        new_config = Config()
        new_config.chunking.max_chunk_tokens = 1024

        set_config(new_config)
        retrieved = get_config()

        assert retrieved.chunking.max_chunk_tokens == 1024


class TestThreadSafeConfig:
    """Tests for thread-safe config access."""

    def test_reset_config(self):
        """Test that reset_config clears the global config."""
        # Get config to initialize it
        config1 = get_config()
        assert config1 is not None

        # Reset and get again - should be a new instance
        reset_config()
        config2 = get_config()

        # After reset, we get a fresh instance
        assert config2 is not None

    def test_concurrent_get_config(self):
        """Test thread-safe concurrent access to get_config."""
        results = []
        errors = []

        def get_config_thread():
            try:
                config = get_config()
                results.append(config)
            except Exception as e:
                errors.append(e)

        # Run multiple threads concurrently
        threads = [threading.Thread(target=get_config_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should succeed and get the same instance
        assert len(errors) == 0
        assert len(results) == 10
        assert all(r is results[0] for r in results)

    def test_concurrent_set_and_get_config(self):
        """Test thread-safe concurrent set and get operations."""
        errors = []

        def modify_config(value: int):
            try:
                new_config = Config()
                new_config.chunking.max_chunk_tokens = value
                set_config(new_config)
                # Read back
                retrieved = get_config()
                # Value should be one of the set values (may not be our value due to race)
                assert retrieved.chunking.max_chunk_tokens >= 100
            except Exception as e:
                errors.append(e)

        # Run multiple threads that set different values
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(modify_config, i * 100) for i in range(1, 6)]
            for f in futures:
                f.result()

        assert len(errors) == 0


class TestConfigContext:
    """Tests for config_context context manager."""

    def test_config_context_overrides_global(self):
        """Test that config_context overrides global config."""
        global_config = get_config()
        assert global_config.chunking.max_chunk_tokens == 512

        custom_config = Config()
        custom_config.chunking.max_chunk_tokens = 2048

        with config_context(custom_config):
            context_config = get_config()
            assert context_config.chunking.max_chunk_tokens == 2048
            assert context_config is custom_config

        # After context, should return to global
        after_config = get_config()
        assert after_config.chunking.max_chunk_tokens == 512

    def test_config_context_restores_on_exception(self):
        """Test that config_context restores config even on exception."""
        custom_config = Config()
        custom_config.chunking.max_chunk_tokens = 4096

        try:
            with config_context(custom_config):
                assert get_config().chunking.max_chunk_tokens == 4096
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should be restored to global
        assert get_config().chunking.max_chunk_tokens == 512

    def test_nested_config_context(self):
        """Test nested config_context calls."""
        config1 = Config()
        config1.chunking.max_chunk_tokens = 1000

        config2 = Config()
        config2.chunking.max_chunk_tokens = 2000

        with config_context(config1):
            assert get_config().chunking.max_chunk_tokens == 1000

            with config_context(config2):
                assert get_config().chunking.max_chunk_tokens == 2000

            # Back to config1
            assert get_config().chunking.max_chunk_tokens == 1000

        # Back to global
        assert get_config().chunking.max_chunk_tokens == 512

    def test_config_context_yields_config(self):
        """Test that config_context yields the provided config."""
        custom_config = Config()
        custom_config.chunking.max_chunk_tokens = 768

        with config_context(custom_config) as cfg:
            assert cfg is custom_config
            assert cfg.chunking.max_chunk_tokens == 768


class TestResearchPresets:
    """Tests for research preset functionality."""

    def test_research_preset_enum_values(self):
        """Test ResearchPreset enum has expected values."""
        assert ResearchPreset.QUICK.value == "quick"
        assert ResearchPreset.DEFAULT.value == "default"
        assert ResearchPreset.THOROUGH.value == "thorough"

    def test_research_presets_dict_has_all_presets(self):
        """Test RESEARCH_PRESETS has all preset configurations."""
        assert ResearchPreset.QUICK in RESEARCH_PRESETS
        assert ResearchPreset.DEFAULT in RESEARCH_PRESETS
        assert ResearchPreset.THOROUGH in RESEARCH_PRESETS

    def test_quick_preset_values(self):
        """Test quick preset has fewer resources."""
        quick = RESEARCH_PRESETS[ResearchPreset.QUICK]
        default = RESEARCH_PRESETS[ResearchPreset.DEFAULT]

        # Quick should use fewer sub-questions and chunks
        assert quick["max_sub_questions"] < default["max_sub_questions"]
        assert quick["chunks_per_subquestion"] < default["chunks_per_subquestion"]
        assert quick["max_total_chunks"] < default["max_total_chunks"]
        assert quick["max_follow_up_queries"] < default["max_follow_up_queries"]
        assert quick["synthesis_max_tokens"] < default["synthesis_max_tokens"]

    def test_thorough_preset_values(self):
        """Test thorough preset uses more resources."""
        thorough = RESEARCH_PRESETS[ResearchPreset.THOROUGH]
        default = RESEARCH_PRESETS[ResearchPreset.DEFAULT]

        # Thorough should use more sub-questions and chunks
        assert thorough["max_sub_questions"] > default["max_sub_questions"]
        assert thorough["chunks_per_subquestion"] > default["chunks_per_subquestion"]
        assert thorough["max_total_chunks"] > default["max_total_chunks"]
        assert thorough["max_follow_up_queries"] > default["max_follow_up_queries"]
        assert thorough["synthesis_max_tokens"] > default["synthesis_max_tokens"]

    def test_with_preset_none_returns_copy(self):
        """Test with_preset(None) returns unchanged copy."""
        config = DeepResearchConfig()
        result = config.with_preset(None)

        assert result.max_sub_questions == config.max_sub_questions
        assert result.chunks_per_subquestion == config.chunks_per_subquestion
        assert result is not config  # Should be a copy

    def test_with_preset_default_returns_copy(self):
        """Test with_preset('default') returns unchanged copy."""
        config = DeepResearchConfig()
        result = config.with_preset("default")

        assert result.max_sub_questions == config.max_sub_questions
        assert result is not config

    def test_with_preset_quick_applies_values(self):
        """Test with_preset('quick') applies quick preset values."""
        config = DeepResearchConfig()
        result = config.with_preset("quick")

        quick = RESEARCH_PRESETS[ResearchPreset.QUICK]
        assert result.max_sub_questions == quick["max_sub_questions"]
        assert result.chunks_per_subquestion == quick["chunks_per_subquestion"]
        assert result.max_total_chunks == quick["max_total_chunks"]
        assert result.max_follow_up_queries == quick["max_follow_up_queries"]
        assert result.synthesis_temperature == quick["synthesis_temperature"]
        assert result.synthesis_max_tokens == quick["synthesis_max_tokens"]

    def test_with_preset_thorough_applies_values(self):
        """Test with_preset('thorough') applies thorough preset values."""
        config = DeepResearchConfig()
        result = config.with_preset("thorough")

        thorough = RESEARCH_PRESETS[ResearchPreset.THOROUGH]
        assert result.max_sub_questions == thorough["max_sub_questions"]
        assert result.chunks_per_subquestion == thorough["chunks_per_subquestion"]
        assert result.max_total_chunks == thorough["max_total_chunks"]
        assert result.max_follow_up_queries == thorough["max_follow_up_queries"]
        assert result.synthesis_temperature == thorough["synthesis_temperature"]
        assert result.synthesis_max_tokens == thorough["synthesis_max_tokens"]

    def test_with_preset_accepts_enum(self):
        """Test with_preset accepts ResearchPreset enum."""
        config = DeepResearchConfig()
        result = config.with_preset(ResearchPreset.QUICK)

        quick = RESEARCH_PRESETS[ResearchPreset.QUICK]
        assert result.max_sub_questions == quick["max_sub_questions"]

    def test_with_preset_case_insensitive(self):
        """Test with_preset is case-insensitive for string input."""
        config = DeepResearchConfig()

        result_lower = config.with_preset("quick")
        result_upper = config.with_preset("QUICK")
        result_mixed = config.with_preset("Quick")

        assert result_lower.max_sub_questions == result_upper.max_sub_questions
        assert result_lower.max_sub_questions == result_mixed.max_sub_questions

    def test_with_preset_invalid_returns_copy(self):
        """Test with_preset with invalid string returns unchanged copy."""
        config = DeepResearchConfig()
        result = config.with_preset("invalid_preset")

        assert result.max_sub_questions == config.max_sub_questions
        assert result is not config

    def test_with_preset_does_not_modify_original(self):
        """Test with_preset does not modify the original config."""
        config = DeepResearchConfig()
        original_value = config.max_sub_questions

        _ = config.with_preset("quick")

        assert config.max_sub_questions == original_value
