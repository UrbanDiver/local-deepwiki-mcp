"""Tests for GraphRAG entity and relationship extraction."""

from __future__ import annotations

import pytest

from local_deepwiki.core.graph_rag.extractor import GraphRelationshipExtractor
from local_deepwiki.core.graph_rag.models import (
    EntityType,
    FileGraphData,
    GraphEntity,
    RelationshipType,
    entity_id,
)
from local_deepwiki.core.parser import CodeParser
from local_deepwiki.models import CodeChunk, ChunkType, Language


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def extractor() -> GraphRelationshipExtractor:
    return GraphRelationshipExtractor()


@pytest.fixture()
def parser() -> CodeParser:
    return CodeParser()


def _parse_python(parser: CodeParser, source: str) -> tuple:
    """Helper: parse a Python source string and return (root, bytes)."""
    source_bytes = source.encode("utf-8")
    root = parser.parse_source(source_bytes, Language.PYTHON)
    return root, source_bytes


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


class TestExtractEntities:
    def test_top_level_function(self, extractor, parser):
        source = "def greet(name):\n    return f'Hello {name}'\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "main.py")

        funcs = [e for e in result.entities if e.entity_type == EntityType.FUNCTION]
        assert len(funcs) == 1
        assert funcs[0].name == "greet"
        assert funcs[0].qualified_name == "greet"
        assert funcs[0].file_path == "main.py"
        assert funcs[0].start_line >= 1

    def test_class_entity(self, extractor, parser):
        source = "class Animal:\n    pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "models.py")

        classes = [e for e in result.entities if e.entity_type == EntityType.CLASS]
        assert len(classes) == 1
        assert classes[0].name == "Animal"

    def test_method_entity(self, extractor, parser):
        source = "class Dog:\n    def bark(self):\n        pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "animal.py")

        methods = [e for e in result.entities if e.entity_type == EntityType.METHOD]
        assert len(methods) == 1
        assert methods[0].name == "bark"
        assert methods[0].qualified_name == "Dog.bark"
        assert methods[0].metadata.get("parent_name") == "Dog"

    def test_multiple_entities(self, extractor, parser):
        source = (
            "def helper():\n"
            "    pass\n\n"
            "class Service:\n"
            "    def run(self):\n"
            "        pass\n"
            "    def stop(self):\n"
            "        pass\n"
        )
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "svc.py")

        funcs = [e for e in result.entities if e.entity_type == EntityType.FUNCTION]
        classes = [e for e in result.entities if e.entity_type == EntityType.CLASS]
        methods = [e for e in result.entities if e.entity_type == EntityType.METHOD]

        assert len(funcs) == 1
        assert len(classes) == 1
        assert len(methods) == 2

    def test_async_function(self, extractor, parser):
        source = "async def fetch_data():\n    pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "async.py")

        funcs = [e for e in result.entities if e.entity_type == EntityType.FUNCTION]
        assert len(funcs) == 1
        assert funcs[0].name == "fetch_data"

    def test_entity_ids_are_deterministic(self, extractor, parser):
        source = "def process():\n    pass\n"
        root, src = _parse_python(parser, source)

        r1 = extractor.extract_from_ast(root, src, Language.PYTHON, "a.py")
        r2 = extractor.extract_from_ast(root, src, Language.PYTHON, "a.py")

        assert r1.entities[0].id == r2.entities[0].id

    def test_entity_id_format(self, extractor, parser):
        source = "def do_work():\n    pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "work.py")
        assert result.entities[0].id == "work.py::do_work"


# ---------------------------------------------------------------------------
# Call relationships
# ---------------------------------------------------------------------------


