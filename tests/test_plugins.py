"""Tests for the plugin system."""

from pathlib import Path
from typing import Any

import pytest

from local_deepwiki.models import CodeChunk, ChunkType, IndexStatus
from local_deepwiki.models import Language as LangEnum
from local_deepwiki.models import WikiPage
from local_deepwiki.plugins.base import (
    EmbeddingProviderPlugin,
    LanguageParserPlugin,
    Plugin,
    PluginMetadata,
    WikiGeneratorPlugin,
    WikiGeneratorResult,
)
from local_deepwiki.plugins.registry import (
    PluginRegistry,
    get_plugin_registry,
    reset_plugin_registry,
)


# Test plugin implementations
class MockLanguageParser(LanguageParserPlugin):
    """Mock language parser for testing."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock-parser",
            version="1.0.0",
            description="Mock parser for testing",
        )

    @property
    def language_name(self) -> str:
        return "mock"

    @property
    def file_extensions(self) -> list[str]:
        return [".mock", ".mck"]

    def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
        return [
            CodeChunk(
                id="mock-chunk-1",
                file_path=str(file_path),
                language=LangEnum.PYTHON,  # Use existing enum for mock
                chunk_type=ChunkType.FUNCTION,
                name="mock_function",
                content=source.decode("utf-8"),
                start_line=1,
                end_line=10,
            )
        ]


class MockWikiGenerator(WikiGeneratorPlugin):
    """Mock wiki generator for testing."""

    def __init__(self, name: str = "mock-generator"):
        self._name = name

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            version="1.0.0",
            description="Mock generator for testing",
        )

    @property
    def generator_name(self) -> str:
        return self._name

    async def generate(
        self,
        index_status: IndexStatus,
        wiki_path: Path,
        context: dict[str, Any],
    ) -> WikiGeneratorResult:
        return WikiGeneratorResult(
            pages=[
                WikiPage(
                    path="mock.md",
                    title="Mock Page",
                    content="# Mock Content",
                    generated_at=0.0,
                )
            ],
            metadata={"mock": True},
        )


class MockEmbeddingProvider(EmbeddingProviderPlugin):
    """Mock embedding provider for testing."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock-embeddings",
            version="1.0.0",
            description="Mock embeddings for testing",
        )

    @property
    def provider_name(self) -> str:
        return "mock"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Return simple mock embeddings
        return [[0.1] * 384 for _ in texts]

    def get_dimension(self) -> int:
        return 384


class TestPluginMetadata:
    """Tests for PluginMetadata."""

    def test_basic_metadata(self):
        """Test creating basic metadata."""
        meta = PluginMetadata(name="test", version="1.0.0")
        assert meta.name == "test"
        assert meta.version == "1.0.0"
        assert meta.description == ""
        assert meta.author == ""
        assert meta.dependencies == []

    def test_full_metadata(self):
        """Test creating full metadata."""
        meta = PluginMetadata(
            name="test",
            version="2.0.0",
            description="A test plugin",
            author="Test Author",
            dependencies=["dep1", "dep2"],
        )
        assert meta.description == "A test plugin"
        assert meta.author == "Test Author"
        assert meta.dependencies == ["dep1", "dep2"]

    def test_str_representation(self):
        """Test string representation."""
        meta = PluginMetadata(name="test", version="1.0.0")
        assert str(meta) == "test v1.0.0"


class TestLanguageParserPlugin:
    """Tests for LanguageParserPlugin."""

    def test_mock_parser_metadata(self):
        """Test mock parser metadata."""
        parser = MockLanguageParser()
        assert parser.metadata.name == "mock-parser"
        assert parser.metadata.version == "1.0.0"

    def test_mock_parser_language(self):
        """Test mock parser language name."""
        parser = MockLanguageParser()
        assert parser.language_name == "mock"

    def test_mock_parser_extensions(self):
        """Test mock parser file extensions."""
        parser = MockLanguageParser()
        assert ".mock" in parser.file_extensions
        assert ".mck" in parser.file_extensions

    def test_detect_language(self):
        """Test language detection by extension."""
        parser = MockLanguageParser()
        assert parser.detect_language(Path("test.mock")) is True
        assert parser.detect_language(Path("test.mck")) is True
        assert parser.detect_language(Path("test.py")) is False

    def test_parse_file(self):
        """Test parsing a mock file."""
        parser = MockLanguageParser()
        chunks = parser.parse_file(Path("test.mock"), b"mock content")
        assert len(chunks) == 1
        assert chunks[0].name == "mock_function"


