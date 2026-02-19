"""Pydantic configuration models."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


class ResearchPreset(str, Enum):
    """Research mode presets for deep research pipeline."""

    QUICK = "quick"
    DEFAULT = "default"
    THOROUGH = "thorough"


class GenerationMode(str, Enum):
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


class LocalEmbeddingConfig(BaseModel):
    """Configuration for local embedding model."""

    model_config = {"frozen": True}

    model: str = Field(
        default="all-MiniLM-L6-v2", description="Model name for sentence-transformers"
    )


class OpenAIEmbeddingConfig(BaseModel):
    """Configuration for OpenAI embedding model."""

    model_config = {"frozen": True}

    model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )


class EmbeddingConfig(BaseModel):
    """Embedding provider configuration."""

    model_config = {"frozen": True}

    provider: Literal["local", "openai"] = Field(
        default="local", description="Embedding provider"
    )
    local: LocalEmbeddingConfig = Field(default_factory=LocalEmbeddingConfig)
    openai: OpenAIEmbeddingConfig = Field(default_factory=OpenAIEmbeddingConfig)


class OllamaConfig(BaseModel):
    """Configuration for Ollama LLM."""

    model_config = {"frozen": True}

    model: str = Field(default="qwen3-coder:30b", description="Ollama model name")
    base_url: str = Field(
        default="http://localhost:11434", description="Ollama API URL"
    )


class AnthropicConfig(BaseModel):
    """Configuration for Anthropic LLM."""

    model_config = {"frozen": True}

    model: str = Field(
        default="claude-sonnet-4-20250514", description="Anthropic model name"
    )


class OpenAILLMConfig(BaseModel):
    """Configuration for OpenAI LLM."""

    model_config = {"frozen": True}

    model: str = Field(default="gpt-4o", description="OpenAI model name")


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    model_config = {"frozen": True}

    provider: Literal["ollama", "anthropic", "openai"] = Field(
        default="ollama", description="LLM provider"
    )
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    openai: OpenAILLMConfig = Field(default_factory=OpenAILLMConfig)


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


def _get_default_parallel_workers() -> int:
    """Get the default number of parallel workers based on CPU count.

    Returns a reasonable default: min(CPU count, 8) to avoid excessive overhead.
    Falls back to 4 if CPU count cannot be determined.
    """
    import os

    try:
        cpu_count = os.cpu_count()
        if cpu_count is None:
            return 4
        # Cap at 8 to avoid excessive thread overhead
        return min(cpu_count, 8)
    except (NotImplementedError, OSError):
        return 4


class EmbeddingBatchConfig(BaseModel):
    """Embedding batch processing configuration."""

    model_config = {"frozen": True}

    batch_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Number of texts to embed per batch. "
        "Local models can handle larger batches (100-200), API providers should use smaller (20-50).",
    )
    concurrency: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Number of batches to process in parallel. "
        "Higher values speed up embedding but increase memory/API usage.",
    )
    rate_limit_rpm: int | None = Field(
        default=None,
        description="Requests per minute limit for API providers. "
        "If set, embedding will be throttled to respect this limit. "
        "Set to None for local providers or when using default API limits.",
    )
    retry_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for failed batches.",
    )
    retry_base_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Base delay in seconds between retry attempts (exponential backoff).",
    )

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        """Validate batch_size is reasonable."""
        if v < 1:
            raise ValueError("batch_size must be >= 1")
        return v

    @field_validator("concurrency")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        """Validate concurrency doesn't exceed reasonable limits."""
        cpu_count = os.cpu_count() or 4
        max_concurrency = min(16, cpu_count * 2)
        return min(v, max_concurrency)


class ASTCacheConfig(BaseModel):
    """AST cache configuration for tree-sitter parser.

    Caches parsed ASTs to speed up incremental indexing by avoiding
    re-parsing of unchanged files.
    """

    model_config = {"frozen": True}

    enabled: bool = Field(
        default=True, description="Enable AST caching for incremental indexing"
    )
    max_entries: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Maximum number of cached ASTs before LRU eviction",
    )
    ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,  # 24 hours max
        description="Cache TTL in seconds (default: 1 hour)",
    )


