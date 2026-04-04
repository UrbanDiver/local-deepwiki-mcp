"""MCP tool argument models (Pydantic BaseModel for each tool)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from local_deepwiki.models.provider_types import (
    CodemapFocusType,
    DiagramType,
    EmbeddingProviderType,
    LLMProviderType,
)


class IndexRepositoryArgs(BaseModel):
    """Arguments for the index_repository tool."""

    repo_path: str = Field(description="Absolute path to the repository to index")
    output_dir: str | None = Field(
        default=None,
        description="Output directory for wiki (default: {repo}/.deepwiki)",
    )
    languages: list[str] | None = Field(
        default=None, description="Languages to include (default: all supported)"
    )
    full_rebuild: bool = Field(
        default=False, description="Force full rebuild instead of incremental update"
    )
    llm_provider: LLMProviderType | None = Field(
        default=None, description="LLM provider for wiki generation"
    )
    embedding_provider: EmbeddingProviderType | None = Field(
        default=None, description="Embedding provider for semantic search"
    )
    use_cloud_for_github: bool | None = Field(
        default=None, description="Use cloud LLM for GitHub repos"
    )
    skip_wiki: bool = Field(
        default=False,
        description="Skip wiki page generation (index and embed only). Pages generate on demand.",
    )
    generation_mode: str | None = Field(
        default=None,
        description="Override wiki generation strategy: 'eager', 'lazy', or 'hybrid'.",
    )
    prefetch_drain: bool | None = Field(
        default=None,
        description="Enable drain mode to backfill all remaining pages in the background after indexing.",
    )


class AskQuestionArgs(BaseModel):
    """Arguments for the ask_question tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    question: str = Field(min_length=1, description="Question about the codebase")
    max_context: int = Field(
        default=10, ge=1, le=50, description="Maximum code chunks for context (1-50)"
    )
    agentic_rag: bool = Field(
        default=False,
        description="Enable agentic RAG: grade relevance + auto-rewrite query if needed (default: false)",
    )
    debug: bool = Field(
        default=False,
        description="Include RAG pipeline trace in response for debugging (default: false)",
    )


class DeepResearchArgs(BaseModel):
    """Arguments for the deep_research tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    question: str = Field(
        min_length=1, description="Complex question requiring deep analysis"
    )
    max_chunks: int = Field(
        default=30, ge=10, le=50, description="Maximum code chunks to analyze (10-50)"
    )
    preset: str | None = Field(
        default=None, description="Research preset: 'fast', 'deep', or 'comprehensive'"
    )
    resume_research_id: str | None = Field(
        default=None,
        description="Optional checkpoint ID to resume an interrupted research session",
    )


class ReadWikiStructureArgs(BaseModel):
    """Arguments for the read_wiki_structure tool."""

    wiki_path: str = Field(description="Path to the wiki directory")


class ReadWikiPageArgs(BaseModel):
    """Arguments for the read_wiki_page tool."""

    wiki_path: str = Field(description="Path to the wiki directory")
    page: str = Field(
        min_length=1, description="Relative path to the page within the wiki"
    )


class SearchCodeArgs(BaseModel):
    """Arguments for the search_code tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    query: str = Field(min_length=1, description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results (1-100)")
    language: str | None = Field(default=None, description="Filter by language")
    type: str | None = Field(
        default=None, description="Filter by chunk type (function, class, method, etc.)"
    )
    path: str | None = Field(default=None, description="Filter by file path pattern")
    fuzzy: bool = Field(default=False, description="Enable fuzzy text matching")
    fuzzy_weight: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Weight for fuzzy vs vector (0.0-1.0)"
    )


class ExportWikiHtmlArgs(BaseModel):
    """Arguments for the export_wiki_html tool."""

    wiki_path: str = Field(description="Path to the wiki directory to export")
    output_path: str | None = Field(
        default=None, description="Output directory for HTML files"
    )


