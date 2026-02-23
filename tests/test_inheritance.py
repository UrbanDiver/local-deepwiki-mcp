"""Tests for inheritance tree generation."""

from unittest.mock import MagicMock

import pytest

from local_deepwiki.generators.analysis.inheritance import (
    ClassNode,
    collect_class_hierarchy,
    find_root_classes,
    generate_inheritance_diagram,
    generate_inheritance_page,
    generate_inheritance_tree_text,
)
from local_deepwiki.models import ChunkType, CodeChunk, FileInfo, IndexStatus, Language


def _make_get_all_chunks(chunks: list[CodeChunk]):
    """Create a mock get_all_chunks that filters chunks by chunk_type."""

    _type_map = {
        "class": ChunkType.CLASS,
        "function": ChunkType.FUNCTION,
        "method": ChunkType.METHOD,
    }

    def get_all_chunks(*, batch_size=None, language=None, chunk_type=None):
        for c in chunks:
            if chunk_type is not None:
                expected = _type_map.get(chunk_type)
                if expected is not None and c.chunk_type != expected:
                    continue
            yield c

    return get_all_chunks


class TestClassNode:
    """Tests for ClassNode dataclass."""

    def test_creates_basic_node(self):
        """Test creating a basic class node."""
        node = ClassNode(name="MyClass", file_path="src/myclass.py")
        assert node.name == "MyClass"
        assert node.file_path == "src/myclass.py"
        assert node.parents == []
        assert node.children == []
        assert node.is_abstract is False

    def test_creates_node_with_inheritance(self):
        """Test creating a node with parent classes."""
        node = ClassNode(
            name="ChildClass",
            file_path="src/child.py",
            parents=["BaseClass", "Mixin"],
            is_abstract=True,
        )
        assert node.parents == ["BaseClass", "Mixin"]
        assert node.is_abstract is True


class TestFindRootClasses:
    """Tests for find_root_classes function."""

    def test_finds_root_with_children(self):
        """Test finding root classes that have children."""
        classes = {
            "Base": ClassNode("Base", "base.py", [], ["Child1", "Child2"]),
            "Child1": ClassNode("Child1", "child1.py", ["Base"], []),
            "Child2": ClassNode("Child2", "child2.py", ["Base"], []),
        }
        roots = find_root_classes(classes)
        assert roots == ["Base"]

    def test_excludes_root_without_children(self):
        """Test that classes with no parents but no children are excluded."""
        classes = {
            "Standalone": ClassNode("Standalone", "standalone.py", [], []),
            "Base": ClassNode("Base", "base.py", [], ["Child"]),
            "Child": ClassNode("Child", "child.py", ["Base"], []),
        }
        roots = find_root_classes(classes)
        assert "Standalone" not in roots
        assert "Base" in roots

    def test_returns_empty_for_no_hierarchies(self):
        """Test returns empty when no inheritance hierarchies exist."""
        classes = {
            "Class1": ClassNode("Class1", "c1.py", [], []),
            "Class2": ClassNode("Class2", "c2.py", [], []),
        }
        roots = find_root_classes(classes)
        assert roots == []

    def test_multiple_roots(self):
        """Test finding multiple root classes."""
        classes = {
            "BaseA": ClassNode("BaseA", "a.py", [], ["ChildA"]),
            "ChildA": ClassNode("ChildA", "ca.py", ["BaseA"], []),
            "BaseB": ClassNode("BaseB", "b.py", [], ["ChildB"]),
            "ChildB": ClassNode("ChildB", "cb.py", ["BaseB"], []),
        }
        roots = find_root_classes(classes)
        assert sorted(roots) == ["BaseA", "BaseB"]