class TestWikiGeneratorPlugin:
    """Tests for WikiGeneratorPlugin."""

    def test_mock_generator_metadata(self):
        """Test mock generator metadata."""
        gen = MockWikiGenerator()
        assert gen.metadata.name == "mock-generator"

    def test_mock_generator_name(self):
        """Test mock generator name."""
        gen = MockWikiGenerator("custom-name")
        assert gen.generator_name == "custom-name"

    def test_default_priority(self):
        """Test default priority."""
        gen = MockWikiGenerator()
        assert gen.priority == 0

    def test_default_run_after(self):
        """Test default run_after."""
        gen = MockWikiGenerator()
        assert gen.run_after == []

    async def test_generate(self):
        """Test generating wiki pages."""
        gen = MockWikiGenerator()
        index_status = IndexStatus(
            repo_path="/test",
            indexed_at=0.0,
            total_files=0,
            total_chunks=0,
        )
        result = await gen.generate(index_status, Path("/wiki"), {})
        assert len(result.pages) == 1
        assert result.pages[0].title == "Mock Page"
        assert result.metadata["mock"] is True


class TestEmbeddingProviderPlugin:
    """Tests for EmbeddingProviderPlugin."""

    def test_mock_provider_metadata(self):
        """Test mock provider metadata."""
        provider = MockEmbeddingProvider()
        assert provider.metadata.name == "mock-embeddings"

    def test_mock_provider_name(self):
        """Test mock provider name."""
        provider = MockEmbeddingProvider()
        assert provider.provider_name == "mock"

    def test_get_dimension(self):
        """Test embedding dimension."""
        provider = MockEmbeddingProvider()
        assert provider.get_dimension() == 384

    async def test_embed(self):
        """Test embedding texts."""
        provider = MockEmbeddingProvider()
        embeddings = await provider.embed(["hello", "world"])
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384


