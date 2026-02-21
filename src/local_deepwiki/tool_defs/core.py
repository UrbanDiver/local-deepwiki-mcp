"""Core MCP tool definitions.

Tools: index_repository, ask_question, deep_research, read_wiki_structure,
read_wiki_page, search_code, export_wiki_html, export_wiki_pdf.
"""

from __future__ import annotations

from mcp.types import Tool

from local_deepwiki.tool_defs.annotations import _READ_ONLY, _STATEFUL, _WRITE_SAFE

CORE_TOOLS: tuple[Tool, ...] = (
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
)
