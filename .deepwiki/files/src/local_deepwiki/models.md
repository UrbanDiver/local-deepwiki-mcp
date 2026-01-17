# models.py

## File Overview

The `models.py` file defines the core data models and enums for the local_deepwiki system. This module provides structured data representations for wiki generation, research processes, file indexing, and search functionality using Pydantic models for data validation and serialization.

## Enums

### Language

Enumeration defining supported programming languages for code analysis and wiki generation.

### ChunkType

Enumeration specifying different types of code chunks that can be processed during file analysis.

### IndexStatus

Enumeration representing the current status of file indexing operations.

### WikiPageStatus

Enumeration indicating the generation status of individual wiki pages.

### WikiGenerationStatus

Enumeration tracking the overall status of wiki generation processes.

### ResearchStepType

Enumeration defining different types of research steps in the deep research workflow.

### ResearchProgressType

Enumeration representing different stages of research progress reporting.

## Protocol Classes

### ProgressCallback

Protocol defining the interface for progress callback functions used throughout the system.

## Core Models

### CodeChunk

Pydantic model representing a chunk of code with metadata including type, name, content, and line numbers. Used for organizing and processing code segments during analysis.

### FileInfo

Model containing comprehensive information about analyzed files, including path, language, modification time, and associated code chunks.

### WikiPage

Model representing a generated wiki page with title, content, file path, and generation status tracking.

### WikiStructure

Model defining the overall structure of generated wiki documentation, containing collections of wiki pages and metadata.

### SearchResult

Model for search functionality results, containing matched content and relevance information.

## Research Models

### ResearchStep

Model representing individual steps in the research process, including step type, description, and execution status.

### SubQuestion

Model for breaking down complex research queries into manageable sub-questions with associated metadata.

### SourceReference

Model containing reference information for research sources, including URLs, titles, and relevance scores.

### DeepResearchResult

Comprehensive model containing the results of deep research operations, including findings, sources, and generated insights.

### ResearchProgress

Model for tracking and reporting progress during research operations, including completion percentages and current activity descriptions.

## Usage Examples

### Creating a CodeChunk

```python
from local_deepwiki.models import CodeChunk, ChunkType

chunk = CodeChunk(
    type=ChunkType.CLASS,
    name="MyClass",
    content="class MyClass:\n    pass",
    start_line=1,
    end_line=2
)
```

### Working with FileInfo

```python
from pathlib import Path
from local_deepwiki.models import FileInfo, Language

file_info = FileInfo(
    path=Path("src/example.py"),
    language=Language.PYTHON,
    chunks=[chunk]
)
```

### Creating WikiPage

```python
from local_deepwiki.models import WikiPage, WikiPageStatus

page = WikiPage(
    title="API Documentation",
    content="# API Overview\n\nThis page describes...",
    file_path=Path("docs/api.md"),
    status=WikiPageStatus.GENERATED
)
```

## Related Components

This models file serves as the foundation for data structures used throughout the local_deepwiki system. The models defined here integrate with:

- File analysis and indexing components that populate FileInfo and CodeChunk models
- Wiki generation systems that create and manage WikiPage and WikiStructure instances  
- Research functionality that utilizes the research-related models for deep analysis
- Search capabilities that return SearchResult instances
- Progress tracking systems that implement the ProgressCallback protocol

The Pydantic BaseModel inheritance provides automatic JSON serialization/deserialization and data validation for all model classes.

## API Reference

### class `ProgressCallback`

**Inherits from:** `Protocol`

Protocol for progress callback functions.  Progress callbacks are used to report progress during long-running operations like indexing and wiki generation.

**Methods:**


<details>
<summary>View Source (lines 11-26) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L11-L26">GitHub</a></summary>

```python
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
```

</details>

#### `__call__`

```python
def __call__(msg: str, current: int, total: int) -> None
```

Report progress.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `msg` | `str` | - | Description of current operation. |
| `current` | `int` | - | Current step number. |
| `total` | `int` | - | Total number of steps. |



<details>
<summary>View Source (lines 11-26) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L11-L26">GitHub</a></summary>

```python
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
```

</details>

### class `Language`

**Inherits from:** `str`, `Enum`

Supported programming languages.


