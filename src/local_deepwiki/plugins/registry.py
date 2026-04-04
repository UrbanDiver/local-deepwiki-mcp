"""Plugin registry for discovering and managing plugins."""

from __future__ import annotations

import importlib.util
import sys
from contextvars import ContextVar
from functools import singledispatchmethod
from pathlib import Path
from typing import Any, TypeVar

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

    def __init__(self) -> None:
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

    def _register_plugin(
        self,
        registry: dict[str, Any],
        plugin: Plugin,
        name_attr: str,
        kind: str,
    ) -> None:
        name = getattr(plugin, name_attr)
        if name in registry:
            logger.warning("%s '%s' already registered, overwriting", kind, name)
        registry[name] = plugin
        plugin.initialize()
        logger.info("Registered %s plugin: %s", kind, plugin.metadata)

    def register_language_parser(self, plugin: LanguageParserPlugin) -> None:
        """Register a language parser plugin."""
        self._register_plugin(
            self._language_parsers, plugin, "language_name", "Language parser"
        )

    def register_wiki_generator(self, plugin: WikiGeneratorPlugin) -> None:
        """Register a wiki generator plugin."""
        self._register_plugin(
            self._wiki_generators, plugin, "generator_name", "Wiki generator"
        )

    def register_embedding_provider(self, plugin: EmbeddingProviderPlugin) -> None:
        """Register an embedding provider plugin."""
        self._register_plugin(
            self._embedding_providers, plugin, "provider_name", "Embedding provider"
        )

    @singledispatchmethod
    def register(self, plugin: Plugin) -> None:
        """Register a plugin based on its type.

        Args:
            plugin: The plugin to register.

        Raises:
            TypeError: If plugin type is not recognized.
        """
        raise TypeError(f"Unknown plugin type: {type(plugin)}")

    @register.register
    def _(self, plugin: LanguageParserPlugin) -> None:
        self.register_language_parser(plugin)

    @register.register
    def _(self, plugin: WikiGeneratorPlugin) -> None:
        self.register_wiki_generator(plugin)

    @register.register
    def _(self, plugin: EmbeddingProviderPlugin) -> None:
        self.register_embedding_provider(plugin)

    def _unregister_plugin(
        self, registry: dict[str, Any], name: str, kind: str
    ) -> bool:
        if name in registry:
            plugin = registry.pop(name)
            plugin.cleanup()
            logger.info("Unregistered %s: %s", kind, name)
            return True
        return False

    def unregister_language_parser(self, name: str) -> bool:
        """Unregister a language parser plugin."""
        return self._unregister_plugin(self._language_parsers, name, "language parser")

    def unregister_wiki_generator(self, name: str) -> bool:
        """Unregister a wiki generator plugin."""
        return self._unregister_plugin(self._wiki_generators, name, "wiki generator")

    def unregister_embedding_provider(self, name: str) -> bool:
        """Unregister an embedding provider plugin."""
        return self._unregister_plugin(
            self._embedding_providers, name, "embedding provider"
        )

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

            except Exception as e:  # noqa: BLE001 — plugin isolation: one bad plugin must not crash the system
                logger.warning("Failed to load plugin %s: %s", py_file, e)

        return loaded

    def _load_entry_point(self, ep: Any) -> bool:
        """Try to load and register a single entry point plugin.

        Returns True on success, False on failure.
        """
        try:
            plugin_class = ep.load()
            plugin = plugin_class()
            self.register(plugin)
            return True
        except Exception as e:  # noqa: BLE001 — plugin isolation: one bad plugin must not crash the system
            logger.warning("Failed to load entry point %s: %s", ep.name, e)
            return False

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
                    for ep in entry_points(group=group):
                        if self._load_entry_point(ep):
                            loaded += 1
            else:
                # Python 3.9 compatibility
                from importlib.metadata import entry_points as get_entry_points

                all_eps = get_entry_points()
                for group in self.ENTRY_POINT_GROUPS.values():
                    if group not in all_eps:
                        continue
                    for ep in all_eps[group]:
                        if self._load_entry_point(ep):
                            loaded += 1

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
            except Exception as e:  # noqa: BLE001 — plugin isolation: one bad plugin must not crash the system
                logger.warning("Error cleaning up parser plugin: %s", e)

        for gen_plugin in self._wiki_generators.values():
            try:
                gen_plugin.cleanup()
            except Exception as e:  # noqa: BLE001 — plugin isolation: one bad plugin must not crash the system
                logger.warning("Error cleaning up generator plugin: %s", e)

        for emb_plugin in self._embedding_providers.values():
            try:
                emb_plugin.cleanup()
            except Exception as e:  # noqa: BLE001 — plugin isolation: one bad plugin must not crash the system
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
_registry_var: ContextVar[PluginRegistry | None] = ContextVar("registry", default=None)


def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry instance.

    Returns:
        The global PluginRegistry singleton.
    """
    val = _registry_var.get()
    if val is None:
        val = PluginRegistry()
        _registry_var.set(val)
    return val


def reset_plugin_registry() -> None:
    """Reset the global plugin registry.

    Useful for testing.
    """
    val = _registry_var.get()
    if val is not None:
        val.cleanup_all()
    _registry_var.set(None)
