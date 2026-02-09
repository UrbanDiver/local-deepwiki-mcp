"""Tests for class diagram generation in diagrams module."""

import pytest

from local_deepwiki.generators.diagrams import (
    ClassInfo,
    _extract_class_attributes,
    _extract_method_signature,
    generate_class_diagram,
)
from local_deepwiki.models import ChunkType, CodeChunk, Language


class TestExtractClassAttributes:
    """Tests for _extract_class_attributes function."""

    def test_extracts_type_annotations(self):
        """Test extraction of class-level type annotations."""
        content = """class MyClass:
    name: str
    count: int
"""
        attrs = _extract_class_attributes(content, "python")
        assert "+name: str" in attrs
        assert "+count: int" in attrs

    def test_extracts_init_assignments(self):
        """Test extraction from __init__ assignments."""
        content = """class MyClass:
    def __init__(self):
        self.value = 42
        self._private = "secret"
"""
        attrs = _extract_class_attributes(content, "python")
        assert "+value" in attrs
        assert "-_private" in attrs

    def test_marks_private_attributes(self):
        """Test private attributes get - prefix."""
        content = """class MyClass:
    _hidden: str
"""
        attrs = _extract_class_attributes(content, "python")
        assert any(a.startswith("-_hidden") for a in attrs)


class TestExtractMethodSignature:
    """Tests for _extract_method_signature function."""

    def test_extracts_return_type(self):
        """Test extraction of return type."""
        content = "def process(x: int, y: str) -> bool:"
        sig = _extract_method_signature(content)
        assert "bool" in sig

    def test_extracts_parameters(self):
        """Test extraction of parameters."""
        content = "def process(x: int, y: str) -> bool:"
        sig = _extract_method_signature(content)
        assert "x: int" in sig
        assert "y: str" in sig

    def test_excludes_self(self):
        """Test self parameter is excluded."""
        content = "def process(self, x: int) -> None:"
        sig = _extract_method_signature(content)
        assert "self" not in sig
        assert "x: int" in sig

    def test_limits_parameters(self):
        """Test long parameter lists are truncated."""
        content = "def process(a: int, b: int, c: int, d: int, e: int, f: int) -> None:"
        sig = _extract_method_signature(content)
        assert "..." in sig

    def test_returns_none_for_invalid(self):
        """Test returns None for non-def content."""
        content = "class MyClass:"
        sig = _extract_method_signature(content)
        assert sig is None


class TestClassInfo:
    """Tests for ClassInfo dataclass."""

    def test_basic_class_info(self):
        """Test basic ClassInfo creation."""
        info = ClassInfo(
            name="MyClass",
            methods=["do_work", "process"],
            attributes=["+name: str"],
            parents=["BaseClass"],
        )
        assert info.name == "MyClass"
        assert len(info.methods) == 2
        assert info.is_abstract is False
        assert info.is_dataclass is False

    def test_abstract_class(self):
        """Test abstract class flag."""
        info = ClassInfo(
            name="AbstractBase",
            methods=[],
            attributes=[],
            parents=["ABC"],
            is_abstract=True,
        )
        assert info.is_abstract is True