<details>
<summary>View Source (lines 29-45) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L29-L45">GitHub</a></summary>

```python
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
```

</details>

### class `ChunkType`

**Inherits from:** `str`, `Enum`

Types of code chunks.


<details>
<summary>View Source (lines 48-57) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L48-L57">GitHub</a></summary>

```python
class ChunkType(str, Enum):
    """Types of code chunks."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    IMPORT = "import"
    COMMENT = "comment"
    OTHER = "other"
```

</details>

### class `CodeChunk`

**Inherits from:** `BaseModel`

A chunk of code extracted from the repository.

**Methods:**


<details>
<summary>View Source (lines 60-107) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L60-L107">GitHub</a></summary>

```python
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
    parent_name: str | None = Field(default=None, description="Parent class/module name")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

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
```

</details>

#### `to_vector_record`

```python
def to_vector_record(vector: list[float] | None = None) -> dict[str, Any]
```

Convert chunk to a dict suitable for vector store storage.


| [Parameter](generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `vector` | `list[float] | None` | `None` | Optional embedding vector to include in the record. |



<details>
<summary>View Source (lines 60-107) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L60-L107">GitHub</a></summary>

```python
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
    parent_name: str | None = Field(default=None, description="Parent class/module name")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

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
```

</details>

### class `FileInfo`

**Inherits from:** `BaseModel`

Information about a source file.


<details>
<summary>View Source (lines 110-123) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L110-L123">GitHub</a></summary>

```python
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
```

</details>

### class `IndexStatus`

**Inherits from:** `BaseModel`

Status of repository indexing.


<details>
<summary>View Source (lines 126-142) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L126-L142">GitHub</a></summary>

```python
class IndexStatus(BaseModel):
    """Status of repository indexing."""

    repo_path: str = Field(description="Path to the repository")
    indexed_at: float = Field(description="Timestamp of last indexing")
    total_files: int = Field(description="Total files processed")
    total_chunks: int = Field(description="Total chunks extracted")
    languages: dict[str, int] = Field(default_factory=dict, description="Files per language")
    files: list[FileInfo] = Field(default_factory=list, description="Indexed file info")
    schema_version: int = Field(default=1, description="Schema version for migration support")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return (
            f"<IndexStatus {self.repo_path} "
            f"({self.total_files} files, {self.total_chunks} chunks)>"
        )
```

</details>

### class `WikiPage`

**Inherits from:** `BaseModel`

A generated wiki page.


<details>
<summary>View Source (lines 145-155) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L145-L155">GitHub</a></summary>

```python
class WikiPage(BaseModel):
    """A generated wiki page."""

    path: str = Field(description="Relative path in wiki directory")
    title: str = Field(description="Page title")
    content: str = Field(description="Markdown content")
    generated_at: float = Field(description="Generation timestamp")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<WikiPage {self.path} ({self.title!r})>"
```

</details>

### class `WikiStructure`

**Inherits from:** `BaseModel`

Structure of the generated wiki.

**Methods:**


<details>
<summary>View Source (lines 158-181) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L158-L181">GitHub</a></summary>

```python
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
                section = next((s for s in current.get("sections", []) if s["name"] == part), None)
                if not section:
                    section = {"name": part, "sections": [], "pages": []}
                    current.setdefault("sections", []).append(section)
                current = section
            current.setdefault("pages", []).append({"path": page.path, "title": page.title})
        return toc
```

</details>

#### `to_toc`

```python
def to_toc() -> dict[str, Any]
```

Generate table of contents.



<details>
<summary>View Source (lines 158-181) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L158-L181">GitHub</a></summary>

```python
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
                section = next((s for s in current.get("sections", []) if s["name"] == part), None)
                if not section:
                    section = {"name": part, "sections": [], "pages": []}
                    current.setdefault("sections", []).append(section)
                current = section
            current.setdefault("pages", []).append({"path": page.path, "title": page.title})
        return toc
```

</details>

### class `SearchResult`

**Inherits from:** `BaseModel`

A search result from semantic search.


<details>
<summary>View Source (lines 184-194) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L184-L194">GitHub</a></summary>

```python
class SearchResult(BaseModel):
    """A search result from semantic search."""

    chunk: CodeChunk = Field(description="The matched code chunk")
    score: float = Field(description="Similarity score")
    highlights: list[str] = Field(default_factory=list, description="Relevant snippets")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        name = self.chunk.name or self.chunk.chunk_type.value
        return f"<SearchResult {name} score={self.score:.3f}>"
```

</details>

### class `WikiPageStatus`

**Inherits from:** `BaseModel`

Status of a generated wiki page for incremental generation.


<details>
<summary>View Source (lines 197-216) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L197-L216">GitHub</a></summary>

```python
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
```

</details>

### class `WikiGenerationStatus`

**Inherits from:** `BaseModel`

Status of wiki generation for tracking incremental updates.


<details>
<summary>View Source (lines 219-234) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L219-L234">GitHub</a></summary>

```python
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
```

</details>

### class `ResearchStepType`

**Inherits from:** `str`, `Enum`

Types of steps in the deep research process.


<details>
<summary>View Source (lines 240-246) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L240-L246">GitHub</a></summary>

```python
class ResearchStepType(str, Enum):
    """Types of steps in the deep research process."""

    DECOMPOSITION = "decomposition"
    RETRIEVAL = "retrieval"
    GAP_ANALYSIS = "gap_analysis"
    SYNTHESIS = "synthesis"
```

</details>

### class `ResearchStep`

**Inherits from:** `BaseModel`

A single step in the deep research process.


<details>
<summary>View Source (lines 249-258) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L249-L258">GitHub</a></summary>

```python
class ResearchStep(BaseModel):
    """A single step in the deep research process."""

    step_type: ResearchStepType = Field(description="Type of research step")
    description: str = Field(description="Description of what was done")
    duration_ms: int = Field(description="Duration of this step in milliseconds")

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<ResearchStep {self.step_type.value} ({self.duration_ms}ms)>"
```

</details>

### class `SubQuestion`

**Inherits from:** `BaseModel`

A decomposed sub-question for deep research.


<details>
<summary>View Source (lines 261-271) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L261-L271">GitHub</a></summary>

```python
class SubQuestion(BaseModel):
    """A decomposed sub-question for deep research."""

    question: str = Field(description="The sub-question to investigate")
    category: str = Field(
        description="Category: structure, flow, dependencies, impact, or comparison"
    )

    def __repr__(self) -> str:
        """Return a concise representation for debugging."""
        return f"<SubQuestion [{self.category}] {self.question[:50]}...>"
```

</details>

### class `SourceReference`

**Inherits from:** `BaseModel`

A reference to a source code location.


<details>
<summary>View Source (lines 274-287) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L274-L287">GitHub</a></summary>

```python
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
```

</details>

### class `DeepResearchResult`

**Inherits from:** `BaseModel`

Result from deep research analysis.


<details>
<summary>View Source (lines 290-312) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L290-L312">GitHub</a></summary>

```python
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
```

</details>

### class `ResearchProgressType`

**Inherits from:** `str`, `Enum`

Types of deep research progress events.


<details>
<summary>View Source (lines 315-325) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L315-L325">GitHub</a></summary>

```python
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
```

</details>

### class `ResearchProgress`

**Inherits from:** `BaseModel`

Progress update from deep research pipeline.  Sent via MCP progress notifications to provide real-time feedback during long-running deep research operations.



<details>
<summary>View Source (lines 328-350) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](export/pdf.md)/src/local_deepwiki/models.py#L328-L350">GitHub</a></summary>