class ExportWikiPdfArgs(BaseModel):
    """Arguments for the export_wiki_pdf tool."""

    wiki_path: str = Field(description="Path to the wiki directory to export")
    output_path: str | None = Field(default=None, description="Output path for PDF")
    single_file: bool = Field(
        default=True, description="Combine all pages into single PDF"
    )


class GetGlossaryArgs(BaseModel):
    """Arguments for the get_glossary tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    search: str | None = Field(
        default=None, description="Optional search term to filter entities"
    )
    file_path: str | None = Field(
        default=None,
        description="Filter to entities from a specific file (relative path)",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Maximum entities to return (1-5000, default 100)",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of entities to skip for pagination (default 0)",
    )


class GetDiagramsArgs(BaseModel):
    """Arguments for the get_diagrams tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    diagram_type: DiagramType = Field(
        default=DiagramType.CLASS, description="Type of diagram to generate"
    )
    entry_point: str | None = Field(
        default=None,
        description="Entry point function for sequence diagrams",
    )


class GetInheritanceArgs(BaseModel):
    """Arguments for the get_inheritance tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    search: str | None = Field(
        default=None,
        description="Filter classes by name (case-insensitive substring)",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Maximum classes to return (1-5000, default 100)",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of classes to skip for pagination (default 0)",
    )


class GetCallGraphArgs(BaseModel):
    """Arguments for the get_call_graph tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    file_path: str | None = Field(
        default=None,
        description="Specific file to get call graph for (relative to repo root)",
    )


class GetCoverageArgs(BaseModel):
    """Arguments for the get_coverage tool."""

    repo_path: str = Field(description="Path to the indexed repository")


class DetectStaleDocsArgs(BaseModel):
    """Arguments for the detect_stale_docs tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    threshold_days: int = Field(
        default=0,
        ge=0,
        description="Minimum days since source changed to consider stale (default: 0)",
    )


class GetChangelogArgs(BaseModel):
    """Arguments for the get_changelog tool."""

    repo_path: str = Field(description="Path to the repository (must be a git repo)")
    max_commits: int = Field(
        default=30, ge=1, le=200, description="Maximum commits to include (1-200)"
    )


class DetectSecretsArgs(BaseModel):
    """Arguments for the detect_secrets tool."""

    repo_path: str = Field(description="Path to the repository to scan")
    exclude_tests: bool = Field(
        default=False,
        description="Exclude test files from scan results (files matching test_*, *_test.*, tests/, etc.)",
    )


class GetTestExamplesArgs(BaseModel):
    """Arguments for the get_test_examples tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    entity_name: str = Field(
        min_length=1,
        description="Name of function or class to find usage examples for",
    )
    max_examples: int = Field(
        default=5, ge=1, le=20, description="Maximum examples to return (1-20)"
    )


class GetApiDocsArgs(BaseModel):
    """Arguments for the get_api_docs tool."""

    repo_path: str = Field(description="Path to the repository")
    file_path: str = Field(
        min_length=1,
        description="File path relative to repo root to get API docs for",
    )


class ListIndexedReposArgs(BaseModel):
    """Arguments for the list_indexed_repos tool."""

    base_path: str | None = Field(
        default=None,
        description="Base directory to search for indexed repos (default: current directory)",
    )


class GetIndexStatusArgs(BaseModel):
    """Arguments for the get_index_status tool."""

    repo_path: str = Field(description="Path to the indexed repository")


class SearchWikiArgs(BaseModel):
    """Arguments for the search_wiki tool."""

    repo_path: str = Field(
        max_length=4096, description="Path to the indexed repository"
    )
    query: str = Field(min_length=1, max_length=1000, description="Search query string")
    limit: int = Field(
        default=20, ge=1, le=100, description="Maximum results to return (1-100)"
    )
    entity_types: list[str] | None = Field(
        default=None,
        description="Optional filter by entity type: 'function', 'class', 'method', or 'page'",
    )