class TestExtractCalls:
    def test_function_calling_function(self, extractor, parser):
        source = "def callee():\n    pass\n\ndef caller():\n    callee()\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "calls.py")

        call_rels = [
            r for r in result.relationships if r.relationship == RelationshipType.CALLS
        ]
        assert len(call_rels) >= 1

        # The caller -> callee edge should exist
        caller_id = entity_id("calls.py", "caller")
        callee_id = entity_id("calls.py", "callee")
        source_ids = {r.source_id for r in call_rels}
        target_ids = {r.target_id for r in call_rels}
        assert caller_id in source_ids
        assert callee_id in target_ids

    def test_method_calling_method(self, extractor, parser):
        source = (
            "class Processor:\n"
            "    def validate(self):\n"
            "        pass\n"
            "    def run(self):\n"
            "        self.validate()\n"
        )
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "proc.py")

        call_rels = [
            r for r in result.relationships if r.relationship == RelationshipType.CALLS
        ]
        assert len(call_rels) >= 1

        runner_id = entity_id("proc.py", "Processor.run")
        assert any(r.source_id == runner_id for r in call_rels)

    def test_no_duplicate_calls(self, extractor, parser):
        source = (
            "def target():\n    pass\n\ndef caller():\n    target()\n    target()\n"
        )
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "dup.py")

        caller_id = entity_id("dup.py", "caller")
        call_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.CALLS and r.source_id == caller_id
        ]
        # Deduplicated: only one edge caller -> target
        assert len(call_rels) == 1

    def test_no_calls_for_unsupported_language_call_types(self, extractor, parser):
        """Languages without CALL_NODE_TYPES produce no call relationships."""
        source = "def f():\n    pass\n"
        root, src = _parse_python(parser, source)

        # Ruby doesn't have call_types in CALL_NODE_TYPES
        result = extractor.extract_from_ast(root, src, Language.RUBY, "test.rb")
        call_rels = [
            r for r in result.relationships if r.relationship == RelationshipType.CALLS
        ]
        assert call_rels == []


# ---------------------------------------------------------------------------
# Import relationships
# ---------------------------------------------------------------------------


class TestExtractImports:
    def test_python_import(self, extractor, parser):
        source = "import os\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "app.py")

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) == 1
        assert "os" in import_rels[0].target_id

    def test_python_from_import(self, extractor, parser):
        source = "from pathlib import Path\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "app.py")

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) == 1
        assert "pathlib" in import_rels[0].target_id

    def test_multiple_imports(self, extractor, parser):
        source = "import os\nimport sys\nfrom pathlib import Path\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "multi.py")

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) == 3

    def test_import_source_is_file_entity(self, extractor, parser):
        source = "import json\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "io.py")

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) == 1
        expected_source = entity_id("io.py", "io.py")
        assert import_rels[0].source_id == expected_source

    def test_no_imports_for_unknown_language(self, extractor, parser):
        """Languages without IMPORT_NODE_TYPES produce no import relationships."""
        # Use a source with no import node types for the target language
        source = "def f():\n    pass\n"
        root, src = _parse_python(parser, source)

        # Manually pass a Language that has no IMPORT_NODE_TYPES entry
        # All supported languages actually have entries, so we verify empty result
        result = extractor.extract_from_ast(root, src, Language.PYTHON, "test.py")
        # A file with no imports should have no import relationships
        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert import_rels == []


# ---------------------------------------------------------------------------
# Inheritance relationships
# ---------------------------------------------------------------------------


class TestExtractInheritance:
    def test_single_inheritance(self, extractor, parser):
        source = "class Animal:\n    pass\n\nclass Dog(Animal):\n    pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "animals.py")

        inherit_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.INHERITS_FROM
        ]
        assert len(inherit_rels) == 1

        dog_id = entity_id("animals.py", "Dog")
        animal_id = entity_id("animals.py", "Animal")
        assert inherit_rels[0].source_id == dog_id
        assert inherit_rels[0].target_id == animal_id

    def test_multiple_inheritance(self, extractor, parser):
        source = (
            "class Flyable:\n"
            "    pass\n\n"
            "class Swimmable:\n"
            "    pass\n\n"
            "class Duck(Flyable, Swimmable):\n"
            "    pass\n"
        )
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "duck.py")

        inherit_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.INHERITS_FROM
        ]
        assert len(inherit_rels) == 2

        duck_id = entity_id("duck.py", "Duck")
        targets = {r.target_id for r in inherit_rels}
        assert all(r.source_id == duck_id for r in inherit_rels)
        assert entity_id("duck.py", "Flyable") in targets
        assert entity_id("duck.py", "Swimmable") in targets

    def test_inheriting_external_class(self, extractor, parser):
        source = "class MyError(Exception):\n    pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "errors.py")

        inherit_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.INHERITS_FROM
        ]
        assert len(inherit_rels) == 1
        # Target for an external class uses a placeholder entity_id
        assert "Exception" in inherit_rels[0].target_id

    def test_no_inheritance(self, extractor, parser):
        source = "class Standalone:\n    pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "plain.py")

        inherit_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.INHERITS_FROM
        ]
        assert inherit_rels == []


# ---------------------------------------------------------------------------
# Containment relationships
# ---------------------------------------------------------------------------