```python
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
```

</details>

## Class Diagram

```mermaid
classDiagram
    class CodeChunk {
        <<dataclass>>
        +id: str
        +file_path: str
        +language: Language
        +chunk_type: ChunkType
        +name: str | None
        +content: str
        +start_line: int
        +end_line: int
        +docstring: str | None
        +parent_name: str | None
        +to_vector_record() -> dict[str, Any]
        -__repr__() -> str
    }
    class DeepResearchResult {
        <<dataclass>>
        +question: str
        +answer: str
        +sub_questions: list[SubQuestion]
        +sources: list[SourceReference]
        +reasoning_trace: list[ResearchStep]
        +total_chunks_analyzed: int
        +total_llm_calls: int
        -__repr__() -> str
    }
    class FileInfo {
        <<dataclass>>
        +path: str
        +language: Language | None
        +size_bytes: int
        +last_modified: float
        +hash: str
        +chunk_count: int
        -__repr__() -> str
    }
    class IndexStatus {
        <<dataclass>>
        +repo_path: str
        +indexed_at: float
        +total_files: int
        +total_chunks: int
        +languages: dict[str, int]
        +files: list[FileInfo]
        +schema_version: int
        -__repr__() -> str
    }
    class ProgressCallback {
        -__call__() -> None
    }
    class ResearchProgress {
        <<dataclass>>
        +step: int
        +total_steps: int
        +step_type: ResearchProgressType
        +message: str
        +sub_questions: list[SubQuestion] | None
        +chunks_retrieved: int | None
        +follow_up_queries: list[str] | None
        +duration_ms: int | None
    }
    class ResearchStep {
        <<dataclass>>
        +step_type: ResearchStepType
        +description: str
        +duration_ms: int
        -__repr__() -> str
    }
    class SearchResult {
        <<dataclass>>
        +chunk: CodeChunk
        +score: float
        +highlights: list[str]
        -__repr__() -> str
    }
    class SourceReference {
        <<dataclass>>
        +file_path: str
        +start_line: int
        +end_line: int
        +chunk_type: str
        +name: str | None
        +relevance_score: float
        -__repr__() -> str
    }
    class SubQuestion {
        <<dataclass>>
        +question: str
        +category: str
        -__repr__() -> str
    }
    class WikiGenerationStatus {
        <<dataclass>>
        +repo_path: str
        +generated_at: float
        +total_pages: int
        +index_status_hash: str
        +pages: dict[str, WikiPageStatus]
        -__repr__() -> str
    }
    class WikiPage {
        <<dataclass>>
        +path: str
        +title: str
        +content: str
        +generated_at: float
        -__repr__() -> str
    }
    class WikiPageStatus {
        <<dataclass>>
        +path: str
        +source_files: list[str]
        +source_hashes: dict[str, str]
        +source_line_info: dict[str, dict[str, int]]
        +content_hash: str
        +generated_at: float
        -__repr__() -> str
    }
    class WikiStructure {
        <<dataclass>>
        +root: str
        +pages: list[WikiPage]
        -__repr__() -> str
        +to_toc() -> dict[str, Any]
    }
    CodeChunk --|> BaseModel
    DeepResearchResult --|> BaseModel
    FileInfo --|> BaseModel
    IndexStatus --|> BaseModel
    ProgressCallback --|> Protocol
    ResearchProgress --|> BaseModel
    ResearchStep --|> BaseModel
    SearchResult --|> BaseModel
    SourceReference --|> BaseModel
    SubQuestion --|> BaseModel
    WikiGenerationStatus --|> BaseModel
    WikiPage --|> BaseModel
    WikiPageStatus --|> BaseModel
    WikiStructure --|> BaseModel
```