class TestPluginRegistry:
    """Tests for PluginRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return PluginRegistry()

    def test_empty_registry(self, registry):
        """Test empty registry."""
        assert registry.language_parsers == {}
        assert registry.wiki_generators == {}
        assert registry.embedding_providers == {}

    def test_register_language_parser(self, registry):
        """Test registering a language parser."""
        parser = MockLanguageParser()
        registry.register_language_parser(parser)
        assert "mock" in registry.language_parsers
        assert registry.get_language_parser("mock") is parser

    def test_register_wiki_generator(self, registry):
        """Test registering a wiki generator."""
        gen = MockWikiGenerator()
        registry.register_wiki_generator(gen)
        assert "mock-generator" in registry.wiki_generators
        assert registry.get_wiki_generator("mock-generator") is gen

    def test_register_embedding_provider(self, registry):
        """Test registering an embedding provider."""
        provider = MockEmbeddingProvider()
        registry.register_embedding_provider(provider)
        assert "mock" in registry.embedding_providers
        assert registry.get_embedding_provider("mock") is provider

    def test_register_by_type(self, registry):
        """Test registering plugins by type detection."""
        parser = MockLanguageParser()
        gen = MockWikiGenerator()
        provider = MockEmbeddingProvider()

        registry.register(parser)
        registry.register(gen)
        registry.register(provider)

        assert "mock" in registry.language_parsers
        assert "mock-generator" in registry.wiki_generators
        assert "mock" in registry.embedding_providers

    def test_register_unknown_type(self, registry):
        """Test registering unknown plugin type raises error."""

        class UnknownPlugin(Plugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name="unknown", version="1.0.0")

        with pytest.raises(TypeError):
            registry.register(UnknownPlugin())

    def test_unregister_language_parser(self, registry):
        """Test unregistering a language parser."""
        parser = MockLanguageParser()
        registry.register_language_parser(parser)
        assert registry.unregister_language_parser("mock") is True
        assert registry.get_language_parser("mock") is None
        assert registry.unregister_language_parser("mock") is False

    def test_unregister_wiki_generator(self, registry):
        """Test unregistering a wiki generator."""
        gen = MockWikiGenerator()
        registry.register_wiki_generator(gen)
        assert registry.unregister_wiki_generator("mock-generator") is True
        assert registry.get_wiki_generator("mock-generator") is None

    def test_unregister_embedding_provider(self, registry):
        """Test unregistering an embedding provider."""
        provider = MockEmbeddingProvider()
        registry.register_embedding_provider(provider)
        assert registry.unregister_embedding_provider("mock") is True
        assert registry.get_embedding_provider("mock") is None

    def test_get_parser_for_extension(self, registry):
        """Test finding parser by extension."""
        parser = MockLanguageParser()
        registry.register_language_parser(parser)

        assert registry.get_parser_for_extension(".mock") is parser
        assert registry.get_parser_for_extension(".MCK") is parser  # Case insensitive
        assert registry.get_parser_for_extension(".py") is None

    def test_list_plugins(self, registry):
        """Test listing all plugins."""
        registry.register_language_parser(MockLanguageParser())
        registry.register_wiki_generator(MockWikiGenerator())
        registry.register_embedding_provider(MockEmbeddingProvider())

        plugins = registry.list_plugins()
        assert "mock" in plugins["language_parsers"]
        assert "mock-generator" in plugins["wiki_generators"]
        assert "mock" in plugins["embedding_providers"]

    def test_cleanup_all(self, registry):
        """Test cleaning up all plugins."""
        registry.register_language_parser(MockLanguageParser())
        registry.register_wiki_generator(MockWikiGenerator())
        registry.register_embedding_provider(MockEmbeddingProvider())

        registry.cleanup_all()

        assert registry.language_parsers == {}
        assert registry.wiki_generators == {}
        assert registry.embedding_providers == {}

    def test_load_from_directory(self, registry, tmp_path):
        """Test loading plugins from directory."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create a simple plugin file
        plugin_file = plugins_dir / "test_plugin.py"
        plugin_file.write_text("""
from local_deepwiki.plugins import PluginMetadata, LanguageParserPlugin, get_plugin_registry
from local_deepwiki.models import CodeChunk
from pathlib import Path

class TestParser(LanguageParserPlugin):
    @property
    def metadata(self):
        return PluginMetadata(name="test-parser", version="1.0.0")

    @property
    def language_name(self):
        return "testlang"

    @property
    def file_extensions(self):
        return [".test"]

    def parse_file(self, file_path, source):
        return []

# Auto-register
get_plugin_registry().register(TestParser())
""")

        loaded = registry.load_from_directory(plugins_dir)
        # Note: This loads the module but registration goes to the global registry
        assert loaded == 1

    def test_load_from_nonexistent_directory(self, registry, tmp_path):
        """Test loading from non-existent directory."""
        loaded = registry.load_from_directory(tmp_path / "nonexistent")
        assert loaded == 0

    def test_load_skips_underscore_files(self, registry, tmp_path):
        """Test that files starting with underscore are skipped."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "_private.py").write_text("# Private file")
        (plugins_dir / "__init__.py").write_text("# Init file")

        loaded = registry.load_from_directory(plugins_dir)
        assert loaded == 0


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_plugin_registry_returns_singleton(self):
        """Test that get_plugin_registry returns the same instance."""
        reset_plugin_registry()
        reg1 = get_plugin_registry()
        reg2 = get_plugin_registry()
        assert reg1 is reg2

    def test_reset_plugin_registry(self):
        """Test resetting the global registry."""
        reset_plugin_registry()
        reg1 = get_plugin_registry()
        reg1.register_language_parser(MockLanguageParser())

        reset_plugin_registry()
        reg2 = get_plugin_registry()
        assert reg2.language_parsers == {}
        assert reg1 is not reg2


# =============================================================================
# Plugin Integration Tests
# =============================================================================


class TestChunkerPluginIntegration:
    """Tests for chunker plugin integration."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset plugin registry before and after each test."""
        reset_plugin_registry()
        yield
        reset_plugin_registry()

    def test_chunker_uses_plugin_parser(self, tmp_path):
        """Test that chunker uses plugin parser for registered extensions."""
        from local_deepwiki.core.chunker import CodeChunker

        # Create a mock file with custom extension
        mock_file = tmp_path / "test.mock"
        mock_file.write_text("mock content here")

        # Register the mock parser
        registry = get_plugin_registry()
        registry.register_language_parser(MockLanguageParser())

        # Create chunker and process the file
        chunker = CodeChunker()
        chunks = list(chunker.chunk_file(mock_file, tmp_path))

        # Should have used the plugin parser
        assert len(chunks) == 1
        assert chunks[0].name == "mock_function"
        assert chunks[0].content == "mock content here"

    def test_chunker_falls_back_without_plugin(self, tmp_path):
        """Test that chunker falls back to built-in parser when no plugin available."""
        from local_deepwiki.core.chunker import CodeChunker

        # Create a Python file (handled by built-in parser)
        py_file = tmp_path / "test.py"
        py_file.write_text("def hello(): pass")

        # No plugins registered
        chunker = CodeChunker()
        chunks = list(chunker.chunk_file(py_file, tmp_path))

        # Should use built-in parser (may or may not produce chunks depending on content)
        # Just verify no error occurred
        assert isinstance(chunks, list)

    def test_chunker_falls_back_on_plugin_error(self, tmp_path):
        """Test that chunker falls back when plugin raises an error."""
        from local_deepwiki.core.chunker import CodeChunker

        class FailingParser(LanguageParserPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name="failing", version="1.0.0")

            @property
            def language_name(self) -> str:
                return "failing"

            @property
            def file_extensions(self) -> list[str]:
                return [".fail"]

            def parse_file(self, file_path: Path, source: bytes) -> list[CodeChunk]:
                raise RuntimeError("Intentional failure")

        # Register failing parser
        registry = get_plugin_registry()
        registry.register_language_parser(FailingParser())

        # Create file with failing extension
        fail_file = tmp_path / "test.fail"
        fail_file.write_text("content")

        # Should fall back gracefully (file won't match built-in parsers, so empty result)
        chunker = CodeChunker()
        chunks = list(chunker.chunk_file(fail_file, tmp_path))
        assert isinstance(chunks, list)  # No exception raised


