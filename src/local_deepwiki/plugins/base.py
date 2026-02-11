"""Base classes for local-deepwiki plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from local_deepwiki.models import CodeChunk, IndexStatus, WikiPage


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


class Plugin(ABC):
    """Base class for all plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        pass

    def initialize(self) -> None:
        """Initialize the plugin.

        Called when the plugin is loaded. Override to perform setup.
        """
        pass

    def cleanup(self) -> None:
        """Clean up plugin resources.

        Called when the plugin is unloaded. Override to release resources.
        """
        pass


class LanguageParserPlugin(Plugin):
    """Plugin for adding support for new programming languages.

    Subclass this to add parsing support for languages not built into
    local-deepwiki.

    Example:
        class ScalaParserPlugin(LanguageParserPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="scala-parser",
                    version="1.0.0",
                    description="Scala language support",
                )

            @property
            def language_name(self) -> str:
                return "scala"

            @property
            def file_extensions(self) -> list[str]:
                return [".scala", ".sc"]

            def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
                # Parse Scala source and return chunks
                ...
    """

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Get the language name (lowercase, e.g., 'scala', 'elixir')."""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """Get list of file extensions this plugin handles.

        Include the dot, e.g., ['.scala', '.sc'].
        """
        pass

    @abstractmethod
    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        """Parse a source file and extract code chunks.

        Args:
            file_path: Path to the source file.
            source: The file contents as bytes.

        Returns:
            List of CodeChunk objects extracted from the file.
        """
        pass

    def detect_language(self, file_path: Path) -> bool:
        """Check if this plugin can handle the given file.

        Args:
            file_path: Path to check.

        Returns:
            True if this plugin should handle the file.
        """
        return file_path.suffix.lower() in self.file_extensions


@dataclass
class WikiGeneratorResult:
    """Result from a wiki generator plugin."""

    pages: list[WikiPage]
    """Generated wiki pages."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Optional metadata about the generation."""


class WikiGeneratorPlugin(Plugin):
    """Plugin for adding custom wiki page generators.

    Subclass this to add new types of wiki pages or sections.

    Example:
        class APIDocsGeneratorPlugin(WikiGeneratorPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="api-docs-generator",
                    version="1.0.0",
                    description="Generate API documentation pages",
                )

            @property
            def generator_name(self) -> str:
                return "api_docs"

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                # Generate API documentation pages
                ...
    """

    @property
    @abstractmethod
    def generator_name(self) -> str:
        """Get the generator name (used for identification)."""
        pass

    @property
    def priority(self) -> int:
        """Get the generator priority (higher runs first).

        Default is 0. Built-in generators run at priority 100.
        """
        return 0

    @property
    def run_after(self) -> list[str]:
        """Get list of generator names this should run after.

        Use this for generators that depend on output from other generators.
        """
        return []

    @abstractmethod
    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        """Generate wiki pages.

        Args:
            index_status: The repository index status.
            wiki_path: Path to the wiki output directory.
            context: Context dictionary with:
                - 'vector_store': VectorStore instance
                - 'llm': LLM provider instance
                - 'config': Config instance
                - 'existing_pages': List of already-generated WikiPage objects

        Returns:
            WikiGeneratorResult with generated pages.
        """
        pass


class EmbeddingProviderPlugin(Plugin):
    """Plugin for adding custom embedding providers.

    Subclass this to add support for custom embedding models or services.

    Example:
        class CohereEmbeddingPlugin(EmbeddingProviderPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="cohere-embeddings",
                    version="1.0.0",
                    description="Cohere embedding support",
                )

            @property
            def provider_name(self) -> str:
                return "cohere"

            async def embed(self, texts: list[str]) -> list[list[float]]:
                # Call Cohere API to generate embeddings
                ...

            def get_dimension(self) -> int:
                return 1024  # Cohere embed-english-v3.0 dimension
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name (used in config)."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        pass
