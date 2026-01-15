# test_config.py

## File Overview

This file contains comprehensive test suites for the configuration system of the local_deepwiki package. It tests default configuration values, provider-specific settings, global configuration management, and configuration validation across different components including embeddings, LLMs, parsing, chunking, wiki generation, and deep research functionality.

## Classes

### TestConfig

The [main](../src/local_deepwiki/export/html.md) test class that validates the core configuration system functionality.

**Key Test Methods:**
- `test_default_config` - Verifies default configuration values are set correctly
- `test_embedding_config` - Tests embedding provider configuration 
- `test_llm_config` - Validates LLM provider settings including Ollama, Anthropic, and OpenAI models
- `test_parsing_config` - Tests file parsing configuration including exclusion patterns and file size limits
- `test_chunking_config` - Verifies text chunking parameters
- `test_wiki_config` - Tests wiki generation settings
- `test_deep_research_config` - Validates deep research functionality parameters
- `test_deep_research_config_validation` - Tests configuration validation rules
- `test_get_wiki_path` - Tests wiki path generation functionality
- `test_get_vector_db_path` - Tests vector database path generation
- `test_global_config` - Validates global configuration singleton behavior
- `test_set_config` - Tests global configuration updates

### TestThreadSafeConfig

Tests thread safety of the configuration system (class structure shown but methods not detailed in provided code).

### TestConfigContext

Tests configuration context management functionality (class structure shown but methods not detailed in provided code).

### TestResearchPresets

Tests research preset functionality with a method for validating that presets don't modify original configurations:

**Key Methods:**
- `test_with_preset_does_not_modify_original` - Ensures applying presets creates new instances without modifying the original

### TestProviderPrompts

Tests provider-specific prompt configurations across different LLM providers.

**Key Test Methods:**
- `test_provider_prompts_config_has_all_fields` - Validates all required prompt fields are present
- `test_prompts_config_has_all_providers` - Ensures configurations exist for all supported providers (Ollama, Anthropic, OpenAI)
- `test_default_prompts_are_different_per_provider` - Verifies provider-specific prompt variations
- `test_get_for_provider_ollama` - Tests Ollama-specific prompt retrieval
- `test_get_for_provider_anthropic` - Tests Anthropic-specific prompt retrieval
- `test_get_for_provider_openai` - Tests OpenAI-specific prompt retrieval
- `test_get_for_provider_unknown_defaults_to_anthropic` - Validates fallback behavior for unknown providers
- `test_config_get_prompts_uses_current_provider` - Tests dynamic prompt selection based on current provider
- `test_config_get_prompts_changes_with_provider` - Verifies prompt updates when provider changes
- `test_wiki_system_prompts_dict_has_all_providers` - Tests system prompt availability
- `test_research_prompts_dicts_have_all_providers` - Tests research prompt availability
- `test_prompts_contain_essential_instructions` - Validates prompt content quality
- `test_custom_prompts_can_override_defaults` - Tests custom prompt override functionality

## Functions

### reset_global_config

A pytest fixture that resets the global configuration state before and after each test.

```python
def reset_global_config():
    """Reset global config before and after each test."""
    reset_config()
    yield
    reset_config()
```

## Usage Examples

### Testing Default Configuration

```python
def test_default_config(self):
    """Test default configuration values."""
    config = Config()

    assert config.embedding.provider == "local"
    assert config.llm.provider == "ollama"
    assert "python" in config.parsing.languages
    assert config.chunking.max_chunk_tokens == 512
```

### Testing LLM Configuration

```python
def test_llm_config(self):
    """Test LLM configuration."""
    config = Config()

    assert config.llm.ollama.model == "qwen3-coder:30b"
    assert config.llm.ollama.base_url == "http://localhost:11434"
    assert config.llm.anthropic.model == "claude-sonnet-4-20250514"
    assert config.llm.openai.model == "gpt-4o"
```

### Testing Global Configuration Management

```python
def test_set_config(self):
    """Test setting global config."""
    new_config = Config()
    new_config.chunking.max_chunk_tokens = 1024

    set_config(new_config)
    retrieved = get_config()

    assert retrieved.chunking.max_chunk_tokens == 1024
```

### Testing Provider-Specific Prompts

```python
def test_config_get_prompts_changes_with_provider(self):
    """Test Config.get_prompts() changes when provider changes."""
    config = Config()

    # Test with different providers
    config.llm.provider = "anthropic"
    prompts_anthropic = config.get_prompts()
    assert prompts_anthropic == config.prompts.anthropic

    config.llm.provider = "openai"
    prompts_openai = config.get_prompts()
    assert prompts_openai == config.prompts.openai
```