class TestGenerateInheritanceDiagram:
    """Tests for generate_inheritance_diagram function."""

    def test_returns_none_for_empty(self):
        """Test returns None for empty classes."""
        assert generate_inheritance_diagram({}) is None

    def test_returns_none_for_no_inheritance(self):
        """Test returns None when no classes have inheritance."""
        classes = {
            "Class1": ClassNode("Class1", "c1.py", [], []),
            "Class2": ClassNode("Class2", "c2.py", [], []),
        }
        assert generate_inheritance_diagram(classes) is None

    def test_generates_diagram_with_inheritance(self):
        """Test generates diagram for classes with inheritance."""
        classes = {
            "Base": ClassNode("Base", "base.py", [], ["Child"]),
            "Child": ClassNode("Child", "child.py", ["Base"], []),
        }
        diagram = generate_inheritance_diagram(classes)
        assert diagram is not None
        assert "```mermaid" in diagram
        assert "classDiagram" in diagram
        assert "--|>" in diagram  # Inheritance arrow

    def test_marks_abstract_classes(self):
        """Test that abstract classes are marked."""
        classes = {
            "AbstractBase": ClassNode(
                "AbstractBase", "base.py", [], ["Impl"], is_abstract=True
            ),
            "Impl": ClassNode("Impl", "impl.py", ["AbstractBase"], []),
        }
        diagram = generate_inheritance_diagram(classes)
        assert "<<abstract>>" in diagram


class TestGenerateInheritanceTreeText:
    """Tests for generate_inheritance_tree_text function."""

    def test_generates_single_node(self):
        """Test generating tree for single node with no children."""
        classes = {
            "Root": ClassNode("Root", "root.py", [], []),
        }
        lines = generate_inheritance_tree_text(classes, "Root")
        assert len(lines) == 1
        assert "Root" in lines[0]

    def test_generates_tree_with_children(self):
        """Test generating tree with parent and children."""
        classes = {
            "Base": ClassNode("Base", "base.py", [], ["Child1", "Child2"]),
            "Child1": ClassNode("Child1", "c1.py", ["Base"], []),
            "Child2": ClassNode("Child2", "c2.py", ["Base"], []),
        }
        lines = generate_inheritance_tree_text(classes, "Base")
        assert len(lines) == 3
        assert "Base" in lines[0]
        assert any("Child1" in line for line in lines)
        assert any("Child2" in line for line in lines)

    def test_handles_deep_hierarchy(self):
        """Test generating tree with multiple levels."""
        classes = {
            "Root": ClassNode("Root", "root.py", [], ["Middle"]),
            "Middle": ClassNode("Middle", "mid.py", ["Root"], ["Leaf"]),
            "Leaf": ClassNode("Leaf", "leaf.py", ["Middle"], []),
        }
        lines = generate_inheritance_tree_text(classes, "Root")
        assert len(lines) == 3
        # Check proper nesting
        assert lines[0].startswith("- ")  # Root at top level
        assert "└─" in lines[1]  # Children indented

    def test_avoids_cycles(self):
        """Test that cycles are handled gracefully."""
        classes = {
            "A": ClassNode("A", "a.py", ["B"], ["B"]),
            "B": ClassNode("B", "b.py", ["A"], ["A"]),
        }
        lines = generate_inheritance_tree_text(classes, "A")
        # Should not infinite loop - just visit each once
        assert len(lines) <= 2

    def test_includes_file_name(self):
        """Test that file name is included in output."""
        classes = {
            "MyClass": ClassNode("MyClass", "src/mymodule/myclass.py", [], []),
        }
        lines = generate_inheritance_tree_text(classes, "MyClass")
        assert "myclass.py" in lines[0]

    def test_marks_abstract_classes(self):
        """Test that abstract classes are marked in text tree."""
        classes = {
            "AbstractBase": ClassNode(
                "AbstractBase", "base.py", [], [], is_abstract=True
            ),
        }
        lines = generate_inheritance_tree_text(classes, "AbstractBase")
        assert "(abstract)" in lines[0]

    def test_returns_empty_for_nonexistent_class(self):
        """Test returns empty list for non-existent class."""
        classes = {
            "Existing": ClassNode("Existing", "existing.py", [], []),
        }
        lines = generate_inheritance_tree_text(classes, "NonExistent")
        assert lines == []

    def test_truncates_long_docstring(self):
        """Test that long docstrings are truncated."""
        long_docstring = "A" * 100  # Very long docstring
        classes = {
            "MyClass": ClassNode(
                "MyClass",
                "myclass.py",
                [],
                [],
                docstring=long_docstring,
            ),
        }
        lines = generate_inheritance_tree_text(classes, "MyClass")
        assert "..." in lines[0]
        # The line should contain truncated docstring
        assert len(lines[0]) < 200  # Reasonable length

    def test_includes_short_docstring(self):
        """Test that short docstrings are included fully."""
        classes = {
            "MyClass": ClassNode(
                "MyClass",
                "myclass.py",
                [],
                [],
                docstring="A short description.",
            ),
        }
        lines = generate_inheritance_tree_text(classes, "MyClass")
        assert "A short description." in lines[0]


