"""Embedding-related configuration models (caching)."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
