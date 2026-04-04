"""Tool handlers for the MCP server.

This package exports public handler functions and shared utilities.
Private implementation details (underscore-prefixed) are not part of
the public API and should be imported from their defining modules.
"""

from __future__ import annotations

# --- Shared helpers, types, and constants ---
from local_deepwiki.handlers._error_handling import ToolHandler, handle_tool_errors
from local_deepwiki.handlers._export_validation import (
    FORBIDDEN_EXPORT_DIRS,
    FORBIDDEN_VAR_SUBDIRS,
)
from local_deepwiki.handlers._progress import ProgressNotifier, create_progress_notifier

# --- Analysis and search tool handlers ---
from local_deepwiki.handlers.analysis_architecture import (
    handle_analyze_architecture,
    handle_compare_architecture,
    handle_get_architecture_health,
    handle_get_architecture_summary,
    handle_get_architecture_trends,
    handle_get_churn_metrics,
    handle_get_co_change,
    handle_get_cohesion_metrics,
    handle_get_coupling_metrics,
    handle_get_cross_module_dependencies,
    handle_get_design_smells,
    handle_get_guided_tour,
    handle_get_hotspots,
    handle_get_layer_dependencies,
    handle_get_module_health,
    handle_get_onboarding_guide,
    handle_get_recommendations,
)
from local_deepwiki.handlers.analysis_diff import (
    handle_analyze_diff,
    handle_ask_about_diff,
)
from local_deepwiki.handlers.analysis_entity import (
    handle_explain_entity,
    handle_impact_analysis,
)
from local_deepwiki.handlers.analysis_metadata import (
    handle_get_complexity_metrics,
    handle_get_file_context,
    handle_get_project_manifest,
    handle_get_status,
    handle_get_wiki_stats,
)
from local_deepwiki.handlers.analysis_search import (
    handle_fuzzy_search,
    handle_search_wiki,
)

# --- Agentic tool handlers ---
from local_deepwiki.handlers.agentic import (
    handle_batch_explain_entities,
    handle_find_tools,
    handle_query_codebase,
    handle_suggest_next_actions,
)
from local_deepwiki.handlers.agentic_workflows import handle_run_workflow

# --- Codemap tool handlers ---
from local_deepwiki.handlers.codemap import (
    handle_generate_codemap,
    handle_suggest_codemap_topics,
)

# --- Core tool handlers ---
from local_deepwiki.handlers.core import (
    handle_ask_question,
    handle_export_wiki_html,
    handle_export_wiki_pdf,
    handle_read_wiki_page,
    handle_read_wiki_structure,
    handle_search_code,
)
from local_deepwiki.handlers.indexing import handle_index_repository

# --- Generator tool handlers ---
from local_deepwiki.handlers.generators import (
    handle_detect_secrets,
    handle_detect_stale_docs,
    handle_get_api_docs,
    handle_get_call_graph,
    handle_get_changelog,
    handle_get_coverage,
    handle_get_diagrams,
    handle_get_glossary,
    handle_get_index_status,
    handle_get_inheritance,
    handle_get_test_examples,
    handle_list_indexed_repos,
)

# --- Web server lifecycle handlers ---
from local_deepwiki.handlers.web_server import (
    handle_serve_wiki,
    handle_stop_wiki_server,
)

# --- Research tool handlers ---
from local_deepwiki.handlers.research import (
    handle_cancel_research,
    handle_deep_research,
    handle_get_operation_progress,
    handle_list_research_checkpoints,
    handle_resume_research,
)

__all__ = [
    # Types and constants
    "FORBIDDEN_EXPORT_DIRS",
    "FORBIDDEN_VAR_SUBDIRS",
    "ProgressNotifier",
    "ToolHandler",
    # Shared helpers
    "create_progress_notifier",
    "handle_tool_errors",
    # Core handlers
    "handle_ask_question",
    "handle_export_wiki_html",
    "handle_export_wiki_pdf",
    "handle_index_repository",
    "handle_read_wiki_page",
    "handle_read_wiki_structure",
    "handle_search_code",
    # Research handlers
    "handle_cancel_research",
    "handle_deep_research",
    "handle_get_operation_progress",
    "handle_list_research_checkpoints",
    "handle_resume_research",
    # Generator handlers
    "handle_detect_secrets",
    "handle_detect_stale_docs",
    "handle_get_api_docs",
    "handle_get_call_graph",
    "handle_get_changelog",
    "handle_get_coverage",
    "handle_get_diagrams",
    "handle_get_glossary",
    "handle_get_index_status",
    "handle_get_inheritance",
    "handle_get_test_examples",
    "handle_list_indexed_repos",
    # Analysis handlers
    "handle_analyze_architecture",
    "handle_analyze_diff",
    "handle_ask_about_diff",
    "handle_compare_architecture",
    "handle_explain_entity",
    "handle_fuzzy_search",
    "handle_get_architecture_health",
    "handle_get_architecture_summary",
    "handle_get_architecture_trends",
    "handle_get_churn_metrics",
    "handle_get_co_change",
    "handle_get_cohesion_metrics",
    "handle_get_guided_tour",
    "handle_get_complexity_metrics",
    "handle_get_coupling_metrics",
    "handle_get_cross_module_dependencies",
    "handle_get_design_smells",
    "handle_get_file_context",
    "handle_get_hotspots",
    "handle_get_layer_dependencies",
    "handle_get_module_health",
    "handle_get_onboarding_guide",
    "handle_get_recommendations",
    "handle_get_project_manifest",
    "handle_get_status",
    "handle_get_wiki_stats",
    "handle_impact_analysis",
    "handle_search_wiki",
    # Codemap handlers
    "handle_generate_codemap",
    "handle_suggest_codemap_topics",
    # Agentic handlers
    "handle_suggest_next_actions",
    "handle_run_workflow",
    "handle_batch_explain_entities",
    "handle_find_tools",
    "handle_query_codebase",
    # Web server handlers
    "handle_serve_wiki",
    "handle_stop_wiki_server",
]
