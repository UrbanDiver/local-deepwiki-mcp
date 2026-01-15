# See Also Generator

## File Overview

The `see_also.py` module provides functionality for analyzing relationships between source files and generating "See Also" sections for wiki pages. It builds mappings between source files and their corresponding wiki pages, then adds cross-references to related files based on code relationships.

## Classes

### FileRelationships

A data class that stores relationship information for a source file.

### RelationshipAnalyzer  

Analyzes code relationships between files to determine which files should be cross-referenced in "See Also" sections.

## Functions

### build_file_to_wiki_map

```python
def build_file_to_wiki_map(pages: list[WikiPage]) -> dict[str, str]
```

Builds a mapping from source file paths to wiki page paths.

**Parameters:**
- `pages`: List of [WikiPage](../models.md) objects to process

**Returns:**
- Dictionary mapping source file path to wiki page path

The function processes wiki pages with paths starting with "files/" and maps them to their corresponding source files by removing the "files/" prefix and changing the .md extension to .py.

### generate_see_also_section

Generates a "See Also" section for a wiki page based on file relationships.

### _relative_path

A helper function for calculating relative paths between files.

### add_see_also_sections

Adds "See Also" sections to multiple wiki pages based on analyzed relationships.

## Related Components

This module works with the following components from the codebase:

- **[WikiPage](../models.md)**: The [main](../export/html.md) page model used for storing wiki content and metadata
- **[CodeChunk](../models.md)**: Represents chunks of code with type information
- **[ChunkType](../models.md)**: Enumeration defining different types of code chunks

The module uses these models to analyze code structure and generate appropriate cross-references between related files in the wiki documentation.

## Usage Context

This module is part of the wiki generation pipeline, specifically handling the cross-referencing aspect by analyzing how files relate to each other through imports, class usage, and other code relationships, then adding appropriate "See Also" sections to help users navigate between related documentation pages.

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
    class FileRelationships {
        +file_path: str
        +imports: set[str]
        +imported_by: set[str]
        +shared_deps_with: dict[str, int]
    }
    class RelationshipAnalyzer {
        -__init__() None
        +analyze_chunks(chunks: list[CodeChunk]) None
        -_parse_import_line(line: str) str | None
        -_module_to_file_path(module: str) str | None
        +get_relationships(file_path: str) FileRelationships
        -_module_matches_file(module: str, file_path: str) bool
        +get_all_known_files() set[str]
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

## Usage Examples

*Examples extracted from test files*

### Test analyzing Python import statements

From `test_see_also.py::test_analyze_python_imports`:

```python
name="imports",
        content="from local_deepwiki.core.chunker import CodeChunker\nfrom local_deepwiki.models import CodeChunk",
        start_line=1,
        end_line=2,
    ),
    CodeChunk(
        id="2",
        file_path="src/local_deepwiki/core/chunker.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.IMPORT,
        name="imports",
        content="from local_deepwiki.models import CodeChunk",
        start_line=1,
        end_line=1,
    ),
]

analyzer.analyze_chunks(chunks)

# Check that files are tracked
known_files = analyzer.get_all_known_files()
assert "src/local_deepwiki/core/indexer.py" in known_files
```

### Test analyzing Python import statements

From `test_see_also.py::test_analyze_python_imports`:

```python
analyzer = RelationshipAnalyzer()
chunks = [
    CodeChunk(
        id="1",
        file_path="src/local_deepwiki/core/indexer.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.IMPORT,
        name="imports",
        content="from local_deepwiki.core.chunker import CodeChunker\nfrom local_deepwiki.models import CodeChunk",
        start_line=1,
        end_line=2,
    ),
    CodeChunk(
        id="2",
        file_path="src/local_deepwiki/core/chunker.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.IMPORT,
        name="imports",
        content="from local_deepwiki.models import CodeChunk",
        start_line=1,
        end_line=1,
    ),
]

analyzer.analyze_chunks(chunks)
```

### Test analyzing Python import statements

From `test_see_also.py::test_analyze_python_imports`:

```python
analyzer.analyze_chunks(chunks)

# Check that files are tracked
known_files = analyzer.get_all_known_files()
assert "src/local_deepwiki/core/indexer.py" in known_files
```

### Test analyzing Python import statements

From `test_see_also.py::test_analyze_python_imports`:

```python
known_files = analyzer.get_all_known_files()
assert "src/local_deepwiki/core/indexer.py" in known_files
```

### Test getting import relationships for a file

From `test_see_also.py::test_get_relationships_imports`:

```python
name="imports",
        content="from local_deepwiki.core.chunker import CodeChunker",
        start_line=1,
        end_line=1,
    ),
    CodeChunk(
        id="2",
        file_path="src/local_deepwiki/core/chunker.py",
        language=Language.PYTHON,
        chunk_type=ChunkType.IMPORT,
        name="imports",
        content="from local_deepwiki.models import CodeChunk",
        start_line=1,
        end_line=1,
    ),
]

analyzer.analyze_chunks(chunks)
relationships = analyzer.get_relationships("src/local_deepwiki/core/indexer.py")

assert isinstance(relationships, FileRelationships)
```

## Relevant Source Files

- `src/local_deepwiki/generators/see_also.py:16-22`

## See Also

- [test_see_also](../../../tests/test_see_also.md) - uses this
- [wiki](wiki.md) - uses this
- [models](../models.md) - dependency
- [crosslinks](crosslinks.md) - shares 4 dependencies
- [diagrams](diagrams.md) - shares 4 dependencies