## Related Components

This test file works with several configuration-related components:

- **[Config](../src/local_deepwiki/config.md)** - Main configuration class
- **[DeepResearchConfig](../src/local_deepwiki/config.md)** - Deep research functionality configuration
- **[ProviderPromptsConfig](../src/local_deepwiki/config.md)** - Provider-specific prompt configurations
- **[PromptsConfig](../src/local_deepwiki/config.md)** - Overall prompts configuration
- **[ResearchPreset](../src/local_deepwiki/config.md)** - Research preset configurations
- **RESEARCH_PRESETS** - Available research presets
- **WIKI_SYSTEM_PROMPTS** - System prompts for wiki generation
- **RESEARCH_DECOMPOSITION_PROMPTS** - Prompts for research decomposition
- **RESEARCH_GAP_ANALYSIS_PROMPTS** - Prompts for gap analysis
- **RESEARCH_SYNTHESIS_PROMPTS** - Prompts for research synthesis

The tests also utilize configuration management functions:
- [`config_context`](../src/local_deepwiki/config.md) - Configuration context manager
- [`get_config`](../src/local_deepwiki/config.md) - Global configuration retrieval
- [`reset_config`](../src/local_deepwiki/config.md) - Configuration reset functionality  
- [`set_config`](../src/local_deepwiki/config.md) - Global configuration updates

## API Reference

### class `TestConfig`

Test suite for [Config](../src/local_deepwiki/config.md).

**Methods:**

#### `test_default_config`

```python
def test_default_config()
```

Test default configuration values.

#### `test_embedding_config`

```python
def test_embedding_config()
```

Test embedding configuration.

#### `test_llm_config`

```python
def test_llm_config()
```

Test LLM configuration.

#### `test_parsing_config`

```python
def test_parsing_config()
```

Test parsing configuration.

#### `test_chunking_config`

```python
def test_chunking_config()
```

Test chunking configuration.

#### `test_wiki_config`

```python
def test_wiki_config()
```

Test wiki generation configuration.

#### `test_deep_research_config`

```python
def test_deep_research_config()
```

Test deep research configuration.

#### `test_deep_research_config_validation`

```python
def test_deep_research_config_validation()
```

Test deep research config validation bounds.

#### `test_get_wiki_path`

```python
def test_get_wiki_path(tmp_path)
```

Test wiki path generation.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_get_vector_db_path`

```python
def test_get_vector_db_path(tmp_path)
```

Test vector database path generation.


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_path` | - | - | - |

#### `test_global_config`

```python
def test_global_config()
```

Test global config singleton.

#### `test_set_config`

```python
def test_set_config()
```

Test setting global config.


### class `TestThreadSafeConfig`

Tests for thread-safe config access.

**Methods:**

#### `test_reset_config`

```python
def test_reset_config()
```

Test that [reset_config](../src/local_deepwiki/config.md) clears the global config.

#### `test_concurrent_get_config`

```python
def test_concurrent_get_config()
```

Test thread-safe concurrent access to [get_config](../src/local_deepwiki/config.md).

#### `get_config_thread`

```python
def get_config_thread()
```

#### `test_concurrent_set_and_get_config`

```python
def test_concurrent_set_and_get_config()
```

Test thread-safe concurrent set and get operations.

#### `modify_config`

```python
def modify_config(value: int)
```


