# File Overview

This file, `api_docs.py`, provides functionality for extracting API documentation from source code, specifically targeting Python code. It leverages the `tree_sitter` library for parsing and extracting structured information like function signatures, parameters, return types, decorators, and docstrings.

The [main](../export/html.md) purpose of this file is to parse Python code and extract API-related information for use in documentation generation or other tools that require structured code analysis.

# Classes

## Parameter

The Parameter class represents a single parameter in a function signature.

### Key Attributes

- `name`: The name of the parameter.
- `type`: The type annotation of the parameter (if available).
- `default`: The default value of the parameter (if applicable).

## FunctionSignature

The FunctionSignature class represents a function's signature, including its name, parameters, return type, and decorators.

### Key Attributes

- `name`: The name of the function.
- `parameters`: A list of `Parameter` objects representing the function's parameters.
- `return_type`: The return type annotation of the function (if available).
- `decorators`: A list of decorators applied to the function.
- `docstring`: The docstring of the function (if available).

## ClassSignature

The ClassSignature class represents a class's signature, including its name, methods, and decorators.

### Key Attributes

- `name`: The name of the class.
- `methods`: A list of `FunctionSignature` objects representing the class's methods.
- `decorators`: A list of decorators applied to the class.
- `docstring`: The docstring of the class (if available).

## APIDocExtractor

The APIDocExtractor class is responsible for extracting API documentation from Python code using tree-sitter parsing.

### Key Methods

- `extract_from_code(code: str) -> list[FunctionSignature | ClassSignature]`: Extracts function and class signatures from a given code string.
- `extract_from_file(file_path: Path) -> list[FunctionSignature | ClassSignature]`: Extracts function and class signatures from a file.

# Functions

## extract_python_parameters

Extracts parameter information from a function node.

### Parameters

- `node`: A `tree_sitter.Node` representing a function node.

### Returns

- A list of `Parameter` objects representing the function's parameters.

## extract_python_return_type

Extracts the return type annotation from a function node.

### Parameters

- `node`: A `tree_sitter.Node` representing a function node.

### Returns

- The return type annotation as a string, or `None` if not found.

## extract_python_decorators

Extracts decorators from a function or class node.

### Parameters

- `node`: A `tree_sitter.Node` representing a function or class node.

### Returns

- A list of decorator names as strings.

## extract_python_docstring

Extracts the docstring from a function or class node.

### Parameters

- `node`: A `tree_sitter.Node` representing a function or class node.

### Returns

- The docstring as a string, or `None` if not found.

## parse_google_docstring

Parses a Google-style docstring into structured information.

### Parameters

- `docstring`: A string representing the docstring to parse.

### Returns

- A dictionary containing parsed docstring information.

## parse_num

Parses a number from a string.

### Parameters

- `s`: A string to parse into a number.

### Returns

- The parsed number as an integer or float, or `None` if parsing fails.

# Usage Examples

The following examples show how to use the components defined in this file:

### Extracting API Documentation from Code

```python
from local_deepwiki.generators.api_docs import APIDocExtractor

extractor = APIDocExtractor()
code = '''
def example_function(param1: str, param2: int = 42) -> bool:
    """An example function."""
    return True
'''

docs = extractor.extract_from_code(code)
```

### Extracting API Documentation from a File

```python
from local_deepwiki.generators.api_docs import APIDocExtractor
from pathlib import Path

extractor = APIDocExtractor()
file_path = Path("example.py")
docs = extractor.extract_from_file(file_path)
```

# Related Components

This file works with the following components:

- [`CodeParser`](../core/parser.md) from `local_deepwiki.core.parser`: Used for parsing code.
- [`find_nodes_by_type`](../core/parser.md) from `local_deepwiki.core.parser`: Used to [find](manifest.md) specific nodes in the parse tree.
- [`get_node_text`](../core/parser.md) from `local_deepwiki.core.parser`: Used to extract text from nodes.
- [`get_node_name`](../core/parser.md) from `local_deepwiki.core.parser`: Used to extract names from nodes.
- `FUNCTION_NODE_TYPES` from `local_deepwiki.core.chunker`: Defines node types for functions.
- `CLASS_NODE_TYPES` from `local_deepwiki.core.chunker`: Defines node types for classes.
- `Language` from `local_deepwiki.models`: Represents the programming language (used for type hints).

## API Reference

### class `Parameter`

Represents a function parameter.

### class `FunctionSignature`

Represents a function/method signature.

### class `ClassSignature`

Represents a class signature.

### class `APIDocExtractor`

Extracts API documentation from source files.

**Methods:**

#### `__init__`

```python
def __init__()
```

Initialize the extractor.

#### `extract_from_file`

```python
def extract_from_file(file_path: Path) -> tuple[list[FunctionSignature], list[ClassSignature]]
```

Extract API documentation from a source file.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to the source file. |


---

### Functions

#### `extract_python_parameters`

```python
def extract_python_parameters(func_node: Node, source: bytes) -> list[Parameter]
```

Extract parameters from a Python function definition.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `func_node` | `Node` | - | The function_definition AST node. |
| `source` | `bytes` | - | Source code bytes. |

**Returns:** `list[Parameter]`


#### `extract_python_return_type`

```python
def extract_python_return_type(func_node: Node, source: bytes) -> str | None
```

Extract return type annotation from a Python function.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `func_node` | `Node` | - | The function_definition AST node. |
| `source` | `bytes` | - | Source code bytes. |

**Returns:** `str | None`


#### `extract_python_decorators`

```python
def extract_python_decorators(func_node: Node, source: bytes) -> list[str]
```