class TestGenerateClassDiagram:
    """Tests for generate_class_diagram function."""

    def test_generates_diagram_with_class(self):
        """Test diagram generation with a single class."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "classDiagram" in diagram
        assert "MyClass" in diagram
        assert "method" in diagram

    def test_returns_none_for_empty_classes(self):
        """Test returns None when classes have no content."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class Empty: pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=1,
                name="Empty",
                metadata={},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is None

    def test_shows_inheritance(self):
        """Test inheritance relationships are shown."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class Child:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="Child",
                metadata={"parent_classes": ["Parent"]},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "--|>" in diagram
        assert "Parent" in diagram

    def test_marks_dataclass(self):
        """Test dataclass annotation is shown."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="@dataclass\nclass Data:\n    name: str",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="Data",
                metadata={},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "<<dataclass>>" in diagram

    def test_shows_method_visibility(self):
        """Test private methods are marked with -."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def public(self): pass\n    def _private(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="MyClass",
                metadata={},
            )
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "+public" in diagram
        assert "-_private" in diagram


class TestClassDiagramAbstract:
    """Tests for abstract class handling in diagrams."""

    def test_marks_abstract_class(self):
        """Test abstract class annotation is shown (line 147)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="from abc import ABC\nclass AbstractBase(ABC):\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="AbstractBase",
                metadata={"parent_classes": ["ABC"]},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "<<abstract>>" in diagram

    def test_marks_abstract_by_content(self):
        """Test abstract detection from content keyword."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyAbstract:\n    # abstract base\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="MyAbstract",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "<<abstract>>" in diagram


class TestDuplicateClassHandling:
    """Tests for duplicate class handling in diagram generation."""

    def test_skips_duplicate_class(self):
        """Test that duplicate class chunks are skipped (line 57)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test2.py",
                content="class MyClass:\n    def other(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "MyClass" in diagram
        assert diagram.count("class MyClass") == 1


class TestMethodChunkCollection:
    """Tests for METHOD chunk collection in diagrams."""

    def test_collects_method_chunks(self):
        """Test that METHOD chunks are collected (lines 89-99, 208)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test.py",
                content="def process(self, x: int) -> str:\n    return str(x)",
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=3,
                end_line=4,
                name="process",
                parent_name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks, show_types=True)
        assert diagram is not None
        assert "process" in diagram

    def test_method_with_unknown_parent(self):
        """Test method chunk with no parent in classes dict (lines 94-95)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test.py",
                content="def orphan_method(self):\n    pass",
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=5,
                end_line=6,
                name="orphan_method",
                parent_name="UnknownClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)

    def test_skips_duplicate_methods(self):
        """Test that duplicate method names are skipped (lines 97-99)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test.py",
                content="def method(self):\n    pass",
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=2,
                end_line=3,
                name="method",
                parent_name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="3",
                file_path="test.py",
                content="def method(self):\n    pass",
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=4,
                end_line=5,
                name="method",
                parent_name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None


class TestMethodWithoutSignature:
    """Tests for method display without signature."""

    def test_method_without_types(self):
        """Test method shown without types when show_types=False (line 159)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks, show_types=False)
        assert diagram is not None
        assert "method()" in diagram