## Call Graph

```mermaid
flowchart TD
    N0[CodeChunk.to_vector_record]
    N1[Path]
    N2[WikiStructure.to_toc]
    N3[dumps]
    N4[setdefault]
    N0 --> N3
    N2 --> N1
    N2 --> N4
    classDef func fill:#e1f5fe
    class N1,N3,N4 func
    classDef method fill:#fff3e0
    class N0,N2 method
```

## Used By

Functions and methods in this file and their callers:

- **`Path`**: called by `WikiStructure.to_toc`
- **`dumps`**: called by `CodeChunk.to_vector_record`
- **`setdefault`**: called by `WikiStructure.to_toc`

## Usage Examples

*Examples extracted from test files*

### Test basic chunk to vector record conversion

From `test_models.py::TestCodeChunkToVectorRecord::test_basic_conversion`:

```python
language=Language.PYTHON,
    chunk_type=ChunkType.FUNCTION,
    name="test_func",
    content="def test_func(): pass",
    start_line=1,
    end_line=1,
)

record = chunk.to_vector_record()

assert record["id"] == "test_id"
assert record["file_path"] == "src/main.py"
```

### Test basic chunk to vector record conversion

From `test_models.py::TestCodeChunkToVectorRecord::test_basic_conversion`:

```python
chunk_type=ChunkType.FUNCTION,
    name="test_func",
    content="def test_func(): pass",
    start_line=1,
    end_line=1,
)

record = chunk.to_vector_record()

assert record["id"] == "test_id"
assert record["file_path"] == "src/main.py"
```

