# File Overview

This file provides a core parser implementation for source code analysis using the Tree-sitter library. It supports multiple programming languages and provides functionality to parse source code into Abstract Syntax Trees (ASTs), extract text content from nodes, and identify programming languages based on file extensions.

# Classes

## CodeParser

The CodeParser class is responsible for managing parsers for different programming languages and provides methods to parse source code and files into ASTs.

### Methods

#### `__init__`

Initialize the parser with language support.

#### `_get_parser`

Get or create a parser for the given language.

- **Parameters**:
  - `language` (LangEnum): The programming language.
- **Returns**:
  - A tree-sitter Parser configured for the language.

#### `detect_language`

Detect the programming language based on a file path.

- **Parameters**:
  - `file_path` (Path): Path to the source file.
- **Returns**:
  - The detected programming language (LangEnum) or None if not supported.

#### `parse_file`

Parse a source file and return the AST root.

- **Parameters**:
  - `file_path` (Path): Path to the source file.
- **Returns**:
  - Tuple of (AST root node, language, source bytes) or None if not supported.

#### `parse_source`

Parse source code string and return the AST root.

- **Parameters**:
  - `source` (str | bytes): The source code.
  - `language` (LangEnum): The programming language.
- **Returns**:
  - The AST root node.

#### `get_file_info`

Extract file information including language, hash, and content.

- **Parameters**:
  - `file_path` (Path): Path to the source file.
- **Returns**:
  - FileInfo object containing language, hash, and content.

# Functions

## get_node_text

Extract text content from a tree-sitter node.

- **Parameters**:
  - `node` (Node): The tree-sitter node.
  - `source` (bytes): The original source bytes.
- **Returns**:
  - The text content of the node.

## find_nodes_by_type

Find all nodes of a given type in the AST.

- **Parameters**:
  - `node` (Node): The tree-sitter node to search from.
  - `node_type` (str): The type of node to [find](../generators/manifest.md).
- **Returns**:
  - List of matching nodes.

## walk

Walk through the AST and yield nodes.

- **Parameters**:
  - `node` (Node): The tree-sitter node to start walking from.
- **Yields**:
  - Each node in the AST in a depth-first manner.

## get_node_name

Extract the name of a node.

- **Parameters**:
  - `node` (Node): The tree-sitter node.
- **Returns**:
  - The name of the node as a string or None if not found.

## get_docstring

Extract docstring from a function/class node.

- **Parameters**:
  - `node` (Node): The tree-sitter node.
  - `source` (bytes): The original source bytes.
  - `language` (LangEnum): The programming language.
- **Returns**:
  - The docstring or None if not found.

# Usage Examples

## Initialize a parser

```python
from local_deepwiki.core.parser import CodeParser

parser = CodeParser()
```

## Parse source code

```python
from local_deepwiki.models import Language as LangEnum

source_code = "def hello():\n    return 'world'"
ast_root = parser.parse_source(source_code, LangEnum.PYTHON)
```

## Parse a file

```python
from pathlib import Path

file_path = Path("example.py")
result = parser.parse_file(file_path)
if result:
    ast_root, language, source_bytes = result
```

## Extract text from a node

```python
node_text = get_node_text(ast_root, source_bytes)
```

# Related Components

This file depends on:

- `tree_sitter` library for AST parsing
- `tree_sitter_*` modules for specific language support
- `local_deepwiki.models.Language` (LangEnum) for language enumeration
- `FileInfo` model for file information handling

The CodeParser class works with Tree-sitter's Node, Parser, and Language classes to provide language-specific parsing capabilities.

## API Reference

### class `CodeParser`

Multi-language code parser using tree-sitter.

**Methods:**

#### `__init__`

```python
def __init__()
```

Initialize the parser with language support.

#### `detect_language`

```python
def detect_language(file_path: Path) -> LangEnum | None
```

Detect the programming language from file extension.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to the source file. |

#### `parse_file`

```python
def parse_file(file_path: Path) -> tuple[Node, LangEnum, bytes] | None
```