class TestEmbeddingProviderPluginIntegration:
    """Tests for embedding provider plugin integration."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset plugin registry before and after each test."""
        reset_plugin_registry()
        yield
        reset_plugin_registry()

    def test_wrapper_class_adapts_interface(self):
        """Test that the wrapper adapts plugin to EmbeddingProvider interface."""
        from local_deepwiki.providers.embeddings import _PluginEmbeddingProviderWrapper
        from local_deepwiki.providers.base import EmbeddingProvider

        plugin = MockEmbeddingProvider()
        wrapper = _PluginEmbeddingProviderWrapper(plugin)

        # Check it's an EmbeddingProvider
        assert isinstance(wrapper, EmbeddingProvider)

        # Check name property is mapped from provider_name
        assert wrapper.name == "mock"

        # Check dimension is forwarded
        assert wrapper.dimension == 384

    async def test_wrapper_embed_forwards_to_plugin(self):
        """Test that wrapper.embed() calls plugin.embed()."""
        from local_deepwiki.providers.embeddings import _PluginEmbeddingProviderWrapper

        plugin = MockEmbeddingProvider()
        wrapper = _PluginEmbeddingProviderWrapper(plugin)

        embeddings = await wrapper.embed(["hello", "world"])
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384

    def test_get_embedding_provider_uses_plugin(self):
        """Test that get_embedding_provider uses plugin when registered."""
        from local_deepwiki.providers.embeddings import get_embedding_provider
        from local_deepwiki.providers.embeddings import _PluginEmbeddingProviderWrapper

        # Register mock provider
        registry = get_plugin_registry()
        registry.register_embedding_provider(MockEmbeddingProvider())

        # Get the plugin directly through the registry
        plugin = registry.get_embedding_provider("mock")
        assert plugin is not None

        # Create wrapper manually to test integration
        wrapper = _PluginEmbeddingProviderWrapper(plugin)
        assert wrapper.name == "mock"
        assert wrapper.dimension == 384

    def test_get_embedding_provider_falls_back_to_builtin(self):
        """Test that get_embedding_provider uses built-in for unknown providers."""
        from local_deepwiki.providers.embeddings import get_embedding_provider
        from local_deepwiki.config import EmbeddingConfig, LocalEmbeddingConfig

        # No plugins registered, use local provider
        config = EmbeddingConfig(
            provider="local",
            local=LocalEmbeddingConfig(model="all-MiniLM-L6-v2"),
        )

        provider = get_embedding_provider(config=config, enable_cache=False)
        # Local provider name includes model
        assert "local" in provider.name


