"""Parameter objects for the search and embedding pipelines.

Frozen dataclasses that bundle long parameter lists into cohesive groups,
eliminating ``long_parameter_list`` design smells across the vectorstore
subsystem.

Each dataclass follows the project convention of ``@dataclass(frozen=True)``
to ensure immutability (see ``ResearchConfig``, ``SearchRequest`` for prior art).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from local_deepwiki.models import CodeChunk

if TYPE_CHECKING:
    from local_deepwiki.core.vectorstore.maintenance import LazyIndexManager
    from local_deepwiki.core.vectorstore.utils import RateLimiter
    from local_deepwiki.providers.base import EmbeddingProvider

    from .schema import SearchProfile

# Type alias matching the one in search_engine.py / search_pipeline.py
RowToChunk = Callable[[dict[str, Any]], CodeChunk]


@dataclass(frozen=True, slots=True)
class SearchPipelineParams:
    """Immutable bundle for the low-level search pipeline functions.

    Groups the parameters that ``run_vector_pipeline``,
    ``run_hybrid_pipeline``, and ``dispatch_search`` all share: the LanceDB
    table, query data, filters, fetch limit, scoring thresholds, and the
    infrastructure callbacks needed to convert rows and track latency.
    """

    table: Any
    query: str
    query_embedding: list[float]
    filters: list[str]
    fetch_limit: int
    min_similarity: float
    bm25_weight: float
    row_to_chunk: RowToChunk
    lazy_index_manager: "LazyIndexManager"


@dataclass(frozen=True, slots=True)
class SearchExecutionContext:
    """Immutable bundle for the resolved search execution state.

    Carries the post-resolution values that ``_execute_and_record`` and
    ``_record_and_store_results`` need after the ``SearchEngine`` has
    resolved profiles, modes, and cache eligibility.
    """

    query_embedding: list[float]
    filters: list[str]
    profile_config: Any
    resolved_profile: "SearchProfile"
    effective_min_similarity: float
    effective_mode: str
    use_cache: bool


@dataclass(frozen=True, slots=True)
class EmbeddingBatchParams:
    """Immutable bundle for embedding batch execution parameters.

    Groups the provider, configuration, and concurrency controls that
    ``embed_single_batch_with_retry`` and ``_run_parallel_batches`` need.
    """

    embedding_provider: "EmbeddingProvider"
    config: Any  # EmbeddingBatchConfig
    rate_limiter: "RateLimiter | None"
    semaphore: Any  # asyncio.Semaphore


@dataclass(frozen=True, slots=True)
class SearchEngineConfig:
    """Immutable configuration scalars for ``SearchEngine.__init__``.

    Bundles the scalar configuration options that are orthogonal to the
    injected collaborator objects (table accessor, embedding provider, etc.).
    """

    default_search_profile: Any = None  # SearchProfile enum; default set at use site
    adaptive_search_enabled: bool = True
    default_search_mode: str = "vector"
    bm25_weight: float = 0.3