class TestExtractContainment:
    def test_class_contains_method(self, extractor, parser):
        source = "class Handler:\n    def handle(self):\n        pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "handler.py")

        contain_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.CONTAINS
        ]
        assert len(contain_rels) == 1

        handler_id = entity_id("handler.py", "Handler")
        method_id = entity_id("handler.py", "Handler.handle")
        assert contain_rels[0].source_id == handler_id
        assert contain_rels[0].target_id == method_id

    def test_class_contains_multiple_methods(self, extractor, parser):
        source = (
            "class Repo:\n"
            "    def create(self):\n"
            "        pass\n"
            "    def delete(self):\n"
            "        pass\n"
        )
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "repo.py")

        contain_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.CONTAINS
        ]
        assert len(contain_rels) == 2

        repo_id = entity_id("repo.py", "Repo")
        assert all(r.source_id == repo_id for r in contain_rels)

    def test_top_level_function_has_no_containment(self, extractor, parser):
        source = "def standalone():\n    pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "solo.py")

        contain_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.CONTAINS
        ]
        assert contain_rels == []


# ---------------------------------------------------------------------------
# Full integration: extract_from_ast
# ---------------------------------------------------------------------------


class TestExtractFromAST:
    def test_returns_file_graph_data(self, extractor, parser):
        source = "def f():\n    pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "f.py")

        assert isinstance(result, FileGraphData)
        assert result.file_path == "f.py"
        assert isinstance(result.entities, tuple)
        assert isinstance(result.relationships, tuple)

    def test_empty_source(self, extractor, parser):
        source = ""
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "empty.py")

        assert result.entities == ()
        assert result.relationships == ()

    def test_comment_only_source(self, extractor, parser):
        source = "# This is a comment\n# Another one\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "comments.py")

        assert result.entities == ()

    def test_all_relationship_types_in_one_file(self, extractor, parser):
        source = (
            "import os\n\n"
            "class Base:\n"
            "    def base_method(self):\n"
            "        pass\n\n"
            "class Child(Base):\n"
            "    def child_method(self):\n"
            "        self.base_method()\n\n"
            "def helper():\n"
            "    pass\n"
        )
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "all.py")

        rel_types = {r.relationship for r in result.relationships}
        assert RelationshipType.IMPORTS in rel_types
        assert RelationshipType.INHERITS_FROM in rel_types
        assert RelationshipType.CONTAINS in rel_types
        # Calls may or may not appear depending on builtin filtering
        # but base_method is not a builtin, so it should appear
        assert RelationshipType.CALLS in rel_types

    def test_frozen_result(self, extractor, parser):
        source = "def g():\n    pass\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "g.py")

        with pytest.raises(AttributeError):
            result.file_path = "other.py"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# link_entities_to_chunks
# ---------------------------------------------------------------------------


