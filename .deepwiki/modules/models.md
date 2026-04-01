# models Module Documentation

## Module Purpose

The `models` module defines foundational data structures, protocols, and enumerations used throughout the Local DeepWiki MCP Server. It provides core type definitions for code chunks, research operations, wiki pages, and provider types that are shared across various components of the system.

## Key Classes and Functions

### CodeChunk
Defined in `chunks.py`
A data structure representing a semantic unit of code extracted from source files. Used during parsing and indexing operations.

### ProgressCallback
Defined in `foundation.py`
A protocol for progress callback functions used to report progress during long-running operations like indexing and wiki generation.
```python
def __call__(self, msg: str, current: int, total: int, /) -> None:
    """Report progress.
    
    Args:
        msg: Description of current operation.
        current: Current step number.
        total: Total number of steps.
    """
```
### CancellationChecker
Defined in `foundation.py`
A protocol that checks whether an operation has been cancelled, returning True if the operation should stop.
```python
def __call__(self) -> bool: ...
```
### ProgressReporter
Defined in `foundation.py`
A protocol for reporting progress for research operations, called with a [`ResearchProgress`](../files/src/local_deepwiki/models/research.md) instance during long-running research pipelines.
```python
def __call__(self, progress: "ResearchProgress", /) -> Awaitable[None]: ...
```
### LogCallback
Defined in `foundation.py`
A protocol for logging message strings used for lightweight progress or status callbacks that accept a single human-readable message.
```python
def __call__(self, message: str, /) -> None: ...
```
### PageGenerator
Defined in `foundation.py`
A protocol for generating wiki pages on demand, returning a coroutine that produces a [`WikiPage`](../files/src/local_deepwiki/export/streaming.md).
```python
def __call__(self) -> Awaitable["WikiPage"]: ...
```
### RowMapper
Defined in `foundation.py`
A protocol for mapping dictionary rows to [`CodeChunk`](../files/src/local_deepwiki/models/chunks.md) objects used by vector store iterators.
```python
def __call__(self, row: dict, /) -> "CodeChunk": ...
```
### Language
Defined in `foundation.py`
An enumeration of supported programming languages used in code parsing and indexing.

Values:
- PYTHON = "python"
- JAVASCRIPT = "javascript"
- TYPESCRIPT = "typescript"
- TSX = "tsx"
- GO = "go"
- RUST = "rust"
- JAVA = "java"
- C = "c"
- CPP = "cpp"
- SWIFT = "swift"
- RUBY = "ruby"
- PHP = "php"
- KOTLIN = "kotlin"
- CSHARP = "csharp"

### ChunkType
Defined in `foundation.py`
An enumeration of types of code chunks used during semantic analysis and indexing.

Values:
- FUNCTION = "function"
- CLASS = "class"
- METHOD = "method"
- MODULE = "module"
- IMPORT = "import"
- COMMENT = "comment"
- OTHER = "other"
- FILE_SUMMARY = "file_summary"
- MODULE_SUMMARY = "module_summary"

### LLMProviderType
Defined in `provider_types.py`
An enumeration of supported LLM providers used for documentation generation and research.

Values:
- OLLAMA = "ollama"
- ANTHROPIC = "anthropic"
- OPENAI = "openai"

### EmbeddingProviderType
Defined in `provider_types.py`
An enumeration of supported embedding providers used for vector storage and retrieval.

Values:
- LOCAL = "local"
- OPENAI = "openai"

### DiagramType
Defined in `provider_types.py`
An enumeration of types of diagrams that can be generated for code visualization.

Values:
- CLASS = "class"
- DEPENDENCY = "dependency"
- MODULE = "module"
- SEQUENCE = "sequence"
- LANGUAGE_PIE = "language_pie"

### CodemapFocusType
Defined in `provider_types.py`
An enumeration of focus modes for codemap generation.