| [Parameter](../src/local_deepwiki/generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | `int` | - | - |


### class `TestConfigContext`

Tests for [config_context](../src/local_deepwiki/config.md) context manager.

**Methods:**

#### `test_config_context_overrides_global`

```python
def test_config_context_overrides_global()
```

Test that [config_context](../src/local_deepwiki/config.md) overrides global config.

#### `test_config_context_restores_on_exception`

```python
def test_config_context_restores_on_exception()
```

Test that [config_context](../src/local_deepwiki/config.md) restores config even on exception.

#### `test_nested_config_context`

```python
def test_nested_config_context()
```

Test nested [config_context](../src/local_deepwiki/config.md) calls.

#### `test_config_context_yields_config`

```python
def test_config_context_yields_config()
```

Test that [config_context](../src/local_deepwiki/config.md) yields the provided config.


### class `TestResearchPresets`

Tests for research preset functionality.

**Methods:**

#### `test_research_preset_enum_values`

```python
def test_research_preset_enum_values()
```

Test [ResearchPreset](../src/local_deepwiki/config.md) enum has expected values.

#### `test_research_presets_dict_has_all_presets`

```python
def test_research_presets_dict_has_all_presets()
```

Test RESEARCH_PRESETS has all preset configurations.

#### `test_quick_preset_values`

```python
def test_quick_preset_values()
```

Test quick preset has fewer resources.

#### `test_thorough_preset_values`

```python
def test_thorough_preset_values()
```

Test thorough preset uses more resources.

#### `test_with_preset_none_returns_copy`

```python
def test_with_preset_none_returns_copy()
```

Test with_preset(None) returns unchanged copy.

#### `test_with_preset_default_returns_copy`

```python
def test_with_preset_default_returns_copy()
```

Test with_preset('default') returns unchanged copy.

#### `test_with_preset_quick_applies_values`

```python
def test_with_preset_quick_applies_values()
```

Test with_preset('quick') applies quick preset values.

#### `test_with_preset_thorough_applies_values`

```python
def test_with_preset_thorough_applies_values()
```

Test with_preset('thorough') applies thorough preset values.

#### `test_with_preset_accepts_enum`

```python
def test_with_preset_accepts_enum()
```

Test with_preset accepts [ResearchPreset](../src/local_deepwiki/config.md) enum.

#### `test_with_preset_case_insensitive`

```python
def test_with_preset_case_insensitive()
```

Test with_preset is case-insensitive for string input.

#### `test_with_preset_invalid_returns_copy`

```python
def test_with_preset_invalid_returns_copy()
```

Test with_preset with invalid string returns unchanged copy.

#### `test_with_preset_does_not_modify_original`

```python
def test_with_preset_does_not_modify_original()
```

Test with_preset does not modify the original config.


### class `TestProviderPrompts`

Tests for provider-specific prompts configuration.

**Methods:**

#### `test_provider_prompts_config_has_all_fields`

```python
def test_provider_prompts_config_has_all_fields()
```

Test [ProviderPromptsConfig](../src/local_deepwiki/config.md) has all required prompt fields.

#### `test_prompts_config_has_all_providers`

```python
def test_prompts_config_has_all_providers()
```

Test [PromptsConfig](../src/local_deepwiki/config.md) has configurations for all providers.

#### `test_default_prompts_are_different_per_provider`

```python
def test_default_prompts_are_different_per_provider()
```

Test that default prompts are optimized differently per provider.

#### `test_get_for_provider_ollama`

```python
def test_get_for_provider_ollama()
```

Test get_for_provider returns ollama prompts.

#### `test_get_for_provider_anthropic`

```python
def test_get_for_provider_anthropic()
```

Test get_for_provider returns anthropic prompts.

#### `test_get_for_provider_openai`

```python
def test_get_for_provider_openai()
```

Test get_for_provider returns openai prompts.

#### `test_get_for_provider_unknown_defaults_to_anthropic`

```python
def test_get_for_provider_unknown_defaults_to_anthropic()
```

Test get_for_provider defaults to anthropic for unknown providers.

#### `test_config_get_prompts_uses_current_provider`

```python
def test_config_get_prompts_uses_current_provider()
```

Test [Config](../src/local_deepwiki/config.md).get_prompts() returns prompts for current LLM provider.

#### `test_config_get_prompts_changes_with_provider`

```python
def test_config_get_prompts_changes_with_provider()
```

Test [Config](../src/local_deepwiki/config.md).get_prompts() changes when provider changes.

#### `test_wiki_system_prompts_dict_has_all_providers`

```python
def test_wiki_system_prompts_dict_has_all_providers()
```

Test WIKI_SYSTEM_PROMPTS has entries for all providers.

#### `test_research_prompts_dicts_have_all_providers`

```python
def test_research_prompts_dicts_have_all_providers()
```

Test all research prompt dicts have entries for all providers.

#### `test_prompts_contain_essential_instructions`

```python
def test_prompts_contain_essential_instructions()
```

Test that prompts contain essential instructions.

#### `test_custom_prompts_can_override_defaults`

```python
def test_custom_prompts_can_override_defaults()
```

Test that custom prompts can be provided via config.


---

### Functions

#### `reset_global_config`

`@pytest.fixture(autouse=True)`

```python
def reset_global_config()
```

Reset global config before and after each test.



## Class Diagram

```mermaid
classDiagram
    class TestConfig {
        +test_default_config()
        +test_embedding_config()
        +test_llm_config()
        +test_parsing_config()
        +test_chunking_config()
        +test_wiki_config()
        +test_deep_research_config()
        +test_deep_research_config_validation()
        +test_get_wiki_path(tmp_path)
        +test_get_vector_db_path(tmp_path)
        +test_global_config()
        +test_set_config()
    }
    class TestConfigContext {
        +test_config_context_overrides_global()
        +test_config_context_restores_on_exception()
        +test_nested_config_context()
        +test_config_context_yields_config()
    }
    class TestProviderPrompts {
        +test_provider_prompts_config_has_all_fields()
        +test_prompts_config_has_all_providers()
        +test_default_prompts_are_different_per_provider()
        +test_get_for_provider_ollama()
        +test_get_for_provider_anthropic()
        +test_get_for_provider_openai()
        +test_get_for_provider_unknown_defaults_to_anthropic()
        +test_config_get_prompts_uses_current_provider()
        +test_config_get_prompts_changes_with_provider()
        +test_wiki_system_prompts_dict_has_all_providers()
        +test_research_prompts_dicts_have_all_providers()
        +test_prompts_contain_essential_instructions()
        +test_custom_prompts_can_override_defaults()
    }
    class TestResearchPresets {
        +test_research_preset_enum_values()
        +test_research_presets_dict_has_all_presets()
        +test_quick_preset_values()
        +test_thorough_preset_values()
        +test_with_preset_none_returns_copy()
        +test_with_preset_default_returns_copy()
        +test_with_preset_quick_applies_values()
        +test_with_preset_thorough_applies_values()
        +test_with_preset_accepts_enum()
        +test_with_preset_case_insensitive()
        +test_with_preset_invalid_returns_copy()
        +test_with_preset_does_not_modify_original()
    }
    class TestThreadSafeConfig {
        +test_reset_config()
        +test_concurrent_get_config()
        +get_config_thread()
        +test_concurrent_set_and_get_config()
        +modify_config()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[Config]
    N1[DeepResearchConfig]
    N2[PromptsConfig]
    N3[TestConfig.test_deep_resear...]
    N4[TestConfig.test_get_vector_...]
    N5[TestConfig.test_get_wiki_path]
    N6[TestConfig.test_set_config]
    N7[TestConfigContext.test_conf...]
    N8[TestConfigContext.test_conf...]
    N9[TestConfigContext.test_conf...]
    N10[TestConfigContext.test_nest...]
    N11[TestProviderPrompts.test_cu...]
    N12[TestResearchPresets.test_wi...]
    N13[TestResearchPresets.test_wi...]
    N14[TestResearchPresets.test_wi...]
    N15[TestResearchPresets.test_wi...]
    N16[TestResearchPresets.test_wi...]
    N17[TestResearchPresets.test_wi...]
    N18[TestResearchPresets.test_wi...]
    N19[TestResearchPresets.test_wi...]
    N20[TestThreadSafeConfig.modify...]
    N21[TestThreadSafeConfig.test_c...]
    N22[TestThreadSafeConfig.test_c...]
    N23[TestThreadSafeConfig.test_r...]
    N24[config_context]
    N25[get_config]
    N26[get_for_provider]
    N27[reset_config]
    N28[set_config]
    N29[with_preset]
    N3 --> N0
    N5 --> N0
    N4 --> N0
    N6 --> N0
    N6 --> N28
    N6 --> N25
    N23 --> N25
    N23 --> N27
    N21 --> N25
    N22 --> N0
    N22 --> N28
    N22 --> N25
    N20 --> N0
    N20 --> N28
    N20 --> N25
    N7 --> N25
    N7 --> N0
    N7 --> N24
    N8 --> N0
    N8 --> N24
    N8 --> N25
    N10 --> N0
    N10 --> N24
    N10 --> N25
    N9 --> N0
    N9 --> N24
    N17 --> N1
    N17 --> N29
    N14 --> N1
    N14 --> N29
    N18 --> N1
    N18 --> N29
    N19 --> N1
    N19 --> N29
    N12 --> N1
    N12 --> N29
    N13 --> N1
    N13 --> N29
    N16 --> N1
    N16 --> N29
    N15 --> N1
    N15 --> N29
    N11 --> N0
    N11 --> N2
    classDef func fill:#e1f5fe
    class N0,N1,N2,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23 method
```

## Relevant Source Files

- `tests/test_config.py:35-150`

## See Also

- [config](../src/local_deepwiki/config.md) - dependency
- [test_indexer](test_indexer.md) - shares 3 dependencies
- [test_chunker](test_chunker.md) - shares 2 dependencies