class ChunkingConfig(BaseModel):
    """Chunking configuration."""

    model_config = {"frozen": True}

    max_chunk_tokens: int = Field(default=512, description="Max tokens per chunk")
    overlap_tokens: int = Field(default=50, description="Overlap between chunks")
    batch_size: int = Field(
        default=500,
        description="Number of chunks to process in each batch for memory efficiency",
    )
    class_split_threshold: int = Field(
        default=100,
        description="Line count threshold above which classes are split into summary + method chunks",
    )
    parallel_workers: int = Field(
        default_factory=_get_default_parallel_workers,
        ge=1,
        le=32,
        description="Number of parallel workers for file parsing. "
        "Defaults to min(CPU count, 8). Higher values speed up indexing on multi-core systems.",
    )

    @field_validator("parallel_workers")
    @classmethod
    def validate_parallel_workers(cls, v: int) -> int:
        """Validate parallel_workers doesn't exceed CPU count."""
        if v < 1:
            raise ValueError("parallel_workers must be >= 1")
        cpu_count = os.cpu_count() or 4
        return min(v, cpu_count)

    @model_validator(mode="after")
    def validate_overlap_less_than_max(self) -> "ChunkingConfig":
        """Validate overlap_tokens is less than max_chunk_tokens."""
        if self.overlap_tokens >= self.max_chunk_tokens:
            raise ValueError(
                f"overlap_tokens ({self.overlap_tokens}) must be less than "
                f"max_chunk_tokens ({self.max_chunk_tokens})"
            )
        return self


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


# Default prompts optimized for each provider
# Ollama: Concise, direct (local models have limited context)
# Anthropic: Detailed, nuanced (Claude excels at complex instructions)
# OpenAI: Balanced, structured

WIKI_SYSTEM_PROMPTS = {
    "ollama": """You are a technical documentation expert. Generate clear, concise documentation.

RULES:
- Use markdown formatting
- Write class/function names as plain text for cross-linking
- ONLY describe what you see in the code - never guess or invent
- If uncertain, omit the information""",
    "anthropic": """You are a technical documentation expert. Generate clear, concise documentation for code.

FORMATTING:
- Use markdown formatting
- Include code examples where helpful
- When mentioning class or function names in prose explanations, write them as plain text (e.g., "The WikiGenerator class") rather than inline code, so they can be cross-linked
- Only use backticks for code snippets, variable names in context, or when showing exact syntax

ACCURACY CONSTRAINTS - CRITICAL:
- ONLY describe what you can verify from the code/context provided
- NEVER invent or guess features, libraries, patterns, or capabilities not explicitly shown
- NEVER fabricate CLI commands, API endpoints, or configuration options
- If the context doesn't show something, DO NOT mention it
- When uncertain, omit the information rather than guess
- Stick to facts from the provided code - do not extrapolate or assume

CONTENT GUIDELINES:
- Focus on explaining what the code does and how to use it
- Keep explanations practical and actionable
- Base technology stack descriptions ONLY on actual dependencies shown
- Base directory structure descriptions ONLY on actual files listed""",
    "openai": """You are a technical documentation expert. Generate clear, concise documentation for code.

FORMATTING:
- Use markdown formatting
- Include code examples where helpful
- Write class/function names as plain text (not in backticks) so they can be cross-linked
- Only use backticks for actual code snippets

ACCURACY RULES:
- ONLY describe what is shown in the provided code
- NEVER invent features, patterns, or capabilities not explicitly shown
- If uncertain about something, omit it rather than guess
- Base all descriptions on actual code/dependencies provided""",
}

WIKI_OVERVIEW_PROMPTS = {
    "ollama": """You are a technical documentation expert writing a project overview.

RULES:
- Use markdown formatting
- Ground your description against any AUTHORITATIVE PROJECT DOCUMENTATION provided
- ONLY describe features you can verify from the code samples
- If the authoritative docs mention something, prioritize it over inferences from code""",
    "anthropic": """You are a technical documentation expert writing a project overview page.

GROUNDING:
- If AUTHORITATIVE PROJECT DOCUMENTATION is provided, treat it as the most reliable source of truth
- Align your description and features with the authoritative docs
- Code samples provide supporting detail but should not contradict the authoritative docs

FORMATTING:
- Use markdown formatting
- Include code examples where helpful
- Write class/function names as plain text for cross-linking

ACCURACY CONSTRAINTS - CRITICAL:
- ONLY describe features you can VERIFY from the provided sources
- NEVER invent features, libraries, or capabilities not shown
- Base technology stack descriptions ONLY on actual dependencies
- When uncertain, omit rather than guess""",
    "openai": """You are a technical documentation expert writing a project overview.

RULES:
- Ground your description against any AUTHORITATIVE PROJECT DOCUMENTATION provided
- ONLY describe features verifiable from the provided sources
- Write class/function names as plain text for cross-linking
- When uncertain, omit rather than guess""",
}

