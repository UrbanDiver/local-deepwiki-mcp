# wiki_status.py

## File Overview

This file provides functionality for managing the status of wiki generation processes. It handles tracking file hashes for incremental generation, loading and saving wiki generation status, and managing page-level status information.

## Classes

### WikiStatusManager

The WikiStatusManager class manages the status tracking for wiki generation processes. It handles incremental generation by tracking file changes through hashes and maintains both previous and current generation status information.

#### Constructor

```python
def __init__(self, wiki_path: Path)
```

Initializes the status manager with the wiki output directory path.

**Parameters:**
- `wiki_path` (Path): Path to wiki output directory

The constructor sets up several internal tracking dictionaries:
- File hashes from index_status for incremental generation
- Previous wiki generation status for incremental updates  
- New page statuses for current generation
- Line info for source files

#### Methods

##### load_status

```python
async def load_status(self) -> WikiGenerationStatus | None
```

Loads the previous wiki generation status from the wiki directory.

**Returns:**
- `WikiGenerationStatus | None`: The previous generation status, or None if no status file exists

The method reads from a status file in the wiki path and validates the JSON data against the [WikiGenerationStatus](../models.md) model.

## Related Components

This file works with several other components from the local_deepwiki package:

- **[WikiGenerationStatus](../models.md)**: Model class for representing the overall status of wiki generation
- **[WikiPage](../models.md)**: Model class representing individual wiki pages
- **[WikiPageStatus](../models.md)**: Model class for tracking the status of individual pages
- **Logging utilities**: Uses the [get_logger](../logging.md) function for logging functionality

The file uses standard Python libraries including `asyncio` for asynchronous operations, `hashlib` for generating file hashes, `json` for status file serialization, and `pathlib` for file system operations.

## API Reference

### class `WikiStatusManager`

Manage wiki generation status for incremental updates.

**Methods:**


<details>
<summary>View Source (lines 15-220) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L15-L220">GitHub</a></summary>

```python
class WikiStatusManager:
    # Methods: __init__, file_hashes, file_hashes, file_line_info, file_line_info, page_statuses, previous_status, load_status, _read_status, save_status, _write_status, compute_content_hash, needs_regeneration, load_existing_page, _read_page, record_page_status
```

</details>

#### `__init__`

```python
def __init__(wiki_path: Path)
```

Initialize the status manager.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | Path to wiki output directory. |


<details>
<summary>View Source (lines 20-38) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L20-L38">GitHub</a></summary>

```python
def __init__(self, wiki_path: Path):
        """Initialize the status manager.

        Args:
            wiki_path: Path to wiki output directory.
        """
        self.wiki_path = wiki_path

        # Track file hashes from index_status for incremental generation
        self._file_hashes: dict[str, str] = {}

        # Previous wiki generation status for incremental updates
        self._previous_status: WikiGenerationStatus | None = None

        # New page statuses for current generation
        self._page_statuses: dict[str, WikiPageStatus] = {}

        # Line info for source files (computed from chunks)
        self._file_line_info: dict[str, tuple[int, int]] = {}
```

</details>

#### `file_hashes`

```python
def file_hashes() -> dict[str, str]
```

Get file hashes map.


<details>
<summary>View Source (lines 46-48) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L46-L48">GitHub</a></summary>

```python
def file_hashes(self, value: dict[str, str]) -> None:
        """Set file hashes map."""
        self._file_hashes = value
```

</details>

#### `file_hashes`

```python
def file_hashes(value: dict[str, str]) -> None
```

Set file hashes map.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | `dict[str, str]` | - | - |


<details>
<summary>View Source (lines 46-48) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L46-L48">GitHub</a></summary>

```python
def file_hashes(self, value: dict[str, str]) -> None:
        """Set file hashes map."""
        self._file_hashes = value
```

</details>

#### `file_line_info`

```python
def file_line_info() -> dict[str, tuple[int, int]]
```

Get file line info map.


<details>
<summary>View Source (lines 56-58) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L56-L58">GitHub</a></summary>

```python
def file_line_info(self, value: dict[str, tuple[int, int]]) -> None:
        """Set file line info map."""
        self._file_line_info = value
```

</details>

#### `file_line_info`

```python
def file_line_info(value: dict[str, tuple[int, int]]) -> None
```

Set file line info map.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | `dict[str, tuple[int, int]]` | - | - |


<details>
<summary>View Source (lines 56-58) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L56-L58">GitHub</a></summary>

```python
def file_line_info(self, value: dict[str, tuple[int, int]]) -> None:
        """Set file line info map."""
        self._file_line_info = value
```

