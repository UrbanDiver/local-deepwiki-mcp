"""Tests for configuration."""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from local_deepwiki.config import (
    RESEARCH_DECOMPOSITION_PROMPTS,
    RESEARCH_GAP_ANALYSIS_PROMPTS,
    RESEARCH_PRESETS,
    RESEARCH_SYNTHESIS_PROMPTS,
    WIKI_SYSTEM_PROMPTS,
    ASTCacheConfig,
    ChunkingConfig,
    Config,
    DeepResearchConfig,
    PromptsConfig,
    ProviderPromptsConfig,
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

        assert config.embedding.local.model == "multi-qa-MiniLM-L6-cos-v1"
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

        assert config.wiki.max_file_docs == 500  # Increased for larger repos
        assert (
            config.wiki.max_concurrent_llm_calls == 8
        )  # Increased for faster generation
        assert config.wiki.use_cloud_for_github is False
        assert config.wiki.github_llm_provider == "anthropic"
        assert config.wiki.chat_llm_provider == "default"
        assert config.wiki.import_search_limit == 200
        assert config.wiki.context_search_limit == 50
        assert config.wiki.fallback_search_limit == 30

    def test_embedding_cache_config(self):
        """Test embedding cache configuration."""
        config = Config()

        assert config.embedding_cache.enabled is True
        assert config.embedding_cache.ttl_seconds == 604800  # 7 days
        assert config.embedding_cache.max_entries == 100000

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

    def test_ast_cache_config_defaults(self):
        """Test AST cache configuration defaults."""
        config = Config()

        assert config.ast_cache.enabled is True
        assert config.ast_cache.max_entries == 1000
        assert config.ast_cache.ttl_seconds == 3600

    def test_ast_cache_config_custom(self):
        """Test AST cache with custom configuration."""
        config = Config(
            ast_cache={"enabled": False, "max_entries": 500, "ttl_seconds": 1800}
        )

        assert config.ast_cache.enabled is False
        assert config.ast_cache.max_entries == 500
        assert config.ast_cache.ttl_seconds == 1800

    def test_ast_cache_config_validation(self):
        """Test AST cache config validation bounds."""
        from pydantic import ValidationError

        # Test max_entries bounds
        with pytest.raises(ValidationError):
            Config(ast_cache={"max_entries": 50})  # Below min (100)

        with pytest.raises(ValidationError):
            Config(ast_cache={"max_entries": 20000})  # Above max (10000)

        # Test ttl_seconds bounds
        with pytest.raises(ValidationError):
            Config(ast_cache={"ttl_seconds": 30})  # Below min (60)

        with pytest.raises(ValidationError):
            Config(ast_cache={"ttl_seconds": 100000})  # Above max (86400)

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
        # Config classes are frozen, so we use model_copy to create modified versions
        new_chunking = ChunkingConfig().model_copy(update={"max_chunk_tokens": 1024})
        new_config = Config().model_copy(update={"chunking": new_chunking})

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
        """Test context-isolated concurrent access to get_config.

        With ContextVar, each thread gets its own context and lazily
        creates its own Config instance — so we verify that every
        thread receives a valid Config (not that they share one).
        """
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

        # All threads should succeed and get a valid Config
        assert len(errors) == 0
        assert len(results) == 10
        assert all(isinstance(r, Config) for r in results)

    def test_concurrent_set_and_get_config(self):
        """Test context-isolated concurrent set and get operations.

        With ContextVar, each thread's set_config only affects its own
        context, so the read-back always sees exactly the value that
        thread set.
        """
        errors = []

        def modify_config(value: int):
            try:
                new_chunking = ChunkingConfig().model_copy(
                    update={"max_chunk_tokens": value}
                )
                new_config = Config().model_copy(update={"chunking": new_chunking})
                set_config(new_config)
                # Read back — with ContextVar this is always our own value
                retrieved = get_config()
                assert retrieved.chunking.max_chunk_tokens == value
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

        # Config classes are frozen, so we use model_copy to create modified versions
        custom_chunking = ChunkingConfig().model_copy(update={"max_chunk_tokens": 2048})
        custom_config = Config().model_copy(update={"chunking": custom_chunking})

        with config_context(custom_config):
            context_config = get_config()
            assert context_config.chunking.max_chunk_tokens == 2048
            assert context_config is custom_config

        # After context, should return to global
        after_config = get_config()
        assert after_config.chunking.max_chunk_tokens == 512

    def test_config_context_restores_on_exception(self):
        """Test that config_context restores config even on exception."""
        # Config classes are frozen, so we use model_copy to create modified versions
        custom_chunking = ChunkingConfig().model_copy(update={"max_chunk_tokens": 4096})
        custom_config = Config().model_copy(update={"chunking": custom_chunking})

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
        # Config classes are frozen, so we use model_copy to create modified versions
        chunking1 = ChunkingConfig().model_copy(update={"max_chunk_tokens": 1000})
        config1 = Config().model_copy(update={"chunking": chunking1})

        chunking2 = ChunkingConfig().model_copy(update={"max_chunk_tokens": 2000})
        config2 = Config().model_copy(update={"chunking": chunking2})

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
        # Config classes are frozen, so we use model_copy to create modified versions
        custom_chunking = ChunkingConfig().model_copy(update={"max_chunk_tokens": 768})
        custom_config = Config().model_copy(update={"chunking": custom_chunking})

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
        # Config classes are frozen, so we use with_llm_provider to create modified versions
        config_anthropic = Config().with_llm_provider("anthropic")
        prompts_anthropic = config_anthropic.get_prompts()
        assert prompts_anthropic == config_anthropic.prompts.anthropic

        config_openai = Config().with_llm_provider("openai")
        prompts_openai = config_openai.get_prompts()
        assert prompts_openai == config_openai.prompts.openai

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
        assert (
            "code" in config.anthropic.research_synthesis.lower()
            or "architecture" in config.anthropic.research_synthesis.lower()
        )

    def test_custom_prompts_can_override_defaults(self):
        """Test that custom prompts can be provided via config."""
        custom_prompt = "Custom wiki prompt for testing"
        custom_ollama = ProviderPromptsConfig(
            wiki_system=custom_prompt,
            research_decomposition="custom decomp",
            research_gap_analysis="custom gap",
            research_synthesis="custom synth",
        )
        config = Config(prompts=PromptsConfig(ollama=custom_ollama))

        assert config.prompts.ollama.wiki_system == custom_prompt


class TestComputedFields:
    """Tests for Pydantic computed fields."""

    def test_effective_embedding_batch_size_local(self):
        """Test effective_embedding_batch_size for local provider."""
        config = Config()  # Default is local
        assert config.embedding.provider == "local"
        # Local providers can use up to 200
        assert config.effective_embedding_batch_size <= 200
        assert (
            config.effective_embedding_batch_size <= config.embedding_batch.batch_size
        )

    def test_effective_embedding_batch_size_openai(self):
        """Test effective_embedding_batch_size for OpenAI provider."""
        config = Config().with_embedding_provider("openai")
        # API providers should use max 50
        assert config.effective_embedding_batch_size <= 50

    def test_effective_max_workers(self):
        """Test effective_max_workers respects CPU count."""
        import os

        config = Config()
        cpu_count = os.cpu_count() or 4
        assert config.effective_max_workers <= cpu_count
        assert config.effective_max_workers >= 1

    def test_effective_llm_concurrency_ollama(self):
        """Test effective_llm_concurrency caps local models at 3."""
        config = Config()  # Default is ollama
        assert config.llm.provider == "ollama"
        # Local models capped at 3 (single GPU, avoid OOM)
        assert config.effective_llm_concurrency <= 3

    def test_effective_llm_concurrency_cloud(self):
        """Test effective_llm_concurrency allows full concurrency for cloud."""
        config = Config().with_llm_provider("anthropic")
        # Cloud providers get full configured concurrency
        assert config.effective_llm_concurrency == config.wiki.max_concurrent_llm_calls


class TestValidationHooks:
    """Tests for Pydantic validation hooks."""

    def test_chunking_overlap_less_than_max(self):
        """Test overlap_tokens must be less than max_chunk_tokens."""
        from pydantic import ValidationError

        # Valid configuration
        config = Config(chunking={"max_chunk_tokens": 512, "overlap_tokens": 50})
        assert config.chunking.overlap_tokens < config.chunking.max_chunk_tokens

        # Invalid configuration
        with pytest.raises(ValidationError):
            Config(chunking={"max_chunk_tokens": 100, "overlap_tokens": 100})

        with pytest.raises(ValidationError):
            Config(chunking={"max_chunk_tokens": 100, "overlap_tokens": 150})

    def test_wiki_search_limits_consistency(self):
        """Test fallback_search_limit should not exceed context_search_limit."""
        from pydantic import ValidationError

        # Valid configuration
        config = Config(wiki={"context_search_limit": 50, "fallback_search_limit": 30})
        assert config.wiki.fallback_search_limit <= config.wiki.context_search_limit

        # Invalid configuration
        with pytest.raises(ValidationError):
            Config(wiki={"context_search_limit": 30, "fallback_search_limit": 50})

    def test_parallel_workers_capped_at_cpu_count(self):
        """Test parallel_workers is capped at CPU count via validator."""
        import os

        cpu_count = os.cpu_count() or 4
        # Use a value within the Field's le constraint but above CPU count
        # The validator should cap it to CPU count
        test_value = min(32, cpu_count + 4)  # Within 1-32 range but above CPU
        config = Config(chunking={"parallel_workers": test_value})
        # Should be capped at CPU count by the validator
        assert config.chunking.parallel_workers <= cpu_count

    def test_embedding_batch_concurrency_capped(self):
        """Test embedding batch concurrency is capped reasonably via validator."""
        import os

        cpu_count = os.cpu_count() or 4
        max_expected = min(16, cpu_count * 2)
        # Use a value within the Field's le constraint (16)
        config = Config(embedding_batch={"concurrency": 16})
        assert config.embedding_batch.concurrency <= max_expected


class TestConfigDiff:
    """Tests for ConfigDiff class."""

    def test_config_diff_no_changes(self):
        """Test ConfigDiff with identical configs."""
        from local_deepwiki.config import ConfigDiff

        config1 = Config()
        config2 = Config()
        diff = ConfigDiff(config1, config2)

        assert not diff.has_changes()
        assert len(diff.get_changes()) == 0
        assert diff.summary() == "No configuration changes"

    def test_config_diff_detects_changes(self):
        """Test ConfigDiff detects changed fields."""
        from local_deepwiki.config import ConfigDiff

        config1 = Config()
        config2 = Config().with_llm_provider("anthropic")
        diff = ConfigDiff(config1, config2)

        assert diff.has_changes()
        changes = diff.get_changes()
        assert len(changes) >= 1

        # Find the provider change
        provider_changes = [c for c in changes if "provider" in c.field]
        assert len(provider_changes) >= 1
        assert any(c.new_value == "anthropic" for c in provider_changes)

    def test_config_diff_nested_changes(self):
        """Test ConfigDiff detects nested field changes."""
        from local_deepwiki.config import ConfigDiff

        config1 = Config()
        config2 = Config(chunking={"max_chunk_tokens": 1024})
        diff = ConfigDiff(config1, config2)

        assert diff.has_changes()
        changes = diff.get_changes()

        # Find the max_chunk_tokens change
        chunk_changes = [c for c in changes if "max_chunk_tokens" in c.field]
        assert len(chunk_changes) == 1
        assert chunk_changes[0].old_value == 512
        assert chunk_changes[0].new_value == 1024

    def test_config_diff_summary(self):
        """Test ConfigDiff summary is human-readable."""
        from local_deepwiki.config import ConfigDiff

        config1 = Config()
        config2 = Config().with_llm_provider("anthropic")
        diff = ConfigDiff(config1, config2)

        summary = diff.summary()
        assert "Configuration changes" in summary
        assert "anthropic" in summary

    def test_config_diff_apply(self):
        """Test ConfigDiff.apply creates correct config."""
        from local_deepwiki.config import ConfigDiff

        config1 = Config()
        config2 = Config().with_llm_provider("anthropic")
        diff = ConfigDiff(config1, config2)

        # Apply to a fresh config
        config3 = Config()
        result = diff.apply(config3)

        assert result.llm.provider == "anthropic"

    def test_config_change_str(self):
        """Test ConfigChange string representation."""
        from local_deepwiki.config import ConfigChange

        change = ConfigChange(
            field="llm.provider",
            old_value="ollama",
            new_value="anthropic",
            source="cli",
        )
        str_repr = str(change)
        assert "llm.provider" in str_repr
        assert "ollama" in str_repr
        assert "anthropic" in str_repr
        assert "cli" in str_repr


class TestMergeConfigs:
    """Tests for merge_configs function."""

    def test_merge_configs_cli_highest_priority(self):
        """Test CLI config has highest priority."""
        from local_deepwiki.config import merge_configs

        cli = {"llm": {"provider": "anthropic"}}
        env = {"llm": {"provider": "openai"}}
        file = {"llm": {"provider": "ollama"}}

        config, diff = merge_configs(cli, env, file)

        assert config.llm.provider == "anthropic"

    def test_merge_configs_env_over_file(self):
        """Test env config overrides file config."""
        from local_deepwiki.config import merge_configs

        env = {"embedding": {"provider": "openai"}}
        file = {"embedding": {"provider": "local"}}

        config, diff = merge_configs(None, env, file)

        assert config.embedding.provider == "openai"

    def test_merge_configs_file_over_defaults(self):
        """Test file config overrides defaults."""
        from local_deepwiki.config import merge_configs

        file = {"chunking": {"max_chunk_tokens": 1024}}

        config, diff = merge_configs(None, None, file)

        assert config.chunking.max_chunk_tokens == 1024

    def test_merge_configs_diff_tracks_source(self):
        """Test merge_configs diff tracks sources correctly."""
        from local_deepwiki.config import merge_configs

        cli = {"llm": {"provider": "anthropic"}}
        env = {"embedding": {"provider": "openai"}}

        config, diff = merge_configs(cli, env, None)

        # Check sources are tracked
        for change in diff.get_changes():
            if "llm" in change.field and "provider" in change.field:
                assert change.source == "cli"
            elif "embedding" in change.field and "provider" in change.field:
                assert change.source == "env"

    def test_merge_configs_returns_diff(self):
        """Test merge_configs returns ConfigDiff."""
        from local_deepwiki.config import ConfigDiff, merge_configs

        cli = {"llm": {"provider": "anthropic"}}
        config, diff = merge_configs(cli, None, None)

        assert isinstance(diff, ConfigDiff)
        assert diff.has_changes()

    def test_merge_configs_deep_merge(self):
        """Test merge_configs handles nested dicts correctly."""
        from local_deepwiki.config import merge_configs

        cli = {"wiki": {"max_file_docs": 100}}
        file = {"wiki": {"max_concurrent_llm_calls": 4}}

        config, diff = merge_configs(cli, None, file)

        # Both values should be set
        assert config.wiki.max_file_docs == 100
        assert config.wiki.max_concurrent_llm_calls == 4


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_validate_config_default_no_warnings(self):
        """Test default config with local providers has no major warnings."""
        from local_deepwiki.config import validate_config

        config = Config()  # Default uses local/ollama
        warnings = validate_config(config)

        # Default config should not warn about API keys
        api_warnings = [w for w in warnings if "API_KEY" in w]
        assert len(api_warnings) == 0

    def test_validate_config_warns_missing_api_key(self, monkeypatch):
        """Test validate_config warns about missing API keys."""
        from local_deepwiki.config import validate_config

        # Clear API keys
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config = Config().with_llm_provider("anthropic")
        warnings = validate_config(config)

        assert any("ANTHROPIC_API_KEY" in w for w in warnings)

    def test_validate_config_warns_large_batch_size(self, monkeypatch):
        """Test validate_config warns about large batch size with API provider."""
        from local_deepwiki.config import validate_config

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config = Config(
            embedding={"provider": "openai"},
            embedding_batch={"batch_size": 200},
        )
        warnings = validate_config(config)

        assert any("batch_size" in w.lower() for w in warnings)

    def test_validate_config_warns_missing_plugin_dir(self, tmp_path):
        """Test validate_config warns about missing plugin directory."""
        from local_deepwiki.config import validate_config

        fake_dir = tmp_path / "nonexistent_plugins"
        config = Config(plugins={"custom_dir": str(fake_dir)})
        warnings = validate_config(config)

        assert any("plugins directory" in w.lower() for w in warnings)

    def test_validate_config_returns_list(self):
        """Test validate_config always returns a list."""
        from local_deepwiki.config import validate_config

        config = Config()
        warnings = validate_config(config)

        assert isinstance(warnings, list)


class TestLoadConfigFromEnv:
    """Tests for load_config_from_env function."""

    def test_load_config_from_env_parses_values(self, monkeypatch):
        """Test load_config_from_env parses different value types."""
        from local_deepwiki.config import load_config_from_env

        monkeypatch.setenv("DEEPWIKI_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("DEEPWIKI_CHUNKING_MAX_CHUNK_TOKENS", "1024")
        monkeypatch.setenv("DEEPWIKI_PLUGINS_ENABLED", "false")

        env_config = load_config_from_env()

        assert env_config["llm"]["provider"] == "anthropic"
        assert env_config["chunking"]["max_chunk_tokens"] == 1024
        assert env_config["plugins"]["enabled"] is False

    def test_load_config_from_env_ignores_unrelated(self, monkeypatch):
        """Test load_config_from_env ignores non-DEEPWIKI_ variables."""
        from local_deepwiki.config import load_config_from_env

        monkeypatch.setenv("SOME_OTHER_VAR", "value")
        monkeypatch.setenv("DEEPWIKI_LLM_PROVIDER", "anthropic")

        env_config = load_config_from_env()

        assert "some_other_var" not in env_config
        assert "some" not in env_config

    def test_load_config_from_env_parses_floats(self, monkeypatch):
        """Test load_config_from_env parses float values."""
        from local_deepwiki.config import load_config_from_env

        monkeypatch.setenv("DEEPWIKI_DEEPRESEARCH_SYNTHESIS_TEMPERATURE", "0.7")

        env_config = load_config_from_env()

        assert env_config["deepresearch"]["synthesis_temperature"] == 0.7
