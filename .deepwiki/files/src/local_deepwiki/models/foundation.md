# File: `src/local_deepwiki/models/foundation.py`

## File Overview

This file defines foundational types and protocols used throughout the `local_deepwiki` project. It serves as a central location for shared abstractions that enable consistent communication between different components of the system, particularly in areas like progress reporting, asynchronous operations, and language-specific code handling.

The core purpose of this file is to establish a common interface for interacting with long-running operations, such as indexing, research pipelines, and wiki generation. It also defines core enumerations for supported programming languages and code chunk types, which are used across various modules to maintain consistency and type safety.

## Key Concepts

### Protocols for Asynchronous and Callback Patterns
The file introduces several `Protocol` classes that define expected interfaces for callbacks and asynchronous operations:
- `ProgressCallback`: Used for reporting step-by-step progress during long-running tasks.
- `CancellationChecker`: Allows operations to be cancelled gracefully.
- `ProgressReporter`: Designed for reporting detailed research progress using [`ResearchProgress`](research.md) objects.
- `LogCallback`: A simple string-based logging mechanism for lightweight messages.
- `PageGenerator`: Enables on-demand generation of [`WikiPage`](../export/streaming.md) objects.
- `RowMapper`: Converts raw dictionary rows (e.g., from a database) into typed [`CodeChunk`](chunks.md) objects.

These protocols support a decoupled architecture where different parts of the system can interact without tight coupling, allowing for easier testing and extension.

### Enumerations for Language and Chunk Types
Two `StrEnum` classes define fixed sets of values:
- `Language`: Lists all supported programming languages for code analysis and processing.
- `ChunkType`: Defines the types of code chunks that can be identified and stored, such as functions, classes, and comments.

Using `StrEnum` ensures that these values are both strongly typed and string-compatible, making them suitable for configuration, storage, and user-facing interfaces.

## Integration

This file is imported and used by multiple modules within the project:
- The `ProgressCallback` protocol is used by `cli_progress` to provide feedback during CLI operations.
- The `PageGenerator` protocol is consumed by `lazy_generator` and `test_lazy_generator`, enabling dynamic wiki page creation.
- The `Language` enum is referenced by `init_cli`, `languages`, and `source_formatter`, ensuring consistent handling of language-specific features.
- The `ChunkType` enum is used in `fuzzy_search`, `source_formatter`, and `test_chunker`, supporting code chunk classification and retrieval.

These integrations highlight the role of this file as a shared foundation that enables cross-cutting concerns like language support, progress tracking, and chunking strategies to be implemented consistently across the codebase.

## Design Notes

### Use of Protocols Over Concrete Classes
Protocols are preferred over concrete classes to allow flexibility in implementation. This design choice supports dependency injection and makes it easier to mock components during testing. For example, `ProgressCallback` can be implemented by any function matching its signature, enabling both simple print statements and complex UI updates.

### StrEnum for Type Safety and Readability
Using `StrEnum` for `Language` and `ChunkType` provides compile-time checks and runtime safety while maintaining string compatibility. This is especially important when these values are used in configuration files or external APIs, where string representations are expected.

### Asynchronous Support
Several protocols involve `Awaitable` types, indicating that the system supports asynchronous workflows. This reflects modern Python practices and aligns with the need to handle I/O-bound operations like file reading, network requests, or database queries efficiently.

### Lightweight Logging vs. Full Progress Reporting
The distinction between `LogCallback` and `ProgressReporter` shows a thoughtful separation of concerns. `LogCallback` is for simple status messages, while `ProgressReporter` is for detailed, structured progress updates involving [`ResearchProgress`](research.md). This allows developers to choose the appropriate level of detail depending on the context.

## API Reference

### class `ProgressCallback`

**Inherits from:** `Protocol`

Protocol for progress callback functions.  Progress callbacks are used to report progress during long-running operations like indexing and wiki generation.

**Methods:**


<details>
<summary>View Source (lines 16-31) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L16-L31">GitHub</a></summary>