WIKI_ARCHITECTURE_PROMPTS = {
    "ollama": """You are a technical documentation expert writing architecture documentation.

RULES:
- Use markdown formatting
- Describe component relationships visible in the code
- Do NOT invent design patterns not shown in the code
- Write class names as plain text for cross-linking""",
    "anthropic": """You are a technical documentation expert writing architecture documentation.

FOCUS:
- Describe component relationships, data flow, and module boundaries visible in the code
- Explain how components interact based on actual imports and call patterns
- Create accurate Mermaid diagrams showing ONLY relationships visible in the code

FORMATTING:
- Use markdown formatting with clear sections
- Write class/function names as plain text for cross-linking
- Only use backticks for code snippets and syntax

ACCURACY CONSTRAINTS - CRITICAL:
- ONLY describe classes, components, and patterns that are shown in the code
- ONLY mention design patterns if you can point to specific classes implementing them
- Do NOT invent components, relationships, or data flows not visible in the code
- If AUTHORITATIVE PROJECT DOCUMENTATION is provided, align your architecture description with it
- If uncertain about a relationship, omit it rather than guess""",
    "openai": """You are a technical documentation expert writing architecture documentation.

RULES:
- Describe component relationships visible in the code
- Only mention design patterns if supported by specific code
- Write class names as plain text for cross-linking
- Do NOT invent components or relationships not shown in the code""",
}

WIKI_FILE_PROMPTS = {
    "ollama": """You are a technical documentation expert writing file-level documentation.

RULES:
- Use markdown formatting
- Document each class and function visible in the code
- Use caller/import context to explain integration
- Do NOT invent APIs or methods not shown""",
    "anthropic": """You are a technical documentation expert writing file-level documentation.

FOCUS:
- Provide precise API documentation for each class, method, and function
- Use the caller and import context to explain how this file integrates with the codebase
- Document parameters, return types, and side effects as shown in the code

FORMATTING:
- Use markdown formatting with clear sections
- Write class/function names as plain text for cross-linking
- Only use backticks for code snippets and syntax
- Do NOT include mermaid class diagrams (they are auto-generated)

ACCURACY CONSTRAINTS - CRITICAL:
- ONLY document classes, methods, and functions that appear in the code
- ONLY describe parameters and return types visible in the signatures
- Do NOT invent additional methods, parameters, or capabilities
- Do NOT fabricate usage examples with APIs not visible in the code
- Use dependency and caller information to explain integration, but don't fabricate""",
    "openai": """You are a technical documentation expert writing file-level documentation.

RULES:
- Document each class and function with precise API details from the code
- Use caller/import context for integration explanations
- Write class names as plain text for cross-linking
- Do NOT invent APIs, methods, or parameters not shown""",
}

WIKI_MODULE_PROMPTS = {
    "ollama": """You are a technical documentation expert writing module documentation.

RULES:
- Use markdown formatting
- Explain the module's purpose based on the code shown
- Use the file list to ground your description
- Do NOT invent components not shown""",
    "anthropic": """You are a technical documentation expert writing module-level documentation.

FOCUS:
- Explain the module's overall purpose and responsibility within the project
- Use the file list to describe the module's scope and organization
- Use import information to explain module dependencies
- If AUTHORITATIVE PROJECT DOCUMENTATION is provided, align your description with it

FORMATTING:
- Use markdown formatting with clear sections
- Write class/function names as plain text for cross-linking
- Only use backticks for code snippets and syntax

ACCURACY CONSTRAINTS - CRITICAL:
- ONLY describe classes, functions, and behaviors visible in the code context
- Use the file list to ground your description of module scope
- Do NOT invent additional components or behaviors not shown
- Do NOT fabricate usage patterns or APIs not visible in the code""",
    "openai": """You are a technical documentation expert writing module documentation.

RULES:
- Explain the module's purpose based on code shown and file list
- Use import information for dependency context
- Write class names as plain text for cross-linking
- Do NOT invent components not shown in the code""",
}

RESEARCH_DECOMPOSITION_PROMPTS = {
    "ollama": """Break complex questions into simpler sub-questions. Respond with JSON only.""",
    "anthropic": """You are analyzing questions about codebases. Your task is to break down complex questions into simpler sub-questions that can be investigated independently.

Always respond with valid JSON only, no other text.""",
    "openai": """You are analyzing questions about codebases. Break down complex questions into simpler sub-questions for investigation.

Always respond with valid JSON only.""",
}