Extract decorators from a Python function.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `func_node` | `Node` | - | The function_definition AST node. |
| `source` | `bytes` | - | Source code bytes. |

**Returns:** `list[str]`


#### `extract_python_docstring`

```python
def extract_python_docstring(node: Node, source: bytes) -> str | None
```

Extract docstring from a Python function or class.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | - | The function_definition or class_definition AST node. |
| `source` | `bytes` | - | Source code bytes. |

**Returns:** `str | None`


#### `parse_google_docstring`

```python
def parse_google_docstring(docstring: str) -> dict
```

Parse a Google-style docstring.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `docstring` | `str` | - | The docstring content. |

**Returns:** `dict`


#### `parse_numpy_docstring`

```python
def parse_numpy_docstring(docstring: str) -> dict
```

Parse a NumPy-style docstring.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `docstring` | `str` | - | The docstring content. |

**Returns:** `dict`


#### `parse_docstring`

```python
def parse_docstring(docstring: str) -> dict
```

Parse a docstring, auto-detecting format.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `docstring` | `str` | - | The docstring content. |

**Returns:** `dict`


#### `extract_function_signature`

```python
def extract_function_signature(func_node: Node, source: bytes, language: Language, class_name: str | None = None) -> FunctionSignature | None
```

Extract signature from a function node.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `func_node` | `Node` | - | The function AST node. |
| `source` | `bytes` | - | Source code bytes. |
| `language` | `Language` | - | Programming language. |
| `class_name` | `str | None` | `None` | Parent class name if this is a method. |

**Returns:** `FunctionSignature | None`


#### `extract_class_signature`

```python
def extract_class_signature(class_node: Node, source: bytes, language: Language) -> ClassSignature | None
```

Extract signature from a class node.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `class_node` | `Node` | - | The class AST node. |
| `source` | `bytes` | - | Source code bytes. |
| `language` | `Language` | - | Programming language. |

**Returns:** `ClassSignature | None`


#### `format_parameter`

```python
def format_parameter(param: Parameter) -> str
```

Format a parameter for display.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `param` | `Parameter` | - | The parameter to format. |

**Returns:** `str`


#### `format_function_signature_line`

```python
def format_function_signature_line(sig: FunctionSignature) -> str
```

Format a function signature as a single line.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sig` | `FunctionSignature` | - | The function signature. |

**Returns:** `str`


#### `generate_api_reference_markdown`

```python
def generate_api_reference_markdown(functions: list[FunctionSignature], classes: list[ClassSignature], include_private: bool = False) -> str
```

Generate markdown API reference documentation.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `functions` | `list[FunctionSignature]` | - | List of function signatures. |
| `classes` | `list[ClassSignature]` | - | List of class signatures. |
| `include_private` | `bool` | `False` | Whether to include private (underscore) items. |

**Returns:** `str`


#### `get_file_api_docs`

```python
def get_file_api_docs(file_path: Path) -> str | None
```

Get API documentation for a single file.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `Path` | - | Path to the source file. |

**Returns:** `str | None`



## Class Diagram

```mermaid
classDiagram
    class APIDocExtractor {
        -__init__()
        +extract_from_file()
        -_is_inside_class()
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[APIDocExtractor]
    N1[APIDocExtractor.__init__]
    N2[APIDocExtractor.extract_fro...]
    N3[ClassSignature]
    N4[CodeParser]
    N5[FunctionSignature]
    N6[Parameter]
    N7[child_by_field_name]
    N8[extract_class_signature]
    N9[extract_from_file]
    N10[extract_function_signature]
    N11[extract_python_decorators]
    N12[extract_python_docstring]
    N13[extract_python_parameters]
    N14[extract_python_return_type]
    N15[find_nodes_by_type]
    N16[format_function_signature_line]
    N17[format_parameter]
    N18[generate_api_reference_mark...]
    N19[get_file_api_docs]
    N20[get_node_name]
    N21[get_node_text]
    N22[group]
    N23[lstrip]
    N24[match]
    N25[parse_docstring]
    N26[parse_file]
    N27[parse_google_docstring]
    N28[parse_numpy_docstring]
    N29[search]
    N13 --> N7
    N13 --> N21
    N13 --> N6
    N14 --> N7
    N14 --> N21
    N11 --> N21
    N12 --> N7
    N12 --> N21
    N27 --> N24
    N27 --> N22
    N28 --> N24
    N28 --> N22
    N25 --> N29
    N25 --> N27
    N25 --> N28
    N10 --> N20
    N10 --> N5
    N10 --> N13
    N10 --> N14
    N10 --> N11
    N10 --> N12
    N10 --> N25
    N10 --> N23
    N8 --> N20
    N8 --> N3
    N8 --> N21
    N8 --> N12
    N8 --> N25
    N8 --> N15
    N8 --> N10
    N16 --> N17
    N18 --> N16
    N19 --> N0
    N19 --> N9
    N19 --> N18
    N1 --> N4
    N2 --> N26
    N2 --> N15
    N2 --> N10
    N2 --> N8
    classDef func fill:#e1f5fe
    class N0,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19,N20,N21,N22,N23,N24,N25,N26,N27,N28,N29 func
    classDef method fill:#fff3e0
    class N1,N2 method
```

## Relevant Source Files

- `src/local_deepwiki/generators/api_docs.py:23-28`

## See Also

- [test_api_docs](../../../tests/test_api_docs.md) - uses this
- [wiki](wiki.md) - uses this
- [chunker](../core/chunker.md) - dependency
- [parser](../core/parser.md) - dependency
- [crosslinks](crosslinks.md) - shares 4 dependencies
