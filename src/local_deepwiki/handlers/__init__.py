"""Tool handlers for the MCP server.

This package re-exports all public handler functions and shared utilities
for backward compatibility. External code can continue to import from
``local_deepwiki.handlers`` without changes.
"""

# --- Shared helpers, types, and constants ---
from local_deepwiki.handlers._shared import (
    FORBIDDEN_EXPORT_DIRS,
    FORBIDDEN_VAR_SUBDIRS,
    ProgressNotifier,
    ToolHandler,
    _format_research_results,
    _is_test_file,
    _load_index_status,
    _validate_export_path,
    create_progress_notifier,
    handle_tool_errors,
    # Re-export commonly-patched dependencies so that
    # ``patch("local_deepwiki.handlers.X")`` continues to work.
    RepositoryIndexer,
    VectorStore,
    generate_wiki,
    get_access_controller,
    get_audit_logger,
    get_config,
    get_embedding_provider,
    get_progress_registry,
    get_rate_limiter,
    get_repository_access_controller,
)

# --- Core tool handlers ---
from local_deepwiki.handlers.core import (
    _handle_index_repository_impl,
    handle_ask_question,
    handle_export_wiki_html,
    handle_export_wiki_pdf,
    handle_index_repository,
    handle_read_wiki_page,
    handle_read_wiki_structure,
    handle_search_code,
)

# --- Research tool handlers ---
from local_deepwiki.handlers.research import (
    _DeepResearchContext,
    _create_progress_callbacks,
    _create_research_pipeline,
    _execute_research_phases,
    _handle_deep_research_impl,
    _setup_deep_research_config,
    handle_cancel_research,
    handle_deep_research,
    handle_get_operation_progress,
    handle_list_research_checkpoints,
    handle_resume_research,
)

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

# --- Analysis and search tool handlers ---
from local_deepwiki.handlers.analysis import (
    handle_analyze_diff,
    handle_ask_about_diff,
    handle_explain_entity,
    handle_fuzzy_search,
    handle_get_complexity_metrics,
    handle_get_file_context,
    handle_get_project_manifest,
    handle_get_wiki_stats,
    handle_impact_analysis,
    handle_search_wiki,
)

# --- Codemap tool handlers ---
from local_deepwiki.handlers.codemap import (
    handle_generate_codemap,
    handle_suggest_codemap_topics,
)

__all__ = [
    # Types and constants
    "FORBIDDEN_EXPORT_DIRS",
    "FORBIDDEN_VAR_SUBDIRS",
    "ProgressNotifier",
    "ToolHandler",
    # Shared helpers
    "_format_research_results",
    "_is_test_file",
    "_load_index_status",
    "_validate_export_path",
    "create_progress_notifier",
    "handle_tool_errors",
    # Re-exported dependencies (for test patching compatibility)
    "RepositoryIndexer",
    "VectorStore",
    "generate_wiki",
    "get_access_controller",
    "get_audit_logger",
    "get_config",
    "get_embedding_provider",
    "get_progress_registry",
    "get_rate_limiter",
    "get_repository_access_controller",
    # Core handlers
    "_handle_index_repository_impl",
    "handle_ask_question",
    "handle_export_wiki_html",
    "handle_export_wiki_pdf",
    "handle_index_repository",
    "handle_read_wiki_page",
    "handle_read_wiki_structure",
    "handle_search_code",
    # Research handlers
    "_DeepResearchContext",
    "_create_progress_callbacks",
    "_create_research_pipeline",
    "_execute_research_phases",
    "_handle_deep_research_impl",
    "_setup_deep_research_config",
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
    "handle_analyze_diff",
    "handle_ask_about_diff",
    "handle_explain_entity",
    "handle_fuzzy_search",
    "handle_get_complexity_metrics",
    "handle_get_file_context",
    "handle_get_project_manifest",
    "handle_get_wiki_stats",
    "handle_impact_analysis",
    "handle_search_wiki",
    # Codemap handlers
    "handle_generate_codemap",
    "handle_suggest_codemap_topics",
]