RESEARCH_GAP_ANALYSIS_PROMPTS = {
    "ollama": """Identify missing information needed to answer the question. Respond with JSON only.""",
    "anthropic": """You are analyzing code context to identify missing information. Your task is to determine what additional context would help answer the question more completely.

Always respond with valid JSON only, no other text.""",
    "openai": """You are analyzing code context to identify gaps. Determine what additional context would help answer the question.

Always respond with valid JSON only.""",
}

RESEARCH_SYNTHESIS_PROMPTS = {
    "ollama": """You are a senior software engineer. Explain code architecture clearly based on the provided context. Cite specific files and line numbers.""",
    "anthropic": """You are a senior software engineer explaining code architecture. Provide clear, accurate answers based on the code context provided. Always cite specific files and line numbers when referencing code.

When explaining:
- Be precise and accurate
- Reference specific code locations
- Explain architectural decisions and patterns
- Note any limitations or uncertainties in your analysis""",
    "openai": """You are a senior software engineer explaining code architecture. Provide clear, accurate answers based on the code context provided.

Guidelines:
- Cite specific files and line numbers when referencing code
- Explain architectural reasoning
- Note any limitations or uncertainties""",
}


class ProviderPromptsConfig(BaseModel):
    """Prompts configuration for a specific provider."""

    model_config = {"frozen": True}

    wiki_system: str = Field(
        description="System prompt for wiki documentation generation"
    )
    research_decomposition: str = Field(
        description="System prompt for question decomposition"
    )
    research_gap_analysis: str = Field(description="System prompt for gap analysis")
    research_synthesis: str = Field(description="System prompt for answer synthesis")


class PromptsConfig(BaseModel):
    """Provider-specific prompts configuration."""

    model_config = {"frozen": True}

    custom_dir: str | None = Field(
        default=None,
        description="Custom prompts directory path. Prompts in this directory "
        "override built-in defaults. Supports files like wiki_system.md, "
        "wiki_system.anthropic.md (provider-specific), etc.",
    )

    ollama: ProviderPromptsConfig = Field(
        default_factory=lambda: ProviderPromptsConfig(
            wiki_system=WIKI_SYSTEM_PROMPTS["ollama"],
            research_decomposition=RESEARCH_DECOMPOSITION_PROMPTS["ollama"],
            research_gap_analysis=RESEARCH_GAP_ANALYSIS_PROMPTS["ollama"],
            research_synthesis=RESEARCH_SYNTHESIS_PROMPTS["ollama"],
        )
    )
    anthropic: ProviderPromptsConfig = Field(
        default_factory=lambda: ProviderPromptsConfig(
            wiki_system=WIKI_SYSTEM_PROMPTS["anthropic"],
            research_decomposition=RESEARCH_DECOMPOSITION_PROMPTS["anthropic"],
            research_gap_analysis=RESEARCH_GAP_ANALYSIS_PROMPTS["anthropic"],
            research_synthesis=RESEARCH_SYNTHESIS_PROMPTS["anthropic"],
        )
    )
    openai: ProviderPromptsConfig = Field(
        default_factory=lambda: ProviderPromptsConfig(
            wiki_system=WIKI_SYSTEM_PROMPTS["openai"],
            research_decomposition=RESEARCH_DECOMPOSITION_PROMPTS["openai"],
            research_gap_analysis=RESEARCH_GAP_ANALYSIS_PROMPTS["openai"],
            research_synthesis=RESEARCH_SYNTHESIS_PROMPTS["openai"],
        )
    )

    def get_for_provider(self, provider: str) -> ProviderPromptsConfig:
        """Get prompts for a specific provider.

        Args:
            provider: Provider name ("ollama", "anthropic", "openai").

        Returns:
            ProviderPromptsConfig for the specified provider.
            Falls back to anthropic prompts for unknown providers.
        """
        if provider == "ollama":
            return self.ollama
        elif provider == "openai":
            return self.openai
        else:
            # Default to anthropic (most detailed prompts)
            return self.anthropic


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
        if self.embedding.provider == "local":
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
        if self.llm.provider == "ollama":
            return min(base_concurrency, 3)

        # Cloud providers: allow higher concurrency, cap at configured limit
        return base_concurrency

    def with_embedding_provider(self, provider: Literal["local", "openai"]) -> "Config":
        """Return a new Config with the embedding provider changed.

        Args:
            provider: The embedding provider to use.

        Returns:
            A new Config instance with the updated embedding provider.
        """
        new_embedding = self.embedding.model_copy(update={"provider": provider})
        return self.model_copy(update={"embedding": new_embedding})

    def with_llm_provider(
        self, provider: Literal["ollama", "anthropic", "openai"]
    ) -> "Config":
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
