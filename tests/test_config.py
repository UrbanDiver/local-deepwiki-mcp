"""Tests for configuration."""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from local_deepwiki.config import (
    Config,
    DeepResearchConfig,
    ProviderPromptsConfig,
    PromptsConfig,
    RESEARCH_PRESETS,
    ResearchPreset,
    WIKI_SYSTEM_PROMPTS,
    RESEARCH_DECOMPOSITION_PROMPTS,
    RESEARCH_GAP_ANALYSIS_PROMPTS,
    RESEARCH_SYNTHESIS_PROMPTS,
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
        assert config.wiki.max_concurrent_llm_calls == 3
        assert config.wiki.use_cloud_for_github is False
        assert config.wiki.github_llm_provider == "anthropic"
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


class TestProviderPrompts:
    """Tests for provider-specific prompts configuration."""

    def test_provider_prompts_config_has_all_fields(self):
        """Test ProviderPromptsConfig has all required prompt fields."""
        prompts = ProviderPromptsConfig(
            wiki_system="wiki",
            research_decomposition="decomp",
            research_gap_analysis="gap",
            research_synthesis="synth",
        )
        assert prompts.wiki_system == "wiki"
        assert prompts.research_decomposition == "decomp"
        assert prompts.research_gap_analysis == "gap"
        assert prompts.research_synthesis == "synth"

    def test_prompts_config_has_all_providers(self):
        """Test PromptsConfig has configurations for all providers."""
        config = PromptsConfig()
        assert config.ollama is not None
        assert config.anthropic is not None
        assert config.openai is not None

    def test_default_prompts_are_different_per_provider(self):
        """Test that default prompts are optimized differently per provider."""
        config = PromptsConfig()

        # Ollama prompts should be shorter (for smaller context windows)
        assert len(config.ollama.wiki_system) < len(config.anthropic.wiki_system)

        # All providers should have non-empty prompts
        for provider in [config.ollama, config.anthropic, config.openai]:
            assert len(provider.wiki_system) > 0
            assert len(provider.research_decomposition) > 0
            assert len(provider.research_gap_analysis) > 0
            assert len(provider.research_synthesis) > 0

    def test_get_for_provider_ollama(self):
        """Test get_for_provider returns ollama prompts."""
        config = PromptsConfig()
        prompts = config.get_for_provider("ollama")
        assert prompts == config.ollama

    def test_get_for_provider_anthropic(self):
        """Test get_for_provider returns anthropic prompts."""
        config = PromptsConfig()
        prompts = config.get_for_provider("anthropic")
        assert prompts == config.anthropic

    def test_get_for_provider_openai(self):
        """Test get_for_provider returns openai prompts."""
        config = PromptsConfig()
        prompts = config.get_for_provider("openai")
        assert prompts == config.openai

    def test_get_for_provider_unknown_defaults_to_anthropic(self):
        """Test get_for_provider defaults to anthropic for unknown providers."""
        config = PromptsConfig()
        prompts = config.get_for_provider("unknown_provider")
        assert prompts == config.anthropic

    def test_config_get_prompts_uses_current_provider(self):
        """Test Config.get_prompts() returns prompts for current LLM provider."""
        config = Config()
        # Default provider is ollama
        assert config.llm.provider == "ollama"
        prompts = config.get_prompts()
        assert prompts == config.prompts.ollama

    def test_config_get_prompts_changes_with_provider(self):
        """Test Config.get_prompts() changes when provider changes."""
        config = Config()

        # Test with different providers
        config.llm.provider = "anthropic"  # type: ignore
        prompts_anthropic = config.get_prompts()
        assert prompts_anthropic == config.prompts.anthropic

        config.llm.provider = "openai"  # type: ignore
        prompts_openai = config.get_prompts()
        assert prompts_openai == config.prompts.openai

    def test_wiki_system_prompts_dict_has_all_providers(self):
        """Test WIKI_SYSTEM_PROMPTS has entries for all providers."""
        assert "ollama" in WIKI_SYSTEM_PROMPTS
        assert "anthropic" in WIKI_SYSTEM_PROMPTS
        assert "openai" in WIKI_SYSTEM_PROMPTS

    def test_research_prompts_dicts_have_all_providers(self):
        """Test all research prompt dicts have entries for all providers."""
        for prompts_dict in [
            RESEARCH_DECOMPOSITION_PROMPTS,
            RESEARCH_GAP_ANALYSIS_PROMPTS,
            RESEARCH_SYNTHESIS_PROMPTS,
        ]:
            assert "ollama" in prompts_dict
            assert "anthropic" in prompts_dict
            assert "openai" in prompts_dict

    def test_prompts_contain_essential_instructions(self):
        """Test that prompts contain essential instructions."""
        config = PromptsConfig()

        # Wiki prompts should mention documentation
        assert "documentation" in config.anthropic.wiki_system.lower()

        # Decomposition prompts should mention JSON
        assert "json" in config.anthropic.research_decomposition.lower()

        # Gap analysis prompts should mention JSON
        assert "json" in config.anthropic.research_gap_analysis.lower()

        # Synthesis prompts should mention code/architecture
        assert "code" in config.anthropic.research_synthesis.lower() or \
               "architecture" in config.anthropic.research_synthesis.lower()

    def test_custom_prompts_can_override_defaults(self):
        """Test that custom prompts can be provided via config."""
        custom_prompt = "Custom wiki prompt for testing"
        custom_ollama = ProviderPromptsConfig(
            wiki_system=custom_prompt,
            research_decomposition="custom decomp",
            research_gap_analysis="custom gap",
            research_synthesis="custom synth",
        )
        config = Config(
            prompts=PromptsConfig(ollama=custom_ollama)
        )

        assert config.prompts.ollama.wiki_system == custom_prompt
