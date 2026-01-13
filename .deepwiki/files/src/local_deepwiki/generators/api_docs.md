# File Overview

This file, `api_docs.py`, provides functionality for extracting and parsing API documentation from Python code. It uses the Tree-sitter library for code parsing and supports extracting information such as function signatures, parameters, return types, decorators, and docstrings from Python source code. The module is part of the `local_deepwiki` package and is designed to work with Python code analysis.

# Classes

## Parameter

The Parameter class represents a function parameter, storing its name, type, and default value.

### Key Methods

- `__init__(self, name: str, type_annotation: str = "", default_value: str = "")`: Initializes a Parameter instance with the given name, type annotation, and default value.

## FunctionSignature

The FunctionSignature class holds information about a function's signature, including its name, parameters, return type, and decorators.

### Key Methods

- `__init__(self, name: str, parameters: list, return_type: str = "", decorators: list = None)`: Initializes a FunctionSignature instance with the function's name, list of parameters, return type, and decorators.

## ClassSignature

The ClassSignature class stores information about a class, including its name, methods, and decorators.

### Key Methods

- `__init__(self, name: str, methods: list, decorators: list = None)`: Initializes a ClassSignature instance with the class's name, list of methods, and decorators.

## APIDocExtractor

The APIDocExtractor class is responsible for extracting API documentation from Python code using Tree-sitter parsing.

### Key Methods

- `__init__(self, parser: CodeParser)`: Initializes the APIDocExtractor with a [CodeParser](../core/parser.md) instance.
- `extract_from_file(self, file_path: Path)`: Extracts API documentation from a given file path.
- `extract_from_code(self, code: str)`: Extracts API documentation from a string of code.
- `extract_classes(self, node: Node)`: Extracts class information from a Tree-sitter node.
- `extract_functions(self, node: Node)`: Extracts function information from a Tree-sitter node.
- `extract_class_methods(self, node: Node)`: Extracts methods from a class node.
- `extract_function_signature(self, node: Node)`: Extracts the signature of a function from a Tree-sitter node.
- `extract_class_signature(self, node: Node)`: Extracts the signature of a class from a Tree-sitter node.

# Functions

## extract_python_parameters

Extracts parameters from a Tree-sitter node representing a function.

### Parameters

- `node: Node`: A Tree-sitter node representing a function.

### Returns

- `list[Parameter]`: A list of Parameter objects extracted from the function node.

## extract_python_return_type

Extracts the return type annotation from a Tree-sitter node representing a function.

### Parameters

- `node: Node`: A Tree-sitter node representing a function.

### Returns

- `str`: The return type annotation as a string, or an empty string if not found.

## extract_python_decorators

Extracts decorators from a Tree-sitter node representing a function or class.

### Parameters

- `node: Node`: A Tree-sitter node representing a function or class.

### Returns

- `list[str]`: A list of decorator names as strings.

## extract_python_docstring

Extracts the docstring from a Tree-sitter node representing a function or class.

### Parameters

- `node: Node`: A Tree-sitter node representing a function or class.

### Returns

- `str`: The docstring content as a string, or an empty string if not found.

## parse_google_docstring

Parses a Google-style docstring into structured information.

### Parameters

- `docstring: str`: The Google-style docstring to parse.

### Returns

- `dict`: A dictionary containing parsed information from the docstring.

## parse_numpy_docstring

Parses a NumPy-style docstring into structured information.

### Parameters

- `docstring: str`: The NumPy-style docstring to parse.

### Returns

- `dict`: A dictionary containing parsed information from the docstring.

## parse_docstring

Parses a docstring using either Google or NumPy style parsing based on content.

### Parameters

- `docstring: str`: The docstring to parse.

### Returns

- `dict`: A dictionary containing parsed information from the docstring.

## ext

A utility function for extracting information from Tree-sitter nodes.

### Parameters

- `node: Node`: A Tree-sitter node to extract information from.

### Returns

- `str`: The extracted text content from the node.

# Usage Examples

To use the APIDocExtractor for extracting API documentation from Python code:

```python
from local_deepwiki.generators.api_docs import APIDocExtractor
from local_deepwiki.core.parser import CodeParser
from pathlib import Path

# Initialize the parser and extractor
parser = CodeParser(Language.PYTHON)
extractor = APIDocExtractor(parser)

# Extract API documentation from a file
file_path = Path("example.py")
api_docs = extractor.extract_from_file(file_path)

# Extract API documentation from a code string
code = '''
def example_function(param1: str, param2: int = 0) -> bool:
    """This is an example function."""
    return True
'''
api_docs = extractor.extract_from_code(code)
```

# Related Components

This module works with the following components:

- [`CodeParser`](../core/parser.md) from `local_deepwiki.core.parser`: Used for parsing Python code into Tree-sitter nodes.
- `CLASS_NODE_TYPES` and `FUNCTION_NODE_TYPES` from `local_deepwiki.core.chunker`: Used to identify node types for classes and functions.
- `Language` from `local_deepwiki.models`: Used to specify the language for parsing.
- `Node` from `tree_sitter`: Used for representing parsed code elements.
- [`get_node_name`](../core/parser.md) and [`get_node_text`](../core/parser.md) from `local_deepwiki.core.parser`: Utility functions for extracting node information.
- [`find_nodes_by_type`](../core/parser.md) from `local_deepwiki.core.parser`: Used to [find](manifest.md) nodes of specific types in the parsed code.

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

- `src/local_deepwiki/generators/api_docs.py:15-21`

## See Also

- [test_api_docs](../../../tests/test_api_docs.md) - uses this
- [crosslinks](crosslinks.md) - shares 4 dependencies
- [diagrams](diagrams.md) - shares 4 dependencies
