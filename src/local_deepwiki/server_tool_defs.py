"""MCP tool definitions for local-deepwiki.

This module contains the 40 Tool objects returned by the server's list_tools
handler. Extracted from server.py to keep that file focused on server setup
and request dispatch.
"""

from __future__ import annotations

from mcp.types import Tool, ToolAnnotations

# --- Annotation constants ---

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_WRITE_SAFE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_STATEFUL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="index_repository",
        description=(
            "Index a repository and generate wiki documentation. This parses all "
            "source files, extracts semantic code chunks, generates embeddings, and "
            "creates wiki markdown files."
            "\n\nNo prior indexing required."
            '\n\nExample: {"repo_path": "/path/to/repo"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the repository to index",
                },
                "output_dir": {
                    "type": "string",
                    "description": "Optional output directory for wiki (default: {repo}/.deepwiki)",
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of languages to include (default: all supported)",
                },
                "full_rebuild": {
                    "type": "boolean",
                    "description": "Force full rebuild instead of incremental update (default: false)",
                },
                "llm_provider": {
                    "type": "string",
                    "enum": ["ollama", "anthropic", "openai"],
                    "description": "LLM provider for wiki generation (default: from config)",
                },
                "embedding_provider": {
                    "type": "string",
                    "enum": ["local", "openai"],
                    "description": "Embedding provider for semantic search (default: from config)",
                },
                "use_cloud_for_github": {
                    "type": "boolean",
                    "description": "Use cloud LLM (Anthropic Claude) for GitHub repos. Faster and higher quality but requires API key. (default: from config)",
                },
                "skip_wiki": {
                    "type": "boolean",
                    "description": "Skip wiki page generation (index and embed only). Pages will generate on demand when read. (default: false)",
                },
                "generation_mode": {
                    "type": "string",
                    "enum": ["eager", "lazy", "hybrid"],
                    "description": "Override wiki generation strategy for this invocation. If not provided, uses the config file setting.",
                },
                "prefetch_drain": {
                    "type": "boolean",
                    "description": "Enable drain mode to backfill all remaining pages in the background after indexing. Most useful with 'hybrid' or 'lazy' mode. (default: from config)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_WRITE_SAFE,
    ),
    Tool(
        name="ask_question",
        description=(
            "Ask a question about an indexed repository using RAG. Returns an "
            "answer based on relevant code context."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "question": "How does authentication work?"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "question": {
                    "type": "string",
                    "description": "Natural language question about the codebase",
                },
                "max_context": {
                    "type": "integer",
                    "description": "Maximum number of code chunks for context (default: 10)",
                },
                "agentic_rag": {
                    "type": "boolean",
                    "description": "Enable agentic RAG: grade chunk relevance and auto-rewrite query if results are poor (default: false)",
                },
            },
            "required": ["repo_path", "question"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="deep_research",
        description=(
            "Perform deep research on a codebase question using multi-step reasoning. "
            "Unlike ask_question (single retrieval), this performs query decomposition, "
            "parallel retrieval, gap analysis, and comprehensive synthesis. Best for "
            "complex architectural questions. Supports checkpointing for long-running "
            "research that can be resumed if interrupted."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "question": "How is the event system architected?"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "question": {
                    "type": "string",
                    "description": "Complex architectural question about the codebase",
                },
                "max_chunks": {
                    "type": "integer",
                    "description": "Maximum total code chunks to analyze (default: 30)",
                },
                "preset": {
                    "type": "string",
                    "enum": ["quick", "default", "thorough"],
                    "description": "Research mode preset: 'quick' (fast, fewer sub-questions), 'default' (balanced), 'thorough' (comprehensive, more analysis)",
                },
                "resume_research_id": {
                    "type": "string",
                    "description": "Optional checkpoint ID to resume an interrupted research session. Use list_research_checkpoints to see available checkpoints.",
                },
            },
            "required": ["repo_path", "question"],
        },
        annotations=_STATEFUL,
    ),
    Tool(
        name="read_wiki_structure",
        description=(
            "Get the table of contents and structure of a generated wiki."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "wiki_path": {
                    "type": "string",
                    "description": "Path to the wiki directory (typically {repo}/.deepwiki)",
                },
            },
            "required": ["wiki_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="read_wiki_page",
        description=(
            "Read a specific wiki page content."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "wiki_path": {
                    "type": "string",
                    "description": "Path to the wiki directory",
                },
                "page": {
                    "type": "string",
                    "description": "Page path relative to wiki root (e.g., 'index.md', 'modules/auth.md')",
                },
            },
            "required": ["wiki_path", "page"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="search_code",
        description=(
            "Semantic search across the indexed codebase with optional fuzzy "
            "matching and filters. Returns relevant code chunks with similarity scores."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "query": "error handling"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "query": {
                    "type": "string",
                    "description": "Semantic search query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                },
                "language": {
                    "type": "string",
                    "enum": [
                        "python",
                        "javascript",
                        "typescript",
                        "tsx",
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
                    "description": "Filter by programming language",
                },
                "type": {
                    "type": "string",
                    "enum": [
                        "function",
                        "class",
                        "method",
                        "module",
                        "import",
                        "comment",
                        "other",
                    ],
                    "description": "Filter by chunk type (e.g., function, class, method)",
                },
                "path": {
                    "type": "string",
                    "description": "Filter by file path pattern (e.g., 'src/**/*.py', 'tests/*')",
                },
                "fuzzy": {
                    "type": "boolean",
                    "description": "Enable fuzzy matching to improve results for exact name matches (default: false)",
                },
                "fuzzy_weight": {
                    "type": "number",
                    "description": "Weight for fuzzy matching score (0.0-1.0, default: 0.3). Higher values favor exact text matches over semantic similarity.",
                },
            },
            "required": ["repo_path", "query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="export_wiki_html",
        description=(
            "Export wiki documentation to static HTML files. Creates a "
            "self-contained website that can be viewed without a server."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "wiki_path": {
                    "type": "string",
                    "description": "Path to the wiki directory (typically {repo}/.deepwiki)",
                },
                "output_path": {
                    "type": "string",
                    "description": "Output directory for HTML files (default: {wiki_path}_html)",
                },
            },
            "required": ["wiki_path"],
        },
        annotations=_WRITE_SAFE,
    ),
    Tool(
        name="export_wiki_pdf",
        description=(
            "Export wiki documentation to PDF format. Creates a printable PDF "
            "document with proper formatting, page numbers, and table of contents."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "wiki_path": {
                    "type": "string",
                    "description": "Path to the wiki directory (typically {repo}/.deepwiki)",
                },
                "output_path": {
                    "type": "string",
                    "description": "Output path for PDF file (default: {wiki_path}.pdf)",
                },
                "single_file": {
                    "type": "boolean",
                    "description": "If true, combine all pages into one PDF. If false, create separate PDFs for each page. Default: true",
                },
            },
            "required": ["wiki_path"],
        },
        annotations=_WRITE_SAFE,
    ),
    Tool(
        name="list_research_checkpoints",
        description=(
            "List all research checkpoints for a repository. Shows incomplete "
            "and cancelled research sessions that can be resumed using the "
            "deep_research tool with resume_research_id."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository to list checkpoints for",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="cancel_research",
        description=(
            "Cancel an active deep research session and save its checkpoint. "
            "The research can be resumed later using the deep_research tool "
            "with resume_research_id."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository",
                },
                "research_id": {
                    "type": "string",
                    "description": "ID of the research session to cancel (from list_research_checkpoints)",
                },
            },
            "required": ["repo_path", "research_id"],
        },
        annotations=_STATEFUL,
    ),
    Tool(
        name="resume_research",
        description=(
            "Resume a previously interrupted deep research session from its "
            "checkpoint. This is a convenience wrapper - you can also use "
            "deep_research with resume_research_id directly."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository",
                },
                "research_id": {
                    "type": "string",
                    "description": "ID of the research checkpoint to resume (from list_research_checkpoints)",
                },
            },
            "required": ["repo_path", "research_id"],
        },
        annotations=_STATEFUL,
    ),
    Tool(
        name="get_operation_progress",
        description=(
            "Get progress for active long-running operations. Supports "
            "polling-based progress tracking for clients that cannot receive "
            "push notifications. Returns current progress, ETA, and phase information."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "operation_id": {
                    "type": "string",
                    "description": "Specific operation ID to get progress for. If not provided, returns all active operations.",
                },
            },
            "required": [],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_glossary",
        description=(
            "Get a searchable glossary of all code entities (classes, functions, "
            "methods) in an indexed repository. Useful for discovering what's in "
            "the codebase."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "search": {
                    "type": "string",
                    "description": "Optional search term to filter entities by name or docstring",
                },
                "file_path": {
                    "type": "string",
                    "description": "Filter to entities from a specific file (relative path)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum entities to return (default: 100, max: 5000)",
                    "default": 100,
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of entities to skip for pagination (default: 0)",
                    "default": 0,
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_diagrams",
        description=(
            "Generate Mermaid diagrams for an indexed repository. Supports class "
            "diagrams, dependency graphs, module overviews, language distribution "
            "pie charts, and sequence diagrams."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "diagram_type": "class"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "diagram_type": {
                    "type": "string",
                    "enum": [
                        "class",
                        "dependency",
                        "module",
                        "sequence",
                        "language_pie",
                    ],
                    "description": "Type of diagram to generate (default: class)",
                },
                "entry_point": {
                    "type": "string",
                    "description": "Entry point function name (required for sequence diagrams)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_inheritance",
        description=(
            "Get class inheritance hierarchy trees for an indexed repository. "
            "Shows parent-child relationships, abstract classes, and generates "
            "a Mermaid inheritance diagram."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "search": {
                    "type": "string",
                    "description": "Filter classes by name (case-insensitive substring)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum classes to return (default: 100, max: 5000)",
                    "default": 100,
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of classes to skip for pagination (default: 0)",
                    "default": 0,
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_call_graph",
        description=(
            "Get function call graphs showing which functions call which. Can "
            "analyze a specific file or the entire repository. Returns a "
            "Mermaid flowchart."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "file_path": {
                    "type": "string",
                    "description": "Specific file to analyze (relative to repo root). If omitted, analyzes entire repo.",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_coverage",
        description=(
            "Get documentation coverage report for an indexed repository. "
            "Shows which classes, functions, and methods have docstrings "
            "and which don't."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="detect_stale_docs",
        description=(
            "Find wiki pages that may be outdated because their source files "
            "have been modified since the documentation was generated."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "threshold_days": {
                    "type": "integer",
                    "description": "Minimum days since source changed to consider stale (default: 0)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_changelog",
        description=(
            "Extract recent git commit history as a formatted changelog. "
            "Groups commits by date and includes file change information."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository (must be a git repo)",
                },
                "max_commits": {
                    "type": "integer",
                    "description": "Maximum number of commits to include (default: 30, max: 200)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="detect_secrets",
        description=(
            "Scan a repository for hardcoded credentials and secrets (API keys, "
            "tokens, passwords, private keys). Returns findings with type, "
            "location, confidence, and remediation advice."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository to scan",
                },
                "exclude_tests": {
                    "type": "boolean",
                    "description": "Exclude test files from scan results (files matching test_*, *_test.*, tests/, etc.). Default: false",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_test_examples",
        description=(
            "Find usage examples for a function or class by searching test "
            "files in the indexed repository. Returns code snippets showing "
            "how the entity is used in tests."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "entity_name": {
                    "type": "string",
                    "description": "Name of the function or class to find examples for",
                },
                "max_examples": {
                    "type": "integer",
                    "description": "Maximum number of examples to return (default: 5)",
                },
            },
            "required": ["repo_path", "entity_name"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_api_docs",
        description=(
            "Get API documentation with function signatures, parameters, return "
            "types, and docstrings for a specific file. Uses tree-sitter AST "
            "parsing for accuracy."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root to get API docs for",
                },
            },
            "required": ["repo_path", "file_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="list_indexed_repos",
        description=(
            "Discover all indexed repositories under a given directory. "
            "Searches for .deepwiki directories and returns index metadata "
            "for each."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "base_path": {
                    "type": "string",
                    "description": "Base directory to search for indexed repos (default: current directory)",
                },
            },
            "required": [],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_index_status",
        description=(
            "Get index statistics for a repository without re-indexing. "
            "Shows file count, chunk count, languages, and when it was "
            "last indexed."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="search_wiki",
        description=(
            "Full-text search across wiki pages and code entities. Searches "
            "titles, headings, code terms, descriptions, and keywords. "
            "Returns ranked matches."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 20, max: 100)",
                },
                "entity_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by type: 'page', 'function', 'class', 'method'",
                },
            },
            "required": ["repo_path", "query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_project_manifest",
        description=(
            "Get parsed project metadata from package manifest files "
            "(pyproject.toml, package.json, Cargo.toml, go.mod, etc.). "
            "Returns name, version, dependencies, scripts, tech stack summary."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository",
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Use cached manifest if available (default: true)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_file_context",
        description=(
            "Get rich context for a source file: imports, callers (who uses "
            "this file), related files, and type definitions used. Helps "
            "understand a file's role in the codebase."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root (e.g., 'src/local_deepwiki/server.py')",
                },
            },
            "required": ["repo_path", "file_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="fuzzy_search",
        description=(
            "Fuzzy name matching for functions, classes, and methods using "
            "Levenshtein distance. Returns 'Did you mean?' suggestions, file "
            "locations, and similarity scores. Great for finding entities when "
            "you don't know the exact name."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "query": {
                    "type": "string",
                    "description": "Name to search for (function, class, method)",
                },
                "threshold": {
                    "type": "number",
                    "description": "Minimum similarity score 0.0-1.0 (default: 0.6)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 10, max: 50)",
                },
                "entity_type": {
                    "type": "string",
                    "description": "Filter: 'function', 'class', 'method', or 'module'",
                },
            },
            "required": ["repo_path", "query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_wiki_stats",
        description=(
            "Get a wiki health dashboard with index stats, page counts, "
            "search index size, coverage data, and wiki status - all in "
            "a single call."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="explain_entity",
        description=(
            "Get a comprehensive explanation of a function, class, or method "
            "by combining glossary info, call graph, inheritance tree, test "
            "examples, and API docs into a single response."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "entity_name": "MyClass"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "entity_name": {
                    "type": "string",
                    "description": "Name of function, class, or method to explain",
                },
                "include_call_graph": {
                    "type": "boolean",
                    "description": "Include call graph info - callers and callees (default: true)",
                },
                "include_inheritance": {
                    "type": "boolean",
                    "description": "Include inheritance tree for classes (default: true)",
                },
                "include_test_examples": {
                    "type": "boolean",
                    "description": "Include usage examples from tests (default: true)",
                },
                "include_api_docs": {
                    "type": "boolean",
                    "description": "Include API signature details (default: true)",
                },
                "max_test_examples": {
                    "type": "integer",
                    "description": "Max test examples to include (default: 3, range: 1-10)",
                },
            },
            "required": ["repo_path", "entity_name"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="impact_analysis",
        description=(
            "Analyze the blast radius of changes to a file or entity. Combines "
            "reverse call graph, inheritance dependents, file-level imports, and "
            "affected wiki pages to help understand impact before making changes."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "file_path": "src/auth.py"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root to analyze impact for",
                },
                "entity_name": {
                    "type": "string",
                    "description": "Optional: specific function/class name to narrow analysis",
                },
                "include_reverse_calls": {
                    "type": "boolean",
                    "description": "Include reverse call graph - who calls functions in this file (default: true)",
                },
                "include_dependents": {
                    "type": "boolean",
                    "description": "Include files that import from this file (default: true)",
                },
                "include_inheritance": {
                    "type": "boolean",
                    "description": "Include classes that inherit from classes in this file (default: true)",
                },
                "include_wiki_pages": {
                    "type": "boolean",
                    "description": "Include wiki pages that document this file (default: true)",
                },
            },
            "required": ["repo_path", "file_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="get_complexity_metrics",
        description=(
            "Analyze code complexity for a source file using tree-sitter AST "
            "parsing. Returns function/class counts, line metrics, cyclomatic "
            "complexity, nesting depth, and parameter counts."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository",
                },
                "file_path": {
                    "type": "string",
                    "description": "File path relative to repo root to analyze",
                },
            },
            "required": ["repo_path", "file_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="analyze_diff",
        description=(
            "Analyze git diff between two refs and map changed files to "
            "affected wiki pages and code entities. Helps understand "
            "documentation impact of code changes."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository (must be a git repo)",
                },
                "base_ref": {
                    "type": "string",
                    "description": "Git ref to diff from (default: HEAD~1)",
                },
                "head_ref": {
                    "type": "string",
                    "description": "Git ref to diff to (default: HEAD)",
                },
                "include_content": {
                    "type": "boolean",
                    "description": "Include diff content for each file (default: false)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="ask_about_diff",
        description=(
            "Ask questions about recent code changes using RAG. Combines git "
            "diff with vector search context and LLM synthesis to answer "
            "questions like 'What changed?', 'Are there any bugs?', or "
            "'What's the impact?'."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository (must be a git repo)",
                },
                "question": {
                    "type": "string",
                    "description": "Question about the code changes",
                },
                "base_ref": {
                    "type": "string",
                    "description": "Git ref to diff from (default: HEAD~1)",
                },
                "head_ref": {
                    "type": "string",
                    "description": "Git ref to diff to (default: HEAD)",
                },
                "max_context": {
                    "type": "integer",
                    "description": "Maximum code chunks for context (default: 10, max: 30)",
                },
            },
            "required": ["repo_path", "question"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="generate_codemap",
        description=(
            "Generate a Windsurf-style codemap: a focused execution-flow map with "
            "Mermaid diagram and narrative trace for a question or topic. Shows how "
            "code flows across files with file paths and line numbers. Best for "
            "understanding 'How does X work?' questions."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "query": "How does request handling work?"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Question or topic to map (e.g., 'How does authentication work?', "
                        "'Trace the request handling pipeline')"
                    ),
                },
                "entry_point": {
                    "type": "string",
                    "description": (
                        "Optional function/class to start from (e.g., 'handle_ask_question'). "
                        "Auto-discovered if not provided."
                    ),
                },
                "focus": {
                    "type": "string",
                    "enum": ["execution_flow", "data_flow", "dependency_chain"],
                    "description": "Focus mode: execution_flow (calls), data_flow (transformations), dependency_chain (imports). Default: execution_flow",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Max call graph traversal depth (default: 5, range: 1-10)",
                },
                "max_nodes": {
                    "type": "integer",
                    "description": "Max nodes in the codemap (default: 30, range: 5-60)",
                },
            },
            "required": ["repo_path", "query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="suggest_codemap_topics",
        description=(
            "Suggest interesting codemap topics for a repository based on call graph hubs, "
            "core modules, and common entry patterns. Use before generate_codemap to discover "
            "what flows are worth exploring."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "max_suggestions": {
                    "type": "integer",
                    "description": "Maximum topic suggestions to return (default: 10, range: 1-30)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="suggest_next_actions",
        description=(
            "Suggest which tools to use next based on tools already used. "
            "Returns ranked suggestions with reasons. No LLM calls - uses a "
            "static decision tree for instant responses."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tools_used": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tool names the agent has already used in this session",
                },
                "context": {
                    "type": "string",
                    "description": "Optional context about what the agent is trying to accomplish",
                },
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository (used to check if wiki exists)",
                },
            },
            "required": [],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="run_workflow",
        description=(
            "Run a pre-built multi-step workflow. Available presets: 'onboarding' "
            "(project overview), 'security_audit' (secrets + complexity), "
            "'full_analysis' (stats + coverage + stale + secrets), 'quick_refresh' "
            "(stale docs + changelog)."
            "\n\nRequires: index_repository must be called first."
            '\n\nExample: {"repo_path": "/path/to/repo", "workflow": "onboarding"}'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "workflow": {
                    "type": "string",
                    "enum": [
                        "onboarding",
                        "security_audit",
                        "full_analysis",
                        "quick_refresh",
                    ],
                    "description": "Workflow preset to run",
                },
            },
            "required": ["repo_path", "workflow"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="batch_explain_entities",
        description=(
            "Explain multiple code entities in a single call. Loads the search "
            "index once and looks up each entity name. More efficient than "
            "calling explain_entity repeatedly."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "entity_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of entity names to explain (max 20)",
                    "maxItems": 20,
                },
                "depth": {
                    "type": "string",
                    "enum": ["shallow", "full"],
                    "description": "Depth of explanation: 'shallow' (search index only, default) or 'full' (calls explain_entity for each)",
                },
            },
            "required": ["repo_path", "entity_names"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="query_codebase",
        description=(
            "Smart query that combines ask_question with automatic escalation "
            "to deep_research when the initial answer is insufficient. Single "
            "entry point for codebase Q&A."
            "\n\nRequires: index_repository must be called first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the indexed repository",
                },
                "query": {
                    "type": "string",
                    "description": "Natural language question about the codebase",
                },
                "auto_escalate": {
                    "type": "boolean",
                    "description": "Automatically escalate to deep_research if initial answer is insufficient (default: true)",
                },
            },
            "required": ["repo_path", "query"],
        },
        annotations=_READ_ONLY,
    ),
    Tool(
        name="find_tools",
        description=(
            "Search for tools by capability description. Returns ranked matches "
            "with tool name, description, and whether indexing is required. "
            "Useful when an agent needs to discover which tool to use."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Capability description to search for (e.g., 'security scanning', 'code visualization')",
                },
            },
            "required": ["query"],
        },
        annotations=_READ_ONLY,
    ),
]