</details>

#### `page_statuses`

```python
def page_statuses() -> dict[str, WikiPageStatus]
```

Get page statuses map.


<details>
<summary>View Source (lines 61-63) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L61-L63">GitHub</a></summary>

```python
def page_statuses(self) -> dict[str, WikiPageStatus]:
        """Get page statuses map."""
        return self._page_statuses
```

</details>

#### `previous_status`

```python
def previous_status() -> WikiGenerationStatus | None
```

Get previous wiki generation status.


<details>
<summary>View Source (lines 66-68) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L66-L68">GitHub</a></summary>

```python
def previous_status(self) -> WikiGenerationStatus | None:
        """Get previous wiki generation status."""
        return self._previous_status
```

</details>

#### `load_status`

```python
async def load_status() -> WikiGenerationStatus | None
```

Load previous wiki generation status.


<details>
<summary>View Source (lines 70-93) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L70-L93">GitHub</a></summary>

```python
async def load_status(self) -> WikiGenerationStatus | None:
        """Load previous wiki generation status.

        Returns:
            WikiGenerationStatus or None if not found.
        """
        status_path = self.wiki_path / self.WIKI_STATUS_FILE
        if not status_path.exists():
            return None

        def _read_status() -> WikiGenerationStatus | None:
            try:
                with open(status_path) as f:
                    data = json.load(f)
                return WikiGenerationStatus.model_validate(data)
            except (json.JSONDecodeError, OSError, ValueError) as e:
                # json.JSONDecodeError: Corrupted or invalid JSON
                # OSError: File read issues
                # ValueError: Pydantic validation failure
                logger.warning(f"Failed to load wiki status from {status_path}: {e}")
                return None

        self._previous_status = await asyncio.to_thread(_read_status)
        return self._previous_status
```

</details>

#### `save_status`

```python
async def save_status(status: WikiGenerationStatus) -> None
```

Save wiki generation status.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | [`WikiGenerationStatus`](../models.md) | - | The [WikiGenerationStatus](../models.md) to save. |


<details>
<summary>View Source (lines 95-108) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L95-L108">GitHub</a></summary>

```python
async def save_status(self, status: WikiGenerationStatus) -> None:
        """Save wiki generation status.

        Args:
            status: The WikiGenerationStatus to save.
        """
        status_path = self.wiki_path / self.WIKI_STATUS_FILE
        data = status.model_dump()

        def _write_status() -> None:
            with open(status_path, "w") as f:
                json.dump(data, f, indent=2)

        await asyncio.to_thread(_write_status)
```

</details>

#### `compute_content_hash`

```python
def compute_content_hash(content: str) -> str
```

Compute hash of page content.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | Page content. |


<details>
<summary>View Source (lines 110-119) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L110-L119">GitHub</a></summary>

```python
def compute_content_hash(self, content: str) -> str:
        """Compute hash of page content.

        Args:
            content: Page content.

        Returns:
            SHA256 hash of content (first 16 chars).
        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]
```

</details>

#### `needs_regeneration`

```python
def needs_regeneration(page_path: str, source_files: list[str]) -> bool
```

Check if a page needs regeneration based on source file changes.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `page_path` | `str` | - | Wiki page path. |
| `source_files` | `list[str]` | - | List of source files that contribute to this page. |


<details>
<summary>View Source (lines 121-156) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L121-L156">GitHub</a></summary>

```python
def needs_regeneration(
        self,
        page_path: str,
        source_files: list[str],
    ) -> bool:
        """Check if a page needs regeneration based on source file changes.

        Args:
            page_path: Wiki page path.
            source_files: List of source files that contribute to this page.

        Returns:
            True if page needs regeneration, False if it can be skipped.
        """
        if self._previous_status is None:
            return True

        prev_page = self._previous_status.pages.get(page_path)
        if prev_page is None:
            return True

        # Check if any source file has changed
        for source_file in source_files:
            current_hash = self._file_hashes.get(source_file)
            prev_hash = prev_page.source_hashes.get(source_file)

            if current_hash is None or prev_hash is None:
                return True
            if current_hash != prev_hash:
                return True

        # Check if source files list changed
        if set(source_files) != set(prev_page.source_files):
            return True

        return False
```

</details>

#### `load_existing_page`

```python
async def load_existing_page(page_path: str) -> WikiPage | None
```

Load an existing wiki page from disk.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `page_path` | `str` | - | Relative path to the page. |


<details>
<summary>View Source (lines 158-191) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L158-L191">GitHub</a></summary>

