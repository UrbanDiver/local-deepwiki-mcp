"""Re-export shim for backward compatibility.

All analysis handlers have been split into focused submodules:
  - analysis_search: handle_search_wiki, handle_fuzzy_search
  - analysis_entity: handle_explain_entity, handle_impact_analysis
  - analysis_diff: handle_analyze_diff, handle_ask_about_diff
  - analysis_metadata: handle_get_project_manifest, handle_get_file_context,
                       handle_get_wiki_stats, handle_get_complexity_metrics
"""

from __future__ import annotations

from local_deepwiki.handlers.analysis_diff import handle_analyze_diff, handle_ask_about_diff
from local_deepwiki.handlers.analysis_entity import (
    _set_section_error,
    handle_explain_entity,
    handle_impact_analysis,
)
from local_deepwiki.handlers.analysis_metadata import (
    handle_get_complexity_metrics,
    handle_get_file_context,
    handle_get_project_manifest,
    handle_get_wiki_stats,
)
from local_deepwiki.handlers.analysis_search import handle_fuzzy_search, handle_search_wiki

__all__ = [
    "handle_search_wiki",
    "handle_fuzzy_search",
    "handle_explain_entity",
    "handle_impact_analysis",
    "_set_section_error",
    "handle_analyze_diff",
    "handle_ask_about_diff",
    "handle_get_project_manifest",
    "handle_get_file_context",
    "handle_get_wiki_stats",
    "handle_get_complexity_metrics",
]
