# Parser Module

## File Overview

The `parser.py` module provides source code parsing capabilities using tree-sitter parsers for multiple programming languages. It handles AST generation, language detection, and docstring extraction from source code files.

## Classes

### CodeParser

The CodeParser class manages tree-sitter parsers for different programming languages and provides methods to parse source code into Abstract Syntax Trees (ASTs).

**Key Methods:**

- **`__init__`**: Initializes the parser with empty dictionaries for parsers and languages
- **`_get_parser`**: Gets or creates a parser for a specific language, handling language-specific module loading
- **`parse_source`**: Parses source code strings/bytes and returns the AST root node
- **`parse_file`**: Parses source code files (method signature visible in class definition)
- **`detect_language`**: Detects programming language from file content (method signature visible in class definition)
- **`get_file_info`**: Retrieves file information including parsing metadata (method signature visible in class definition)

## Functions

### Core Parsing Functions

#### `parse_source`
```python
def parse_source(self, source: str | bytes, language: LangEnum) -> Node:
```
Parses source code and returns the AST root node.

**Parameters:**
- `source`: The source code as string or bytes
- `language`: The programming language enum value

**Returns:** The AST root node

#### `get_docstring`
```python
def get_docstring(node: Node, source: bytes, language: LangEnum) -> str | None:
```
Extracts docstrings from function or class nodes.

**Parameters:**
- `node`: The tree-sitter node
- `source`: The original source bytes
- `language`: The programming language enum

**Returns:** The extracted docstring or None if not found

### Docstring Extraction Functions

#### `_get_jsdoc_or_line_comments`
```python
def _get_jsdoc_or_line_comments(node: Node, source: bytes) -> str | None:
```
Extracts JSDoc (`/** */`) comments or multi-line `//` comments from JavaScript/TypeScript code.

**Parameters:**
- `node`: The tree-sitter node
- `source`: The source bytes

**Returns:** Extracted comment text or None

#### `_get_javadoc_or_doxygen`
```python
def _get_javadoc_or_doxygen(node: Node, source: bytes) -> str | None:
```
Extracts Javadoc/Doxygen (`/** */`) or `///` comments from Java/C++ code.

**Parameters:**
- `node`: The tree-sitter node  
- `source`: The source bytes

**Returns:** Extracted comment text or None

### Utility Functions

The module also includes several utility functions for AST manipulation:
- `_read_file_content`: Reads file content
- `_compute_file_hash`: Computes file hashes
- `get_node_text`: Extracts text from nodes
- `find_nodes_by_type`: Finds nodes by type
- `walk`: Walks AST nodes
- `get_node_name`: Gets node names
- `_collect_preceding_comments`: Collects comments before nodes
- `_strip_line_comment_prefix`: Strips comment prefixes
- `_get_python_docstring`: Extracts Python docstrings
- `_get_line_comments`: Gets line comments
- `_get_swift_docstring`: Extracts Swift docstrings
- `_get_block_comment`: Gets block comments

## Usage Examples

### Basic Source Parsing

```python
from local_deepwiki.core.parser import CodeParser
from local_deepwiki.core.types import LangEnum

# Initialize parser
parser = CodeParser()

# Parse source code
source_code = "def hello():\n    pass"
ast_root = parser.parse_source(source_code, LangEnum.PYTHON)
```

### Docstring Extraction

```python
# Extract docstring from a node
docstring = get_docstring(function_node, source_bytes, LangEnum.PYTHON)
if docstring:
    print(f"Found docstring: {docstring}")
```

## Related Components

This module works with several other components:

- **Language Support**: Imports multiple tree-sitter language modules (tree_sitter_c, tree_sitter_python, tree_sitter_javascript, etc.)
- **Type System**: Uses `LangEnum` for language enumeration and `Node` types from tree-sitter
- **File Handling**: Integrates with `pathlib.Path` for file operations
- **Memory Management**: Uses `mmap` for efficient file reading

The parser serves as a foundational component for code analysis and documentation generation workflows.

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


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to the source file. |

#### `parse_file`

```python
def parse_file(file_path: Path) -> tuple[Node, LangEnum, bytes] | None
```

Parse a source file and return the AST root.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to the source file. |

#### `parse_source`

```python
def parse_source(source: str | bytes, language: LangEnum) -> Node
```

Parse source code string and return the AST root.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | `str | bytes` | - | The source code. |
| `language` | `LangEnum` | - | The programming language. |