### Test basic chunk to vector record conversion

From `test_models.py::TestCodeChunkToVectorRecord::test_basic_conversion`:

```python
chunk = CodeChunk(
    id="test_id",
    file_path="src/main.py",
    language=Language.PYTHON,
    chunk_type=ChunkType.FUNCTION,
    name="test_func",
    content="def test_func(): pass",
    start_line=1,
    end_line=1,
)

record = chunk.to_vector_record()

assert record["id"] == "test_id"
assert record["file_path"] == "src/main.py"
```

### Test conversion with vector embedding

From `test_models.py::TestCodeChunkToVectorRecord::test_with_vector`:

```python
language=Language.PYTHON,
    chunk_type=ChunkType.FUNCTION,
    content="def test(): pass",
    start_line=1,
    end_line=1,
)
vector = [0.1, 0.2, 0.3]

record = chunk.to_vector_record(vector=vector)

assert record["vector"] == [0.1, 0.2, 0.3]
```

### Test conversion with vector embedding

From `test_models.py::TestCodeChunkToVectorRecord::test_with_vector`:

```python
chunk_type=ChunkType.FUNCTION,
    content="def test(): pass",
    start_line=1,
    end_line=1,
)
vector = [0.1, 0.2, 0.3]

record = chunk.to_vector_record(vector=vector)

assert record["vector"] == [0.1, 0.2, 0.3]
```


## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `Language` | class | Brian Breidenbach | yesterday | `55d665c` Fix TypeScript/TSX parsing ... |
| `ResearchProgressType` | class | Brian Breidenbach | 2 days ago | `7096531` Add cancellation support fo... |
| `ResearchProgress` | class | Brian Breidenbach | 2 days ago | `28ab9b8` Add streaming progress upda... |
| `ResearchStepType` | class | Brian Breidenbach | 2 days ago | `2d97082` Add Deep Research mode for ... |
| `ResearchStep` | class | Brian Breidenbach | 2 days ago | `2d97082` Add Deep Research mode for ... |
| `SubQuestion` | class | Brian Breidenbach | 2 days ago | `2d97082` Add Deep Research mode for ... |
| `SourceReference` | class | Brian Breidenbach | 2 days ago | `2d97082` Add Deep Research mode for ... |
| `DeepResearchResult` | class | Brian Breidenbach | 2 days ago | `2d97082` Add Deep Research mode for ... |
| `ProgressCallback` | class | Brian Breidenbach | 3 days ago | `c568951` Add input validation, type ... |
| `CodeChunk` | class | Brian Breidenbach | 3 days ago | `c568951` Add input validation, type ... |
| `FileInfo` | class | Brian Breidenbach | 3 days ago | `c568951` Add input validation, type ... |
| `IndexStatus` | class | Brian Breidenbach | 3 days ago | `c568951` Add input validation, type ... |
| `WikiPage` | class | Brian Breidenbach | 3 days ago | `c568951` Add input validation, type ... |
| `WikiStructure` | class | Brian Breidenbach | 3 days ago | `c568951` Add input validation, type ... |
| `SearchResult` | class | Brian Breidenbach | 3 days ago | `c568951` Add input validation, type ... |
| `WikiPageStatus` | class | Brian Breidenbach | 3 days ago | `c568951` Add input validation, type ... |
| `WikiGenerationStatus` | class | Brian Breidenbach | 3 days ago | `c568951` Add input validation, type ... |
| `ChunkType` | class | Brian Breidenbach | 5 days ago | `cdae76f` Initial commit: Local DeepW... |

## Relevant Source Files

- `src/local_deepwiki/models.py:11-26`

## See Also

- [search](generators/search.md) - uses this
- [api_docs](generators/api_docs.md) - uses this
- [source_refs](generators/source_refs.md) - uses this
- [chunker](core/chunker.md) - uses this
- [see_also](generators/see_also.md) - uses this
