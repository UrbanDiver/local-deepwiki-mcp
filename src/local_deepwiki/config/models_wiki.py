"""Wiki generation and infrastructure configuration models."""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    ollama_max_concurrent: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum concurrent LLM calls when using Ollama (local model). "
        "Local models run on a single GPU; higher values may cause OOM/thrashing.",
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
        default=5,
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