```python
async def load_existing_page(self, page_path: str) -> WikiPage | None:
        """Load an existing wiki page from disk.

        Args:
            page_path: Relative path to the page.

        Returns:
            WikiPage if found, None otherwise.
        """
        full_path = self.wiki_path / page_path
        if not full_path.exists():
            return None

        # Capture values needed for the sync function
        prev_page = self._previous_status.pages.get(page_path) if self._previous_status else None
        title = Path(page_path).stem.replace("_", " ").title()
        generated_at = prev_page.generated_at if prev_page else time.time()

        def _read_page() -> WikiPage | None:
            try:
                content = full_path.read_text()
                return WikiPage(
                    path=page_path,
                    title=title,
                    content=content,
                    generated_at=generated_at,
                )
            except (OSError, UnicodeDecodeError) as e:
                # OSError: File read issues
                # UnicodeDecodeError: File encoding issues
                logger.warning(f"Failed to load existing page {page_path}: {e}")
                return None

        return await asyncio.to_thread(_read_page)
```

</details>

#### `record_page_status`

```python
def record_page_status(page: WikiPage, source_files: list[str]) -> None
```

Record status for a generated/loaded page.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | [`WikiPage`](../models.md) | - | The wiki page. |
| `source_files` | `list[str]` | - | Source files that contributed to this page. |




<details>
<summary>View Source (lines 193-220) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L193-L220">GitHub</a></summary>

```python
def record_page_status(
        self,
        page: WikiPage,
        source_files: list[str],
    ) -> None:
        """Record status for a generated/loaded page.

        Args:
            page: The wiki page.
            source_files: Source files that contributed to this page.
        """
        source_hashes = {f: self._file_hashes.get(f, "") for f in source_files}

        # Include line info for source files that have it
        source_line_info = {
            f: {"start_line": self._file_line_info[f][0], "end_line": self._file_line_info[f][1]}
            for f in source_files
            if f in self._file_line_info
        }

        self._page_statuses[page.path] = WikiPageStatus(
            path=page.path,
            source_files=source_files,
            source_hashes=source_hashes,
            source_line_info=source_line_info,
            content_hash=self.compute_content_hash(page.content),
            generated_at=page.generated_at,
        )
```

</details>

## Class Diagram

```mermaid
classDiagram
    class WikiStatusManager {
        -__init__(wiki_path: Path)
        +file_hashes() dict[str, str]
        +file_line_info() dict[str, tuple[int, int]]
        +page_statuses() dict[str, WikiPageStatus]
        +previous_status() WikiGenerationStatus | None
        +load_status() WikiGenerationStatus | None
        -_read_status() WikiGenerationStatus | None
        +save_status(status: WikiGenerationStatus) None
        -_write_status() None
        +compute_content_hash(content: str) str
        +needs_regeneration(page_path: str, source_files: list[str]) bool
        +load_existing_page(page_path: str) WikiPage | None
        -_read_page() WikiPage | None
        +record_page_status(page: WikiPage, source_files: list[str]) None
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[Path]
    N1[WikiPage]
    N2[WikiPageStatus]
    N3[WikiStatusManager._read_page]
    N4[WikiStatusManager._read_status]
    N5[WikiStatusManager._write_st...]
    N6[WikiStatusManager.compute_c...]
    N7[WikiStatusManager.load_exis...]
    N8[WikiStatusManager.load_status]
    N9[WikiStatusManager.record_pa...]
    N10[WikiStatusManager.save_status]
    N11[compute_content_hash]
    N12[dump]
    N13[encode]
    N14[exists]
    N15[hexdigest]
    N16[load]
    N17[model_dump]
    N18[model_validate]
    N19[read_text]
    N20[sha256]
    N21[time]
    N22[title]
    N23[to_thread]
    N8 --> N14
    N8 --> N16
    N8 --> N18
    N8 --> N23
    N4 --> N16
    N4 --> N18
    N10 --> N17
    N10 --> N12
    N10 --> N23
    N5 --> N12
    N6 --> N15
    N6 --> N20
    N6 --> N13
    N7 --> N14
    N7 --> N22
    N7 --> N0
    N7 --> N21
    N7 --> N19
    N7 --> N1
    N7 --> N23
    N3 --> N19
    N3 --> N1
    N9 --> N2
    N9 --> N11
    classDef func fill:#e1f5fe
    class N0,N1,N2,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23 func
    classDef method fill:#fff3e0
    class N3,N4,N5,N6,N7,N8,N9,N10 method
```

## Used By

