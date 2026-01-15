# callgraph.py

## File Overview

This module provides functionality for extracting and visualizing call graphs from source code files. It analyzes code to identify function calls and generates Mermaid diagrams showing the relationships between functions.

## Classes

### CallGraphExtractor

Extracts call graphs from source files by parsing code and identifying function calls.

**Constructor:**
- `__init__()`: Initializes the extractor with a CodeParser instance

**Methods:**
- `extract_from_file(file_path: Path, repo_root: Path) -> dict[str, list[str]]`: Extracts call graph from a source file, returning a dictionary mapping function names to lists of called functions

## Functions

### get_file_call_graph

```python
def get_file_call_graph(file_path: Path, repo_root: Path) -> str | None
```

Gets a call graph diagram for a single file.

**Parameters:**
- `file_path`: Path to the source file
- `repo_root`: Repository root path

**Returns:**
- Mermaid diagram string or None if no calls found

### extract_call_name

Extracts function names from call expressions in the parsed code.

### extract_calls_from_function

Identifies all function calls within a given function's code block.

### _is_builtin_or_noise

Helper function to filter out built-in functions or irrelevant calls from the call graph analysis.

### generate_call_graph_diagram

Converts call graph data into a Mermaid diagram format for visualization.

## Usage Examples

### Basic Call Graph Extraction

```python
from pathlib import Path
from local_deepwiki.generators.callgraph import get_file_call_graph

# Generate call graph for a single file
file_path = Path("src/example.py")
repo_root = Path(".")
diagram = get_file_call_graph(file_path, repo_root)

if diagram:
    print(diagram)
```

### Using CallGraphExtractor Directly

```python
from pathlib import Path
from local_deepwiki.generators.callgraph import CallGraphExtractor

# Create extractor instance
extractor = CallGraphExtractor()

# Extract call graph data
call_graph = extractor.extract_from_file(
    file_path=Path("src/example.py"),
    repo_root=Path(".")
)

# call_graph is a dict mapping function names to their called functions
for function, calls in call_graph.items():
    print(f"{function} calls: {calls}")
```

## Related Components

This module integrates with several other components:

- **CodeParser**: Used for parsing source code files and extracting syntax tree information
- **[Language](../models.md)**: Enum for specifying programming language types
- **Core chunker**: Provides constants for identifying class and function node types (`CLASS_NODE_TYPES`, `FUNCTION_NODE_TYPES`)
- **Parser utilities**: Uses functions like `find_nodes_by_type`, `get_node_name`, and `get_node_text` for AST navigation

The module works with Tree-sitter Node objects for precise code analysis and supports the broader local_deepwiki documentation generation system.

## API Reference

### class `CallGraphExtractor`

Extracts call graphs from source files.

**Methods:**

#### `__init__`

```python
def __init__()
```

Initialize the extractor.

#### `extract_from_file`

```python
def extract_from_file(file_path: Path, repo_root: Path) -> dict[str, list[str]]
```

Extract call graph from a source file.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to the source file. |
| `repo_root` | `Path` | - | Repository root path. |


---

### Functions

#### `extract_call_name`

```python
def extract_call_name(call_node: Node, source: bytes, language: Language) -> str | None
```

Extract the function/method name from a call expression.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `call_node` | `Node` | - | The call expression AST node. |
| `source` | `bytes` | - | Source bytes. |
| `language` | [`Language`](../models.md) | - | Programming language. |

**Returns:** `str | None`


#### `extract_calls_from_function`

```python
def extract_calls_from_function(func_node: Node, source: bytes, language: Language) -> list[str]
```

Extract all function calls from a function body.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `func_node` | `Node` | - | The function AST node. |
| `source` | `bytes` | - | Source bytes. |
| `language` | [`Language`](../models.md) | - | Programming language. |

**Returns:** `list[str]`


#### `generate_call_graph_diagram`

```python
def generate_call_graph_diagram(call_graph: dict[str, list[str]], title: str | None = None, max_nodes: int = 30) -> str | None
```

Generate a Mermaid flowchart for a call graph.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `call_graph` | `dict[str, list[str]]` | - | Mapping of caller to list of callees. |
| `title` | `str | None` | `None` | Optional diagram title. |
| `max_nodes` | `int` | `30` | Maximum number of nodes to include. |

**Returns:** `str | None`


#### `get_file_call_graph`

```python
def get_file_call_graph(file_path: Path, repo_root: Path) -> str | None
```

Get a call graph diagram for a single file.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to the source file. |
| `repo_root` | `Path` | - | Repository root path. |

**Returns:** `str | None`



## Class Diagram

```mermaid
classDiagram
    class CallGraphExtractor {
        +parser
        -__init__()
        +extract_from_file() -> dict[str, list[str]]
        -_is_inside_class() -> bool
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[CallGraphExtractor]
    N1[CallGraphExtractor.__init__]
    N2[CallGraphExtractor.extract_...]
    N3[CodeParser]
    N4[_is_builtin_or_noise]
    N5[_is_inside_class]
    N6[add]
    N7[child_by_field_name]
    N8[extract_call_name]
    N9[extract_calls_from_function]
    N10[extract_from_file]
    N11[find_nodes_by_type]
    N12[generate_call_graph_diagram]
    N13[get_file_call_graph]
    N14[get_node_name]
    N15[get_node_text]
    N16[parse_file]
    N8 --> N7
    N8 --> N15
    N9 --> N11
    N9 --> N8
    N9 --> N4
    N12 --> N6
    N13 --> N0
    N13 --> N10
    N13 --> N12
    N1 --> N3
    N2 --> N16
    N2 --> N11
    N2 --> N5
    N2 --> N14
    N2 --> N9
    classDef func fill:#e1f5fe
    class N0,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16 func
    classDef method fill:#fff3e0
    class N1,N2 method
```

## Usage Examples

*Examples extracted from test files*

### Test that common built-ins are filtered

From `test_callgraph.py::test_common_builtins_filtered`:

```python
assert _is_builtin_or_noise("print", Language.PYTHON) is True
```

### Test Python-specific built-ins are filtered

From `test_callgraph.py::test_python_specific_builtins`:

```python
assert _is_builtin_or_noise("super", Language.PYTHON) is True
```

### Test extracting a simple function call

From `test_callgraph.py::test_simple_function_call`:

```python
source = dedent(
    """
    def main():
        process_data()
"""
).strip()
root = parser.parse_source(source, Language.PYTHON)
func_node = root.children[0]  # function_definition

calls = extract_calls_from_function(func_node, source.encode(), Language.PYTHON)
assert "process_data" in calls
```

### Test extracting multiple function calls

From `test_callgraph.py::test_multiple_function_calls`:

```python
source = dedent(
    """
    def main():
        load_data()
        process_data()
        save_results()
"""
).strip()
root = parser.parse_source(source, Language.PYTHON)
func_node = root.children[0]

calls = extract_calls_from_function(func_node, source.encode(), Language.PYTHON)
assert "load_data" in calls
```

### Test that empty call graph returns None

From `test_callgraph.py::test_empty_graph_returns_none`:

```python
result = generate_call_graph_diagram({})
assert result is None
```

## Relevant Source Files

- `src/local_deepwiki/generators/callgraph.py:257-324`

## See Also

- [chunker](../core/chunker.md) - dependency
- [models](../models.md) - dependency
- [api_docs](api_docs.md) - shares 5 dependencies
- [test_examples](test_examples.md) - shares 4 dependencies