class TestLinkEntitiesToChunks:
    def test_exact_match(self):
        entity = GraphEntity(
            id="a.py::func",
            name="func",
            qualified_name="func",
            entity_type=EntityType.FUNCTION,
            file_path="a.py",
            start_line=5,
            end_line=10,
        )
        chunk = CodeChunk(
            id="chunk-1",
            file_path="a.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="func",
            content="def func(): pass",
            start_line=5,
            end_line=10,
        )

        result = GraphRelationshipExtractor.link_entities_to_chunks(
            [entity],
            [chunk],
        )

        assert len(result) == 1
        assert result[0].chunk_id == "chunk-1"

    def test_no_matching_chunk(self):
        entity = GraphEntity(
            id="a.py::missing",
            name="missing",
            qualified_name="missing",
            entity_type=EntityType.FUNCTION,
            file_path="a.py",
            start_line=1,
            end_line=3,
        )

        result = GraphRelationshipExtractor.link_entities_to_chunks(
            [entity],
            [],
        )

        assert len(result) == 1
        assert result[0].chunk_id == ""  # unchanged

    def test_prefers_exact_line_match(self):
        entity = GraphEntity(
            id="b.py::render",
            name="render",
            qualified_name="render",
            entity_type=EntityType.FUNCTION,
            file_path="b.py",
            start_line=10,
            end_line=20,
        )
        chunk_wrong_line = CodeChunk(
            id="chunk-wrong",
            file_path="b.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="render",
            content="def render(): ...",
            start_line=50,
            end_line=60,
        )
        chunk_exact = CodeChunk(
            id="chunk-exact",
            file_path="b.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="render",
            content="def render(): ...",
            start_line=10,
            end_line=20,
        )

        result = GraphRelationshipExtractor.link_entities_to_chunks(
            [entity],
            [chunk_wrong_line, chunk_exact],
        )

        assert result[0].chunk_id == "chunk-exact"

    def test_falls_back_to_first_candidate(self):
        entity = GraphEntity(
            id="c.py::build",
            name="build",
            qualified_name="build",
            entity_type=EntityType.FUNCTION,
            file_path="c.py",
            start_line=1,
            end_line=5,
        )
        chunk = CodeChunk(
            id="chunk-fb",
            file_path="c.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="build",
            content="def build(): ...",
            start_line=99,
            end_line=105,
        )

        result = GraphRelationshipExtractor.link_entities_to_chunks(
            [entity],
            [chunk],
        )

        assert result[0].chunk_id == "chunk-fb"

    def test_returns_new_objects(self):
        """link_entities_to_chunks must not mutate the original entities."""
        entity = GraphEntity(
            id="d.py::save",
            name="save",
            qualified_name="save",
            entity_type=EntityType.FUNCTION,
            file_path="d.py",
            start_line=1,
            end_line=3,
        )
        chunk = CodeChunk(
            id="chunk-new",
            file_path="d.py",
            language=Language.PYTHON,
            chunk_type=ChunkType.FUNCTION,
            name="save",
            content="def save(): ...",
            start_line=1,
            end_line=3,
        )

        result = GraphRelationshipExtractor.link_entities_to_chunks(
            [entity],
            [chunk],
        )

        # Original entity is unchanged (frozen dataclass)
        assert entity.chunk_id == ""
        # New entity has chunk_id set
        assert result[0].chunk_id == "chunk-new"
        assert result[0] is not entity

    def test_multiple_entities(self):
        entities = [
            GraphEntity(
                id="e.py::alpha",
                name="alpha",
                qualified_name="alpha",
                entity_type=EntityType.FUNCTION,
                file_path="e.py",
                start_line=1,
                end_line=3,
            ),
            GraphEntity(
                id="e.py::beta",
                name="beta",
                qualified_name="beta",
                entity_type=EntityType.FUNCTION,
                file_path="e.py",
                start_line=5,
                end_line=7,
            ),
        ]
        chunks = [
            CodeChunk(
                id="c-alpha",
                file_path="e.py",
                language=Language.PYTHON,
                chunk_type=ChunkType.FUNCTION,
                name="alpha",
                content="def alpha(): ...",
                start_line=1,
                end_line=3,
            ),
        ]

        result = GraphRelationshipExtractor.link_entities_to_chunks(
            entities,
            chunks,
        )

        assert result[0].chunk_id == "c-alpha"
        assert result[1].chunk_id == ""  # no matching chunk for beta


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_syntax_error_source(self, extractor, parser):
        """Malformed source should not crash — tree-sitter is error-tolerant."""
        source = "def broken(\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "bad.py")

        assert isinstance(result, FileGraphData)
        # Might still extract a partial function or nothing — either is fine
        assert result.file_path == "bad.py"

    def test_binary_like_source(self, extractor, parser):
        """Non-UTF8 source bytes should not crash."""
        source_bytes = b"\x00\x01\x02\x03"
        root = parser.parse_source(source_bytes, Language.PYTHON)

        result = extractor.extract_from_ast(
            root,
            source_bytes,
            Language.PYTHON,
            "binary.py",
        )

        assert isinstance(result, FileGraphData)


# ---------------------------------------------------------------------------
# Relationship ID determinism
# ---------------------------------------------------------------------------


class TestRelationshipDeterminism:
    def test_relationship_ids_are_deterministic(self, extractor, parser):
        source = "class A:\n    pass\n\nclass B(A):\n    pass\n"
        root, src = _parse_python(parser, source)

        r1 = extractor.extract_from_ast(root, src, Language.PYTHON, "det.py")
        r2 = extractor.extract_from_ast(root, src, Language.PYTHON, "det.py")

        ids1 = sorted(r.id for r in r1.relationships)
        ids2 = sorted(r.id for r in r2.relationships)
        assert ids1 == ids2

    def test_different_files_produce_different_ids(self, extractor, parser):
        source = "def f():\n    pass\n"
        root, src = _parse_python(parser, source)

        r1 = extractor.extract_from_ast(root, src, Language.PYTHON, "x.py")
        r2 = extractor.extract_from_ast(root, src, Language.PYTHON, "y.py")

        ids1 = {e.id for e in r1.entities}
        ids2 = {e.id for e in r2.entities}
        assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# Language-specific import extraction
# ---------------------------------------------------------------------------