Values:
- EXECUTION_FLOW = "execution_flow"
- DATA_FLOW = "data_flow"
- DEPENDENCY_CHAIN = "dependency_chain"

### ResearchStepType
Defined in `research.py`
An enumeration of types of steps in the deep research process.

Values:
- DECOMPOSITION = "decomposition"
- RETRIEVAL = "retrieval"
- GAP_ANALYSIS = "gap_analysis"
- SYNTHESIS = "synthesis"

### ResearchStep
Defined in `research.py`
A data structure representing a single step in the deep research process, containing type, description, and duration information.

### SubQuestion
Defined in `research.py`
A data structure representing a decomposed sub-question for deep research analysis.

### SourceReference
Defined in `research.py`
A data structure referencing a source code location with file path, line numbers, chunk type, name, and relevance score.

### DeepResearchResult
Defined in `research.py`
A data structure containing the result from deep research analysis including question, answer, sub-questions, sources, reasoning trace, and statistics.

## How Components Interact

The components in this module work together to provide a consistent type system across the Local DeepWiki MCP Server. The protocols ([`ProgressCallback`](../files/src/local_deepwiki/models/foundation.md), [`CancellationChecker`](../files/src/local_deepwiki/models/foundation.md), etc.) define interfaces that various operations can implement to report status or check for cancellation. The enumerations provide standardized values for language, chunk types, and provider types used throughout the system.

The [`CodeChunk`](../files/src/local_deepwiki/models/chunks.md) and [`WikiPage`](../files/src/local_deepwiki/export/streaming.md) classes serve as core data structures that flow between components during parsing, indexing, and documentation generation processes. The research-related models support multi-step reasoning pipelines with structured reporting of progress and results.

## Usage Examples

### Using ProgressCallback Protocol```python
from local_deepwiki.models.foundation import ProgressCallback

def my_progress_callback(msg: str, current: int, total: int) -> None:
    print(f"{msg}: {current}/{total}")

# Pass to indexing or research functions
index_repository(args, progress_callback=my_progress_callback)
```
### Using Language Enum```python
from local_deepwiki.models.foundation import Language

def process_language(lang: Language):
    if lang == Language.PYTHON:
        # Handle Python-specific logic
        pass
```
### Using ResearchStepType```python
from local_deepwiki.models.research import ResearchStepType

def handle_research_step(step_type: ResearchStepType):
    match step_type:
        case ResearchStepType.DECOMPOSITION:
            # Handle decomposition step
            pass
        case ResearchStepType.RETRIEVAL:
            # Handle retrieval step
            pass
```
## Dependencies

This module depends on:
- `collections.abc` - for `Awaitable` type
- `enum` - for `StrEnum` base class
- `typing` - for `Protocol`, `TYPE_CHECKING`, and `runtime_checkable`
- `pydantic` - for `BaseModel` and `Field` in research models
- `local_deepwiki.models.chunks` - for [`CodeChunk`](../files/src/local_deepwiki/models/chunks.md) type
- `local_deepwiki.models.research` - for [`ResearchProgress`](../files/src/local_deepwiki/models/research.md) type
- `local_deepwiki.models.wiki` - for [`WikiPage`](../files/src/local_deepwiki/export/streaming.md) type

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/models/foundation.py:16-31`](../files/src/local_deepwiki/models/foundation.md)
- [`src/local_deepwiki/models/provider_types.py:8-13`](../files/src/local_deepwiki/models/provider_types.md)
- [`src/local_deepwiki/models/research.py:10-16`](../files/src/local_deepwiki/models/research.md)
- `src/local_deepwiki/models/__init__.py`
- [`src/local_deepwiki/models/tool_args.py:15-49`](../files/src/local_deepwiki/models/tool_args.md)
- [`src/local_deepwiki/models/chunks.py:13-64`](../files/src/local_deepwiki/models/chunks.md)
- [`src/local_deepwiki/models/wiki.py:13-33`](../files/src/local_deepwiki/models/wiki.md)
