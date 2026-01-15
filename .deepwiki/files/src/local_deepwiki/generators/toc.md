# Table of Contents Generator

## File Overview

The `toc.py` module provides functionality for generating, reading, and writing hierarchical table of contents structures for wiki documentation. It creates numbered sections and subsections from a list of wiki pages, with support for JSON serialization and deserialization.

## Classes

### TocEntry

A single entry in the table of contents that represents a page or section with hierarchical numbering.

**Attributes:**
- `number`: String representation of the section number (e.g., "1.2.3")
- `title`: Display title of the entry
- `path`: File path to the associated page
- `children`: List of child TocEntry objects for nested sections

**Methods:**
- `to_dict()`: Converts the entry to a dictionary format suitable for JSON serialization, including all children recursively

### TableOfContents

Container class that holds the complete hierarchical table of contents structure.

**Attributes:**
- `entries`: List of root-level TocEntry objects

**Methods:**
- `to_dict()`: Converts the entire table of contents to a dictionary format
- `to_json(indent=2)`: Serializes the table of contents to a JSON string with optional indentation
- `from_dict(data)`: Class method that creates a TableOfContents instance from a dictionary

## Functions

### generate_toc

```python
def generate_toc(pages: list[dict[str, str]]) -> TableOfContents
```

Generates a hierarchical numbered table of contents from a list of wiki pages.

**Parameters:**
- `pages`: List of dictionaries, each containing 'path' and 'title' keys

**Returns:**
- TableOfContents object with numbered entries organized hierarchically

The function follows a predefined ordering system with root pages like "index.md", "architecture.md", and "dependencies.md" appearing first, followed by organized sections for "modules" and "files".

### write_toc

```python
def write_toc(toc: TableOfContents, wiki_path: Path) -> None
```

Writes a table of contents to a `toc.json` file in the specified wiki directory.

**Parameters:**
- `toc`: The TableOfContents object to write
- `wiki_path`: Path to the wiki directory where the file will be created

### read_toc

```python
def read_toc(wiki_path: Path) -> TableOfContents | None
```

Reads a table of contents from a `toc.json` file in the wiki directory.

**Parameters:**
- `wiki_path`: Path to the wiki directory containing the toc.json file

**Returns:**
- TableOfContents object if the file exists and is valid, None otherwise

The function handles missing files and JSON parsing errors gracefully by returning None.

## Usage Examples

### Creating a Table of Contents

```python
from pathlib import Path

# Generate TOC from page data
pages = [
    {"path": "index.md", "title": "Overview"},
    {"path": "modules/example.md", "title": "Example Module"}
]
toc = generate_toc(pages)

# Write to file
wiki_path = Path("./wiki")
write_toc(toc, wiki_path)
```

### Reading an Existing Table of Contents

```python
# Read TOC from file
toc = read_toc(Path("./wiki"))
if toc:
    print(toc.to_json())
```

### Working with TOC Entries

```python
# Create a manual entry
entry = TocEntry(
    number="1.1",
    title="Getting Started",
    path="getting-started.md",
    children=[]
)

# Convert to dictionary
entry_dict = entry.to_dict()
```

## Related Components

This module works with:
- `json` module for serialization
- `pathlib.Path` for file system operations
- `dataclasses` for the class definitions

The module is designed to integrate with wiki generation systems that provide page lists with path and title information.

## API Reference

### class `TocEntry`

A single entry in the table of contents.

**Methods:**

#### `to_dict`

```python
def to_dict() -> dict[str, Any]
```

Convert to dictionary for JSON serialization.


### class `TableOfContents`

Hierarchical table of contents with numbered sections.

**Methods:**

#### `to_dict`

```python
def to_dict() -> dict[str, Any]
```

Convert to dictionary for JSON serialization.

#### `to_json`

```python
def to_json(indent: int = 2) -> str
```

Convert to JSON string.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `indent` | `int` | `2` | - |

#### `from_dict`

```python
def from_dict(data: dict[str, Any]) -> "TableOfContents"
```

Create from dictionary.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `dict[str, Any]` | - | - |

#### `parse_entry`

```python
def parse_entry(entry_data: dict[str, Any]) -> TocEntry
```


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `entry_data` | `dict[str, Any]` | - | - |

#### `from_json`

```python
def from_json(json_str: str) -> "TableOfContents"
```

Create from JSON string.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `json_str` | `str` | - | - |


---

### Functions

#### `generate_toc`

