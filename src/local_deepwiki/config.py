"""Configuration management for local-deepwiki."""

import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Literal

import yaml
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


class ResearchPreset(str, Enum):
    """Research mode presets for deep research pipeline."""

    QUICK = "quick"
    DEFAULT = "default"
    THOROUGH = "thorough"


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
    except Exception:
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

        Cloud providers may have rate limits, so we adjust concurrency
        accordingly.

        Returns:
            Optimal LLM concurrency for the current provider.
        """
        base_concurrency = self.wiki.max_concurrent_llm_calls

        # Local models can handle more concurrent requests
        if self.llm.provider == "ollama":
            return base_concurrency

        # Cloud providers may have rate limits
        return min(base_concurrency, 5)

    @model_validator(mode="after")
    def validate_config_consistency(self) -> "Config":
        """Validate cross-field consistency.

        Ensures configuration values are consistent across different
        sections of the config.

        Returns:
            The validated config instance.

        Raises:
            ValueError: If configuration is inconsistent.
        """
        # Validate embedding batch rate limit makes sense for API providers
        if (
            self.embedding.provider == "openai"
            and self.embedding_batch.rate_limit_rpm is None
        ):
            # This is just a warning condition, not an error
            pass

        # Validate chunking and deep research are compatible
        if self.deep_research.max_total_chunks > 100:
            # Large chunk counts may cause memory issues
            pass

        return self

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


# Thread-safe global config singleton
_config: Config | None = None
_config_lock = threading.Lock()

# Context-local config override for async contexts
_context_config: ContextVar[Config | None] = ContextVar("config", default=None)


def get_config() -> Config:
    """Get the configuration instance.

    Returns the context-local config if set, otherwise the global config.
    Thread-safe for concurrent access.

    Returns:
        The active configuration instance.
    """
    # Check for context-local override first (async-safe)
    context_cfg = _context_config.get()
    if context_cfg is not None:
        return context_cfg

    # Fall back to global singleton (thread-safe)
    global _config
    with _config_lock:
        if _config is None:
            _config = Config.load()
        return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance.

    Thread-safe. Note: This sets the global config, not a context-local one.
    Use config_context() for temporary context-local overrides.

    Args:
        config: The configuration to set globally.
    """
    global _config
    with _config_lock:
        _config = config


def reset_config() -> None:
    """Reset the global configuration to uninitialized state.

    Useful for testing to ensure a fresh config is loaded.
    Also clears any context-local override.
    """
    global _config
    with _config_lock:
        _config = None
    _context_config.set(None)


@contextmanager
def config_context(config: Config) -> Generator[Config, None, None]:
    """Context manager for temporary config override.

    Sets a context-local configuration that takes precedence over the global
    config within the context. Useful for testing or per-request config.

    Args:
        config: The configuration to use within the context.

    Yields:
        The provided configuration.

    Example:
        with config_context(custom_config):
            # get_config() returns custom_config here
            do_something()
        # get_config() returns global config again
    """
    token = _context_config.set(config)
    try:
        yield config
    finally:
        _context_config.reset(token)


# ---------------------------------------------------------------------------
# ConfigChange and ConfigDiff classes for tracking configuration changes
# ---------------------------------------------------------------------------


@dataclass
class ConfigChange:
    """Represents a single configuration change.

    Attributes:
        field: The dot-separated path to the changed field (e.g., "llm.provider").
        old_value: The previous value of the field.
        new_value: The new value of the field.
        source: The source of the change ("cli", "env", "file", "default").
    """

    field: str
    old_value: Any
    new_value: Any
    source: str  # "cli", "env", "file", "default"

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        return f"{self.field}: {self.old_value!r} -> {self.new_value!r} (from {self.source})"