#### `get_file_info`

```python
def get_file_info(file_path: Path, repo_root: Path) -> FileInfo
```

Get information about a source file.  Uses chunked reading for large files to avoid loading the entire file into memory just for hash computation.


| Parameter | Type | Default | Description |
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


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | - | The tree-sitter node. |
| `source` | `bytes` | - | The original source bytes. |

**Returns:** `str`


#### `find_nodes_by_type`

```python
def find_nodes_by_type(root: Node, node_types: set[str]) -> list[Node]
```

Find all nodes of specified types in the AST.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `root` | `Node` | - | The root node to search from. |
| `node_types` | `set[str]` | - | Set of node type names to [find](../generators/manifest.md). |

**Returns:** `list[Node]`


#### `walk`

```python
def walk(node: Node)
```


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | - | - |


#### `get_node_name`

```python
def get_node_name(node: Node, source: bytes, language: LangEnum) -> str | None
```

Extract the name from a function/class/method node.


| Parameter | Type | Default | Description |
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


| Parameter | Type | Default | Description |
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
        -_get_parser(language: LangEnum) Parser
        +detect_language(file_path: Path) LangEnum | None
        +parse_file(file_path: Path) tuple[Node, LangEnum, bytes] | None
        +parse_source(source: str | bytes, language: LangEnum) Node
        +get_file_info(file_path: Path, repo_root: Path) FileInfo
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[CodeParser._get_parser]
    N1[CodeParser.get_file_info]
    N2[CodeParser.parse_file]
    N3[CodeParser.parse_source]
    N4[_collect_preceding_comments]
    N5[_compute_file_hash]
    N6[_get_javadoc_or_doxygen]
    N7[_get_jsdoc_or_line_comments]
    N8[_get_line_comments]
    N9[_get_parser]
    N10[_get_python_docstring]
    N11[_get_swift_docstring]
    N12[_read_file_content]
    N13[_strip_line_comment_prefix]
    N14[bytes]
    N15[child_by_field_name]
    N16[decode]
    N17[detect_language]
    N18[fileno]
    N19[find_nodes_by_type]
    N20[get_node_name]
    N21[get_node_text]
    N22[hexdigest]
    N23[mmap]
    N24[parse]
    N25[read]
    N26[read_bytes]
    N27[sha256]
    N28[stat]
    N29[walk]
    N12 --> N28
    N12 --> N26
    N12 --> N23
    N12 --> N18
    N12 --> N14
    N5 --> N28
    N5 --> N22
    N5 --> N27
    N5 --> N26
    N5 --> N25
    N21 --> N16
    N19 --> N29
    N29 --> N29
    N20 --> N21
    N20 --> N15
    N4 --> N21
    N10 --> N15
    N10 --> N21
    N7 --> N21
    N7 --> N4
    N7 --> N13
    N8 --> N4
    N8 --> N13
    N6 --> N21
    N6 --> N4
    N6 --> N13
    N11 --> N4
    N11 --> N13
    N11 --> N21
    N2 --> N17
    N2 --> N12
    N2 --> N9
    N2 --> N24
    N3 --> N9
    N3 --> N24
    N1 --> N28
    N1 --> N17
    N1 --> N5
    classDef func fill:#e1f5fe
    class N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N0,N1,N2,N3 method
```

## Usage Examples

*Examples extracted from test files*

### Test Python language detection

From `test_parser.py::test_detect_language_python`:

```python
assert self.parser.detect_language(Path("test.py")) == Language.PYTHON
```

### Test Python language detection

From `test_parser.py::test_detect_language_python`:

```python
assert self.parser.detect_language(Path("test.py")) == Language.PYTHON
```

### Test JavaScript language detection

From `test_parser.py::test_detect_language_javascript`:

```python
assert self.parser.detect_language(Path("test.js")) == Language.JAVASCRIPT
```

### Test JavaScript language detection

From `test_parser.py::test_detect_language_javascript`:

```python
assert self.parser.detect_language(Path("test.js")) == Language.JAVASCRIPT
```

### Test parsing a Python file

From `test_parser.py::test_parse_python_file`:

```python
result = self.parser.parse_file(test_file)
assert result is not None
```

## Relevant Source Files

- [`src/local_deepwiki/core/parser.py:138-247`](https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser.py#L138-L247)

## See Also

- [test_api_docs](../../../tests/test_api_docs.md) - uses this
- [test_parser](../../../tests/test_parser.md) - uses this
