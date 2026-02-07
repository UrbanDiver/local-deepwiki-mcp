"""Data models for local-deepwiki."""

import json
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field


class ProgressCallback(Protocol):
    """Protocol for progress callback functions.

    Progress callbacks are used to report progress during long-running
    operations like indexing and wiki generation.
    """

    def __call__(self, msg: str, current: int, total: int) -> None:
        """Report progress.

        Args:
            msg: Description of current operation.
            current: Current step number.
            total: Total number of steps.
        """
        ...


class Language(str, Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    TSX = "tsx"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    SWIFT = "swift"
    RUBY = "ruby"
    PHP = "php"
    KOTLIN = "kotlin"
    CSHARP = "csharp"


class ChunkType(str, Enum):
    """Types of code chunks."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    IMPORT = "import"
    COMMENT = "comment"
    OTHER = "other"


class CodeChunk(BaseModel):
    """A chunk of code extracted from the repository."""

    id: str = Field(description="Unique identifier for this chunk")
    file_path: str = Field(description="Path to the source file")
    language: Language = Field(description="Programming language")
    chunk_type: ChunkType = Field(description="Type of code chunk")
    name: str | None = Field(default=None, description="Name of function/class/etc")
    content: str = Field(description="The actual code content")
    start_line: int = Field(description="Starting line number")
    end_line: int = Field(description="Ending line number")
    docstring: str | None = Field(default=None, description="Associated docstring")
    parent_name: str | None = Field(
        default=None, description="Parent class/module name"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    def to_vector_record(self, vector: list[float] | None = None) -> dict[str, Any]:
        """Convert chunk to a dict suitable for vector store storage.

        Args:
            vector: Optional embedding vector to include in the record.

        Returns:
            Dict with all fields formatted for LanceDB storage.
        """
        record: dict[str, Any] = {
            "id": self.id,
            "file_path": self.file_path,
            "language": self.language.value,
            "chunk_type": self.chunk_type.value,
            "name": self.name or "",
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "docstring": self.docstring or "",
            "parent_name": self.parent_name or "",
            "metadata": json.dumps(self.metadata),
        }
        if vector is not None:
            record["vector"] = vector
        return record

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        name_part = f" {self.name}" if self.name else ""
        return (
            f"<CodeChunk {self.chunk_type.value}{name_part} "
            f"at {self.file_path}:{self.start_line}-{self.end_line}>"
        )


class FileInfo(BaseModel):
    """Information about a source file."""

    path: str = Field(description="Relative path from repo root")
    language: Language | None = Field(default=None, description="Detected language")
    size_bytes: int = Field(description="File size in bytes")
    last_modified: float = Field(description="Last modification timestamp")
    hash: str = Field(description="Content hash for change detection")
    chunk_count: int = Field(default=0, description="Number of chunks extracted")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        lang = self.language.value if self.language else "unknown"
        return f"<FileInfo {self.path} ({lang}, {self.chunk_count} chunks)>"


class IndexStatus(BaseModel):
    """Status of repository indexing."""

    repo_path: str = Field(description="Path to the repository")
    indexed_at: float = Field(description="Timestamp of last indexing")
    total_files: int = Field(description="Total files processed")
    total_chunks: int = Field(description="Total chunks extracted")
    languages: dict[str, int] = Field(
        default_factory=dict, description="Files per language"
    )
    files: list[FileInfo] = Field(default_factory=list, description="Indexed file info")
    schema_version: int = Field(
        default=1, description="Schema version for migration support"
    )

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return (
            f"<IndexStatus {self.repo_path} "
            f"({self.total_files} files, {self.total_chunks} chunks)>"
        )


class WikiPage(BaseModel):
    """A generated wiki page."""

    path: str = Field(description="Relative path in wiki directory")
    title: str = Field(description="Page title")
    content: str = Field(description="Markdown content")
    generated_at: float = Field(description="Generation timestamp")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<WikiPage {self.path} ({self.title!r})>"


class WikiStructure(BaseModel):
    """Structure of the generated wiki."""

    root: str = Field(description="Wiki root directory")
    pages: list[WikiPage] = Field(default_factory=list, description="All wiki pages")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<WikiStructure {self.root} ({len(self.pages)} pages)>"

    def to_toc(self) -> dict[str, Any]:
        """Generate table of contents."""
        toc: dict[str, Any] = {"sections": []}
        for page in sorted(self.pages, key=lambda p: p.path):
            parts = Path(page.path).parts
            current = toc
            for part in parts[:-1]:
                section = next(
                    (s for s in current.get("sections", []) if s["name"] == part), None
                )
                if not section:
                    section = {"name": part, "sections": [], "pages": []}
                    current.setdefault("sections", []).append(section)
                current = section
            current.setdefault("pages", []).append(
                {"path": page.path, "title": page.title}
            )
        return toc


class SearchResult(BaseModel):
    """A search result from semantic search."""

    chunk: CodeChunk = Field(description="The matched code chunk")
    score: float = Field(description="Similarity score")
    highlights: list[str] = Field(default_factory=list, description="Relevant snippets")
    suggestions: list[str] | None = Field(
        default=None, description="'Did you mean?' suggestions when results are poor"
    )

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        name = self.chunk.name or self.chunk.chunk_type.value
        suggestion_str = (
            f" suggestions={len(self.suggestions)}" if self.suggestions else ""
        )
        return f"<SearchResult {name} score={self.score:.3f}{suggestion_str}>"


class WikiPageStatus(BaseModel):
    """Status of a generated wiki page for incremental generation."""

    path: str = Field(description="Wiki page path (e.g., 'files/src/module/file.md')")
    source_files: list[str] = Field(
        default_factory=list, description="Source files that contributed to this page"
    )
    source_hashes: dict[str, str] = Field(
        default_factory=dict, description="Mapping of source file path to content hash"
    )
    source_line_info: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Mapping of source file path to {start_line, end_line}",
    )
    content_hash: str = Field(description="Hash of the generated page content")
    generated_at: float = Field(description="Timestamp when page was generated")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<WikiPageStatus {self.path} ({len(self.source_files)} sources)>"


class WikiGenerationStatus(BaseModel):
    """Status of wiki generation for tracking incremental updates."""

    repo_path: str = Field(description="Path to the repository")
    generated_at: float = Field(description="Timestamp of last generation")
    total_pages: int = Field(description="Total pages generated")
    index_status_hash: str = Field(
        default="", description="Hash of index status for detecting changes"
    )
    pages: dict[str, WikiPageStatus] = Field(
        default_factory=dict, description="Mapping of page path to status"
    )

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<WikiGenerationStatus {self.repo_path} ({self.total_pages} pages)>"


# Deep Research Models


class ResearchStepType(str, Enum):
    """Types of steps in the deep research process."""

    DECOMPOSITION = "decomposition"
    RETRIEVAL = "retrieval"
    GAP_ANALYSIS = "gap_analysis"
    SYNTHESIS = "synthesis"


class ResearchStep(BaseModel):
    """A single step in the deep research process."""

    step_type: ResearchStepType = Field(description="Type of research step")
    description: str = Field(description="Description of what was done")
    duration_ms: int = Field(description="Duration of this step in milliseconds")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<ResearchStep {self.step_type.value} ({self.duration_ms}ms)>"


class SubQuestion(BaseModel):
    """A decomposed sub-question for deep research."""

    question: str = Field(description="The sub-question to investigate")
    category: str = Field(
        description="Category: structure, flow, dependencies, impact, or comparison"
    )

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<SubQuestion [{self.category}] {self.question[:50]}...>"


class SourceReference(BaseModel):
    """A reference to a source code location."""

    file_path: str = Field(description="Path to the source file")
    start_line: int = Field(description="Starting line number")
    end_line: int = Field(description="Ending line number")
    chunk_type: str = Field(description="Type of code chunk")
    name: str | None = Field(default=None, description="Name of the code element")
    relevance_score: float = Field(description="Relevance score from search")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        name = self.name or self.chunk_type
        return f"<Source {self.file_path}:{self.start_line}-{self.end_line} ({name})>"


class DeepResearchResult(BaseModel):
    """Result from deep research analysis."""

    question: str = Field(description="Original question asked")
    answer: str = Field(description="Comprehensive answer with citations")
    sub_questions: list[SubQuestion] = Field(
        default_factory=list, description="Decomposed sub-questions investigated"
    )
    sources: list[SourceReference] = Field(
        default_factory=list, description="Source code references used"
    )
    reasoning_trace: list[ResearchStep] = Field(
        default_factory=list, description="Steps taken during research"
    )
    total_chunks_analyzed: int = Field(description="Total code chunks analyzed")
    total_llm_calls: int = Field(description="Total LLM calls made")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return (
            f"<DeepResearchResult {len(self.sub_questions)} sub-questions, "
            f"{len(self.sources)} sources, {self.total_llm_calls} LLM calls>"
        )


class IndexingProgressType(str, Enum):
    """Types of indexing progress events."""

    STARTED = "started"
    SCANNING_FILES = "scanning_files"
    PARSING_FILES = "parsing_files"
    GENERATING_EMBEDDINGS = "generating_embeddings"
    STORING_VECTORS = "storing_vectors"
    GENERATING_WIKI = "generating_wiki"
    GENERATING_PAGES = "generating_pages"
    COMPLETE = "complete"


class IndexingProgress(BaseModel):
    """Progress update from repository indexing.

    Sent via MCP progress notifications to provide real-time feedback
    during long-running indexing operations.
    """

    step: int = Field(description="Current step number")
    total_steps: int = Field(description="Total number of steps")
    step_type: IndexingProgressType = Field(description="Type of progress event")
    message: str = Field(description="Human-readable progress message")
    files_processed: int | None = Field(
        default=None, description="Number of files processed"
    )
    total_files: int | None = Field(default=None, description="Total files to process")
    chunks_created: int | None = Field(
        default=None, description="Number of chunks created"
    )
    pages_generated: int | None = Field(
        default=None, description="Wiki pages generated"
    )
    duration_ms: int | None = Field(
        default=None, description="Duration of step in milliseconds"
    )


class ResearchProgressType(str, Enum):
    """Types of deep research progress events."""

    STARTED = "started"
    DECOMPOSITION_COMPLETE = "decomposition_complete"
    RETRIEVAL_COMPLETE = "retrieval_complete"
    GAP_ANALYSIS_COMPLETE = "gap_analysis_complete"
    FOLLOWUP_COMPLETE = "followup_complete"
    SYNTHESIS_STARTED = "synthesis_started"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class ResearchProgress(BaseModel):
    """Progress update from deep research pipeline.

    Sent via MCP progress notifications to provide real-time feedback
    during long-running deep research operations.
    """

    step: int = Field(description="Current step number (0-5)")
    total_steps: int = Field(default=5, description="Total number of steps")
    step_type: ResearchProgressType = Field(description="Type of progress event")
    message: str = Field(description="Human-readable progress message")
    sub_questions: list[SubQuestion] | None = Field(
        default=None, description="Sub-questions after decomposition"
    )
    chunks_retrieved: int | None = Field(
        default=None, description="Number of chunks retrieved so far"
    )
    follow_up_queries: list[str] | None = Field(
        default=None, description="Follow-up queries from gap analysis"
    )
    duration_ms: int | None = Field(
        default=None, description="Duration of completed step in milliseconds"
    )


# =============================================================================
# MCP Tool Argument Models
# =============================================================================


class LLMProviderType(str, Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class EmbeddingProviderType(str, Enum):
    """Supported embedding providers."""

    LOCAL = "local"
    OPENAI = "openai"


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


class AskQuestionArgs(BaseModel):
    """Arguments for the ask_question tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    question: str = Field(min_length=1, description="Question about the codebase")
    max_context: int = Field(
        default=10, ge=1, le=50, description="Maximum code chunks for context (1-50)"
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


# =============================================================================
# Research Checkpoint Models
# =============================================================================


class ResearchCheckpointStep(str, Enum):
    """Current step in a research checkpoint."""

    DECOMPOSITION = "decomposition"
    RETRIEVAL = "retrieval"
    GAP_ANALYSIS = "gap_analysis"
    FOLLOW_UP_RETRIEVAL = "follow_up_retrieval"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


class ResearchCheckpoint(BaseModel):
    """Checkpoint state for resumable deep research operations.

    This model captures the complete state of a research operation,
    allowing it to be saved after each step and resumed if interrupted.
    """

    research_id: str = Field(description="UUID for this research session")
    question: str = Field(description="Original research question")
    repo_path: str = Field(description="Path to the repository being researched")
    started_at: float = Field(description="Unix timestamp when research started")
    updated_at: float = Field(description="Unix timestamp of last update")
    current_step: ResearchCheckpointStep = Field(
        description="Current step in the research pipeline"
    )
    sub_questions: list[SubQuestion] | None = Field(
        default=None, description="Decomposed sub-questions"
    )
    retrieved_contexts: dict[str, list[dict]] | None = Field(
        default=None, description="Mapping of sub_question to retrieved chunk data"
    )
    follow_up_queries: list[str] | None = Field(
        default=None, description="Follow-up queries from gap analysis"
    )
    follow_up_contexts: list[dict] | None = Field(
        default=None, description="Retrieved contexts from follow-up queries"
    )
    partial_synthesis: str | None = Field(
        default=None, description="Partial synthesis result if available"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    completed_steps: list[str] = Field(
        default_factory=list, description="List of completed step names"
    )

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return (
            f"<ResearchCheckpoint {self.research_id[:8]}... "
            f"step={self.current_step.value} "
            f"completed={len(self.completed_steps)}>"
        )


class ListResearchCheckpointsArgs(BaseModel):
    """Arguments for the list_research_checkpoints tool."""

    repo_path: str = Field(description="Path to the repository to list checkpoints for")


class ResumeResearchArgs(BaseModel):
    """Arguments for resuming research with a checkpoint."""

    repo_path: str = Field(description="Path to the indexed repository")
    research_id: str = Field(description="ID of the research checkpoint to resume")


class CancelResearchArgs(BaseModel):
    """Arguments for cancelling and checkpointing research."""

    repo_path: str = Field(description="Path to the repository")
    research_id: str = Field(description="ID of the research to cancel")


# =============================================================================
# New Tool Argument Models
# =============================================================================


class DiagramType(str, Enum):
    """Types of diagrams that can be generated."""

    CLASS = "class"
    DEPENDENCY = "dependency"
    MODULE = "module"
    SEQUENCE = "sequence"
    LANGUAGE_PIE = "language_pie"


class GetGlossaryArgs(BaseModel):
    """Arguments for the get_glossary tool."""

    repo_path: str = Field(description="Path to the indexed repository")
    search: str | None = Field(
        default=None, description="Optional search term to filter entities"
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


class CodemapFocusType(str, Enum):
    """Focus modes for codemap generation."""

    EXECUTION_FLOW = "execution_flow"
    DATA_FLOW = "data_flow"
    DEPENDENCY_CHAIN = "dependency_chain"


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