```python
class ProgressCallback(Protocol):
    """Protocol for progress callback functions.

    Progress callbacks are used to report progress during long-running
    operations like indexing and wiki generation.
    """

    def __call__(self, msg: str, current: int, total: int, /) -> None:
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


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `msg` | `str` | - | Description of current operation. |
| `current` | `int` | - | Current step number. |
| `total` | `int` | - | Total number of steps. |



<details>
<summary>View Source (lines 16-31) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L16-L31">GitHub</a></summary>

```python
class ProgressCallback(Protocol):
    """Protocol for progress callback functions.

    Progress callbacks are used to report progress during long-running
    operations like indexing and wiki generation.
    """

    def __call__(self, msg: str, current: int, total: int, /) -> None:
        """Report progress.

        Args:
            msg: Description of current operation.
            current: Current step number.
            total: Total number of steps.
        """
        ...
```

</details>

### class `CancellationChecker`

**Inherits from:** `Protocol`

Check whether an operation has been cancelled.  Returns True if the operation should stop.

**Methods:**


<details>
<summary>View Source (lines 35-41) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L35-L41">GitHub</a></summary>

```python
class CancellationChecker(Protocol):
    """Check whether an operation has been cancelled.

    Returns True if the operation should stop.
    """

    def __call__(self) -> bool: ...
```

</details>

#### `__call__`

```python
def __call__() -> bool
```



<details>
<summary>View Source (lines 35-41) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L35-L41">GitHub</a></summary>

```python
class CancellationChecker(Protocol):
    """Check whether an operation has been cancelled.

    Returns True if the operation should stop.
    """

    def __call__(self) -> bool: ...
```

</details>

### class `ProgressReporter`

**Inherits from:** `Protocol`

Report progress for a research operation.  Called with a `[`ResearchProgress`](research.md)` instance during long-running research pipelines.

**Methods:**


<details>
<summary>View Source (lines 45-52) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L45-L52">GitHub</a></summary>

```python
class ProgressReporter(Protocol):
    """Report progress for a research operation.

    Called with a ``ResearchProgress`` instance during long-running
    research pipelines.
    """

    def __call__(self, progress: "ResearchProgress", /) -> Awaitable[None]: ...
```

</details>

#### `__call__`

```python
def __call__(progress: "ResearchProgress") -> Awaitable[None]
```


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `progress` | `"ResearchProgress"` | - | - |



<details>
<summary>View Source (lines 45-52) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L45-L52">GitHub</a></summary>

```python
class ProgressReporter(Protocol):
    """Report progress for a research operation.

    Called with a ``ResearchProgress`` instance during long-running
    research pipelines.
    """

    def __call__(self, progress: "ResearchProgress", /) -> Awaitable[None]: ...
```

</details>

### class `LogCallback`

**Inherits from:** `Protocol`

Log a message string.  Used for lightweight progress or status callbacks that accept a single human-readable message.

**Methods:**


<details>
<summary>View Source (lines 56-63) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L56-L63">GitHub</a></summary>

```python
class LogCallback(Protocol):
    """Log a message string.

    Used for lightweight progress or status callbacks that accept a
    single human-readable message.
    """

    def __call__(self, message: str, /) -> None: ...
```

</details>

#### `__call__`

```python
def __call__(message: str) -> None
```


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `message` | `str` | - | - |



<details>
<summary>View Source (lines 56-63) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L56-L63">GitHub</a></summary>

```python
class LogCallback(Protocol):
    """Log a message string.

    Used for lightweight progress or status callbacks that accept a
    single human-readable message.
    """

    def __call__(self, message: str, /) -> None: ...
```

</details>

### class `PageGenerator`

**Inherits from:** `Protocol`

Generate a wiki page on demand.  Returns a coroutine that produces a `[`WikiPage`](../export/streaming.md)`.

**Methods:**


<details>
<summary>View Source (lines 67-73) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L67-L73">GitHub</a></summary>

```python
class PageGenerator(Protocol):
    """Generate a wiki page on demand.

    Returns a coroutine that produces a ``WikiPage``.
    """

    def __call__(self) -> Awaitable["WikiPage"]: ...
