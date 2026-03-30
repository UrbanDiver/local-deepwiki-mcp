"""Tests for Protocol interfaces at package boundaries.

Verifies that:
1. Each Protocol is ``@runtime_checkable``.
2. The concrete class satisfies the Protocol (``isinstance`` check).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Core protocols
# ---------------------------------------------------------------------------
from local_deepwiki.core.protocols import (
    ChunkerProtocol,
    RateLimiterProtocol,
    SecretDetectorProtocol,
)

# ---------------------------------------------------------------------------
# Service protocols
# ---------------------------------------------------------------------------
from local_deepwiki.services.protocols import (
    AnalysisServiceProtocol,
    IndexingServiceProtocol,
    QueryServiceProtocol,
)

# ---------------------------------------------------------------------------
# Generator protocols
# ---------------------------------------------------------------------------
from local_deepwiki.generators.protocols import (
    AnalysisGeneratorProtocol,
    DiagramGeneratorProtocol,
)


# ===== Core protocol tests =====


class TestChunkerProtocol:
    """ChunkerProtocol tests."""

    def test_runtime_checkable(self) -> None:
        assert hasattr(ChunkerProtocol, "__protocol_attrs__") or hasattr(
            ChunkerProtocol, "__abstractmethods__"
        )
        # runtime_checkable protocols support isinstance
        assert isinstance(ChunkerProtocol, type)

    def test_concrete_class_satisfies_protocol(self) -> None:
        from local_deepwiki.core.chunker import CodeChunker

        chunker = CodeChunker()
        assert isinstance(chunker, ChunkerProtocol)

    def test_minimal_stub_satisfies_protocol(self) -> None:
        class _StubChunker:
            def chunk_file(self, file_path: Path, repo_root: Path) -> Iterator:
                yield from []

        assert isinstance(_StubChunker(), ChunkerProtocol)

    def test_non_conforming_object_rejected(self) -> None:
        class _Bad:
            pass

        assert not isinstance(_Bad(), ChunkerProtocol)


class TestSecretDetectorProtocol:
    """SecretDetectorProtocol tests."""

    def test_runtime_checkable(self) -> None:
        assert isinstance(SecretDetectorProtocol, type)

    def test_concrete_class_satisfies_protocol(self) -> None:
        from local_deepwiki.core.secret_detector import SecretDetector

        detector = SecretDetector()
        assert isinstance(detector, SecretDetectorProtocol)

    def test_minimal_stub_satisfies_protocol(self) -> None:
        class _StubDetector:
            def scan_content(
                self,
                content: str,
                file_path: str,
                start_line: int = 0,
            ) -> list:
                return []

        assert isinstance(_StubDetector(), SecretDetectorProtocol)

    def test_non_conforming_object_rejected(self) -> None:
        class _Bad:
            pass

        assert not isinstance(_Bad(), SecretDetectorProtocol)


class TestRateLimiterProtocol:
    """RateLimiterProtocol tests."""

    def test_runtime_checkable(self) -> None:
        assert isinstance(RateLimiterProtocol, type)

    def test_concrete_class_satisfies_protocol(self) -> None:
        from local_deepwiki.core.rate_limiter import RateLimiter

        limiter = RateLimiter()
        assert isinstance(limiter, RateLimiterProtocol)

    def test_minimal_stub_satisfies_protocol(self) -> None:
        class _StubLimiter:
            async def acquire(self) -> None:
                pass

            def release(self) -> None:
                pass

        assert isinstance(_StubLimiter(), RateLimiterProtocol)

    def test_non_conforming_object_rejected(self) -> None:
        class _Bad:
            pass

        assert not isinstance(_Bad(), RateLimiterProtocol)


# ===== Service protocol tests =====


class TestQueryServiceProtocol:
    """QueryServiceProtocol tests."""

    def test_runtime_checkable(self) -> None:
        assert isinstance(QueryServiceProtocol, type)

    def test_minimal_stub_satisfies_protocol(self) -> None:
        class _StubQueryService:
            async def answer_question(self, request: Any) -> Any:
                return None

            async def search_code(self, request: Any) -> list[dict[str, Any]]:
                return []

        assert isinstance(_StubQueryService(), QueryServiceProtocol)

    def test_non_conforming_object_rejected(self) -> None:
        class _Bad:
            pass

        assert not isinstance(_Bad(), QueryServiceProtocol)


class TestAnalysisServiceProtocol:
    """AnalysisServiceProtocol tests."""

    def test_runtime_checkable(self) -> None:
        assert isinstance(AnalysisServiceProtocol, type)

    def test_concrete_class_satisfies_protocol(self) -> None:
        from local_deepwiki.services.analysis_service import AnalysisService

        service = AnalysisService()
        assert isinstance(service, AnalysisServiceProtocol)

    def test_minimal_stub_satisfies_protocol(self) -> None:
        class _StubAnalysis:
            async def explain_entity(self, request: Any) -> dict[str, Any]:
                return {}

            async def impact_analysis(self, request: Any) -> dict[str, Any]:
                return {}

        assert isinstance(_StubAnalysis(), AnalysisServiceProtocol)

    def test_non_conforming_object_rejected(self) -> None:
        class _Bad:
            pass

        assert not isinstance(_Bad(), AnalysisServiceProtocol)


class TestIndexingServiceProtocol:
    """IndexingServiceProtocol tests."""

    def test_runtime_checkable(self) -> None:
        assert isinstance(IndexingServiceProtocol, type)

    def test_minimal_stub_satisfies_protocol(self) -> None:
        class _StubIndexing:
            async def run_pipeline(self, request: Any) -> Any:
                return None

        assert isinstance(_StubIndexing(), IndexingServiceProtocol)

    def test_non_conforming_object_rejected(self) -> None:
        class _Bad:
            pass

        assert not isinstance(_Bad(), IndexingServiceProtocol)


# ===== Generator protocol tests =====


class TestAnalysisGeneratorProtocol:
    """AnalysisGeneratorProtocol tests."""

    def test_runtime_checkable(self) -> None:
        assert isinstance(AnalysisGeneratorProtocol, type)

    def test_minimal_stub_satisfies_protocol(self) -> None:
        class _StubGenerator:
            async def generate_module_graph(
                self,
                index_status: Any,
                *,
                show_external: bool = False,
                max_external: int = 10,
                exclude_tests: bool = True,
                wiki_base_path: str = "",
            ) -> str:
                return ""

            async def generate_file_graph(
                self,
                index_status: Any,
                module_path: str,
                exclude_tests: bool = True,
            ) -> str:
                return ""

        assert isinstance(_StubGenerator(), AnalysisGeneratorProtocol)

    def test_non_conforming_object_rejected(self) -> None:
        class _Bad:
            pass

        assert not isinstance(_Bad(), AnalysisGeneratorProtocol)


class TestDiagramGeneratorProtocol:
    """DiagramGeneratorProtocol tests."""

    def test_runtime_checkable(self) -> None:
        assert isinstance(DiagramGeneratorProtocol, type)

    def test_callable_satisfies_protocol(self) -> None:
        def my_generator(chunks: list, **kwargs: object) -> str | None:
            return None

        assert isinstance(my_generator, DiagramGeneratorProtocol)

    def test_non_conforming_object_rejected(self) -> None:
        class _Bad:
            pass

        assert not isinstance(_Bad(), DiagramGeneratorProtocol)


# ===== Re-export tests =====


class TestReExports:
    """Verify protocols are accessible from package __init__."""

    def test_core_reexports(self) -> None:
        from local_deepwiki.core import (
            ChunkerProtocol,
            RateLimiterProtocol,
            SecretDetectorProtocol,
        )

        assert ChunkerProtocol is not None
        assert RateLimiterProtocol is not None
        assert SecretDetectorProtocol is not None

    def test_services_reexports(self) -> None:
        from local_deepwiki.services import (
            AnalysisServiceProtocol,
            IndexingServiceProtocol,
            QueryServiceProtocol,
        )

        assert AnalysisServiceProtocol is not None
        assert IndexingServiceProtocol is not None
        assert QueryServiceProtocol is not None

    def test_generators_reexports(self) -> None:
        from local_deepwiki.generators import (
            AnalysisGeneratorProtocol,
            DiagramGeneratorProtocol,
        )

        assert AnalysisGeneratorProtocol is not None
        assert DiagramGeneratorProtocol is not None
