"""Pydantic configuration models.

Domain-specific config classes have been split into submodules:
- models_llm: LLM caching configuration
- models_embedding: Embedding caching configuration
- models_wiki: Wiki generation, research, parsing, and infrastructure configs
- models_search: Search, fuzzy search, graph RAG, and index configs

This module retains the root Config class and re-exports everything
for backward compatibility.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, computed_field

from local_deepwiki.config.models_embedding import *  # noqa: F401,F403
from local_deepwiki.config.models_embedding import EmbeddingCacheConfig
from local_deepwiki.config.models_llm import *  # noqa: F401,F403
from local_deepwiki.config.models_llm import LLMCacheConfig
from local_deepwiki.config.models_search import *  # noqa: F401,F403
from local_deepwiki.config.models_search import (
    FuzzySearchConfig,
    GraphRAGConfig,
    LazyIndexConfig,
    SearchCacheConfig,
    SearchConfig,
)
from local_deepwiki.config.models_wiki import *  # noqa: F401,F403
from local_deepwiki.config.models_wiki import (
    DeepResearchConfig,
    HooksConfig,
    ParsingConfig,
    PluginsConfig,
    WikiConfig,
)
from local_deepwiki.config.processing_models import (
    ASTCacheConfig,
    ChunkingConfig,
    EmbeddingBatchConfig,
)
from local_deepwiki.config.prompts import (
    RESEARCH_DECOMPOSITION_PROMPTS,  # noqa: F401
    RESEARCH_GAP_ANALYSIS_PROMPTS,  # noqa: F401
    RESEARCH_SYNTHESIS_PROMPTS,  # noqa: F401
    WIKI_ARCHITECTURE_PROMPTS,  # noqa: F401
    WIKI_FILE_PROMPTS,  # noqa: F401
    WIKI_MODULE_PROMPTS,  # noqa: F401
    WIKI_OVERVIEW_PROMPTS,  # noqa: F401
    WIKI_SYSTEM_PROMPTS,  # noqa: F401
    PromptsConfig,
    ProviderPromptsConfig,  # noqa: F401
)
from local_deepwiki.config.provider_models import (
    AnthropicConfig,  # noqa: F401
    EmbeddingConfig,
    LLMConfig,
    LocalEmbeddingConfig,  # noqa: F401
    OllamaConfig,  # noqa: F401
    OpenAIEmbeddingConfig,  # noqa: F401
    OpenAILLMConfig,  # noqa: F401
)
from local_deepwiki.models.provider_types import EmbeddingProviderType, LLMProviderType


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
    graph_rag: GraphRAGConfig = Field(default_factory=GraphRAGConfig)
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

        # Local models: single GPU, limit concurrency to avoid OOM/thrashing
        if self.llm.provider == LLMProviderType.OLLAMA:
            return min(base_concurrency, self.wiki.ollama_max_concurrent)

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