class GetProjectManifestArgs(BaseModel):
    """Arguments for the get_project_manifest tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    use_cache: bool = Field(
        default=True,
        description="Use cached manifest if available and valid (default: true)",
    )


class GetFileContextArgs(BaseModel):
    """Arguments for the get_file_context tool."""

    repo_path: str = Field(
        max_length=4096, description="Path to the indexed repository"
    )
    file_path: str = Field(
        min_length=1,
        description="File path relative to repo root (e.g., 'src/local_deepwiki/server.py')",
    )
    detail_level: str = Field(
        default="standard",
        description="Output detail: standard (imports, callers, related files) or full (+ entities, tests, commits)",
    )


class FuzzySearchArgs(BaseModel):
    """Arguments for the fuzzy_search tool."""

    repo_path: str = Field(
        max_length=4096, description="Path to the indexed repository"
    )
    query: str = Field(
        min_length=1,
        max_length=1000,
        description="Name to search for (function, class, method)",
    )
    threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Minimum similarity score (0.0-1.0)"
    )
    limit: int = Field(
        default=10, ge=1, le=50, description="Maximum results to return (1-50)"
    )
    entity_type: str | None = Field(
        default=None,
        description="Optional filter: 'function', 'class', 'method', or 'module'",
    )


class ExplainEntityArgs(BaseModel):
    """Arguments for the explain_entity tool."""

    repo_path: str = Field(
        max_length=4096, description="Path to the indexed repository"
    )
    entity_name: str = Field(
        min_length=1,
        max_length=500,
        description="Name of function, class, or method to explain",
    )
    include_call_graph: bool = Field(
        default=True, description="Include call graph info (callers and callees)"
    )
    include_inheritance: bool = Field(
        default=True, description="Include inheritance tree (for classes)"
    )
    include_test_examples: bool = Field(
        default=True, description="Include usage examples from tests"
    )
    include_api_docs: bool = Field(
        default=True, description="Include API signature details"
    )
    max_test_examples: int = Field(
        default=3, ge=1, le=10, description="Max test examples to include (1-10)"
    )


class ImpactAnalysisArgs(BaseModel):
    """Arguments for the impact_analysis tool."""

    repo_path: str = Field(
        max_length=4096, description="Path to the indexed repository"
    )
    file_path: str = Field(
        min_length=1,
        description="File path relative to repo root to analyze impact for",
    )
    entity_name: str | None = Field(
        default=None,
        description="Optional: specific function/class name to narrow analysis",
    )
    include_reverse_calls: bool = Field(
        default=True, description="Include reverse call graph (who calls this)"
    )
    include_dependents: bool = Field(
        default=True, description="Include files that import from this file"
    )
    include_inheritance: bool = Field(
        default=True,
        description="Include classes that inherit from classes in this file",
    )
    include_wiki_pages: bool = Field(
        default=True, description="Include wiki pages that document this file"
    )


class GetComplexityMetricsArgs(BaseModel):
    """Arguments for the get_complexity_metrics tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    file_path: str = Field(
        min_length=1,
        description="File path relative to repo root to analyze",
    )


class AnalyzeDiffArgs(BaseModel):
    """Arguments for the analyze_diff tool."""

    repo_path: str = Field(
        max_length=4096, description="Path to the repository (must be a git repo)"
    )
    base_ref: str = Field(
        default="HEAD~1",
        max_length=256,
        description="Git ref to diff from (default: HEAD~1). Can be a commit SHA, branch, or tag.",
    )
    head_ref: str = Field(
        default="HEAD",
        max_length=256,
        description="Git ref to diff to (default: HEAD). Can be a commit SHA, branch, or tag.",
    )
    include_content: bool = Field(
        default=False,
        description="Include the actual diff content for each file (default: false, can be large)",
    )