Functions and methods in this file and their callers:

- **`Path`**: called by `WikiStatusManager.load_existing_page`
- **[`WikiPage`](../models.md)**: called by `WikiStatusManager._read_page`, `WikiStatusManager.load_existing_page`
- **[`WikiPageStatus`](../models.md)**: called by `WikiStatusManager.record_page_status`
- **`compute_content_hash`**: called by `WikiStatusManager.record_page_status`
- **`dump`**: called by `WikiStatusManager._write_status`, `WikiStatusManager.save_status`
- **`encode`**: called by `WikiStatusManager.compute_content_hash`
- **`exists`**: called by `WikiStatusManager.load_existing_page`, `WikiStatusManager.load_status`
- **`hexdigest`**: called by `WikiStatusManager.compute_content_hash`
- **`load`**: called by `WikiStatusManager._read_status`, `WikiStatusManager.load_status`
- **`model_dump`**: called by `WikiStatusManager.save_status`
- **`model_validate`**: called by `WikiStatusManager._read_status`, `WikiStatusManager.load_status`
- **`read_text`**: called by `WikiStatusManager._read_page`, `WikiStatusManager.load_existing_page`
- **`sha256`**: called by `WikiStatusManager.compute_content_hash`
- **`time`**: called by `WikiStatusManager.load_existing_page`
- **`title`**: called by `WikiStatusManager.load_existing_page`
- **`to_thread`**: called by `WikiStatusManager.load_existing_page`, `WikiStatusManager.load_status`, `WikiStatusManager.save_status`

## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `WikiStatusManager` | class | Brian Breidenbach | yesterday | `39e8c73` Replace generic except Exce... |
| `load_status` | method | Brian Breidenbach | yesterday | `39e8c73` Replace generic except Exce... |
| `_read_status` | method | Brian Breidenbach | yesterday | `39e8c73` Replace generic except Exce... |
| `load_existing_page` | method | Brian Breidenbach | yesterday | `39e8c73` Replace generic except Exce... |
| `_read_page` | method | Brian Breidenbach | yesterday | `39e8c73` Replace generic except Exce... |
| `__init__` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `file_hashes` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `file_hashes` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `file_line_info` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `file_line_info` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `page_statuses` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `previous_status` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `save_status` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `_write_status` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `compute_content_hash` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `needs_regeneration` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |
| `record_page_status` | method | Brian Breidenbach | yesterday | `3defaaa` Refactor: Extract validatio... |

## Additional Source Code

Source code for functions and methods not listed in the API Reference above.

#### `file_hashes`

<details>
<summary>View Source (lines 41-43) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L41-L43">GitHub</a></summary>

```python
def file_hashes(self) -> dict[str, str]:
        """Get file hashes map."""
        return self._file_hashes
```

</details>


#### `file_line_info`

<details>
<summary>View Source (lines 51-53) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L51-L53">GitHub</a></summary>

```python
def file_line_info(self) -> dict[str, tuple[int, int]]:
        """Get file line info map."""
        return self._file_line_info
```

</details>


#### `_read_status`

<details>
<summary>View Source (lines 80-90) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L80-L90">GitHub</a></summary>

```python
def _read_status() -> WikiGenerationStatus | None:
            try:
                with open(status_path) as f:
                    data = json.load(f)
                return WikiGenerationStatus.model_validate(data)
            except (json.JSONDecodeError, OSError, ValueError) as e:
                # json.JSONDecodeError: Corrupted or invalid JSON
                # OSError: File read issues
                # ValueError: Pydantic validation failure
                logger.warning(f"Failed to load wiki status from {status_path}: {e}")
                return None
```

</details>


#### `_write_status`

<details>
<summary>View Source (lines 104-106) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L104-L106">GitHub</a></summary>

```python
def _write_status() -> None:
            with open(status_path, "w") as f:
                json.dump(data, f, indent=2)
```

</details>


#### `_read_page`

<details>
<summary>View Source (lines 176-189) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/wiki_status.py#L176-L189">GitHub</a></summary>

```python
def _read_page() -> WikiPage | None:
            try:
                content = full_path.read_text()
                return WikiPage(
                    path=page_path,
                    title=title,
                    content=content,
                    generated_at=generated_at,
                )
            except (OSError, UnicodeDecodeError) as e:
                # OSError: File read issues
                # UnicodeDecodeError: File encoding issues
                logger.warning(f"Failed to load existing page {page_path}: {e}")
                return None
```

</details>

## Relevant Source Files

- `src/local_deepwiki/generators/wiki_status.py:15-220`