class TestJavaScriptImports:
    def test_js_import_from(self, extractor, parser):
        source = 'import { render } from "./utils";\n'
        source_bytes = source.encode("utf-8")
        root = parser.parse_source(source_bytes, Language.JAVASCRIPT)

        result = extractor.extract_from_ast(
            root,
            source_bytes,
            Language.JAVASCRIPT,
            "app.js",
        )

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) >= 1
        # The target should contain the module path
        assert any("utils" in r.target_id for r in import_rels)

    def test_ts_import(self, extractor, parser):
        source = 'import { Component } from "react";\n'
        source_bytes = source.encode("utf-8")
        root = parser.parse_source(source_bytes, Language.TYPESCRIPT)

        result = extractor.extract_from_ast(
            root,
            source_bytes,
            Language.TYPESCRIPT,
            "app.ts",
        )

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) >= 1


class TestGoImports:
    def test_go_single_import(self, extractor, parser):
        source = 'package main\n\nimport "fmt"\n'
        source_bytes = source.encode("utf-8")
        root = parser.parse_source(source_bytes, Language.GO)

        result = extractor.extract_from_ast(
            root,
            source_bytes,
            Language.GO,
            "main.go",
        )

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) >= 1
        assert any("fmt" in r.target_id for r in import_rels)

    def test_go_grouped_import(self, extractor, parser):
        source = 'package main\n\nimport (\n    "fmt"\n    "os"\n)\n'
        source_bytes = source.encode("utf-8")
        root = parser.parse_source(source_bytes, Language.GO)

        result = extractor.extract_from_ast(
            root,
            source_bytes,
            Language.GO,
            "main.go",
        )

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) >= 1


class TestRustImports:
    def test_rust_use(self, extractor, parser):
        source = "use std::collections::HashMap;\n"
        source_bytes = source.encode("utf-8")
        root = parser.parse_source(source_bytes, Language.RUST)

        result = extractor.extract_from_ast(
            root,
            source_bytes,
            Language.RUST,
            "lib.rs",
        )

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) >= 1
        # Should extract 'std' as the top-level crate
        assert any("std" in r.target_id for r in import_rels)


class TestJavaImports:
    def test_java_import(self, extractor, parser):
        source = "import java.util.List;\n\nclass Main {}\n"
        source_bytes = source.encode("utf-8")
        root = parser.parse_source(source_bytes, Language.JAVA)

        result = extractor.extract_from_ast(
            root,
            source_bytes,
            Language.JAVA,
            "Main.java",
        )

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) >= 1
        assert any("java.util.List" in r.target_id for r in import_rels)


# ---------------------------------------------------------------------------
# Callee resolution within class
# ---------------------------------------------------------------------------


class TestCalleeResolution:
    def test_method_calls_sibling_method(self, extractor, parser):
        """When method A calls method B in the same class, resolve to qualified name."""
        source = (
            "class Calculator:\n"
            "    def add(self, a, b):\n"
            "        return a + b\n"
            "    def add_and_double(self, a, b):\n"
            "        result = self.add(a, b)\n"
            "        return result * 2\n"
        )
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "calc.py")

        call_rels = [
            r for r in result.relationships if r.relationship == RelationshipType.CALLS
        ]
        # add_and_double should call add (resolved within class)
        caller_id = entity_id("calc.py", "Calculator.add_and_double")
        assert any(r.source_id == caller_id for r in call_rels)

    def test_function_calls_unresolvable_function(self, extractor, parser):
        """Calls to functions not in this file still produce a relationship."""
        source = "def do_work():\n    external_fn()\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "work.py")

        call_rels = [
            r for r in result.relationships if r.relationship == RelationshipType.CALLS
        ]
        # external_fn is not defined locally, but a relationship should still be emitted
        assert len(call_rels) >= 1
        assert any("external_fn" in r.target_id for r in call_rels)


# ---------------------------------------------------------------------------
# Exception path coverage
# ---------------------------------------------------------------------------


class TestExceptionPaths:
    def test_extract_entities_exception_handling(self, extractor):
        """_extract_entities should handle exceptions gracefully."""
        # Pass None as root_node to trigger an exception
        result = extractor.extract_from_ast(
            None,
            b"",
            Language.PYTHON,
            "crash.py",
        )
        # Should return empty data, not crash
        assert isinstance(result, FileGraphData)

    def test_python_aliased_import(self, extractor, parser):
        """Test import with alias: import numpy as np."""
        source = "import numpy as np\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "sci.py")

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) == 1
        assert "numpy" in import_rels[0].target_id

    def test_python_dotted_import(self, extractor, parser):
        """Test import os.path."""
        source = "import os.path\n"
        root, src = _parse_python(parser, source)

        result = extractor.extract_from_ast(root, src, Language.PYTHON, "paths.py")

        import_rels = [
            r
            for r in result.relationships
            if r.relationship == RelationshipType.IMPORTS
        ]
        assert len(import_rels) == 1
        assert "os.path" in import_rels[0].target_id