class AskAboutDiffArgs(BaseModel):
    """Arguments for the ask_about_diff tool."""

    repo_path: str = Field(
        max_length=4096,
        description="Path to the indexed repository (must be a git repo)",
    )
    question: str = Field(
        min_length=1,
        max_length=2000,
        description="Question about the code changes (e.g., 'What was changed?' or 'Does this diff introduce bugs?')",
    )
    base_ref: str = Field(
        default="HEAD~1",
        max_length=256,
        description="Git ref to diff from (default: HEAD~1)",
    )
    head_ref: str = Field(
        default="HEAD",
        max_length=256,
        description="Git ref to diff to (default: HEAD)",
    )
    max_context: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum number of code chunks for additional context (1-30)",
    )


class GetWikiStatsArgs(BaseModel):
    """Arguments for the get_wiki_stats tool."""

    repo_path: str = Field(
        max_length=4096, description="Path to the indexed repository"
    )


class GenerateCodemapArgs(BaseModel):
    """Arguments for the generate_codemap tool."""

    repo_path: str = Field(
        max_length=4096, description="Path to the indexed repository"
    )
    query: str = Field(
        min_length=1,
        max_length=2000,
        description=(
            "Question or topic to map (e.g., 'How does authentication work?', "
            "'Trace the request handling pipeline', 'What happens during indexing?')"
        ),
    )
    entry_point: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Optional specific function or class name to start from "
            "(e.g., 'handle_ask_question', 'RepositoryIndexer.index'). "
            "If not provided, the best entry point is auto-discovered."
        ),
    )
    focus: CodemapFocusType = Field(
        default=CodemapFocusType.EXECUTION_FLOW,
        description="Focus mode: execution_flow (calls), data_flow (transformations), dependency_chain (imports)",
    )
    max_depth: int = Field(
        default=5, ge=1, le=10, description="Maximum call graph traversal depth (1-10)"
    )
    max_nodes: int = Field(
        default=30, ge=5, le=60, description="Maximum nodes in the codemap (5-60)"
    )


class SuggestCodemapTopicsArgs(BaseModel):
    """Arguments for the suggest_codemap_topics tool."""

    repo_path: str = Field(
        max_length=4096, description="Path to the indexed repository"
    )
    max_suggestions: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum topic suggestions to return (1-30)",
    )


class SuggestNextActionsArgs(BaseModel):
    """Arguments for the suggest_next_actions tool."""

    tools_used: list[str] = Field(
        default_factory=list,
        description="List of tool names the agent has already used in this session",
    )
    context: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional context about what the agent is trying to accomplish",
    )
    repo_path: str | None = Field(
        default=None,
        description="Path to the repository (used to check if wiki exists)",
    )


class RunWorkflowArgs(BaseModel):
    """Arguments for the run_workflow tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    workflow: str = Field(
        description="Workflow preset to run: 'onboarding', 'security_audit', 'full_analysis', or 'quick_refresh'",
    )


class BatchExplainEntitiesArgs(BaseModel):
    """Arguments for the batch_explain_entities tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    entity_names: list[str] = Field(
        min_length=1,
        max_length=20,
        description="List of entity names to explain (max 20)",
    )
    depth: str = Field(
        default="shallow",
        description="Lookup depth: 'shallow' (search index only) or 'full' (calls explain_entity for each)",
    )


class QueryCodebaseArgs(BaseModel):
    """Arguments for the query_codebase tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    query: str = Field(
        min_length=1,
        max_length=5000,
        description="Natural language question about the codebase",
    )
    auto_escalate: bool = Field(
        default=True,
        description="Automatically escalate to deep_research if initial answer is insufficient (default: true)",
    )


class GetLayerDependenciesArgs(BaseModel):
    """Arguments for the get_layer_dependencies tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    summary_only: bool = Field(
        default=False,
        description="Return only violation count without full layer details",
    )


