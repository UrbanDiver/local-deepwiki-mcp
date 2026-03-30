"""Pipeline parameter bundle for wiki generation phases.

Provides :class:`WikiPipelineParams`, a frozen dataclass that groups
the parameters threaded through post-processing and auxiliary
generation functions (write callback, progress callback, source files)
together with the core :class:`WikiPipelineContext`.

This eliminates long_parameter_list smells in ``phases.py``,
``postprocessing.py``, ``plugin_runner.py``, and ``codemap_pages.py``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_deepwiki.generators.wiki.context import WikiPipelineContext
    from local_deepwiki.models import ProgressCallback, WikiPage


@dataclass(frozen=True, slots=True)
class WikiPipelineParams:
    """Immutable parameter bundle for wiki generation phases.

    Wraps a :class:`WikiPipelineContext` (core immutable state) with the
    mutable-session parameters that many phase functions need:

    * ``write_callback`` -- async function to persist a page to disk
    * ``progress_callback`` -- optional progress reporter
    * ``all_source_files`` -- list of all indexed source file paths

    This allows phase functions to accept a single ``params`` argument
    instead of 7-10 individual parameters.
    """

    ctx: WikiPipelineContext
    """Core immutable pipeline context (index_status, vector_store, llm, etc.)."""

    write_callback: Callable[[WikiPage], Awaitable[None]]
    """Async callback to persist a WikiPage to disk."""

    progress_callback: ProgressCallback | None = None
    """Optional progress reporter callback."""

    all_source_files: list[str] | None = None
    """List of all indexed source file paths (used for status tracking)."""
