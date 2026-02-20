"""Plugin registry for discovering and managing plugins."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TypeVar

from local_deepwiki.logging import get_logger
from local_deepwiki.plugins.base import (
    EmbeddingProviderPlugin,
    LanguageParserPlugin,
    Plugin,
    WikiGeneratorPlugin,
)

logger = get_logger(__name__)

T = TypeVar("T", bound=Plugin)


class PluginRegistry:
    """Registry for discovering and managing plugins."""

    # Entry point group names for setuptools-based plugins
    ENTRY_POINT_GROUPS = {
        "language_parser": "local_deepwiki.plugins.parsers",
        "wiki_generator": "local_deepwiki.plugins.generators",
        "embedding_provider": "local_deepwiki.plugins.embeddings",
    }

    def __init__(self):
        """Initialize the plugin registry."""
        self._language_parsers: dict[str, LanguageParserPlugin] = {}
        self._wiki_generators: dict[str, WikiGeneratorPlugin] = {}
        self._embedding_providers: dict[str, EmbeddingProviderPlugin] = {}
        self._loaded_modules: set[str] = set()

    @property
    def language_parsers(self) -> dict[str, LanguageParserPlugin]:
        """Get registered language parser plugins."""
        return self._language_parsers.copy()

    @property
    def wiki_generators(self) -> dict[str, WikiGeneratorPlugin]:
        """Get registered wiki generator plugins."""
        return self._wiki_generators.copy()

    @property
    def embedding_providers(self) -> dict[str, EmbeddingProviderPlugin]:
        """Get registered embedding provider plugins."""
        return self._embedding_providers.copy()

    def register_language_parser(self, plugin: LanguageParserPlugin) -> None:
        """Register a language parser plugin.

        Args:
            plugin: The plugin to register.
        """
        name = plugin.language_name
        if name in self._language_parsers:
            logger.warning("Language parser '%s' already registered, overwriting", name)
        self._language_parsers[name] = plugin
        plugin.initialize()
        logger.info("Registered language parser plugin: %s", plugin.metadata)

    def register_wiki_generator(self, plugin: WikiGeneratorPlugin) -> None:
        """Register a wiki generator plugin.

        Args:
            plugin: The plugin to register.
        """
        name = plugin.generator_name
        if name in self._wiki_generators:
            logger.warning("Wiki generator '%s' already registered, overwriting", name)
        self._wiki_generators[name] = plugin
        plugin.initialize()
        logger.info("Registered wiki generator plugin: %s", plugin.metadata)

    def register_embedding_provider(self, plugin: EmbeddingProviderPlugin) -> None:
        """Register an embedding provider plugin.

        Args:
            plugin: The plugin to register.
        """
        name = plugin.provider_name
        if name in self._embedding_providers:
            logger.warning(
                "Embedding provider '%s' already registered, overwriting", name
            )
        self._embedding_providers[name] = plugin
        plugin.initialize()
        logger.info("Registered embedding provider plugin: %s", plugin.metadata)

    def register(self, plugin: Plugin) -> None:
        """Register a plugin based on its type.

        Args:
            plugin: The plugin to register.

        Raises:
            TypeError: If plugin type is not recognized.
        """
        if isinstance(plugin, LanguageParserPlugin):
            self.register_language_parser(plugin)
        elif isinstance(plugin, WikiGeneratorPlugin):
            self.register_wiki_generator(plugin)
        elif isinstance(plugin, EmbeddingProviderPlugin):
            self.register_embedding_provider(plugin)
        else:
            raise TypeError(f"Unknown plugin type: {type(plugin)}")

    def unregister_language_parser(self, name: str) -> bool:
        """Unregister a language parser plugin.

        Args:
            name: The language name.

        Returns:
            True if plugin was unregistered, False if not found.
        """
        if name in self._language_parsers:
            plugin = self._language_parsers.pop(name)
            plugin.cleanup()
            logger.info("Unregistered language parser: %s", name)
            return True
        return False

    def unregister_wiki_generator(self, name: str) -> bool:
        """Unregister a wiki generator plugin.

        Args:
            name: The generator name.

        Returns:
            True if plugin was unregistered, False if not found.
        """
        if name in self._wiki_generators:
            plugin = self._wiki_generators.pop(name)
            plugin.cleanup()
            logger.info("Unregistered wiki generator: %s", name)
            return True
        return False

    def unregister_embedding_provider(self, name: str) -> bool:
        """Unregister an embedding provider plugin.

        Args:
            name: The provider name.

        Returns:
            True if plugin was unregistered, False if not found.
        """
        if name in self._embedding_providers:
            plugin = self._embedding_providers.pop(name)
            plugin.cleanup()
            logger.info("Unregistered embedding provider: %s", name)
            return True
        return False

    def get_language_parser(self, name: str) -> LanguageParserPlugin | None:
        """Get a language parser plugin by name.

        Args:
            name: The language name.

        Returns:
            The plugin or None if not found.
        """
        return self._language_parsers.get(name)

    def get_wiki_generator(self, name: str) -> WikiGeneratorPlugin | None:
        """Get a wiki generator plugin by name.

        Args:
            name: The generator name.

        Returns:
            The plugin or None if not found.
        """
        return self._wiki_generators.get(name)

    def get_embedding_provider(self, name: str) -> EmbeddingProviderPlugin | None:
        """Get an embedding provider plugin by name.

        Args:
            name: The provider name.

        Returns:
            The plugin or None if not found.
        """
        return self._embedding_providers.get(name)

    def get_parser_for_extension(self, extension: str) -> LanguageParserPlugin | None:
        """Find a language parser plugin that handles a file extension.

        Args:
            extension: The file extension (with dot, e.g., '.scala').

        Returns:
            The plugin or None if no plugin handles this extension.
        """
        ext_lower = extension.lower()
        for plugin in self._language_parsers.values():
            if ext_lower in [e.lower() for e in plugin.file_extensions]:
                return plugin
        return None

    def load_from_directory(self, directory: Path) -> int:
        """Load plugins from a directory.

        Looks for Python files in the directory and imports them.
        Plugin files should register themselves using the global registry.

        Args:
            directory: Path to the plugins directory.

        Returns:
            Number of plugins loaded.
        """
        if not directory.exists() or not directory.is_dir():
            return 0

        loaded = 0
        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = f"local_deepwiki_plugin_{py_file.stem}"
            if module_name in self._loaded_modules:
                logger.debug("Plugin module already loaded: %s", module_name)
                continue

            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec is None or spec.loader is None:
                    logger.warning("Could not load plugin spec: %s", py_file)
                    continue

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                self._loaded_modules.add(module_name)
                loaded += 1
                logger.debug("Loaded plugin module: %s", py_file.name)

            except Exception as e:  # Broad catch: plugin isolation — one bad plugin must not crash the system
                logger.warning("Failed to load plugin %s: %s", py_file, e)

        return loaded

    def load_from_entry_points(self) -> int:
        """Load plugins from setuptools entry points.

        Discovers plugins registered via pyproject.toml or setup.py
        entry points in the local_deepwiki.plugins.* groups.

        Returns:
            Number of plugins loaded.
        """
        loaded = 0

        try:
            if sys.version_info >= (3, 10):
                from importlib.metadata import entry_points

                for group in self.ENTRY_POINT_GROUPS.values():
                    eps = entry_points(group=group)
                    for ep in eps:
                        try:
                            plugin_class = ep.load()
                            plugin = plugin_class()
                            self.register(plugin)
                            loaded += 1
                        except Exception as e:  # Broad catch: plugin isolation — one bad plugin must not crash the system
                            logger.warning(
                                "Failed to load entry point %s: %s", ep.name, e
                            )
            else:
                # Python 3.9 compatibility
                from importlib.metadata import entry_points as get_entry_points

                all_eps = get_entry_points()
                for group in self.ENTRY_POINT_GROUPS.values():
                    if group in all_eps:
                        for ep in all_eps[group]:
                            try:
                                plugin_class = ep.load()
                                plugin = plugin_class()
                                self.register(plugin)
                                loaded += 1
                            except Exception as e:  # Broad catch: plugin isolation — one bad plugin must not crash the system
                                logger.warning(
                                    "Failed to load entry point %s: %s", ep.name, e
                                )

        except ImportError:
            logger.debug("importlib.metadata not available, skipping entry points")

        return loaded

    def discover_plugins(
        self,
        repo_path: Path | None = None,
        custom_dir: Path | None = None,
    ) -> int:
        """Discover and load plugins from all sources.

        Searches in order:
        1. Custom directory (if specified)
        2. Repository's .deepwiki/plugins/ directory
        3. User's ~/.config/local-deepwiki/plugins/
        4. Setuptools entry points

        Args:
            repo_path: Optional repository path for project-specific plugins.
            custom_dir: Optional custom plugins directory.

        Returns:
            Total number of plugins loaded.
        """
        loaded = 0

        # 1. Custom directory
        if custom_dir:
            loaded += self.load_from_directory(custom_dir)

        # 2. Repository plugins
        if repo_path:
            repo_plugins = repo_path / ".deepwiki" / "plugins"
            loaded += self.load_from_directory(repo_plugins)

        # 3. User plugins
        user_plugins = Path.home() / ".config" / "local-deepwiki" / "plugins"
        loaded += self.load_from_directory(user_plugins)

        # 4. Entry points
        loaded += self.load_from_entry_points()

        logger.info(
            "Plugin discovery complete: %d parsers, %d generators, %d embedding providers",
            len(self._language_parsers),
            len(self._wiki_generators),
            len(self._embedding_providers),
        )

        return loaded

    def cleanup_all(self) -> None:
        """Clean up all registered plugins."""
        for plugin in self._language_parsers.values():
            try:
                plugin.cleanup()
            except Exception as e:  # Broad catch: plugin isolation — one bad plugin must not crash the system
                logger.warning("Error cleaning up parser plugin: %s", e)

        for gen_plugin in self._wiki_generators.values():
            try:
                gen_plugin.cleanup()
            except Exception as e:  # Broad catch: plugin isolation — one bad plugin must not crash the system
                logger.warning("Error cleaning up generator plugin: %s", e)

        for emb_plugin in self._embedding_providers.values():
            try:
                emb_plugin.cleanup()
            except Exception as e:  # Broad catch: plugin isolation — one bad plugin must not crash the system
                logger.warning("Error cleaning up embedding plugin: %s", e)

        self._language_parsers.clear()
        self._wiki_generators.clear()
        self._embedding_providers.clear()
        self._loaded_modules.clear()

    def list_plugins(self) -> dict[str, list[str]]:
        """List all registered plugins by type.

        Returns:
            Dict mapping plugin type to list of plugin names.
        """
        return {
            "language_parsers": list(self._language_parsers.keys()),
            "wiki_generators": list(self._wiki_generators.keys()),
            "embedding_providers": list(self._embedding_providers.keys()),
        }


# Global plugin registry singleton
_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry instance.

    Returns:
        The global PluginRegistry singleton.
    """
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def reset_plugin_registry() -> None:
    """Reset the global plugin registry.

    Useful for testing.
    """
    global _registry
    if _registry is not None:
        _registry.cleanup_all()
    _registry = None