class GetArchitectureSummaryArgs(BaseModel):
    """Arguments for the get_architecture_summary tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")


class GetHotspotsArgs(BaseModel):
    """Arguments for the get_hotspots tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    metric: str = Field(
        default="complexity",
        description="Metric to rank by: complexity, params, length, nesting",
    )
    top_n: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of top results to return (1-100)",
    )
    min_threshold: float | None = Field(
        default=None,
        description="Minimum metric value to include",
    )
    exclude_tests: bool = Field(
        default=True,
        description="Exclude test files from analysis",
    )
    summary_only: bool = Field(
        default=False,
        description="Return only stats without individual hotspot details",
    )


class GetCrossModuleDependenciesArgs(BaseModel):
    """Arguments for the get_cross_module_dependencies tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    module_filter: str | None = Field(
        default=None,
        description="Filter to modules whose label starts with this prefix",
    )
    include_external: bool = Field(
        default=False,
        description="Include third-party and stdlib imports",
    )
    min_edge_weight: int = Field(
        default=1,
        ge=1,
        description="Minimum import count for an edge to be included",
    )
    top_n: int = Field(
        default=20,
        ge=1,
        le=500,
        description="Limit output to the top N modules by edge count (default: 20)",
    )
    summary_only: bool = Field(
        default=False,
        description="Return only stats (module/edge counts) without full lists",
    )


class GetCouplingMetricsArgs(BaseModel):
    """Arguments for the get_coupling_metrics tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    module_filter: str | None = Field(
        default=None,
        description="Filter to modules whose label starts with this prefix",
    )
    top_n: int = Field(
        default=20,
        ge=1,
        le=500,
        description="Limit output to the top N modules by distance (default: 20)",
    )
    include_leaves: bool = Field(
        default=False,
        description="Include modules with zero efferent coupling (pure leaves)",
    )
    summary_only: bool = Field(
        default=False,
        description="Return only stats without individual module metrics",
    )
    exclude_tests: bool = Field(
        default=True,
        description="Exclude test modules from metrics",
    )


class GetDesignSmellsArgs(BaseModel):
    """Arguments for the get_design_smells tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    severity_threshold: str = Field(
        default="medium",
        description="Minimum severity to include: low, medium, high",
    )
    exclude_tests: bool = Field(
        default=True,
        description="Exclude test files from analysis",
    )
    top_n: int | None = Field(
        default=None,
        ge=1,
        description="Limit output to the top N smells by severity",
    )
    summary_only: bool = Field(
        default=False,
        description="Return only smells_by_type counts instead of individual smells",
    )


class GetArchitectureHealthArgs(BaseModel):
    """Arguments for the get_architecture_health tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    top_findings: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top findings per category (1-20)",
    )
    detail_level: str = Field(
        default="standard",
        description="Output detail: summary (~1K), standard (~4K), full (~12K with file metrics)",
    )


class AnalyzeArchitectureArgs(BaseModel):
    """Arguments for the analyze_architecture composite tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    detail_level: str = Field(
        default="standard",
        description="Output detail: summary (~2K), standard (~6K), full (~12K)",
    )
    focus: str = Field(
        default="all",
        description="Focus area: all, complexity, coupling, or smells",
    )


class GetOnboardingGuideArgs(BaseModel):
    """Arguments for the get_onboarding_guide tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    detail_level: str = Field(
        default="standard",
        description="Output detail: summary (~1K), standard (~3K), full (~6K)",
    )


class GetRecommendationsArgs(BaseModel):
    """Arguments for the get_recommendations tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    max_items: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum recommendations to return (1-50)",
    )
    category_filter: str | None = Field(
        default=None,
        description="Filter by category: complexity, coupling, smells, or layers",
    )
    enrich: bool = Field(
        default=False,
        description="Use LLM to generate richer descriptions (slower)",
    )


class GetArchitectureTrendsArgs(BaseModel):
    """Arguments for the get_architecture_trends tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    since: str | None = Field(
        default=None,
        description="ISO date to filter from (e.g., '2026-03-01'). Default: last 30 days",
    )