class TestGenerateInheritanceDiagramAdvanced:
    """Advanced tests for generate_inheritance_diagram."""

    def test_limits_to_max_classes(self):
        """Test that diagram limits classes when too many."""
        # Create many classes with inheritance
        classes = {}
        for i in range(60):
            classes[f"Class{i}"] = ClassNode(
                f"Class{i}",
                f"class{i}.py",
                parents=["BaseClass"] if i > 0 else [],
                children=[f"Class{i + 1}"] if i < 59 else [],
            )
        classes["BaseClass"] = ClassNode(
            "BaseClass",
            "base.py",
            [],
            children=[f"Class{i}" for i in range(1, 60)],
        )

        diagram = generate_inheritance_diagram(classes, max_classes=10)
        assert diagram is not None
        # Should have limited the number of classes
        class_count = diagram.count("class ")
        assert class_count <= 12  # max_classes + some tolerance

    def test_prioritizes_classes_with_more_relationships(self):
        """Test that classes with more relationships are prioritized."""
        classes = {
            "Central": ClassNode("Central", "c.py", [], ["A", "B", "C", "D"]),
            "A": ClassNode("A", "a.py", ["Central"], []),
            "B": ClassNode("B", "b.py", ["Central"], []),
            "C": ClassNode("C", "c.py", ["Central"], []),
            "D": ClassNode("D", "d.py", ["Central"], []),
            "Peripheral": ClassNode("Peripheral", "p.py", [], ["Lonely"]),
            "Lonely": ClassNode("Lonely", "l.py", ["Peripheral"], []),
        }

        diagram = generate_inheritance_diagram(classes, max_classes=3)
        assert diagram is not None
        # Central should be included as it has most relationships
        assert "Central" in diagram

    def test_returns_none_when_no_relationships_after_filtering(self):
        """Test returns None when classes have no internal relationships."""
        classes = {
            # These classes only inherit from external bases
            "Class1": ClassNode("Class1", "c1.py", ["ExternalBase"], []),
            "Class2": ClassNode("Class2", "c2.py", ["AnotherExternal"], []),
        }
        diagram = generate_inheritance_diagram(classes)
        assert diagram is None