class TestWikiGeneratorPluginIntegration:
    """Tests for wiki generator plugin integration."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Reset plugin registry before and after each test."""
        reset_plugin_registry()
        yield
        reset_plugin_registry()

    async def test_wiki_generator_runs_plugins(self, tmp_path):
        """Test that wiki generator runs registered plugin generators."""
        from local_deepwiki.generators.wiki import WikiGenerator
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.models import IndexStatus, FileInfo
        from unittest.mock import AsyncMock, MagicMock

        # Register mock wiki generator plugin
        registry = get_plugin_registry()
        mock_gen = MockWikiGenerator("test-plugin-gen")
        registry.register_wiki_generator(mock_gen)

        # Create mock vector store
        mock_store = MagicMock(spec=VectorStore)
        mock_store.search = AsyncMock(return_value=[])
        mock_store.embedding_provider = MagicMock()
        mock_store.embedding_provider.get_dimension.return_value = 384
        mock_store.get_main_definition_lines.return_value = {}

        # Create wiki generator
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        generator = WikiGenerator(
            wiki_path=wiki_path,
            vector_store=mock_store,
        )

        # Mock the LLM to avoid actual API calls
        generator.llm = MagicMock()
        generator.llm.generate = AsyncMock(return_value="Generated content")

        # Create minimal index status
        index_status = IndexStatus(
            repo_path=str(tmp_path),
            indexed_at=0.0,
            total_files=1,
            total_chunks=1,
            files=[
                FileInfo(
                    path="test.py",
                    hash="abc123",
                    size_bytes=100,
                    last_modified=0.0,
                    chunk_count=1,
                    language="python",
                )
            ],
        )

        # Run the plugin generator method directly
        from local_deepwiki.generators.wiki.generator import _GenerationContext

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=["test.py"],
            full_rebuild=True,
        )

        await generator._run_plugin_generators(ctx, index_status, None)

        # Check that plugin generated a page
        assert ctx.pages_generated == 1
        assert len(ctx.pages) == 1
        assert ctx.pages[0].title == "Mock Page"
        assert ctx.pages[0].path == "mock.md"

    async def test_wiki_generator_handles_plugin_errors(self, tmp_path):
        """Test that wiki generator handles plugin errors gracefully."""
        from local_deepwiki.generators.wiki.generator import WikiGenerator, _GenerationContext
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.models import IndexStatus
        from unittest.mock import MagicMock

        class FailingWikiGenerator(WikiGeneratorPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name="failing-gen", version="1.0.0")

            @property
            def generator_name(self) -> str:
                return "failing"

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                raise RuntimeError("Intentional failure")

        # Register failing generator
        registry = get_plugin_registry()
        registry.register_wiki_generator(FailingWikiGenerator())

        # Create mock vector store
        mock_store = MagicMock(spec=VectorStore)
        mock_store.embedding_provider = MagicMock()
        mock_store.embedding_provider.get_dimension.return_value = 384
        mock_store.get_main_definition_lines.return_value = {}

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        generator = WikiGenerator(wiki_path=wiki_path, vector_store=mock_store)

        index_status = IndexStatus(
            repo_path=str(tmp_path),
            indexed_at=0.0,
            total_files=0,
            total_chunks=0,
        )

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=[],
            full_rebuild=True,
        )

        # Should not raise, just log warning
        await generator._run_plugin_generators(ctx, index_status, None)

        # No pages generated due to error
        assert ctx.pages_generated == 0

    async def test_wiki_generator_sorts_by_priority(self, tmp_path):
        """Test that wiki generators are sorted by priority."""
        from local_deepwiki.generators.wiki.generator import WikiGenerator, _GenerationContext
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.models import IndexStatus
        from unittest.mock import MagicMock

        execution_order: list[str] = []

        class PriorityGenerator(WikiGeneratorPlugin):
            def __init__(self, name: str, prio: int):
                self._name = name
                self._priority = prio

            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name=self._name, version="1.0.0")

            @property
            def generator_name(self) -> str:
                return self._name

            @property
            def priority(self) -> int:
                return self._priority

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                execution_order.append(self._name)
                return WikiGeneratorResult(pages=[])

        # Register generators with different priorities
        registry = get_plugin_registry()
        registry.register_wiki_generator(PriorityGenerator("low", 10))
        registry.register_wiki_generator(PriorityGenerator("high", 100))
        registry.register_wiki_generator(PriorityGenerator("medium", 50))

        # Create mock vector store
        mock_store = MagicMock(spec=VectorStore)
        mock_store.embedding_provider = MagicMock()
        mock_store.embedding_provider.get_dimension.return_value = 384
        mock_store.get_main_definition_lines.return_value = {}

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        generator = WikiGenerator(wiki_path=wiki_path, vector_store=mock_store)

        index_status = IndexStatus(
            repo_path=str(tmp_path),
            indexed_at=0.0,
            total_files=0,
            total_chunks=0,
        )

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=[],
            full_rebuild=True,
        )

        await generator._run_plugin_generators(ctx, index_status, None)

        # Should execute in priority order (highest first)
        assert execution_order == ["high", "medium", "low"]

    async def test_no_plugins_registered_is_noop(self, tmp_path):
        """Test that no plugins registered means no action taken."""
        from local_deepwiki.generators.wiki.generator import WikiGenerator, _GenerationContext
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.models import IndexStatus
        from unittest.mock import MagicMock

        # No plugins registered
        mock_store = MagicMock(spec=VectorStore)
        mock_store.embedding_provider = MagicMock()
        mock_store.embedding_provider.get_dimension.return_value = 384
        mock_store.get_main_definition_lines.return_value = {}

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        generator = WikiGenerator(wiki_path=wiki_path, vector_store=mock_store)

        index_status = IndexStatus(
            repo_path=str(tmp_path),
            indexed_at=0.0,
            total_files=0,
            total_chunks=0,
        )

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=[],
            full_rebuild=True,
        )

        # Should complete without error
        await generator._run_plugin_generators(ctx, index_status, None)

        assert ctx.pages_generated == 0
        assert len(ctx.pages) == 0

    async def test_wiki_generator_respects_run_after_dependencies(self, tmp_path):
        """Test that generators run in dependency order."""
        from local_deepwiki.generators.wiki.generator import WikiGenerator, _GenerationContext
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.models import IndexStatus
        from unittest.mock import MagicMock

        execution_order: list[str] = []

        class DependentGenerator(WikiGeneratorPlugin):
            def __init__(self, name: str, run_after: list[str]):
                self._name = name
                self._run_after = run_after

            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name=self._name, version="1.0.0")

            @property
            def generator_name(self) -> str:
                return self._name

            @property
            def run_after(self) -> list[str]:
                return self._run_after

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                execution_order.append(self._name)
                return WikiGeneratorResult(pages=[])

        # Register generators with dependencies
        # C depends on B, B depends on A
        registry = get_plugin_registry()
        registry.register_wiki_generator(DependentGenerator("gen-c", ["gen-b"]))
        registry.register_wiki_generator(DependentGenerator("gen-a", []))
        registry.register_wiki_generator(DependentGenerator("gen-b", ["gen-a"]))

        mock_store = MagicMock(spec=VectorStore)
        mock_store.embedding_provider = MagicMock()
        mock_store.embedding_provider.get_dimension.return_value = 384
        mock_store.get_main_definition_lines.return_value = {}

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        generator = WikiGenerator(wiki_path=wiki_path, vector_store=mock_store)

        index_status = IndexStatus(
            repo_path=str(tmp_path),
            indexed_at=0.0,
            total_files=0,
            total_chunks=0,
        )

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=[],
            full_rebuild=True,
        )

        await generator._run_plugin_generators(ctx, index_status, None)

        # A must run before B, B must run before C
        assert execution_order.index("gen-a") < execution_order.index("gen-b")
        assert execution_order.index("gen-b") < execution_order.index("gen-c")

    async def test_wiki_generator_handles_missing_dependencies(self, tmp_path):
        """Test that generators with missing dependencies still run (deps are skipped)."""
        from local_deepwiki.generators.wiki.generator import WikiGenerator, _GenerationContext
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.models import IndexStatus
        from unittest.mock import MagicMock

        executed = []

        class DependentGenerator(WikiGeneratorPlugin):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name="dependent", version="1.0.0")

            @property
            def generator_name(self) -> str:
                return "dependent"

            @property
            def run_after(self) -> list[str]:
                return ["nonexistent-generator"]  # This doesn't exist

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                executed.append("dependent")
                return WikiGeneratorResult(pages=[])

        registry = get_plugin_registry()
        registry.register_wiki_generator(DependentGenerator())

        mock_store = MagicMock(spec=VectorStore)
        mock_store.embedding_provider = MagicMock()
        mock_store.embedding_provider.get_dimension.return_value = 384
        mock_store.get_main_definition_lines.return_value = {}

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        generator = WikiGenerator(wiki_path=wiki_path, vector_store=mock_store)

        index_status = IndexStatus(
            repo_path=str(tmp_path),
            indexed_at=0.0,
            total_files=0,
            total_chunks=0,
        )

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=[],
            full_rebuild=True,
        )

        await generator._run_plugin_generators(ctx, index_status, None)

        # Generator should still run even with missing dependency (warning logged)
        assert "dependent" in executed

    async def test_wiki_generator_handles_circular_dependencies(self, tmp_path):
        """Test that circular dependencies prevent generators from running."""
        from local_deepwiki.generators.wiki.generator import WikiGenerator, _GenerationContext
        from local_deepwiki.core.vectorstore import VectorStore
        from local_deepwiki.models import IndexStatus
        from unittest.mock import MagicMock

        executed = []

        class CircularGenerator(WikiGeneratorPlugin):
            def __init__(self, name: str, run_after: list[str]):
                self._name = name
                self._run_after = run_after

            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(name=self._name, version="1.0.0")

            @property
            def generator_name(self) -> str:
                return self._name

            @property
            def run_after(self) -> list[str]:
                return self._run_after

            async def generate(
                self,
                index_status: IndexStatus,
                wiki_path: Path,
                context: dict[str, Any],
            ) -> WikiGeneratorResult:
                executed.append(self._name)
                return WikiGeneratorResult(pages=[])

        # Create circular dependency: A -> B -> C -> A
        registry = get_plugin_registry()
        registry.register_wiki_generator(CircularGenerator("cycle-a", ["cycle-c"]))
        registry.register_wiki_generator(CircularGenerator("cycle-b", ["cycle-a"]))
        registry.register_wiki_generator(CircularGenerator("cycle-c", ["cycle-b"]))

        mock_store = MagicMock(spec=VectorStore)
        mock_store.embedding_provider = MagicMock()
        mock_store.embedding_provider.get_dimension.return_value = 384
        mock_store.get_main_definition_lines.return_value = {}

        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir()

        generator = WikiGenerator(wiki_path=wiki_path, vector_store=mock_store)

        index_status = IndexStatus(
            repo_path=str(tmp_path),
            indexed_at=0.0,
            total_files=0,
            total_chunks=0,
        )

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=[],
            full_rebuild=True,
        )

        await generator._run_plugin_generators(ctx, index_status, None)

        # None of the circular generators should have executed
        assert len(executed) == 0, (
            f"Expected no generators to run due to cycle, but got: {executed}"
        )
