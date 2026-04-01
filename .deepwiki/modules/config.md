# `config` Module Documentation

## Module Purpose

The `config` module provides configuration management for the Local DeepWiki MCP Server. It defines pydantic-based models for various aspects of the system's behavior, including LLM and embedding provider settings, wiki generation parameters, search configurations, and processing parameters. The module also includes utilities for loading, validating, and managing configuration profiles.

## Key Classes and Functions

### `Config` Class
The root configuration class that aggregates all other configuration components into a single structured model. It provides methods for computing effective values based on provider types and managing configuration state.

**Methods:**
- `effective_embedding_batch_size()` - Computes optimal embedding batch size based on the current embedding provider
- `effective_max_workers()` - Computes optimal number of parallel workers based on CPU count
- `effective_llm_concurrency()` - Computes effective LLM concurrency based on the current LLM provider
- `with_embedding_provider(provider)` - Returns a new [Config](../files/src/local_deepwiki/config/models.md) instance with updated embedding provider
- `with_llm_provider(provider)` - Returns a new [Config](../files/src/local_deepwiki/config/models.md) instance with updated LLM provider
- `get_prompts()` - Gets prompts for the currently configured LLM provider
- `load(config_path)` - Loads configuration from file or defaults
- `get_wiki_path(repo_path)` - Gets the wiki output path for a repository
- `get_vector_db_path(repo_path)` - Gets the vector database path for a repository

### `ExportBatchConfig` Class
Configuration for HTML and PDF export batch processing, including batch size, memory limits, and streaming mode settings.

### `OutputConfig` Class
Defines output directory and vector database file names for wiki generation.

### `ConfigChange` Class
Represents a change to the configuration, used in the loader module for tracking configuration modifications.

### `ConfigDiff` Class
Used in the loader module to represent differences between configurations.

### Configuration Loading Functions
- `get_config()` - Gets the current configuration instance
- `set_config(config)` - Sets the global configuration instance
- `load_config_from_env()` - Loads configuration from environment variables
- `validate_config(config)` - Validates a configuration instance
- `merge_configs(base, override)` - Merges two configuration instances
- `reset_config()` - Resets the configuration to defaults
- `activate_profile(profile_name)` - Activates a named configuration profile
- `get_active_profile_name()` - Gets the name of the currently active profile
- `save_profile(profile_name)` - Saves the current configuration as a named profile
- `delete_profile(profile_name)` - Deletes a named configuration profile
- `list_profiles()` - Lists all available configuration profiles
- `config_context()` - Context manager for temporarily changing configuration

## How Components Interact

The configuration system is structured with a root [`Config`](../files/src/local_deepwiki/config/models.md) class that aggregates various specialized configuration models. These include:
- LLM and embedding provider configurations ([`LLMConfig`](../files/src/local_deepwiki/config/provider_models.md), [`EmbeddingConfig`](../files/src/local_deepwiki/config/provider_models.md))
- Wiki generation settings ([`WikiConfig`](../files/src/local_deepwiki/config/models_wiki.md), [`DeepResearchConfig`](../files/src/local_deepwiki/config/models_wiki.md))
- Search and indexing configurations ([`SearchConfig`](../files/src/local_deepwiki/config/models_search.md), [`FuzzySearchConfig`](../files/src/local_deepwiki/config/models_search.md), [`GraphRAGConfig`](../files/src/local_deepwiki/config/models_search.md))
- Processing parameters ([`ChunkingConfig`](../files/src/local_deepwiki/config/processing_models.md), [`ASTCacheConfig`](../files/src/local_deepwiki/config/processing_models.md), [`EmbeddingBatchConfig`](../files/src/local_deepwiki/config/processing_models.md))
- Output paths and export settings ([`OutputConfig`](../files/src/local_deepwiki/config/models.md), [`ExportBatchConfig`](../files/src/local_deepwiki/config/models.md))

The [`Config`](../files/src/local_deepwiki/config/models.md) class provides computed properties that adjust values based on provider types (local vs API), ensuring optimal performance and resource usage. Configuration loading utilities allow for profile-based management, enabling users to maintain multiple configuration states.

## Usage Examples

### Loading Configuration```python
from local_deepwiki.config import Config

# Load configuration from default locations or use defaults
config = Config.load()

# Load configuration from a specific file
config = Config.load(Path("/path/to/config.yaml"))
```
### Getting Effective Values```python
from local_deepwiki.config import Config

config = Config.load()
batch_size = config.effective_embedding_batch_size()
workers = config.effective_max_workers()
concurrency = config.effective_llm_concurrency()
```
### Using Configuration Profiles```python
from local_deepwiki.config import save_profile, activate_profile, get_config

# Save current configuration as a profile
save_profile("production")

# Activate a profile
activate_profile("production")

# Get the active configuration
config = get_config()
```
### Creating New Configurations with Different Providers```python
from local_deepwiki.config import Config
from local_deepwiki.models.provider_types import EmbeddingProviderType, LLMProviderType

config = Config.load()

# Change embedding provider
new_config = config.with_embedding_provider(EmbeddingProviderType.LOCAL)

# Change LLM provider
new_config = config.with_llm_provider(LLMProviderType.OLLAMA)
```
## Dependencies

This module depends on:
- `pydantic` for configuration model definitions and validation
- `yaml` for configuration file parsing
- `pathlib` for path operations
- `os` for system operations
- Submodules within the same package:
  - `local_deepwiki.config.models_embedding`
  - `local_deepwiki.config.models_llm`
  - `local_deepwiki.config.models_search`
  - `local_deepwiki.config.models_wiki`
  - `local_deepwiki.config.processing_models`
  - `local_deepwiki.config.prompts`
  - `local_deepwiki.config.provider_models`
  - `local_deepwiki.config.loader`

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/config/models.py:70-92`](../files/src/local_deepwiki/config/models.md)
- [`src/local_deepwiki/config/processing_models.py:28-80`](../files/src/local_deepwiki/config/processing_models.md)
- `src/local_deepwiki/config/__init__.py`
- [`src/local_deepwiki/config/models_search.py:10-33`](../files/src/local_deepwiki/config/models_search.md)
- [`src/local_deepwiki/config/models_wiki.py:12-17`](../files/src/local_deepwiki/config/models_wiki.md)
- [`src/local_deepwiki/config/prompts.py:234-246`](../files/src/local_deepwiki/config/prompts.md)
- [`src/local_deepwiki/config/provider_models.py:10-20`](../files/src/local_deepwiki/config/provider_models.md)
- [`src/local_deepwiki/config/models_llm.py:8-37`](../files/src/local_deepwiki/config/models_llm.md)
- [`src/local_deepwiki/config/loader.py:87-104`](../files/src/local_deepwiki/config/loader.md)
- [`src/local_deepwiki/config/models_embedding.py:8-25`](../files/src/local_deepwiki/config/models_embedding.md)
