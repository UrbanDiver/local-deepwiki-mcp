# File Overview

This file, `see_also.py`, is part of the `local_deepwiki` package and provides functionality for generating "See Also" sections in wiki pages. It helps establish relationships between source files and their corresponding wiki documentation by mapping file paths and analyzing dependencies to suggest related content.

The module includes utilities for building mappings from source files to wiki pages, generating see-also content, and adding these sections to wiki pages.

# Classes

## FileRelationships

A dataclass used to store information about file relationships.

### Fields

- `source_file` (str): The path of the source file.
- `wiki_page` (str): The corresponding wiki page path.
- `related_files` (list[str]): A list of related file paths.

## RelationshipAnalyzer

A class responsible for analyzing relationships between source files and wiki pages.

### Methods

- `analyze()` → `dict[str, list[str]]`: Analyzes the relationships and returns a dictionary mapping source files to lists of related files.

# Functions

## build_file_to_wiki_map

```python
def build_file_to_wiki_map(pages: list[WikiPage]) -> dict[str, str]:
```

Builds a mapping from source file paths to wiki page paths.

### Parameters

- `pages` (list[WikiPage]): A list of wiki pages to process.

### Returns

- `dict[str, str]`: A dictionary mapping source file paths to wiki page paths.

## generate_see_also_section

```python
def generate_see_also_section(related_files: list[str]) -> str:
```

Generates a formatted "See Also" section for a wiki page based on a list of related files.

### Parameters

- `related_files` (list[str]): A list of file paths related to the current page.

### Returns

- `str`: A formatted markdown string representing the "See Also" section.

## _relative_path

```python
def _relative_path(file_path: str, base_path: str) -> str:
```

Computes the relative path of a file with respect to a base path.

### Parameters

- `file_path` (str): The absolute or full file path.
- `base_path` (str): The base path to compute the relative path from.

### Returns

- `str`: The relative path of `file_path` with respect to `base_path`.

## add_see_also_sections

```python
def add_see_also_sections(wiki_pages: list[WikiPage], file_to_wiki_map: dict[str, str]) -> None:
```

Adds "See Also" sections to the content of wiki pages based on the file-to-wiki mapping.

### Parameters

- `wiki_pages` (list[WikiPage]): A list of wiki pages to update.
- `file_to_wiki_map` (dict[str, str]): A mapping from source file paths to wiki page paths.

### Returns

- `None`: This function modifies the wiki pages in place.

# Usage Examples

## Building a File-to-Wiki Map

```python
from local_deepwiki.generators.see_also import build_file_to_wiki_map
from local_deepwiki.models import WikiPage

pages = [WikiPage(path="files/src/local_deepwiki/core/chunker.md", content="...")]
file_to_wiki_map = build_file_to_wiki_map(pages)
```

## Generating a See Also Section

```python
from local_deepwiki.generators.see_also import generate_see_also_section

related_files = ["src/local_deepwiki/core/chunker.py", "src/local_deepwiki/core/parser.py"]
section = generate_see_also_section(related_files)
```

## Adding See Also Sections to Wiki Pages

```python
from local_deepwiki.generators.see_also import add_see_also_sections
from local_deepwiki.models import WikiPage

wiki_pages = [WikiPage(path="files/src/local_deepwiki/core/chunker.md", content="...")]
file_to_wiki_map = {"src/local_deepwiki/core/chunker.py": "files/src/local_deepwiki/core/chunker.md"}

add_see_also_sections(wiki_pages, file_to_wiki_map)
```

# Related Components

This module interacts with the following components:

- `WikiPage` from `local_deepwiki.models`: Represents a wiki page with a path and content.
- `ChunkType` and `CodeChunk` from `local_deepwiki.models`: Used for handling code chunks and their types, although not directly used in this file.
- `Path` from `pathlib`: Used for handling file paths.
- `re`: Used for regular expressions, although not directly used in this file.

## API Reference

### class `FileRelationships`

Relationships for a single file.

### class `RelationshipAnalyzer`

