"""Search-related configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SearchCacheConfig(BaseModel):
    """Search result caching configuration for vector store."""

    model_config = {"frozen": True}

    enabled: bool = Field(default=True, description="Enable search result caching")
    ttl_seconds: int = Field(
        default=3600,  # 1 hour
        ge=60,
        le=86400,  # 24 hours max
        description="Cache TTL in seconds (default: 1 hour)",
    )
    max_entries: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum cache entries before eviction",
    )
    similarity_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for semantic cache hit (0.0-1.0)",
    )


class SearchConfig(BaseModel):
    """Search behavior configuration for precision/recall trade-offs.

    Controls search profiles and adaptive search depth estimation.
    """

    model_config = {"frozen": True}

    default_profile: Literal["fast", "balanced", "thorough"] = Field(
        default="balanced",
        description="Default search profile for precision/recall trade-off. "
        "'fast' = fewer candidates, faster response; "
        "'balanced' = default behavior, good balance; "
        "'thorough' = exhaustive search, best recall but slower.",
    )
    adaptive_search_enabled: bool = Field(
        default=True,
        description="Enable adaptive search depth estimation. "
        "When enabled, search depth adjusts based on query complexity and history.",
    )
    fast_min_similarity: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for 'fast' profile (0.0-1.0).",
    )
    balanced_min_similarity: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for 'balanced' profile (0.0-1.0).",
    )
    thorough_min_similarity: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for 'thorough' profile (0.0-1.0).",
    )
    reranker_model: str | None = Field(
        default=None,
        description="Cross-encoder model for reranking search results "
        "(e.g. 'cross-encoder/ms-marco-MiniLM-L-6-v2'). "
        "When None, reranking is disabled.",
    )
    default_search_mode: Literal["vector", "keyword", "hybrid"] = Field(
        default="vector",
        description="Default search mode for code search. "
        "'vector' = semantic embedding search (default); "
        "'keyword' = BM25 full-text search; "
        "'hybrid' = combined vector + BM25 with Reciprocal Rank Fusion.",
    )
    bm25_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight of BM25 results in hybrid search RRF (0.0-1.0). "
        "Vector weight is always 1.0. Higher values favor keyword matches.",
    )


class LazyIndexConfig(BaseModel):
    """Lazy vector index configuration for deferred index creation.

    When enabled, vector indexes are not created immediately when the table
    reaches the minimum row threshold. Instead, index creation is scheduled
    as a background task after initial indexing completes, or triggered
    on-demand when search latency exceeds the threshold.
    """

    model_config = {"frozen": True}

    enabled: bool = Field(
        default=True,
        description="Enable lazy/deferred vector index creation. "
        "When enabled, indexes are created in the background after initial indexing.",
    )
    latency_threshold_ms: int = Field(
        default=500,
        ge=50,
        le=5000,
        description="Search latency threshold in milliseconds. "
        "If average latency exceeds this, index creation is triggered automatically.",
    )
    min_rows: int = Field(
        default=1000,
        ge=100,
        le=100000,
        description="Minimum number of rows before considering index creation. "
        "Tables smaller than this threshold use brute-force search.",
    )
    latency_window_size: int = Field(
        default=10,
        ge=3,
        le=100,
        description="Number of recent searches to consider for latency calculation.",
    )


class FuzzySearchConfig(BaseModel):
    """Fuzzy search configuration for typo-tolerant code search.

    When semantic search results have low similarity scores, fuzzy matching
    can be automatically enabled to provide "Did you mean?" suggestions
    based on function/class names in the codebase.
    """

    model_config = {"frozen": True}

    auto_fuzzy_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Similarity score threshold below which fuzzy matching is auto-enabled. "
        "When the best result has a score below this threshold, fuzzy suggestions are generated.",
    )
    suggestion_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum fuzzy similarity score (0.0-1.0) for a name to be included "
        "in 'Did you mean?' suggestions.",
    )
    max_suggestions: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of 'Did you mean?' suggestions to return.",
    )
    enable_auto_fuzzy: bool = Field(
        default=True,
        description="Enable automatic fuzzy fallback when semantic results are poor. "
        "When disabled, fuzzy matching is only used if explicitly requested.",
    )


class GraphRAGConfig(BaseModel):
    """Knowledge graph-augmented retrieval configuration.

    When enabled, entities and relationships are extracted during indexing
    and stored in LanceDB tables. During queries, graph traversal expands
    vector search results with structurally related code.
    """

    model_config = {"frozen": True}

    enabled: bool = Field(
        default=False,
        description="Enable GraphRAG knowledge graph extraction and retrieval. "
        "When disabled (default), no graph tables are created and queries "
        "use pure vector search.",
    )
    max_traversal_depth: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Maximum BFS depth when expanding search results via the graph.",
    )
    max_graph_neighbors: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Maximum neighbor entities to add from graph expansion.",
    )
    relationship_types: list[str] = Field(
        default=["calls", "imports", "inherits_from", "contains", "references"],
        description="Relationship types to traverse during graph expansion.",
    )
    score_boost_factor: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Score multiplier for graph-discovered chunks relative to "
        "the minimum vector search score. Lower values rank graph results below "
        "vector results.",
    )
    extract_during_index: bool = Field(
        default=True,
        description="Extract entities and relationships during indexing. "
        "If False, graph must be built separately.",
    )
