"""Tests for cross-linking functionality."""

from local_deepwiki.generators.crosslinks import (
    CrossLinker,
    EntityRegistry,
    add_cross_links,
    camel_to_spaced,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language, WikiPage


class TestCamelToSpaced:
    """Tests for camel_to_spaced function."""

    def test_simple_camel_case(self):
        """Test simple CamelCase conversion."""
        assert camel_to_spaced("VectorStore") == "Vector Store"
        assert camel_to_spaced("WikiGenerator") == "Wiki Generator"
        assert camel_to_spaced("CodeChunker") == "Code Chunker"

    def test_multi_word(self):
        """Test multi-word CamelCase."""
        assert camel_to_spaced("RepositoryIndexer") == "Repository Indexer"
        assert camel_to_spaced("CrossLinker") == "Cross Linker"

    def test_acronyms(self):
        """Test CamelCase with acronyms."""
        assert camel_to_spaced("LLMProvider") == "LLM Provider"
        assert camel_to_spaced("HTTPClient") == "HTTP Client"
        assert camel_to_spaced("XMLParser") == "XML Parser"

    def test_returns_none_for_invalid(self):
        """Test that None is returned for non-CamelCase names."""
        assert camel_to_spaced("lowercase") is None
        assert camel_to_spaced("UPPERCASE") is None
        assert camel_to_spaced("snake_case") is None
        assert camel_to_spaced("") is None

    def test_already_single_word(self):
        """Test single capitalized word returns None."""
        assert camel_to_spaced("Config") is None
        assert camel_to_spaced("Parser") is None


class TestEntityRegistry:
    """Tests for EntityRegistry class."""

    def test_register_entity(self):
        """Test registering an entity."""
        registry = EntityRegistry()
        registry.register_entity(
            name="WikiGenerator",
            entity_type=ChunkType.CLASS,
            wiki_path="files/wiki.md",
            file_path="src/wiki.py",
        )

        entity = registry.get_entity("WikiGenerator")
        assert entity is not None
        assert entity.name == "WikiGenerator"
        assert entity.entity_type == ChunkType.CLASS
        assert entity.wiki_path == "files/wiki.md"

    def test_skips_short_names(self):
        """Test that short names are not registered."""
        registry = EntityRegistry()
        registry.register_entity(
            name="foo",
            entity_type=ChunkType.FUNCTION,
            wiki_path="files/test.md",
            file_path="test.py",
        )

        assert registry.get_entity("foo") is None

    def test_skips_private_names(self):
        """Test that private names are not registered."""
        registry = EntityRegistry()
        registry.register_entity(
            name="_private_function",
            entity_type=ChunkType.FUNCTION,
            wiki_path="files/test.md",
            file_path="test.py",
        )

        assert registry.get_entity("_private_function") is None

    def test_skips_excluded_names(self):
        """Test that excluded common names are not registered."""
        registry = EntityRegistry()
        registry.register_entity(
            name="Exception",
            entity_type=ChunkType.CLASS,
            wiki_path="files/test.md",
            file_path="test.py",
        )

        assert registry.get_entity("Exception") is None

    def test_register_from_chunks(self):
        """Test registering entities from code chunks."""
        registry = EntityRegistry()
        chunks = [
            CodeChunk(
                id="1",
                file_path="src/wiki.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.CLASS,
                name="WikiGenerator",
                content="class WikiGenerator: pass",
                start_line=1,
                end_line=1,
            ),
            CodeChunk(
                id="2",
                file_path="src/wiki.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="generate_wiki",
                content="def generate_wiki(): pass",
                start_line=2,
                end_line=2,
            ),
            # Methods should not be registered (they're in the class)
            CodeChunk(
                id="3",
                file_path="src/wiki.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.METHOD,
                name="generate",
                content="def generate(): pass",
                start_line=3,
                end_line=3,
                parent_name="WikiGenerator",
            ),
        ]

        registry.register_from_chunks(chunks, "files/wiki.md")

        assert registry.get_entity("WikiGenerator") is not None
        assert registry.get_entity("generate_wiki") is not None
        # Methods are not registered separately
        assert registry.get_entity("generate") is None

    def test_get_page_entities(self):
        """Test getting entities defined in a page."""
        registry = EntityRegistry()
        registry.register_entity(
            name="ClassOne",
            entity_type=ChunkType.CLASS,
            wiki_path="files/one.md",
            file_path="one.py",
        )
        registry.register_entity(
            name="ClassTwo",
            entity_type=ChunkType.CLASS,
            wiki_path="files/two.md",
            file_path="two.py",
        )

        page_entities = registry.get_page_entities("files/one.md")
        assert "ClassOne" in page_entities
        assert "ClassTwo" not in page_entities

    def test_registers_camelcase_aliases(self):
        """Test that CamelCase names get spaced aliases registered."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        aliases = registry.get_all_aliases()
        assert "Vector Store" in aliases
        assert aliases["Vector Store"] == "VectorStore"

    def test_alias_lookup(self):
        """Test looking up entities by alias."""
        registry = EntityRegistry()
        registry.register_entity(
            name="WikiGenerator",
            entity_type=ChunkType.CLASS,
            wiki_path="files/wiki.md",
            file_path="wiki.py",
        )

        result = registry.get_entity_by_alias("Wiki Generator")
        assert result is not None
        name, entity = result
        assert name == "WikiGenerator"
        assert entity.wiki_path == "files/wiki.md"


class TestCrossLinker:
    """Tests for CrossLinker class."""

    def test_adds_links_to_prose(self):
        """Test that links are added to prose text."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="The indexer uses VectorStore to store embeddings.",
            generated_at=0,
        )

        result = linker.add_links(page)
        assert "[VectorStore](vectorstore.md)" in result.content

    def test_does_not_link_in_code_blocks(self):
        """Test that links are not added inside code blocks."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="Example:\n```python\nstore = VectorStore()\n```\nDone.",
            generated_at=0,
        )

        result = linker.add_links(page)
        # The VectorStore in code block should not be linked
        assert "```python\nstore = VectorStore()\n```" in result.content
        # But prose should still work if there was one
        assert "[VectorStore]" not in result.content

    def test_does_not_self_link(self):
        """Test that entities are not linked on their own page."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/vectorstore.md",
            title="VectorStore",
            content="VectorStore is a class that stores vectors.",
            generated_at=0,
        )

        result = linker.add_links(page)
        # Should not create a self-link
        assert "[VectorStore]" not in result.content

    def test_relative_paths(self):
        """Test relative path calculation between pages."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/core/vectorstore.md",
            file_path="core/vectorstore.py",
        )

        linker = CrossLinker(registry)

        # From modules/index.md to files/core/vectorstore.md
        page = WikiPage(
            path="modules/src.md",
            title="Src Module",
            content="Uses VectorStore for storage.",
            generated_at=0,
        )

        result = linker.add_links(page)
        assert "[VectorStore](../files/core/vectorstore.md)" in result.content

    def test_links_backticked_entities(self):
        """Test that backticked entity names get linked."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="Use `VectorStore` for storage.",
            generated_at=0,
        )

        result = linker.add_links(page)
        # Backticked entity should become a link with backticks preserved
        assert "[`VectorStore`](vectorstore.md)" in result.content

    def test_does_not_link_non_entity_inline_code(self):
        """Test that non-entity inline code is preserved unchanged."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="Use `some_variable` in your code.",
            generated_at=0,
        )

        result = linker.add_links(page)
        # Non-entity inline code should be preserved
        assert "`some_variable`" in result.content
        # Should not be linked
        assert "[`some_variable`]" not in result.content

    def test_links_qualified_names(self):
        """Test that qualified names like module.ClassName get linked."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="Import `local_deepwiki.core.VectorStore` from the module.",
            generated_at=0,
        )

        result = linker.add_links(page)
        # Qualified name should be linked, preserving full path
        assert "[`local_deepwiki.core.VectorStore`](vectorstore.md)" in result.content

    def test_links_simple_qualified_names(self):
        """Test that simple qualified names like module.Class get linked."""
        registry = EntityRegistry()
        registry.register_entity(
            name="WikiGenerator",
            entity_type=ChunkType.CLASS,
            wiki_path="files/wiki.md",
            file_path="wiki.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="Use `generators.WikiGenerator` for docs.",
            generated_at=0,
        )

        result = linker.add_links(page)
        assert "[`generators.WikiGenerator`](wiki.md)" in result.content

    def test_preserves_existing_links(self):
        """Test that existing markdown links are preserved."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="See [VectorStore](other.md) for details.",
            generated_at=0,
        )

        result = linker.add_links(page)
        # Should preserve existing link
        assert "[VectorStore](other.md)" in result.content

    def test_links_bold_text(self):
        """Test that bold entity names get linked."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="The **VectorStore** class handles storage.",
            generated_at=0,
        )

        result = linker.add_links(page)
        # Bold text should get linked while preserving bold
        assert "**[VectorStore](vectorstore.md)**" in result.content

    def test_links_spaced_aliases(self):
        """Test that spaced aliases like 'Vector Store' get linked."""
        registry = EntityRegistry()
        registry.register_entity(
            name="VectorStore",
            entity_type=ChunkType.CLASS,
            wiki_path="files/vectorstore.md",
            file_path="vectorstore.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="The Vector Store handles embedding storage.",
            generated_at=0,
        )

        result = linker.add_links(page)
        # Spaced alias should get linked
        assert "[Vector Store](vectorstore.md)" in result.content

    def test_links_bold_spaced_aliases(self):
        """Test that bold spaced aliases get linked."""
        registry = EntityRegistry()
        registry.register_entity(
            name="WikiGenerator",
            entity_type=ChunkType.CLASS,
            wiki_path="files/wiki.md",
            file_path="wiki.py",
        )

        linker = CrossLinker(registry)
        page = WikiPage(
            path="files/indexer.md",
            title="Indexer",
            content="The **Wiki Generator** creates documentation.",
            generated_at=0,
        )

        result = linker.add_links(page)
        # Bold spaced alias should get linked while preserving bold
        assert "**[Wiki Generator](wiki.md)**" in result.content


class TestAddCrossLinks:
    """Tests for add_cross_links function."""

    def test_processes_all_pages(self):
        """Test that all pages are processed."""
        registry = EntityRegistry()
        registry.register_entity(
            name="ClassA",
            entity_type=ChunkType.CLASS,
            wiki_path="files/a.md",
            file_path="a.py",
        )
        registry.register_entity(
            name="ClassB",
            entity_type=ChunkType.CLASS,
            wiki_path="files/b.md",
            file_path="b.py",
        )

        pages = [
            WikiPage(
                path="files/a.md",
                title="ClassA",
                content="ClassA uses ClassB for something.",
                generated_at=0,
            ),
            WikiPage(
                path="files/b.md",
                title="ClassB",
                content="ClassB is used by ClassA.",
                generated_at=0,
            ),
        ]

        result = add_cross_links(pages, registry)

        # a.md should link to b.md
        assert "[ClassB](b.md)" in result[0].content
        # b.md should link to a.md
        assert "[ClassA](a.md)" in result[1].content