class TestExtractMethodsFromContent:
    """Tests for method extraction from class content."""

    def test_extracts_methods_from_class_content(self):
        """Test methods extracted from class content when no METHOD chunks (lines 113, 123)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def method_one(self) -> str:\n        pass\n    def method_two(self) -> int:\n        pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=5,
                name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "method_one" in diagram
        assert "method_two" in diagram

    def test_skips_extraction_when_methods_exist(self):
        """Test extraction skipped when class already has methods (line 113)."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyClass:\n    def in_content(self): pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=2,
                name="MyClass",
                metadata={},
            ),
            CodeChunk(
                id="2",
                file_path="test.py",
                content="def from_chunk(self):\n    pass",
                chunk_type=ChunkType.METHOD,
                language=Language.PYTHON,
                start_line=2,
                end_line=3,
                name="from_chunk",
                parent_name="MyClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None


class TestAttributeExtractionEdgeCases:
    """Tests for attribute extraction edge cases."""

    def test_attribute_without_type(self):
        """Test attribute extraction without type hint (line 259)."""
        content = """class MyClass:
    name: str
    plain
    def __init__(self):
        pass
"""
        attrs = _extract_class_attributes(content, "python")

    def test_init_attribute_with_type(self):
        """Test init assignment with type hint (line 267)."""
        content = """class MyClass:
    def __init__(self):
        self.typed: str = "value"
        self.untyped = 42
"""
        attrs = _extract_class_attributes(content, "python")
        assert any("typed" in a for a in attrs)


class TestMethodSignatureEdgeCases:
    """Tests for method signature edge cases."""

    def test_parameter_without_type(self):
        """Test parameter without type annotation (lines 303-305)."""
        content = "def process(x, y=None) -> bool:"
        sig = _extract_method_signature(content)
        assert sig is not None
        assert "x" in sig


class TestClassDiagramWithSearchResults:
    """Tests for class diagram with SearchResult wrapper."""

    def test_unwraps_search_results(self):
        """Test SearchResult objects are unwrapped."""

        class MockSearchResult:
            def __init__(self, chunk):
                self.chunk = chunk

        inner_chunk = CodeChunk(
            id="1",
            file_path="test.py",
            content="class MyClass:\n    def method(self): pass",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            start_line=1,
            end_line=2,
            name="MyClass",
            metadata={},
        )
        wrapped = MockSearchResult(inner_chunk)
        chunks = [wrapped]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "MyClass" in diagram


class TestClassDiagramBaseModel:
    """Tests for BaseModel detection as dataclass."""

    def test_detects_basemodel_as_dataclass(self):
        """Test Pydantic BaseModel is marked as dataclass."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class MyModel:\n    name: str\n    age: int",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="MyModel",
                metadata={"parent_classes": ["BaseModel"]},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "<<dataclass>>" in diagram


class TestClassDiagramDocstring:
    """Tests for class docstring in diagram."""

    def test_class_with_docstring(self):
        """Test class with docstring is handled."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content='class MyClass:\n    """A documented class."""\n    def method(self): pass',
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="MyClass",
                docstring="A documented class.",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "MyClass" in diagram


class TestMethodsByClassInitialization:
    """Tests for methods_by_class initialization during extraction (line 123)."""

    def test_initializes_methods_by_class_during_extraction(self):
        """Test that methods_by_class[class_name] is initialized when extracting from content."""
        chunks = [
            CodeChunk(
                id="1",
                file_path="test.py",
                content="class NewClass:\n    def extracted_method(self) -> None:\n        pass",
                chunk_type=ChunkType.CLASS,
                language=Language.PYTHON,
                start_line=1,
                end_line=3,
                name="NewClass",
                metadata={},
            ),
        ]
        diagram = generate_class_diagram(chunks)
        assert diagram is not None
        assert "extracted_method" in diagram


class TestAttributeWithoutTypeHint:
    """Tests for attribute extraction without type hint (line 259)."""

    def test_extracts_attribute_without_equals(self):
        """Test extraction of class attribute without equals sign or type."""
        content = """class MyClass:
    plain_attr:
    typed_attr: str
"""
        attrs = _extract_class_attributes(content, "python")


class TestClassDiagramMethodNotInList:
    """Test for method extraction when class not in methods_by_class (line 123)."""

    def test_method_extraction_creates_list(self):
        """Test that method extraction initializes the list for a class."""
        from local_deepwiki.generators.diagrams import (
            _collect_class_from_chunk,
            _extract_methods_from_class_content,
            _unwrap_chunk,
        )

        chunk = CodeChunk(
            id="1",
            file_path="test.py",
            content="class TestClass:\n    def method_a(self) -> int:\n        return 1",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            start_line=1,
            end_line=3,
            name="TestClass",
            metadata={},
        )

        classes = {}
        methods_by_class = {}

        _collect_class_from_chunk(
            chunk, classes, methods_by_class, show_attributes=True
        )

        assert "TestClass" in methods_by_class
        assert methods_by_class["TestClass"] == []

        del methods_by_class["TestClass"]

        _extract_methods_from_class_content(
            [chunk], classes, methods_by_class, show_types=True
        )

        assert "TestClass" in methods_by_class
        assert len(methods_by_class["TestClass"]) > 0


class TestAttributeWithoutTypeDirectly:
    """Direct test for attribute without type (line 259)."""

    def test_attribute_class_level_no_type_value(self):
        """Test attribute with annotation but empty type hint."""
        content = """class MyClass:
    empty_type:   = "value"
    normal: str
"""
        attrs = _extract_class_attributes(content, "python")
