"""Protocol interfaces for service-layer components.

Defines structural typing contracts (``typing.Protocol``) for the service
layer so that handlers and other consumers can depend on the interface
rather than the concrete service class.  This raises the *abstractness*
metric for the ``services`` package and improves the overall coupling score.

All protocols are ``@runtime_checkable`` so that guards and diagnostic
code can use ``isinstance`` checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from local_deepwiki.services.analysis_service import (
        EntityExplainRequest,
        ImpactAnalysisRequest,
    )
    from local_deepwiki.services.indexing_service import IndexPipelineRequest
    from local_deepwiki.services.models import IndexPipelineResult, QueryResult
    from local_deepwiki.services.query_service import CodeSearchRequest, QuestionRequest


@runtime_checkable
class QueryServiceProtocol(Protocol):
    """Protocol defining the interface for the RAG query service.

    Handlers that execute RAG queries or code searches should accept
    this Protocol so that test doubles can be substituted without
    subclassing the concrete ``QueryService``.
    """

    async def answer_question(
        self,
        request: QuestionRequest,
    ) -> QueryResult:
        """Execute the full RAG pipeline: search -> [rerank] -> synthesize.

        Args:
            request: Immutable request containing repo path, question,
                max context, agentic RAG toggle, wiki path, and debug flag.

        Returns:
            QueryResult with the synthesized answer and source references.
        """
        ...

    async def search_code(
        self,
        request: CodeSearchRequest,
    ) -> list[dict[str, Any]]:
        """Search code with optional filters.

        Args:
            request: Immutable request containing repo path, query,
                limit, language, chunk type, path filter, fuzzy settings.

        Returns:
            List of result dicts with file_path, name, type, language,
            lines, score, preview, docstring, and optional highlights.
        """
        ...


@runtime_checkable
class AnalysisServiceProtocol(Protocol):
    """Protocol defining the interface for the entity analysis service.

    Handlers that perform entity explanation or impact analysis should
    accept this Protocol so that lightweight stubs can stand in for the
    concrete ``AnalysisService``.
    """

    async def explain_entity(
        self,
        request: EntityExplainRequest,
    ) -> dict[str, Any]:
        """Composite explanation of a code entity.

        Args:
            request: Immutable request with entity name, repo path,
                index status, wiki path, vector store, and section toggles.

        Returns:
            Dict with entity info and analysis sections.
        """
        ...

    async def impact_analysis(
        self,
        request: ImpactAnalysisRequest,
    ) -> dict[str, Any]:
        """Analyze the blast radius of changes to a file or entity.

        Args:
            request: Immutable request with file path, repo path,
                index status, wiki path, vector store, and section toggles.

        Returns:
            Dict with impact analysis results and risk level.
        """
        ...


@runtime_checkable
class IndexingServiceProtocol(Protocol):
    """Protocol defining the interface for the indexing service.

    Handlers that drive the indexing pipeline should accept this Protocol
    so that tests can provide a stub that returns canned results.
    """

    async def run_pipeline(
        self,
        request: IndexPipelineRequest,
    ) -> IndexPipelineResult:
        """Execute the full indexing pipeline.

        Args:
            request: Immutable request containing repo path, rebuild flag,
                provider overrides, generation mode, and progress callback.

        Returns:
            IndexPipelineResult with indexing statistics.
        """
        ...