@dataclass
class ConfigDiff:
    """Tracks differences between two configurations.

    Useful for understanding what changed between config versions,
    debugging configuration issues, and auditing config changes.

    Example:
        base = Config()
        modified = Config(llm={"provider": "anthropic"})
        diff = ConfigDiff(base, modified)
        for change in diff.get_changes():
            print(f"Changed: {change}")
    """

    base: "Config"
    override: "Config"
    changes: list[ConfigChange] = field(default_factory=list)
    _computed: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        """Compute changes after initialization."""
        if not self._computed:
            self._compute_changes()
            object.__setattr__(self, "_computed", True)

    def _compute_changes(self, source: str = "override") -> None:
        """Compute the differences between base and override configs.

        Args:
            source: The source label for changes (default: "override").
        """
        self._compare_models(self.base, self.override, "", source)

    def _compare_models(
        self,
        base: BaseModel,
        override: BaseModel,
        prefix: str,
        source: str,
    ) -> None:
        """Recursively compare two Pydantic models.

        Args:
            base: The base model to compare from.
            override: The override model to compare to.
            prefix: The current field path prefix.
            source: The source label for changes.
        """
        # Get field names from the class (excluding computed fields)
        for field_name in type(base).model_fields:
            base_value = getattr(base, field_name)
            override_value = getattr(override, field_name)

            field_path = f"{prefix}.{field_name}" if prefix else field_name

            if isinstance(base_value, BaseModel) and isinstance(
                override_value, BaseModel
            ):
                # Recursively compare nested models
                self._compare_models(base_value, override_value, field_path, source)
            elif base_value != override_value:
                self.changes.append(
                    ConfigChange(
                        field=field_path,
                        old_value=base_value,
                        new_value=override_value,
                        source=source,
                    )
                )

    def get_changes(self) -> list[ConfigChange]:
        """Return list of changed fields.

        Returns:
            List of ConfigChange objects representing all differences.
        """
        return self.changes.copy()

    def get_changes_by_source(self, source: str) -> list[ConfigChange]:
        """Return changes from a specific source.

        Args:
            source: The source to filter by ("cli", "env", "file", "default").

        Returns:
            List of ConfigChange objects from the specified source.
        """
        return [c for c in self.changes if c.source == source]

    def has_changes(self) -> bool:
        """Check if there are any changes.

        Returns:
            True if there are any differences between base and override.
        """
        return len(self.changes) > 0

    def summary(self) -> str:
        """Return a human-readable summary of changes.

        Returns:
            A multi-line string summarizing all changes.
        """
        if not self.changes:
            return "No configuration changes"

        lines = [f"Configuration changes ({len(self.changes)} total):"]
        for change in self.changes:
            lines.append(f"  - {change}")
        return "\n".join(lines)

    def apply(self, config: "Config") -> "Config":
        """Apply changes to a config.

        Creates a new config with the changes applied. This is useful
        for applying a diff to a different base config.

        Args:
            config: The config to apply changes to.

        Returns:
            A new Config instance with changes applied.
        """
        if not self.changes:
            return config.model_copy()

        # Build update dict from changes
        updates: dict[str, Any] = {}
        for change in self.changes:
            parts = change.field.split(".")
            _set_nested_value(updates, parts, change.new_value)

        return _apply_nested_updates(config, updates)


def _set_nested_value(d: dict[str, Any], path: list[str], value: Any) -> None:
    """Set a nested value in a dictionary using a path.

    Args:
        d: The dictionary to update.
        path: List of keys representing the path.
        value: The value to set.
    """
    for key in path[:-1]:
        if key not in d:
            d[key] = {}
        d = d[key]
    d[path[-1]] = value