class TestCollectClassHierarchy:
    """Tests for collect_class_hierarchy function."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.get_all_chunks = _make_get_all_chunks([])
        return store

    @pytest.fixture
    def sample_index_status(self):
        """Create a sample index status."""
        return IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            files=[
                FileInfo(
                    path="src/module.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
            ],
        )

    async def test_collects_class_with_parents(
        self, mock_vector_store, sample_index_status
    ):
        """Test collecting a class with parent classes."""
        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class Child(Parent): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=10,
                    name="Child",
                    metadata={"parent_classes": ["Parent"]},
                )
            ]
        )

        classes = await collect_class_hierarchy(sample_index_status, mock_vector_store)

        assert "Child" in classes
        assert classes["Child"].parents == ["Parent"]

    async def test_detects_abstract_class_from_abc(
        self, mock_vector_store, sample_index_status
    ):
        """Test detecting abstract class from ABC parent."""
        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class MyABC(ABC): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=10,
                    name="MyABC",
                    metadata={"parent_classes": ["ABC"]},
                )
            ]
        )

        classes = await collect_class_hierarchy(sample_index_status, mock_vector_store)

        assert classes["MyABC"].is_abstract is True

    async def test_detects_abstract_from_abstractmethod(
        self, mock_vector_store, sample_index_status
    ):
        """Test detecting abstract class from @abstractmethod decorator."""
        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class Base:\n    @abstractmethod\n    def method(self): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=10,
                    name="Base",
                    metadata={"parent_classes": []},
                )
            ]
        )

        classes = await collect_class_hierarchy(sample_index_status, mock_vector_store)

        assert classes["Base"].is_abstract is True

    async def test_detects_abstract_from_keyword(
        self, mock_vector_store, sample_index_status
    ):
        """Test detecting abstract class from 'abstract' keyword in content."""
        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content='"""An abstract base class."""\nclass Base: pass',
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=10,
                    name="Base",
                    metadata={"parent_classes": []},
                )
            ]
        )

        classes = await collect_class_hierarchy(sample_index_status, mock_vector_store)

        assert classes["Base"].is_abstract is True

    async def test_skips_non_class_chunks(self, mock_vector_store, sample_index_status):
        """Test that non-class chunks are skipped."""
        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="def func(): pass",
                    chunk_type=ChunkType.FUNCTION,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="func",
                ),
                CodeChunk(
                    id="chunk2",
                    content="class MyClass: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=7,
                    end_line=10,
                    name="MyClass",
                    metadata={"parent_classes": []},
                ),
            ]
        )

        classes = await collect_class_hierarchy(sample_index_status, mock_vector_store)

        assert "func" not in classes
        assert "MyClass" in classes

    async def test_skips_chunks_without_name(
        self, mock_vector_store, sample_index_status
    ):
        """Test that chunks without name are skipped."""
        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name=None,
                    metadata={"parent_classes": []},
                ),
            ]
        )

        classes = await collect_class_hierarchy(sample_index_status, mock_vector_store)

        assert len(classes) == 0

    async def test_builds_children_relationships(self, mock_vector_store):
        """Test that children relationships are built correctly."""
        index_status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            files=[
                FileInfo(
                    path="src/base.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/child.py",
                    hash="def456",
                    size_bytes=500,
                    last_modified=1234567890.0,
                ),
            ],
        )

        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class Base: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/base.py",
                    start_line=1,
                    end_line=5,
                    name="Base",
                    metadata={"parent_classes": []},
                ),
                CodeChunk(
                    id="chunk2",
                    content="class Child(Base): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/child.py",
                    start_line=1,
                    end_line=5,
                    name="Child",
                    metadata={"parent_classes": ["Base"]},
                ),
            ]
        )

        classes = await collect_class_hierarchy(index_status, mock_vector_store)

        assert "Base" in classes
        assert "Child" in classes
        assert "Child" in classes["Base"].children
        assert "Base" in classes["Child"].parents

    async def test_merges_duplicate_classes(self, mock_vector_store):
        """Test that duplicate class definitions are merged."""
        index_status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            files=[
                FileInfo(
                    path="src/file1.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/file2.py",
                    hash="def456",
                    size_bytes=500,
                    last_modified=1234567890.0,
                ),
            ],
        )

        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class MyClass(Parent1): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/file1.py",
                    start_line=1,
                    end_line=5,
                    name="MyClass",
                    metadata={"parent_classes": ["Parent1"]},
                ),
                CodeChunk(
                    id="chunk2",
                    content="class MyClass(Parent2): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/file2.py",
                    start_line=1,
                    end_line=5,
                    name="MyClass",
                    metadata={"parent_classes": ["Parent2"]},
                ),
            ]
        )

        classes = await collect_class_hierarchy(index_status, mock_vector_store)

        # Should merge parents from both definitions
        assert "MyClass" in classes
        assert "Parent1" in classes["MyClass"].parents
        assert "Parent2" in classes["MyClass"].parents

    async def test_includes_docstring(self, mock_vector_store, sample_index_status):
        """Test that docstring is included in class node."""
        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class MyClass: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=10,
                    name="MyClass",
                    docstring="A well-documented class.",
                    metadata={"parent_classes": []},
                )
            ]
        )

        classes = await collect_class_hierarchy(sample_index_status, mock_vector_store)

        assert classes["MyClass"].docstring == "A well-documented class."


class TestGenerateInheritancePage:
    """Tests for generate_inheritance_page function."""

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock()
        store.get_all_chunks = _make_get_all_chunks([])
        return store

    @pytest.fixture
    def sample_index_status(self):
        """Create a sample index status."""
        return IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=1,
            total_chunks=5,
            files=[
                FileInfo(
                    path="src/module.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
            ],
        )

    async def test_returns_none_for_no_classes(
        self, mock_vector_store, sample_index_status
    ):
        """Test returns None when no classes exist."""
        result = await generate_inheritance_page(sample_index_status, mock_vector_store)
        assert result is None

    async def test_returns_none_for_no_inheritance(
        self, mock_vector_store, sample_index_status
    ):
        """Test returns None when no internal inheritance exists."""
        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class Standalone: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/module.py",
                    start_line=1,
                    end_line=5,
                    name="Standalone",
                    metadata={"parent_classes": ["ExternalBase"]},
                ),
            ]
        )

        result = await generate_inheritance_page(sample_index_status, mock_vector_store)
        assert result is None

    async def test_generates_page_with_inheritance(self, mock_vector_store):
        """Test generates page when inheritance exists."""
        index_status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            files=[
                FileInfo(
                    path="src/base.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/child.py",
                    hash="def456",
                    size_bytes=500,
                    last_modified=1234567890.0,
                ),
            ],
        )

        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class Base: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/base.py",
                    start_line=1,
                    end_line=5,
                    name="Base",
                    metadata={"parent_classes": []},
                ),
                CodeChunk(
                    id="chunk2",
                    content="class Child(Base): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/child.py",
                    start_line=1,
                    end_line=5,
                    name="Child",
                    metadata={"parent_classes": ["Base"]},
                ),
            ]
        )

        result = await generate_inheritance_page(index_status, mock_vector_store)

        assert result is not None
        assert "# Class Inheritance" in result

    async def test_includes_diagram_section(self, mock_vector_store):
        """Test includes inheritance diagram section."""
        index_status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            files=[
                FileInfo(
                    path="src/base.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/child.py",
                    hash="def456",
                    size_bytes=500,
                    last_modified=1234567890.0,
                ),
            ],
        )

        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class Base: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/base.py",
                    start_line=1,
                    end_line=5,
                    name="Base",
                    metadata={"parent_classes": []},
                ),
                CodeChunk(
                    id="chunk2",
                    content="class Child(Base): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/child.py",
                    start_line=1,
                    end_line=5,
                    name="Child",
                    metadata={"parent_classes": ["Base"]},
                ),
            ]
        )

        result = await generate_inheritance_page(index_status, mock_vector_store)

        assert "## Inheritance Diagram" in result
        assert "```mermaid" in result

    async def test_includes_trees_section(self, mock_vector_store):
        """Test includes inheritance trees section."""
        index_status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            files=[
                FileInfo(
                    path="src/base.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/child.py",
                    hash="def456",
                    size_bytes=500,
                    last_modified=1234567890.0,
                ),
            ],
        )

        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class Base: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/base.py",
                    start_line=1,
                    end_line=5,
                    name="Base",
                    metadata={"parent_classes": []},
                ),
                CodeChunk(
                    id="chunk2",
                    content="class Child(Base): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/child.py",
                    start_line=1,
                    end_line=5,
                    name="Child",
                    metadata={"parent_classes": ["Base"]},
                ),
            ]
        )

        result = await generate_inheritance_page(index_status, mock_vector_store)

        assert "## Inheritance Trees" in result

    async def test_includes_all_classes_table(self, mock_vector_store):
        """Test includes all classes table."""
        index_status = IndexStatus(
            repo_path="/test/repo",
            indexed_at=1234567890.0,
            total_files=2,
            total_chunks=10,
            files=[
                FileInfo(
                    path="src/base.py",
                    hash="abc123",
                    size_bytes=1000,
                    last_modified=1234567890.0,
                ),
                FileInfo(
                    path="src/child.py",
                    hash="def456",
                    size_bytes=500,
                    last_modified=1234567890.0,
                ),
            ],
        )

        mock_vector_store.get_all_chunks = _make_get_all_chunks(
            [
                CodeChunk(
                    id="chunk1",
                    content="class Base: pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/base.py",
                    start_line=1,
                    end_line=5,
                    name="Base",
                    metadata={"parent_classes": []},
                ),
                CodeChunk(
                    id="chunk2",
                    content="class Child(Base): pass",
                    chunk_type=ChunkType.CLASS,
                    language=Language.PYTHON,
                    file_path="src/child.py",
                    start_line=1,
                    end_line=5,
                    name="Child",
                    metadata={"parent_classes": ["Base"]},
                ),
            ]
        )

        result = await generate_inheritance_page(index_status, mock_vector_store)

        assert "## All Classes" in result
        assert "| Class | Inherits From | File |" in result
        assert "`Base`" in result
        assert "`Child`" in result
