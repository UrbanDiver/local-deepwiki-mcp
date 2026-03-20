"""Shared context objects for wiki generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_deepwiki.config.models import Config, WikiConfig
    from local_deepwiki.core.index_manager import IndexStatus
    from local_deepwiki.core.vectorstore.store import VectorStore
    from local_deepwiki.generators.manifest import ProjectManifest
    from local_deepwiki.generators.wiki.status import WikiStatusManager
    from local_deepwiki.providers.base import LLMProvider


@dataclass(frozen=True, slots=True)
class WikiPipelineContext:
    """Immutable context shared across wiki page generators.

    Bundles the parameters that are threaded through nearly every
    page generation function to eliminate long parameter lists.
    """

    index_status: IndexStatus
    vector_store: VectorStore
    llm: LLMProvider
    system_prompt: str
    repo_path: Path
    wiki_path: Path
    config: Config
    wiki_config: WikiConfig
    manifest: ProjectManifest | None
    status_manager: WikiStatusManager
    full_rebuild: bool = False
    max_chunk_content_chars: int = 15000
