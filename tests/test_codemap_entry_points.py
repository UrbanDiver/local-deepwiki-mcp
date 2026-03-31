"""Tests for codemap entry point discovery and topic suggestion.

Tests cover:
- discover_entry_points: hint-based, auto-discovery, no results
- Scoring: functions preferred over leaf dataclasses
- Fallback search when all initial results are shallow
- suggest_topics: hub detection, empty repos, chunk type weighting
- Stdlib/external entity filtering in suggest_topics
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Mock helpers ─────────────────────────────────────────────────────


def _make_mock_search_result(
    name="my_func",
    file_path="src/module.py",
    start_line=10,
    end_line=25,
    chunk_type="function",
    content="def my_func(): pass",
    docstring="A function.",
    parent_name=None,
    score=0.9,
):
    """Create a mock search result matching the VectorStore.search return type."""
    chunk = MagicMock()
    chunk.name = name
    chunk.file_path = file_path
    chunk.start_line = start_line
    chunk.end_line = end_line
    chunk.chunk_type = MagicMock(value=chunk_type)
    chunk.content = content
    chunk.docstring = docstring
    chunk.parent_name = parent_name

    result = MagicMock()
    result.chunk = chunk
    result.score = score
    return result


def _make_mock_code_chunk(
    name="my_func",
    file_path="src/module.py",
    start_line=10,
    end_line=25,
    chunk_type="function",
    content="def my_func(): pass",
    docstring="A function.",
    parent_name=None,
):
    """Create a mock CodeChunk for vector store get_all_chunks.

    Uses a real ChunkType enum value so that identity comparisons like
    ``chunk.chunk_type == ChunkType.IMPORT`` work correctly.
    """
    from local_deepwiki.models import ChunkType

    chunk = MagicMock()
    chunk.name = name
    chunk.file_path = file_path
    chunk.start_line = start_line
    chunk.end_line = end_line
    # Use the actual ChunkType enum so both .value and identity checks work
    chunk.chunk_type = ChunkType(chunk_type)
    chunk.content = content
    chunk.docstring = docstring
    chunk.parent_name = parent_name
    return chunk


# ── Entry point discovery tests ──────────────────────────────────────


class TestDiscoverEntryPoints:
    async def test_with_hint(self, tmp_path):
        from local_deepwiki.generators.codemap import discover_entry_points

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(
            return_value=[
                _make_mock_search_result(
                    name="handle_request",
                    file_path="src/server.py",
                    start_line=5,
                    end_line=20,
                ),
            ]
        )

        nodes = await discover_entry_points(
            query="request handling",
            vector_store=mock_vs,
            repo_path=tmp_path,
            entry_point_hint="handle_request",
        )
        assert len(nodes) >= 1
        assert any(n.name == "handle_request" for n in nodes)
        mock_vs.search.assert_called()

    async def test_auto_discovery(self, tmp_path):
        from local_deepwiki.generators.codemap import discover_entry_points

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(
            return_value=[
                _make_mock_search_result(
                    name="process_data",
                    file_path="src/pipeline.py",
                    start_line=1,
                    end_line=30,
                ),
                _make_mock_search_result(
                    name="load_config",
                    file_path="src/config.py",
                    start_line=1,
                    end_line=10,
                    score=0.7,
                ),
            ]
        )

        nodes = await discover_entry_points(
            query="data processing pipeline",
            vector_store=mock_vs,
            repo_path=tmp_path,
        )
        assert len(nodes) >= 1
        names = [n.name for n in nodes]
        assert "process_data" in names

    async def test_no_results(self, tmp_path):
        from local_deepwiki.generators.codemap import discover_entry_points

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(return_value=[])

        nodes = await discover_entry_points(
            query="nonexistent feature",
            vector_store=mock_vs,
            repo_path=tmp_path,
        )
        assert nodes == []

    async def test_prefers_functions_over_leaf_dataclasses(self, tmp_path):
        """Vague queries should prefer functions with callees over leaf dataclasses.

        Regression test: "tell me everything about how the rag works" returned
        RAGTrace/QueryResult/SourceEntry (0-callee dataclasses) instead of
        answer_question (6+ callees orchestrator).
        """
        from local_deepwiki.generators.codemap import discover_entry_points

        # Dataclass with high vector similarity but 0 callees
        dataclass_result = _make_mock_search_result(
            name="RAGTrace",
            file_path="src/tracing.py",
            chunk_type="class",
            content="class RAGTrace: ...",
            score=0.95,
        )
        # Function with lower similarity but many callees
        function_result = _make_mock_search_result(
            name="answer_question",
            file_path="src/query_service.py",
            chunk_type="function",
            content="async def answer_question(question): ...",
            score=0.75,
        )

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(return_value=[dataclass_result, function_result])

        # Mock call graph: answer_question calls many, RAGTrace calls none
        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor",
        ) as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.side_effect = (
                lambda path, repo: {
                    "answer_question": [
                        "search",
                        "rerank",
                        "build_context",
                        "generate",
                    ],
                }
                if "query_service" in str(path)
                else {
                    "RAGTrace": [],
                }
            )
            MockCGE.return_value = extractor

            nodes = await discover_entry_points(
                query="tell me everything about how the rag works",
                vector_store=mock_vs,
                repo_path=tmp_path,
            )

        assert len(nodes) >= 1
        # answer_question should rank above RAGTrace despite lower vector score
        assert nodes[0].name == "answer_question"

    async def test_fallback_search_when_all_shallow(self, tmp_path):
        """When initial search returns only shallow nodes (<=1 callee), a
        fallback search for functions/methods should find orchestrators.

        Regression: "tell me about RAG" matched RAGTrace methods (1 callee each)
        instead of answer_question (4+ callees).
        """
        from local_deepwiki.generators.codemap import discover_entry_points

        # Initial search: classes (0 callees) + methods with 1 callee
        initial_results = [
            _make_mock_search_result(
                name="RAGTrace",
                file_path="src/tracing.py",
                chunk_type="class",
                score=0.95,
            ),
            _make_mock_search_result(
                name="to_dict",
                file_path="src/tracing.py",
                chunk_type="method",
                parent_name="RAGTrace",
                score=0.90,
            ),
            _make_mock_search_result(
                name="finish",
                file_path="src/tracing.py",
                chunk_type="method",
                parent_name="RAGTrace",
                score=0.85,
            ),
        ]
        # Fallback search returns the real pipeline function
        fallback_function = _make_mock_search_result(
            name="answer_question",
            file_path="src/query_service.py",
            chunk_type="function",
            score=0.75,
        )
        fallback_method = _make_mock_search_result(
            name="_execute_pipeline",
            file_path="src/pipeline.py",
            chunk_type="method",
            score=0.70,
        )

        call_count = 0

        async def mock_search(
            query, *, limit=10, min_similarity=0.0, chunk_type=None, **kwargs
        ):
            nonlocal call_count
            call_count += 1
            if chunk_type == "function":
                return [fallback_function]
            if chunk_type == "method":
                return [fallback_method]
            return initial_results

        mock_vs = AsyncMock()
        mock_vs.search = AsyncMock(side_effect=mock_search)

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor",
        ) as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.side_effect = (
                lambda path, repo: {
                    "answer_question": [
                        "search",
                        "rerank",
                        "build_context",
                        "generate",
                    ],
                }
                if "query_service" in str(path)
                else {
                    "_execute_pipeline": ["step1", "step2", "step3"],
                }
                if "pipeline" in str(path)
                else {
                    # tracing.py: methods with 0-1 callees
                    "RAGTrace.to_dict": ["finish"],
                    "RAGTrace.finish": [],
                }
            )
            MockCGE.return_value = extractor

            nodes = await discover_entry_points(
                query="tell me everything about how the rag works",
                vector_store=mock_vs,
                repo_path=tmp_path,
            )

        # Should have found orchestrator functions via fallback
        assert len(nodes) >= 1
        names = [n.name for n in nodes]
        assert "answer_question" in names or "_execute_pipeline" in names
        # Fallback search should have been triggered (3 calls: initial + 2 type filters)
        assert call_count >= 3


# ── Topic suggestion tests ───────────────────────────────────────────


def _setup_suggest_topics_mock(mock_vs: MagicMock) -> None:
    """Add an async search mock that returns callable results for validation.

    ``suggest_topics`` validates each candidate by running a vector search.
    This helper ensures the mock vector store returns results that pass
    the validation filter (callable chunk type, non-test file).
    """
    chunks = mock_vs.get_all_chunks.return_value
    callable_results = [
        _make_mock_search_result(
            name=c.name,
            file_path=c.file_path,
            start_line=c.start_line,
            end_line=c.end_line,
            chunk_type=c.chunk_type.value,
        )
        for c in chunks
        if c.chunk_type.value in ("function", "method", "class")
    ]
    mock_vs.search = AsyncMock(return_value=callable_results)


class TestSuggestTopics:
    async def test_finds_hubs(self, tmp_path):
        from local_deepwiki.generators.codemap import suggest_topics

        mock_vs = MagicMock()
        mock_vs.get_all_chunks.return_value = [
            _make_mock_code_chunk(
                name="main",
                file_path=str(tmp_path / "src" / "main.py"),
                chunk_type="function",
                content="def main(): handle_request(); process_data(); send_response()",
            ),
            _make_mock_code_chunk(
                name="handle_request",
                file_path=str(tmp_path / "src" / "server.py"),
                chunk_type="function",
                content="def handle_request(): pass",
            ),
            _make_mock_code_chunk(
                name="process_data",
                file_path=str(tmp_path / "src" / "pipeline.py"),
                chunk_type="function",
                content="def process_data(): pass",
            ),
        ]

        _setup_suggest_topics_mock(mock_vs)

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.return_value = {
                "main": ["handle_request", "process_data", "send_response"],
            }
            MockCGE.return_value = extractor

            suggestions = await suggest_topics(
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_suggestions=5,
            )

        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        # Should return suggestions with required keys
        for s in suggestions:
            assert isinstance(s, dict)
            assert "topic" in s
            assert "entry_point" in s
            assert "reason" in s

    async def test_empty_repo(self, tmp_path):
        from local_deepwiki.generators.codemap import suggest_topics

        mock_vs = MagicMock()
        mock_vs.get_all_chunks.return_value = []

        suggestions = await suggest_topics(
            vector_store=mock_vs,
            repo_path=tmp_path,
            max_suggestions=10,
        )

        assert isinstance(suggestions, list)
        assert len(suggestions) == 0

    async def test_chunk_type_weighting_favors_functions_over_classes(self, tmp_path):
        """Verify a function with 15 connections ranks above a class with 50."""
        from local_deepwiki.generators.codemap import suggest_topics

        # A class with many connections (50) and a function with fewer (15).
        # After weighting (class * 0.3 = 15, function * 1.0 = 15),
        # but we give function slightly more to ensure it wins.
        mock_vs = MagicMock()
        mock_vs.get_all_chunks.return_value = [
            _make_mock_code_chunk(
                name="BigDataModel",
                file_path=str(tmp_path / "src" / "models.py"),
                chunk_type="class",
                content="class BigDataModel:\n    pass",
            ),
            _make_mock_code_chunk(
                name="handle_request",
                file_path=str(tmp_path / "src" / "server.py"),
                chunk_type="function",
                content="def handle_request(): process(); validate(); transform()",
            ),
        ]
        _setup_suggest_topics_mock(mock_vs)

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
            extractor = MagicMock()

            # BigDataModel gets 50 raw connections; handle_request gets 16
            def extract_side_effect(abs_path, repo):
                name = str(abs_path)
                if "models.py" in name:
                    # Class with many method-like callees
                    callees = [f"method_{i}" for i in range(49)]
                    return {"BigDataModel": callees}
                if "server.py" in name:
                    return {
                        "handle_request": [
                            "process",
                            "validate",
                            "transform",
                            "send",
                            "log_request",
                            "check_auth",
                            "parse_body",
                            "route",
                            "respond",
                            "cleanup",
                            "metrics",
                            "trace",
                            "cache_check",
                            "rate_limit",
                            "serialize",
                        ]
                    }
                return {}

            extractor.extract_from_file.side_effect = extract_side_effect
            MockCGE.return_value = extractor

            suggestions = await suggest_topics(
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_suggestions=5,
            )

        assert len(suggestions) >= 2
        names = [s["entry_point"] for s in suggestions]
        assert "handle_request" in names
        assert "BigDataModel" in names
        # handle_request (16 * 1.0 = 16) should rank above BigDataModel (50 * 0.3 = 15)
        handle_idx = names.index("handle_request")
        class_idx = names.index("BigDataModel")
        assert handle_idx < class_idx, f"Function should rank above class: {names}"


# ── Stdlib filtering tests ───────────────────────────────────────────


class TestSuggestTopicsStdlibFiltering:
    """Verify suggest_topics filters out stdlib/external entities."""

    async def test_filters_stdlib_entities(self, tmp_path):
        from local_deepwiki.generators.codemap import suggest_topics

        mock_vs = MagicMock()
        mock_vs.get_all_chunks.return_value = [
            _make_mock_code_chunk(
                name="main",
                file_path=str(tmp_path / "src" / "main.py"),
                chunk_type="function",
                content="def main(): Path(); MagicMock(); process()",
            ),
            _make_mock_code_chunk(
                name="process",
                file_path=str(tmp_path / "src" / "pipeline.py"),
                chunk_type="function",
                content="def process(data): pass",
            ),
        ]
        _setup_suggest_topics_mock(mock_vs)

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
            extractor = MagicMock()
            # Call graph includes stdlib names as callees
            extractor.extract_from_file.return_value = {
                "main": ["Path", "MagicMock", "process", "mkdir", "exists"],
            }
            MockCGE.return_value = extractor

            suggestions = await suggest_topics(
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_suggestions=10,
            )

        # Should NOT include stdlib entities that have no indexed chunk
        entry_points = {s["entry_point"] for s in suggestions}
        assert "Path" not in entry_points
        assert "MagicMock" not in entry_points
        assert "mkdir" not in entry_points
        assert "exists" not in entry_points

        # file_path should never be "unknown"
        for s in suggestions:
            assert s.get("file_path", "") != "unknown"

    async def test_keeps_project_entities(self, tmp_path):
        from local_deepwiki.generators.codemap import suggest_topics

        mock_vs = MagicMock()
        mock_vs.get_all_chunks.return_value = [
            _make_mock_code_chunk(
                name="handle_request",
                file_path=str(tmp_path / "src" / "server.py"),
                chunk_type="function",
                content="def handle_request(req): validate(req); process(req)",
            ),
            _make_mock_code_chunk(
                name="validate",
                file_path=str(tmp_path / "src" / "validation.py"),
                chunk_type="function",
                content="def validate(req): pass",
            ),
            _make_mock_code_chunk(
                name="process",
                file_path=str(tmp_path / "src" / "pipeline.py"),
                chunk_type="function",
                content="def process(req): pass",
            ),
        ]
        _setup_suggest_topics_mock(mock_vs)

        with patch(
            "local_deepwiki.generators.analysis.callgraph.CallGraphExtractor"
        ) as MockCGE:
            extractor = MagicMock()
            extractor.extract_from_file.return_value = {
                "handle_request": ["validate", "process"],
            }
            MockCGE.return_value = extractor

            suggestions = await suggest_topics(
                vector_store=mock_vs,
                repo_path=tmp_path,
                max_suggestions=10,
            )

        entry_points = {s["entry_point"] for s in suggestions}
        assert "handle_request" in entry_points
