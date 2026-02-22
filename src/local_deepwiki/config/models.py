"""Pydantic configuration models."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from local_deepwiki.config.processing_models import (
    ASTCacheConfig,
    ChunkingConfig,
    EmbeddingBatchConfig,
    _get_default_parallel_workers,
)
from local_deepwiki.config.prompts import (
    RESEARCH_DECOMPOSITION_PROMPTS,
    RESEARCH_GAP_ANALYSIS_PROMPTS,
    RESEARCH_SYNTHESIS_PROMPTS,
    WIKI_ARCHITECTURE_PROMPTS,
    WIKI_FILE_PROMPTS,
    WIKI_MODULE_PROMPTS,
    WIKI_OVERVIEW_PROMPTS,
    WIKI_SYSTEM_PROMPTS,
    PromptsConfig,
    ProviderPromptsConfig,
)
from local_deepwiki.config.provider_models import (
    AnthropicConfig,
    EmbeddingConfig,
    LLMConfig,
    LocalEmbeddingConfig,
    OllamaConfig,
    OpenAIEmbeddingConfig,
    OpenAILLMConfig,
)
from local_deepwiki.models.provider_types import EmbeddingProviderType, LLMProviderType


class ResearchPreset(StrEnum):
    """Research mode presets for deep research pipeline."""

    QUICK = "quick"
    DEFAULT = "default"
    THOROUGH = "thorough"


class GenerationMode(StrEnum):
    """Wiki page generation strategy."""

    EAGER = "eager"
    LAZY = "lazy"
    HYBRID = "hybrid"


# Preset parameter values for each research mode
RESEARCH_PRESETS: dict[ResearchPreset, dict[str, Any]] = {
    ResearchPreset.QUICK: {
        "max_sub_questions": 2,
        "chunks_per_subquestion": 3,
        "max_total_chunks": 15,
        "max_follow_up_queries": 1,
        "synthesis_temperature": 0.3,
        "synthesis_max_tokens": 2048,
    },
    ResearchPreset.DEFAULT: {
        "max_sub_questions": 4,
        "chunks_per_subquestion": 5,
        "max_total_chunks": 30,
        "max_follow_up_queries": 3,
        "synthesis_temperature": 0.5,
        "synthesis_max_tokens": 4096,
    },
    ResearchPreset.THOROUGH: {
        "max_sub_questions": 6,
        "chunks_per_subquestion": 8,
        "max_total_chunks": 50,
        "max_follow_up_queries": 5,
        "synthesis_temperature": 0.5,
        "synthesis_max_tokens": 8192,
    },
}


class ParsingConfig(BaseModel):
    """Code parsing configuration."""

    model_config = {"frozen": True}

    languages: list[str] = Field(
        default=[
            "python",
            "typescript",
            "javascript",
            "go",
            "rust",
            "java",
            "c",
            "cpp",
            "swift",
            "ruby",
            "php",
            "kotlin",
            "csharp",
        ],
        description="Languages to parse",
    )
    max_file_size: int = Field(
        default=1048576, description="Max file size in bytes (1MB)"
    )
    exclude_patterns: list[str] = Field(
        default=[
            "node_modules/**",
            "venv/**",
            ".venv/**",
            "__pycache__/**",
            ".git/**",
            "*.min.js",
            "*.min.css",
            "dist/**",
            "build/**",
            ".next/**",
            "target/**",
            "vendor/**",
            "htmlcov/**",
            ".pytest_cache/**",
            ".mypy_cache/**",
            ".ruff_cache/**",
            ".tox/**",
            ".nox/**",
            "coverage/**",
            ".coverage",
            "coverage_html/**",
            "coverage_openai_embeddings/**",
            ".claude/**",
            ".windsurf/**",
            ".cursor/**",
            ".aider/**",
            "agents/**",
            "AGENTS.md",
        ],
        description="Glob patterns to exclude",
    )


class WikiConfig(BaseModel):
    """Wiki generation configuration."""

    model_config = {"frozen": True}

    max_file_docs: int = Field(
        default=500,
        description="Maximum number of file-level documentation pages to generate. "
        "Set to 0 for unlimited.",
    )
    max_concurrent_llm_calls: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Maximum concurrent LLM calls for file documentation generation. "
        "Higher values speed up generation but increase memory/API usage.",
    )
    use_cloud_for_github: bool = Field(
        default=False,
        description="Use cloud LLM provider (Anthropic Claude) for GitHub repos. "
        "Provides faster, higher-quality documentation but requires API key.",
    )
    github_llm_provider: Literal["anthropic", "openai"] = Field(
        default="anthropic",
        description="Cloud LLM provider to use for GitHub repos when use_cloud_for_github is enabled.",
    )
    chat_llm_provider: Literal["default", "anthropic", "openai", "ollama"] = Field(
        default="default",
        description="LLM provider for chat Q&A. 'default' uses the main llm.provider setting. "
        "Set to 'anthropic' or 'openai' for higher-quality chat responses.",
    )
    import_search_limit: int = Field(
        default=200,
        description="Maximum chunks to search for import/relationship analysis",
    )
    context_search_limit: int = Field(
        default=50,
        description="Maximum chunks to search for context when generating documentation",
    )
    fallback_search_limit: int = Field(
        default=30, description="Maximum chunks to search in fallback queries"
    )
    max_chunk_content_chars: int = Field(
        default=15000,
        ge=500,
        le=50000,
        description="Maximum characters of chunk content included in LLM prompts "
        "during wiki generation. Higher values produce more accurate documentation "
        "for large functions but increase token usage. The previous hardcoded limit "
        "was 1500.",
    )
    max_chunks_per_file: int = Field(
        default=60,
        ge=5,
        le=200,
        description="Maximum number of code chunks included in the LLM prompt when "
        "generating file-level documentation. Chunks are prioritized by type "
        "(functions/methods first, then classes, then module/imports) so the most "
        "documentation-relevant content is preserved when files exceed this limit.",
    )
    codemap_enabled: bool = Field(
        default=True,
        description="Enable automatic codemap generation during wiki build. "
        "Generates execution-flow diagrams for high-value entry points.",
    )
    codemap_max_topics: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum number of codemap topics to auto-generate (0 to disable).",
    )
    codemap_max_depth: int = Field(
        default=4,
        ge=1,
        le=10,
        description="BFS traversal depth for codemap generation.",
    )
    codemap_max_nodes: int = Field(
        default=30,
        ge=5,
        le=60,
        description="Maximum nodes per codemap graph.",
    )
    generation_mode: GenerationMode = Field(
        default=GenerationMode.EAGER,
        description="Wiki page generation strategy. "
        "'eager' (default): generate all pages during indexing. "
        "'lazy': generate pages on first read. "
        "'hybrid': generate summary pages and top N files at index time, rest on demand.",
    )
    hybrid_eager_pages: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Number of top file pages to eagerly generate in hybrid mode.",
    )
    prefetch_workers: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Background workers for predictive page prefetch (0 disables). "
        "Only active in lazy and hybrid modes.",
    )
    prefetch_max_queue: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum pages in the prefetch queue.",
    )
    prefetch_drain: bool = Field(
        default=False,
        description="When true, prefetch workers will eventually generate all "
        "remaining pages after prediction queue drains and system is idle.",
    )
    drain_idle_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Seconds of idle time before drain mode starts backfilling.",
    )

    @field_validator("max_concurrent_llm_calls")
    @classmethod
    def validate_max_concurrent_llm_calls(cls, v: int) -> int:
        """Validate max_concurrent_llm_calls is reasonable."""
        if v < 1:
            raise ValueError("max_concurrent_llm_calls must be >= 1")
        cpu_count = os.cpu_count() or 4
        return min(v, cpu_count * 2)

    @model_validator(mode="after")
    def validate_search_limits(self) -> "WikiConfig":
        """Validate search limits are consistent."""
        if self.fallback_search_limit > self.context_search_limit:
            raise ValueError(
                f"fallback_search_limit ({self.fallback_search_limit}) should not exceed "
                f"context_search_limit ({self.context_search_limit})"
            )
        return self


class DeepResearchConfig(BaseModel):
    """Deep research pipeline configuration."""

    model_config = {"frozen": True}

    max_sub_questions: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum sub-questions generated from query decomposition",
    )
    chunks_per_subquestion: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Code chunks retrieved per sub-question",
    )
    max_total_chunks: int = Field(
        default=30,
        ge=10,
        le=100,
        description="Maximum total chunks used in synthesis",
    )
    max_follow_up_queries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum follow-up queries from gap analysis",
    )
    synthesis_temperature: float = Field(
        default=0.5,
        ge=0.0,
        le=2.0,
        description="LLM temperature for synthesis (higher = more creative)",
    )
    synthesis_max_tokens: int = Field(
        default=4096,
        ge=512,
        le=16000,
        description="Maximum tokens in synthesis response",
    )

    def with_preset(self, preset: ResearchPreset | str | None) -> "DeepResearchConfig":
        """Return a new config with preset values applied.

        The preset values override the current config values. If preset is None
        or "default", returns a copy of the current config unchanged.

        Args:
            preset: The research preset to apply ("quick", "default", "thorough").

        Returns:
            A new DeepResearchConfig with preset values applied.
        """
        if preset is None:
            return self.model_copy()

        # Convert string to enum if needed
        if isinstance(preset, str):
            try:
                preset = ResearchPreset(preset.lower())
            except ValueError:
                # Invalid preset name, return unchanged
                return self.model_copy()

        if preset == ResearchPreset.DEFAULT:
            return self.model_copy()

        # Get preset values and merge with current config
        preset_values = RESEARCH_PRESETS.get(preset, {})
        return self.model_copy(update=preset_values)


class PluginsConfig(BaseModel):
    """Plugin system configuration."""

    model_config = {"frozen": True}

    enabled: bool = Field(default=True, description="Enable plugin system")
    custom_dir: str | None = Field(
        default=None,
        description="Custom plugins directory path. Plugins in this directory "
        "are loaded in addition to repo and user plugins.",
    )
    disable_entry_points: bool = Field(
        default=False,
        description="Disable loading plugins from setuptools entry points",
    )


class HooksConfig(BaseModel):
    """Event hooks configuration."""

    model_config = {"frozen": True}

    enabled: bool = Field(default=True, description="Enable event hooks system")
    scripts_dir: str | None = Field(
        default=None,
        description="Directory containing hook scripts. Scripts are named by event type "
        "(e.g., index.complete.sh, wiki.page.complete.py).",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Maximum execution time for hook scripts in seconds",
    )


class ExportBatchConfig(BaseModel):
    """Export configuration for HTML and PDF generation."""

    model_config = {"frozen": True}

    batch_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Pages per batch for PDF generation in streaming mode",
    )
    memory_limit_mb: int = Field(
        default=500,
        ge=100,
        le=4096,
        description="Memory threshold to trigger streaming mode (MB). "
        "Wikis larger than this will use streaming export.",
    )
    enable_streaming: bool = Field(
        default=True,
        description="Enable streaming mode for large wikis. "
        "When enabled, pages are processed one at a time to avoid OOM.",
    )


class OutputConfig(BaseModel):
    """Output configuration."""

    model_config = {"frozen": True}

    wiki_dir: str = Field(default=".deepwiki", description="Wiki output directory name")
    vector_db_name: str = Field(
        default="vectors.lance", description="Vector DB filename"
    )


class EmbeddingCacheConfig(BaseModel):
    """Embedding cache configuration."""

    model_config = {"frozen": True}

    enabled: bool = Field(default=True, description="Enable embedding caching")
    ttl_seconds: int = Field(
        default=604800,  # 7 days
        ge=60,
        le=2592000,  # 30 days max
        description="Cache TTL in seconds (default: 7 days)",
    )
    max_entries: int = Field(
        default=100000,
        ge=1000,
        le=1000000,
        description="Maximum cache entries before cleanup (default: 100k)",
    )


class LLMCacheConfig(BaseModel):
    """LLM response caching configuration."""

    model_config = {"frozen": True}

    enabled: bool = Field(default=True, description="Enable LLM response caching")
    ttl_seconds: int = Field(
        default=604800,  # 7 days
        ge=60,
        le=2592000,  # 30 days max
        description="Cache TTL in seconds (default: 7 days)",
    )
    max_entries: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum cache entries before eviction",
    )
    similarity_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for cache hit (0.0-1.0)",
    )
    max_cacheable_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Maximum temperature to cache (higher = non-deterministic)",
    )


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


class Config(BaseModel):
    """Main configuration.

    This class and all nested config classes are frozen (immutable) to prevent
    accidental mutation of shared configuration state. Use model_copy(update={...})
    or the with_*() helper methods to create modified copies.
    """

    model_config = {"frozen": True}

    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    embedding_cache: EmbeddingCacheConfig = Field(default_factory=EmbeddingCacheConfig)
    embedding_batch: EmbeddingBatchConfig = Field(default_factory=EmbeddingBatchConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    llm_cache: LLMCacheConfig = Field(default_factory=LLMCacheConfig)
    search_cache: SearchCacheConfig = Field(default_factory=SearchCacheConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    lazy_index: LazyIndexConfig = Field(default_factory=LazyIndexConfig)
    fuzzy_search: FuzzySearchConfig = Field(default_factory=FuzzySearchConfig)
    parsing: ParsingConfig = Field(default_factory=ParsingConfig)
    ast_cache: ASTCacheConfig = Field(default_factory=ASTCacheConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    wiki: WikiConfig = Field(default_factory=WikiConfig)
    deep_research: DeepResearchConfig = Field(default_factory=DeepResearchConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    export: ExportBatchConfig = Field(default_factory=ExportBatchConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)

    @computed_field
    @property
    def effective_embedding_batch_size(self) -> int:
        """Compute optimal batch size based on provider and memory.

        Local providers can handle larger batches, while API providers
        should use smaller batches to avoid rate limits and timeouts.

        Returns:
            Optimal batch size for the current embedding provider.
        """
        base_batch_size = self.embedding_batch.batch_size

        # Local providers can handle larger batches
        if self.embedding.provider == EmbeddingProviderType.LOCAL:
            # Local models benefit from larger batches for throughput
            return min(base_batch_size, 200)
        else:
            # API providers need smaller batches to avoid rate limits
            return min(base_batch_size, 50)

    @computed_field
    @property
    def effective_max_workers(self) -> int:
        """Compute worker count based on CPU cores.

        Ensures we do not exceed available CPU cores while respecting
        user configuration.

        Returns:
            Optimal worker count for parallel processing.
        """
        cpu_count = os.cpu_count() or 4
        configured_workers = self.chunking.parallel_workers

        # Do not exceed CPU count, but also consider configured maximum
        return min(configured_workers, cpu_count)

    @computed_field
    @property
    def effective_llm_concurrency(self) -> int:
        """Compute effective LLM concurrency based on provider.

        Local models (Ollama) run on a single GPU and benefit from limited
        parallelism (2-3 concurrent requests). Cloud providers handle higher
        concurrency but may have rate limits.

        Returns:
            Optimal LLM concurrency for the current provider.
        """
        base_concurrency = self.wiki.max_concurrent_llm_calls

        # Local models: single GPU, limit to 2-3 to avoid OOM/thrashing
        if self.llm.provider == LLMProviderType.OLLAMA:
            return min(base_concurrency, 3)

        # Cloud providers: allow higher concurrency, cap at configured limit
        return base_concurrency

    def with_embedding_provider(
        self, provider: EmbeddingProviderType | str
    ) -> "Config":
        """Return a new Config with the embedding provider changed.

        Args:
            provider: The embedding provider to use.

        Returns:
            A new Config instance with the updated embedding provider.
        """
        new_embedding = self.embedding.model_copy(update={"provider": provider})
        return self.model_copy(update={"embedding": new_embedding})

    def with_llm_provider(self, provider: LLMProviderType | str) -> "Config":
        """Return a new Config with the LLM provider changed.

        Args:
            provider: The LLM provider to use.

        Returns:
            A new Config instance with the updated LLM provider.
        """
        new_llm = self.llm.model_copy(update={"provider": provider})
        return self.model_copy(update={"llm": new_llm})

    def get_prompts(self) -> ProviderPromptsConfig:
        """Get prompts for the currently configured LLM provider.

        Returns:
            ProviderPromptsConfig for the current LLM provider.
        """
        return self.prompts.get_for_provider(self.llm.provider)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load configuration from file or defaults."""
        if config_path and config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f)
            return cls.model_validate(data)

        # Check default locations
        default_paths = [
            Path.home() / ".config" / "local-deepwiki" / "config.yaml",
            Path.home() / ".local-deepwiki.yaml",
        ]
        for path in default_paths:
            if path.exists():
                with open(path) as f:
                    data = yaml.safe_load(f)
                return cls.model_validate(data)

        return cls()

    def get_wiki_path(self, repo_path: Path) -> Path:
        """Get the wiki output path for a repository."""
        return repo_path / self.output.wiki_dir

    def get_vector_db_path(self, repo_path: Path) -> Path:
        """Get the vector database path for a repository."""
        return self.get_wiki_path(repo_path) / self.output.vector_db_name
