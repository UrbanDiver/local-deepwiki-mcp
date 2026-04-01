# plugins Module Documentation

## Module Purpose

The `plugins` module provides a registry-based system for managing and loading plugin components within the Local DeepWiki MCP Server. It enables dynamic discovery and registration of various plugin types including language parsers, wiki generators, and embedding providers. The module supports loading plugins from multiple sources including custom directories, repository-specific locations, user configuration directories, and setuptools entry points.

## Key Classes and Functions

### PluginRegistry Class

The [`PluginRegistry`](../files/src/local_deepwiki/plugins/registry.md) class serves as the central registry for managing different types of plugins within the system. It maintains separate collections for language parsers, wiki generators, and embedding providers, providing methods to register, unregister, and retrieve plugins by name or file extension.

**Methods:**

- `__init__()`: Initializes the plugin registry with empty collections for each plugin type
- `language_parsers()`: Returns a copy of registered language parser plugins
- `wiki_generators()`: Returns a copy of registered wiki generator plugins  
- `embedding_providers()`: Returns a copy of registered embedding provider plugins
- `register_language_parser(plugin)`: Registers a language parser plugin
- `register_wiki_generator(plugin)`: Registers a wiki generator plugin
- `register_embedding_provider(plugin)`: Registers an embedding provider plugin
- `unregister_language_parser(name)`: Removes a language parser plugin by name
- `unregister_wiki_generator(name)`: Removes a wiki generator plugin by name
- `unregister_embedding_provider(name)`: Removes an embedding provider plugin by name
- `get_language_parser(name)`: Retrieves a language parser plugin by name
- `get_wiki_generator(name)`: Retrieves a wiki generator plugin by name
- `get_embedding_provider(name)`: Retrieves an embedding provider plugin by name
- `get_parser_for_extension(extension)`: Finds a language parser that handles a specific file extension
- `load_from_directory(directory)`: Loads plugins from a specified directory
- `load_from_entry_points()`: Loads plugins from setuptools entry points
- `discover_plugins(repo_path, custom_dir)`: Discovers and loads plugins from all configured sources
- `cleanup_all()`: Cleans up all registered plugins by calling their cleanup methods

### Helper Functions

- `get_plugin_registry()`: Returns the global plugin registry instance
- `reset_plugin_registry()`: Resets the global plugin registry to a fresh state

## How Components Interact

The plugin system operates through a centralized [`PluginRegistry`](../files/src/local_deepwiki/plugins/registry.md) that maintains collections of different plugin types. When plugins are discovered through various sources (directories, entry points), they register themselves with the registry using specific registration methods based on their type. The registry provides lookup mechanisms to retrieve plugins by name or by file extension, enabling the core system to dynamically select appropriate plugins for processing code files and generating documentation.

## Usage Examples
```python
from local_deepwiki.plugins.registry import get_plugin_registry

# Get the global plugin registry
registry = get_plugin_registry()

# Discover plugins from all sources
registry.discover_plugins(repo_path="/path/to/repo")

# Register a custom plugin
registry.register(my_language_parser_plugin)

# Retrieve a specific language parser by name
parser = registry.get_language_parser("python")

# Find a parser for a specific file extension
scala_parser = registry.get_parser_for_extension(".scala")
```
## Dependencies

This module depends on:
- `abc` - For abstract base class definitions
- `contextvars` - For context variable management
- `dataclasses` - For data class definitions
- `functools` - For function decorators and utilities
- `importlib` - For dynamic module loading
- `pathlib` - For path manipulation
- `sys` - For system-level operations
- `typing` - For type hints
- `local_deepwiki.logging` - For logging functionality
- `local_deepwiki.models` - For core data models
- `local_deepwiki.plugins.base` - For plugin base classes and metadata definitions
- `importlib.metadata` - For entry point discovery and loading

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/plugins/registry.py:25-394`](../files/src/local_deepwiki/plugins/registry.md)
- `src/local_deepwiki/plugins/__init__.py`
- [`src/local_deepwiki/plugins/base.py:23-33`](../files/src/local_deepwiki/plugins/base.md)