def _apply_nested_updates(config: "Config", updates: dict[str, Any]) -> "Config":
    """Apply nested updates to a config.

    Args:
        config: The config to update.
        updates: Dictionary of updates to apply.

    Returns:
        A new Config with updates applied.
    """
    model_updates: dict[str, Any] = {}

    for key, value in updates.items():
        if isinstance(value, dict):
            # Nested update
            current = getattr(config, key, None)
            if current is not None and isinstance(current, BaseModel):
                # Recursively apply to nested model
                nested_updates = {}
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, dict):
                        nested_current = getattr(current, nested_key, None)
                        if nested_current is not None and isinstance(
                            nested_current, BaseModel
                        ):
                            nested_updates[nested_key] = nested_current.model_copy(
                                update=nested_value
                            )
                        else:
                            nested_updates[nested_key] = nested_value
                    else:
                        nested_updates[nested_key] = nested_value
                model_updates[key] = current.model_copy(update=nested_updates)
            else:
                model_updates[key] = value
        else:
            model_updates[key] = value

    return config.model_copy(update=model_updates)


# ---------------------------------------------------------------------------
# Config merge with hierarchy
# ---------------------------------------------------------------------------


def merge_configs(
    cli_config: dict[str, Any] | None = None,
    env_config: dict[str, Any] | None = None,
    file_config: dict[str, Any] | None = None,
    defaults: Config | None = None,
) -> tuple[Config, ConfigDiff]:
    """Merge configs with CLI > env > file > defaults priority.

    Creates a merged configuration by layering config sources in priority
    order, where CLI arguments have the highest priority and defaults
    have the lowest.

    Args:
        cli_config: Configuration from command-line arguments.
        env_config: Configuration from environment variables.
        file_config: Configuration from config file.
        defaults: Default configuration (if None, uses Config()).

    Returns:
        A tuple of (merged_config, diff) where diff shows all changes
        from defaults.

    Example:
        cli = {"llm": {"provider": "anthropic"}}
        env = {"embedding": {"provider": "openai"}}
        file = {"chunking": {"max_chunk_tokens": 1024}}

        config, diff = merge_configs(cli, env, file)
        print(diff.summary())
    """
    if defaults is None:
        defaults = Config()

    # Start with defaults
    merged_data: dict[str, Any] = defaults.model_dump()

    # Track sources for diff
    change_sources: dict[str, str] = {}

    # Apply file config (lowest priority of overrides)
    if file_config:
        _deep_merge(merged_data, file_config)
        _track_sources(file_config, "", change_sources, "file")

    # Apply env config (medium priority)
    if env_config:
        _deep_merge(merged_data, env_config)
        _track_sources(env_config, "", change_sources, "env")

    # Apply CLI config (highest priority)
    if cli_config:
        _deep_merge(merged_data, cli_config)
        _track_sources(cli_config, "", change_sources, "cli")

    # Create the merged config
    merged = Config.model_validate(merged_data)

    # Compute diff with source tracking
    diff = ConfigDiff(defaults, merged)

    # Update change sources in the diff
    for change in diff.changes:
        if change.field in change_sources:
            change.source = change_sources[change.field]

    return merged, diff


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Deep merge override into base dictionary.

    Args:
        base: The base dictionary to merge into (modified in-place).
        override: The dictionary to merge from.
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _track_sources(
    config: dict[str, Any],
    prefix: str,
    sources: dict[str, str],
    source: str,
) -> None:
    """Track the source of each config field.

    Args:
        config: The config dictionary.
        prefix: Current field path prefix.
        sources: Dictionary mapping field paths to sources.
        source: The source label for this config.
    """
    for key, value in config.items():
        field_path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _track_sources(value, field_path, sources, source)
        else:
            sources[field_path] = source


# ---------------------------------------------------------------------------
# Config validation summary
# ---------------------------------------------------------------------------