class CompareArchitectureArgs(BaseModel):
    """Arguments for the compare_architecture tool."""

    repo_path: str = Field(
        max_length=4096,
        description="Path to the repository (must be a git repo)",
    )
    base_ref: str = Field(
        default="HEAD~1",
        max_length=256,
        description="Git ref for baseline (default: HEAD~1)",
    )
    head_ref: str = Field(
        default="HEAD",
        max_length=256,
        description="Git ref for comparison target (default: HEAD)",
    )
    detail_level: str = Field(
        default="standard",
        description="Output detail: standard (scores + verdict) or full (+ coupling changes + smell diff)",
    )


class GetModuleHealthArgs(BaseModel):
    """Arguments for the get_module_health tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    module_name: str = Field(
        min_length=1,
        max_length=500,
        description="Module to analyze (e.g., 'core.indexer', 'generators.wiki')",
    )


class GetGuidedTourArgs(BaseModel):
    """Arguments for the get_guided_tour tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    topic: str = Field(
        default="architecture",
        description="Tour topic: architecture, data_flow, request_handling, testing, or custom:<query>",
    )
    max_stops: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum tour stops (1-30)",
    )
    enrich: bool = Field(
        default=False,
        description="Use LLM for richer explanations (slower)",
    )


class ServeWikiArgs(BaseModel):
    """Arguments for the serve_wiki tool."""

    wiki_path: str = Field(
        description="Path to the wiki directory (typically {repo}/.deepwiki)"
    )
    host: str = Field(
        default="127.0.0.1",
        max_length=256,
        description="Host to bind to (default: 127.0.0.1)",
    )
    port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="Port to bind to (default: 8080)",
    )
    open_browser: bool = Field(
        default=False,
        description="Open the wiki in the default browser after starting",
    )


class StopWikiServerArgs(BaseModel):
    """Arguments for the stop_wiki_server tool."""

    port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="Port of the wiki server to stop",
    )
    wiki_path: str | None = Field(
        default=None,
        description="Optional wiki path to identify which server to stop",
    )


class GetChurnMetricsArgs(BaseModel):
    """Arguments for the get_churn_metrics tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    window_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Number of days of git history to analyze (default: 90)",
    )
    top_n: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of top results to return (default: 20)",
    )
    include_complexity: bool = Field(
        default=True,
        description="Include churn×complexity composite scores (default: true)",
    )


class GetCoChangeArgs(BaseModel):
    """Arguments for the get_co_change tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    window_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Number of days of git history to analyze (default: 90)",
    )
    min_shared: int = Field(
        default=2,
        ge=1,
        le=50,
        description="Minimum shared commits for a pair to be included (default: 2)",
    )
    top_n: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of top pairs to return (default: 20)",
    )


class GetCohesionMetricsArgs(BaseModel):
    """Arguments for the get_cohesion_metrics tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    top_n: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of top results to return (default: 20)",
    )
    exclude_tests: bool = Field(
        default=True,
        description="Exclude test files from analysis (default: true)",
    )


class GetDuplicationMetricsArgs(BaseModel):
    """Arguments for the get_duplication_metrics tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    min_lines: int = Field(
        default=6,
        ge=3,
        le=50,
        description="Minimum lines for a clone block (default: 6)",
    )
    top_n: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of top results to return (default: 20)",
    )
    exclude_tests: bool = Field(
        default=True,
        description="Exclude test files from analysis (default: true)",
    )


class GetTestabilityMetricsArgs(BaseModel):
    """Arguments for the get_testability_metrics tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")


class GetMaintainabilityMetricsArgs(BaseModel):
    """Arguments for the get_maintainability_metrics tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    top_n: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of top results to return (default: 20)",
    )
    exclude_tests: bool = Field(
        default=True,
        description="Exclude test files from analysis (default: true)",
    )
