# Search Module Documentation

## File Overview

The search module provides functionality for generating search indexes from wiki pages. It processes [WikiPage](../models.md) objects to create searchable JSON indexes that can be used for client-side search functionality.

## Functions

### generate_search_index

Generates a search index from a list of wiki pages.

**Parameters:**
- `pages` (list[[WikiPage](../models.md)]): List of wiki pages to index

**Returns:**
- `list[dict]`: List of search entries

**Usage:**
```python
from local_deepwiki.generators.search import generate_search_index

# Generate search index from pages
index = generate_search_index(pages)
```

### write_search_index

Generates and writes a search index to disk as a JSON file.

**Parameters:**
- `wiki_path` (Path): Path to wiki directory where the search index will be written
- `pages` (list[[WikiPage](../models.md)]): List of wiki pages to index

**Returns:**
- `Path`: Path to the generated search.json file

**Usage:**
```python
from pathlib import Path
from local_deepwiki.generators.search import write_search_index

# Write search index to wiki directory
wiki_dir = Path("./wiki")
index_path = write_search_index(wiki_dir, pages)
print(f"Search index written to: {index_path}")
```

## Additional Functions

The module contains additional helper functions that are referenced but not shown in the provided code:
- `extract_headings`
- `extract_code_terms` 
- `extract_snippet`
- `generate_search_entry`

## Related Components

This module works with:
- **[WikiPage](../models.md)**: The core model class from `local_deepwiki.models` that represents individual wiki pages
- **Path**: From Python's pathlib for file system operations
- **JSON**: For serializing search index data

## Dependencies

- `json`: For JSON serialization
- `re`: For regular expression operations
- `pathlib.Path`: For file path handling
- [`local_deepwiki.models.WikiPage`](../models.md): Core wiki page model

## API Reference

### Functions

#### `extract_headings`

```python
def extract_headings(content: str) -> list[str]
```

Extract all headings from markdown content.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | Markdown content. |

**Returns:** `list[str]`


#### `extract_code_terms`

```python
def extract_code_terms(content: str) -> list[str]
```

Extract code terms (class names, function names) from content.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | Markdown content. |

**Returns:** `list[str]`


#### `extract_snippet`

```python
def extract_snippet(content: str, max_length: int = 200) -> str
```

Extract a text snippet from markdown content.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `str` | - | Markdown content. |
| `max_length` | `int` | `200` | Maximum snippet length. |

**Returns:** `str`


#### `generate_search_entry`

```python
def generate_search_entry(page: WikiPage) -> dict
```

Generate a search index entry for a wiki page.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | [`WikiPage`](../models.md) | - | The wiki page. |

**Returns:** `dict`


#### `generate_search_index`

```python
def generate_search_index(pages: list[WikiPage]) -> list[dict]
```

Generate a search index from wiki pages.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `pages` | `list[WikiPage]` | - | List of wiki pages. |

**Returns:** `list[dict]`


#### `write_search_index`

```python
def write_search_index(wiki_path: Path, pages: list[WikiPage]) -> Path
```

Generate and write search index to disk.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `wiki_path` | `Path` | - | Path to wiki directory. |
| `pages` | `list[WikiPage]` | - | List of wiki pages. |

**Returns:** `Path`



## Call Graph

```mermaid
flowchart TD
    N0[add]
    N1[dumps]
    N2[extract_code_terms]
    N3[extract_headings]
    N4[extract_snippet]
    N5[finditer]
    N6[generate_search_entry]
    N7[generate_search_index]
    N8[group]
    N9[rsplit]
    N10[sub]
    N11[write_search_index]
    N12[write_text]
    N3 --> N10
    N2 --> N5
    N2 --> N8
    N2 --> N0
    N4 --> N10
    N4 --> N9
    N6 --> N3
    N6 --> N2
    N6 --> N4
    N7 --> N6
    N11 --> N7
    N11 --> N12
    N11 --> N1
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12 func
```

## Usage Examples

*Examples extracted from test files*

### Test extraction of h1 headings

From `test_search.py::test_extracts_h1_headings`:

```python
headings = extract_headings(content)
assert "Main Title" in headings
```

### Test extraction of h1, h2, h3 headings

From `test_search.py::test_extracts_multiple_heading_levels`:

```python
headings = extract_headings(content)
assert len(headings) == 4
```

### Test extraction of simple backticked terms

From `test_search.py::test_extracts_simple_terms`:

```python
terms = extract_code_terms(content)
assert "VectorStore" in terms
```

### Test extraction of qualified names

From `test_search.py::test_extracts_qualified_names`:

```python
terms = extract_code_terms(content)
# Should include both full qualified name and last part
assert "VectorStore" in terms
```

### Test basic snippet extraction

From `test_search.py::test_extracts_plain_text`:

```python
snippet = extract_snippet(content)
assert "simple paragraph" in snippet
```

## Relevant Source Files

- `src/local_deepwiki/generators/search.py:14-33`

## See Also

- [wiki](wiki.md) - uses this
- [test_search](../../../tests/test_search.md) - uses this
- [models](../models.md) - dependency
- [crosslinks](crosslinks.md) - shares 3 dependencies
- [diagrams](diagrams.md) - shares 3 dependencies