def validate_config(config: Config) -> list[str]:
    """Return list of validation warnings/errors.

    Performs comprehensive validation of a configuration and returns
    a list of any warnings or potential issues found.

    Args:
        config: The configuration to validate.

    Returns:
        List of warning/error messages. Empty list means config is valid.

    Example:
        config = Config()
        warnings = validate_config(config)
        if warnings:
            for warning in warnings:
                print(f"Warning: {warning}")
    """
    warnings: list[str] = []

    # Check embedding configuration
    if config.embedding.provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            warnings.append(
                "OpenAI embedding provider selected but OPENAI_API_KEY not set"
            )

    # Check LLM configuration
    if config.llm.provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            warnings.append(
                "Anthropic LLM provider selected but ANTHROPIC_API_KEY not set"
            )
    elif config.llm.provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            warnings.append("OpenAI LLM provider selected but OPENAI_API_KEY not set")

    # Check for potential performance issues
    if config.chunking.parallel_workers > (os.cpu_count() or 4):
        warnings.append(
            f"parallel_workers ({config.chunking.parallel_workers}) exceeds "
            f"CPU count ({os.cpu_count() or 4}), may cause contention"
        )

    if config.embedding_batch.batch_size > 100 and config.embedding.provider != "local":
        warnings.append(
            f"Large embedding batch_size ({config.embedding_batch.batch_size}) "
            "with API provider may cause rate limiting"
        )

    # Check for memory concerns
    if config.deep_research.max_total_chunks > 50:
        warnings.append(
            f"Large max_total_chunks ({config.deep_research.max_total_chunks}) "
            "may cause high memory usage during research"
        )

    # Check cache configurations
    if config.embedding_cache.enabled and config.embedding_cache.max_entries > 500000:
        warnings.append(
            f"Very large embedding cache max_entries "
            f"({config.embedding_cache.max_entries}) may cause high memory usage"
        )

    # Check wiki configuration consistency
    if config.wiki.use_cloud_for_github:
        provider = config.wiki.github_llm_provider
        if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
            warnings.append(
                "use_cloud_for_github enabled with anthropic but "
                "ANTHROPIC_API_KEY not set"
            )
        elif provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            warnings.append(
                "use_cloud_for_github enabled with openai but OPENAI_API_KEY not set"
            )

    # Check plugin configuration
    if config.plugins.enabled and config.plugins.custom_dir:
        custom_path = Path(config.plugins.custom_dir)
        if not custom_path.exists():
            warnings.append(f"Custom plugins directory does not exist: {custom_path}")

    # Check hooks configuration
    if config.hooks.enabled and config.hooks.scripts_dir:
        scripts_path = Path(config.hooks.scripts_dir)
        if not scripts_path.exists():
            warnings.append(f"Hook scripts directory does not exist: {scripts_path}")

    return warnings


def load_config_from_env() -> dict[str, Any]:
    """Load configuration overrides from environment variables.

    Environment variables follow the pattern:
        DEEPWIKI_<SECTION>_<FIELD>=value

    For example:
        DEEPWIKI_LLM_PROVIDER=anthropic
        DEEPWIKI_EMBEDDING_PROVIDER=openai
        DEEPWIKI_CHUNKING_MAX_CHUNK_TOKENS=1024

    Returns:
        Dictionary of configuration overrides from environment.
    """
    env_config: dict[str, Any] = {}
    prefix = "DEEPWIKI_"

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Parse the key: DEEPWIKI_SECTION_FIELD -> section.field
        parts = key[len(prefix) :].lower().split("_", 1)
        if len(parts) != 2:
            continue

        section, field = parts

        # Convert value to appropriate type
        parsed_value: Any
        if value.lower() in ("true", "false"):
            parsed_value = value.lower() == "true"
        elif value.isdigit():
            parsed_value = int(value)
        elif _is_float(value):
            parsed_value = float(value)
        else:
            parsed_value = value

        # Build nested dict
        if section not in env_config:
            env_config[section] = {}
        env_config[section][field] = parsed_value

    return env_config


def _is_float(s: str) -> bool:
    """Check if string can be converted to float.

    Args:
        s: The string to check.

    Returns:
        True if the string represents a float.
    """
    try:
        float(s)
        return "." in s  # Only consider it float if it has a decimal point
    except ValueError:
        return False