```

</details>

#### `__call__`

```python
def __call__() -> Awaitable["WikiPage"]
```



<details>
<summary>View Source (lines 67-73) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L67-L73">GitHub</a></summary>

```python
class PageGenerator(Protocol):
    """Generate a wiki page on demand.

    Returns a coroutine that produces a ``WikiPage``.
    """

    def __call__(self) -> Awaitable["WikiPage"]: ...
```

</details>

### class `RowMapper`

**Inherits from:** `Protocol`

Map a dictionary row to a `[`CodeChunk`](chunks.md)`.  Used by vector store iterators to convert raw LanceDB rows into typed `[`CodeChunk`](chunks.md)` objects.

**Methods:**


<details>
<summary>View Source (lines 77-84) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L77-L84">GitHub</a></summary>

```python
class RowMapper(Protocol):
    """Map a dictionary row to a ``CodeChunk``.

    Used by vector store iterators to convert raw LanceDB rows into
    typed ``CodeChunk`` objects.
    """

    def __call__(self, row: dict, /) -> "CodeChunk": ...
```

</details>

#### `__call__`

```python
def __call__(row: dict) -> "CodeChunk"
```


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `row` | `dict` | - | - |



<details>
<summary>View Source (lines 77-84) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L77-L84">GitHub</a></summary>

```python
class RowMapper(Protocol):
    """Map a dictionary row to a ``CodeChunk``.

    Used by vector store iterators to convert raw LanceDB rows into
    typed ``CodeChunk`` objects.
    """

    def __call__(self, row: dict, /) -> "CodeChunk": ...
```

</details>

### class `Language`

**Inherits from:** `StrEnum`

Supported programming languages.


<details>
<summary>View Source (lines 87-104) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L87-L104">GitHub</a></summary>

```python
class Language(StrEnum):
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
    OBJC = "objective_c"
```

</details>

### class `ChunkType`

**Inherits from:** `StrEnum`

Types of code chunks.



<details>
<summary>View Source (lines 107-118) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/models/foundation.py#L107-L118">GitHub</a></summary>

```python
class ChunkType(StrEnum):
    """Types of code chunks."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    IMPORT = "import"
    COMMENT = "comment"
    OTHER = "other"
    FILE_SUMMARY = "file_summary"
    MODULE_SUMMARY = "module_summary"
```

</details>

## Class Diagram

```mermaid
classDiagram
    class CancellationChecker {
        -__call__() -> bool
    }
    class LogCallback {
        -__call__() -> None
    }
    class PageGenerator {
        -__call__() -> Awaitable["WikiPage"]
    }
    class ProgressCallback {
        -__call__() -> None
    }
    class ProgressReporter {
        -__call__() -> Awaitable[None]
    }
    class RowMapper {
        -__call__() -> "CodeChunk"
    }
    CancellationChecker --|> Protocol
    LogCallback --|> Protocol
    PageGenerator --|> Protocol
    ProgressCallback --|> Protocol
    ProgressReporter --|> Protocol
    RowMapper --|> Protocol
```

## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `Language` | class | Not Committed Yet | today | `0000000` Version of src/local_deepwi... |
| `ChunkType` | class | Brian Breidenbach | 2 weeks ago | `9cf0e15` feat: add FILE_SUMMARY and ... |
| `ProgressCallback` | class | Brian Breidenbach | Feb 21, 2026 | `e45a53a` refactor: apply Pythonic id... |
| `CancellationChecker` | class | Brian Breidenbach | Feb 21, 2026 | `e45a53a` refactor: apply Pythonic id... |
| `ProgressReporter` | class | Brian Breidenbach | Feb 21, 2026 | `e45a53a` refactor: apply Pythonic id... |
| `LogCallback` | class | Brian Breidenbach | Feb 21, 2026 | `e45a53a` refactor: apply Pythonic id... |
| `PageGenerator` | class | Brian Breidenbach | Feb 21, 2026 | `e45a53a` refactor: apply Pythonic id... |
| `RowMapper` | class | Brian Breidenbach | Feb 21, 2026 | `e45a53a` refactor: apply Pythonic id... |

## Relevant Source Files

- `src/local_deepwiki/models/foundation.py:16-31`