Analyzes import relationships between source files.  This class builds a graph of file dependencies from import chunks, enabling discovery of related files through various relationship types.

**Methods:**

#### `__init__`

```python
def __init__() -> None
```

Initialize an empty relationship analyzer.

#### `analyze_chunks`

```python
def analyze_chunks(chunks: list[CodeChunk]) -> None
```

Analyze import chunks to build relationship graph.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `chunks` | `list[CodeChunk]` | - | List of code chunks (should include IMPORT chunks). |

#### `get_relationships`

```python
def get_relationships(file_path: str) -> FileRelationships
```

Get all relationships for a file.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | - | Path to the source file. |

#### `get_all_known_files`

```python
def get_all_known_files() -> set[str]
```

Get all known file paths.


---

### Functions

#### `build_file_to_wiki_map`

```python
def build_file_to_wiki_map(pages: list[WikiPage]) -> dict[str, str]
```

Build a mapping from source file paths to wiki page paths.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `pages` | `list[WikiPage]` | - | List of wiki pages. |

**Returns:** `dict[str, str]`


#### `generate_see_also_section`

```python
def generate_see_also_section(relationships: FileRelationships, file_to_wiki: dict[str, str], current_wiki_path: str, max_items: int = 5) -> str | None
```

Generate a See Also section for a wiki page.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `relationships` | `FileRelationships` | - | The file relationships. |
| `file_to_wiki` | `dict[str, str]` | - | Mapping of source files to wiki paths. |
| `current_wiki_path` | `str` | - | Path of the current wiki page. |
| `max_items` | `int` | `5` | Maximum number of items to include. |

**Returns:** `str | None`


#### `add_see_also_sections`

```python
def add_see_also_sections(pages: list[WikiPage], analyzer: RelationshipAnalyzer) -> list[WikiPage]
```

Add See Also sections to wiki pages.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `pages` | `list[WikiPage]` | - | List of wiki pages. |
| `analyzer` | `RelationshipAnalyzer` | - | Relationship analyzer with import data. |

**Returns:** `list[WikiPage]`



## Class Diagram

```mermaid
classDiagram
    class RelationshipAnalyzer {
        -__init__()
        +analyze_chunks()
        -_parse_import_line()
        -_module_to_file_path()
        +get_relationships()
        -_module_matches_file()
        +get_all_known_files()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[FileRelationships]
    N1[Path]
    N2[RelationshipAnalyzer.__init__]
    N3[RelationshipAnalyzer._modul...]
    N4[RelationshipAnalyzer.analyz...]
    N5[RelationshipAnalyzer.get_al...]
    N6[RelationshipAnalyzer.get_re...]
    N7[WikiPage]
    N8[_module_matches_file]
    N9[_module_to_file_path]
    N10[_parse_import_line]
    N11[_relative_path]
    N12[add]
    N13[add_see_also_sections]
    N14[build_file_to_wiki_map]
    N15[copy]
    N16[defaultdict]
    N17[generate_see_also_section]
    N18[get_relationships]
    N19[rstrip]
    N20[sub]
    N21[with_suffix]
    N14 --> N20
    N17 --> N1
    N17 --> N12
    N17 --> N11
    N11 --> N1
    N13 --> N14
    N13 --> N20
    N13 --> N18
    N13 --> N17
    N13 --> N19
    N13 --> N7
    N2 --> N16
    N4 --> N12
    N4 --> N10
    N6 --> N0
    N6 --> N9
    N6 --> N12
    N6 --> N8
    N3 --> N21
    N3 --> N1
    N5 --> N15
    classDef func fill:#e1f5fe
    class N0,N1,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21 func
    classDef method fill:#fff3e0
    class N2,N3,N4,N5,N6 method
```

## Relevant Source Files

- `src/local_deepwiki/generators/see_also.py:16-22`

## See Also

- [wiki](wiki.md) - uses this
- [crosslinks](crosslinks.md) - shares 4 dependencies
- [diagrams](diagrams.md) - shares 4 dependencies
- [api_docs](api_docs.md) - shares 4 dependencies
