# Module: local_deepwiki.plugins.registry

## Module Purpose

The `local_deepwiki.plugins.registry` module provides a plugin registry system for the local_deepwiki project. It enables dynamic discovery, loading, and management of various plugin types including language parsers, wiki generators, and embedding providers. The registry supports loading plugins from directories and entry points, maintaining a collection of registered plugins that can be retrieved by name or used to handle specific file extensions.

## Key Classes and Functions

### PluginRegistry Class

The [`PluginRegistry`](../files/src/local_deepwiki/plugins/registry.md) class is the core component of this module. It maintains dictionaries of registered plugins for different categories:

- [Language](../files/src/local_deepwiki/models/foundation.md) parser plugins (`_language_parsers`)
- Wiki generator plugins (`_wiki_generators`)
- Embedding provider plugins (`_embedding_providers`)

**Methods:**

- `__init__(self)`: Initializes the plugin registry with empty dictionaries for each plugin type and a set to track loaded modules.
- `language_parsers(self)`: Returns a copy of the registered language parser plugins.
- `wiki_generators(self)`: Returns a copy of the registered wiki generator plugins.
- `embedding_providers(self)`: Returns a copy of the registered embedding provider plugins.
- `_register_plugin(self, registry, plugin, name_attr, kind)`: Internal method to register a plugin in the specified registry, handling duplicate warnings and plugin initialization.
- `register_language_parser(self, plugin)`: Registers a language parser plugin.
- `register_wiki_generator(self, plugin)`: Registers a wiki generator plugin.
- `register_embedding_provider(self, plugin)`: Registers an embedding provider plugin.
- `register(self, plugin)`: Raises a `TypeError` for unknown plugin types (currently not implemented for base [`Plugin`](../files/src/local_deepwiki/plugins/base.md)).
- `_unregister_plugin(self, registry, name, kind)`: Internal method to unregister a plugin from the specified registry.
- `unregister_language_parser(self, name)`: Unregisters a language parser plugin by name.
- `unregister_wiki_generator(self, name)`: Unregisters a wiki generator plugin by name.
- `unregister_embedding_provider(self, name)`: Unregisters an embedding provider plugin by name.
- `get_language_parser(self, name)`: Retrieves a language parser plugin by name.
- `get_wiki_generator(self, name)`: Retrieves a wiki generator plugin by name.
- `get_embedding_provider(self, name)`: Retrieves an embedding provider plugin by name.
- `get_parser_for_extension(self, extension)`: Finds a language parser plugin that handles a given file extension.
- `load_from_directory(self, directory)`: Loads plugins from a specified directory by importing Python files.
- `_load_entry_point(self, ep)`: Attempts to load and register a plugin from an entry point.
- `load_from_entry_points(self)`: Loads plugins from entry points using `importlib.metadata`.
- `discover_plugins(self)`: Discovers and loads plugins from both directory and entry point sources.
- `cleanup_all(self)`: Cleans up all registered plugins.
- `list_plugins(self)`: Lists all registered plugins.

## How Components Interact

The [`PluginRegistry`](../files/src/local_deepwiki/plugins/registry.md) class serves as a central hub for plugin management. It allows plugins of different types to be registered and retrieved by name. The registry supports two primary loading mechanisms:

1. **Directory Loading**: Plugins can be loaded from a directory by importing Python files that register themselves with the global registry.
2. **Entry Point Loading**: Plugins can be discovered and loaded via Python's entry point system using `importlib.metadata`.

The registry maintains a mapping of plugin names to plugin instances, and provides methods to find plugins by extension, making it easy to route file processing to the appropriate language parser.

## Usage Examples

```python
from local_deepwiki.plugins.registry import get_plugin_registry

# Get the global plugin registry
registry = get_plugin_registry()

# Register a plugin
registry.register_language_parser(my_parser_plugin)

# Get a plugin by name
parser = registry.get_language_parser("python")

# Get a parser for a specific file extension
parser = registry.get_parser_for_extension(".py")
```

```python
from local_deepwiki.plugins.registry import get_plugin_registry

# Load plugins from a directory
registry = get_plugin_registry()
registry.load_from_directory(Path("/path/to/plugins"))

# Load plugins from entry points
registry.load_from_entry_points()
```

## Dependencies

This module depends on:
- `importlib.util`
- `sys`
- `contextvars.ContextVar`
- `functools.singledispatchmethod`
- `pathlib.Path`
- `typing.Any`, `TypeVar`
- [`local_deepwiki.logging.get_logger`](../files/src/local_deepwiki/logging.md)
- `local_deepwiki.plugins.base` (for plugin base classes)
- `importlib.metadata.entry_points` (for loading plugins from entry points)

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/plugins/registry.py:25-361`](../files/src/local_deepwiki/plugins/registry.md)
- [`src/local_deepwiki/generators/analysis/health_scoring.py:34-39`](../files/src/local_deepwiki/generators/analysis/health_scoring.md)
- [`src/local_deepwiki/generators/analysis/duplication.py:26-37`](../files/src/local_deepwiki/generators/analysis/duplication.md)
- [`src/local_deepwiki/generators/analysis/testability.py:26-37`](../files/src/local_deepwiki/generators/analysis/testability.md)
- [`src/local_deepwiki/export/toc_renderer.py:8-17`](../files/src/local_deepwiki/export/toc_renderer.md)
- [`src/local_deepwiki/export/pdf.py:129-534`](../files/src/local_deepwiki/export/pdf.md)
- [`src/local_deepwiki/generators/analysis/cohesion.py:40-60`](../files/src/local_deepwiki/generators/analysis/cohesion.md)
- [`src/local_deepwiki/generators/analysis/hotspots.py:69-89`](../files/src/local_deepwiki/generators/analysis/hotspots.md)
- [`src/local_deepwiki/logging.py:28-83`](../files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:98-100`](../files/src/local_deepwiki/server.md)


*Showing 10 of 269 source files.*
