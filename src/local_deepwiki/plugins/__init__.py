"""Plugin system for local-deepwiki.

Supports three types of plugins:
- Language Parser Plugins: Add support for new programming languages
- Wiki Generator Plugins: Add custom wiki page generators
- Embedding Provider Plugins: Add custom embedding providers

Plugins can be loaded from:
1. Entry points (setuptools/pyproject.toml) - for installed packages
2. Repository's .deepwiki/plugins/ directory - for project-specific plugins
3. User's ~/.config/local-deepwiki/plugins/ directory - for user-wide plugins
4. Config-specified directory
"""

from __future__ import annotations

from local_deepwiki.plugins.base import (
    EmbeddingProviderPlugin,
    LanguageParserPlugin,
    Plugin,
    PluginMetadata,
    WikiGeneratorPlugin,
)
from local_deepwiki.plugins.registry import PluginRegistry, get_plugin_registry

__all__ = [
    "Plugin",
    "PluginMetadata",
    "LanguageParserPlugin",
    "WikiGeneratorPlugin",
    "EmbeddingProviderPlugin",
    "PluginRegistry",
    "get_plugin_registry",
]