```python
def generate_toc(pages: list[dict[str, str]]) -> TableOfContents
```

Generate hierarchical numbered table of contents from wiki pages.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `pages` | `list[dict[str, str]]` | - | List of dicts with 'path' and 'title' keys. |

**Returns:** `TableOfContents`


#### `write_toc`

```python
def write_toc(toc: TableOfContents, wiki_path: Path) -> None
```

Write table of contents to toc.json file.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `toc` | `TableOfContents` | - | The TableOfContents to write. |
| `wiki_path` | `Path` | - | Path to the wiki directory. |

**Returns:** `None`


#### `read_toc`

```python
def read_toc(wiki_path: Path) -> TableOfContents | None
```

Read table of contents from toc.json file.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | Path to the wiki directory. |

**Returns:** `TableOfContents | None`



## Class Diagram

```mermaid
classDiagram
    class TableOfContents {
        +entries: list[TocEntry]
        +to_dict() -> dict[str, Any]
        +to_json() -> str
        +from_dict() -> "TableOfContents"
        +parse_entry() -> TocEntry
        +from_json() -> "TableOfContents"
    }
    class TocEntry {
        +number: str
        +title: str
        +path: str
        +children: list["TocEntry"]
        +to_dict() -> dict[str, Any]
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[Path]
    N1[TableOfContents]
    N2[TableOfContents.from_dict]
    N3[TableOfContents.from_json]
    N4[TableOfContents.parse_entry]
    N5[TableOfContents.to_dict]
    N6[TableOfContents.to_json]
    N7[TocEntry]
    N8[TocEntry.to_dict]
    N9[_build_section_tree]
    N10[_tree_to_entries]
    N11[cls]
    N12[dumps]
    N13[exists]
    N14[from_dict]
    N15[from_json]
    N16[generate_toc]
    N17[loads]
    N18[parse_entry]
    N19[read_text]
    N20[read_toc]
    N21[title]
    N22[to_dict]
    N23[to_json]
    N24[write_text]
    N25[write_toc]
    N16 --> N7
    N16 --> N0
    N16 --> N9
    N16 --> N1
    N9 --> N21
    N9 --> N0
    N9 --> N10
    N9 --> N7
    N10 --> N7
    N10 --> N0
    N10 --> N10
    N10 --> N21
    N25 --> N24
    N25 --> N23
    N20 --> N13
    N20 --> N15
    N20 --> N19
    N8 --> N22
    N5 --> N22
    N6 --> N12
    N6 --> N22
    N2 --> N18
    N2 --> N7
    N2 --> N11
    N4 --> N18
    N4 --> N7
    N3 --> N14
    N3 --> N17
    classDef func fill:#e1f5fe
    class N0,N1,N7,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25 func
    classDef method fill:#fff3e0
    class N2,N3,N4,N5,N6,N8 method
```

## Usage Examples

*Examples extracted from test files*

### Example: `TocEntry`

From `test_toc.py::test_to_dict_simple`:

```python
entry = TocEntry(number="1", title="Overview", path="index.md")
        result = entry.to_dict()
        assert result == {
```

### Example: `TocEntry`

From `test_toc.py::test_to_dict_with_children`:

```python
child = TocEntry(number="1.1", title="Getting Started", path="start.md")
        entry = TocEntry(
            number="1",
            title="Overview",
            path="index.md",
            children=[child],
        )
        result = entry.to_dict()
        assert result == {
```

### Example: `toc`

From `test_toc.py::test_to_json`:

```python
toc = TableOfContents(entries=[entry])
json_str = toc.to_json()
data = json.loads(json_str)
assert data == {"entries": [{"number": "1", "title": "Overview", "path": "index.md"}]}
```

### Example: `TableOfContents`

From `test_toc.py::test_to_json`:

```python
toc = TableOfContents(entries=[entry])
json_str = toc.to_json()
data = json.loads(json_str)
assert data == {"entries": [{"number": "1", "title": "Overview", "path": "index.md"}]}
```

### Example: `toc`

From `test_toc.py::test_from_dict`:

```python
toc = TableOfContents.from_dict(data)
assert len(toc.entries) == 1
```

## Relevant Source Files

- `src/local_deepwiki/generators/toc.py:10-27`

## See Also

- [diagrams](diagrams.md) - shares 3 dependencies
- [vectorstore](../core/vectorstore.md) - shares 3 dependencies
- [models](../models.md) - shares 3 dependencies