Parse a source file and return the AST root.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to the source file. |

#### `parse_source`

```python
def parse_source(source: str | bytes, language: LangEnum) -> Node
```

Parse source code string and return the AST root.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | `str | bytes` | - | The source code. |
| `language` | `LangEnum` | - | The programming language. |

#### `get_file_info`

```python
def get_file_info(file_path: Path, repo_root: Path) -> FileInfo
```

Get information about a source file.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Absolute path to the file. |
| `repo_root` | `Path` | - | Root directory of the repository. |


---

### Functions

#### `get_node_text`

```python
def get_node_text(node: Node, source: bytes) -> str
```

Extract text content from a tree-sitter node.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | - | The tree-sitter node. |
| `source` | `bytes` | - | The original source bytes. |

**Returns:** `str`


#### `find_nodes_by_type`

```python
def find_nodes_by_type(root: Node, node_types: set[str]) -> list[Node]
```

Find all nodes of specified types in the AST.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `root` | `Node` | - | The root node to search from. |
| `node_types` | `set[str]` | - | Set of node type names to [find](../generators/manifest.md). |

**Returns:** `list[Node]`


#### `walk`

```python
def walk(node: Node)
```


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | - | - |


#### `get_node_name`

```python
def get_node_name(node: Node, source: bytes, language: LangEnum) -> str | None
```

Extract the name from a function/class/method node.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | - | The tree-sitter node. |
| `source` | `bytes` | - | The original source bytes. |
| `language` | `LangEnum` | - | The programming language. |

**Returns:** `str | None`


#### `get_docstring`

```python
def get_docstring(node: Node, source: bytes, language: LangEnum) -> str | None
```

Extract docstring from a function/class node.


| [Parameter](../generators/api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | - | The tree-sitter node. |
| `source` | `bytes` | - | The original source bytes. |
| `language` | `LangEnum` | - | The programming language. |

**Returns:** `str | None`



## Class Diagram

```mermaid
classDiagram
    class CodeParser {
        -__init__()
        -_get_parser()
        +detect_language()
        +parse_file()
        +parse_source()
        +get_file_info()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[CodeParser._get_parser]
    N1[CodeParser.get_file_info]
    N2[CodeParser.parse_file]
    N3[CodeParser.parse_source]
    N4[FileInfo]
    N5[Language]
    N6[Parser]
    N7[ValueError]
    N8[_get_parser]
    N9[child_by_field_name]
    N10[decode]
    N11[detect_language]
    N12[encode]
    N13[find_nodes_by_type]
    N14[get_docstring]
    N15[get_node_name]
    N16[get_node_text]
    N17[hexdigest]
    N18[language]
    N19[language_php]
    N20[lstrip]
    N21[parse]
    N22[read_bytes]
    N23[relative_to]
    N24[rstrip]
    N25[sha256]
    N26[stat]
    N27[walk]
    N16 --> N10
    N13 --> N27
    N27 --> N27
    N15 --> N16
    N15 --> N9
    N14 --> N9
    N14 --> N16
    N14 --> N24
    N14 --> N20
    N0 --> N7
    N0 --> N5
    N0 --> N19
    N0 --> N18
    N0 --> N6
    N2 --> N11
    N2 --> N22
    N2 --> N8
    N2 --> N21
    N3 --> N12
    N3 --> N8
    N3 --> N21
    N1 --> N26
    N1 --> N22
    N1 --> N4
    N1 --> N23
    N1 --> N11
    N1 --> N17
    N1 --> N25
    classDef func fill:#e1f5fe
    class N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27 func
    classDef method fill:#fff3e0
    class N0,N1,N2,N3 method
```

## Relevant Source Files

- `src/local_deepwiki/core/parser.py:69-173`

## See Also

- [api_docs](../generators/api_docs.md) - uses this
- [chunker](chunker.md) - uses this
- [test_api_docs](../../../tests/test_api_docs.md) - uses this
- [wiki](../generators/wiki.md) - shares 4 dependencies
- [diagrams](../generators/diagrams.md) - shares 3 dependencies
