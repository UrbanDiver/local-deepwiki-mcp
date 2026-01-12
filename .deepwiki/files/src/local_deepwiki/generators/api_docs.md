# API Documentation Generator

## File Overview

This file provides functionality for extracting and parsing API documentation from Python source code. It serves as a core component in the local_deepwiki system for generating documentation from code repositories. The module works by parsing Python code using tree-sitter, extracting function and class signatures, docstrings, and other metadata to create structured API documentation.

The API Docs Extractor class is the [main](../web/app.md) entry point for this functionality, working with [CodeParser](../core/parser.md) to analyze source code and extract meaningful documentation information. It integrates with other components like the chunker to identify code elements and the models to represent extracted data.

## Classes

### Parameter

Represents a function parameter with its name, type annotation, and default value.

**Key Attributes:**
- `name`: Parameter name
- `type_annotation`: Type annotation (if available)
- `default_value`: Default value (if specified)
- `is_varargs`: Boolean indicating if parameter is *args or **kwargs

### FunctionSignature

Represents the signature of a Python function including its name, parameters, return type, and decorators.

**Key Attributes:**
- `name`: Function name
- `parameters`: List of Parameter objects
- `return_type`: Return type annotation (if available)
- `decorators`: List of decorators applied to the function
- `docstring`: Function docstring content
- `node`: Tree-sitter node reference

**Key Methods:**
- `__init__(node, parser)`: Initializes the function signature from a tree-sitter node
- `from_node(node, parser)`: Factory method to create FunctionSignature from node

### ClassSignature

Represents the signature of a Python class including its name, methods, and decorators.

**Key Attributes:**
- `name`: Class name
- `methods`: List of FunctionSignature objects representing class methods
- `decorators`: List of decorators applied to the class
- `docstring`: Class docstring content
- `node`: Tree-sitter node reference

**Key Methods:**
- `__init__(node, parser)`: Initializes the class signature from a tree-sitter node
- `from_node(node, parser)`: Factory method to create ClassSignature from node

### APIDocExtractor

Main class for extracting API documentation from Python source code.

**Key Methods:**
- `__init__(parser)`: Initializes the extractor with a [CodeParser](../core/parser.md) instance
- `extract_from_file(file_path)`: Extracts API documentation from a Python file
- `extract_from_code(code)`: Extracts API documentation from code string
- `extract_functions(node, parser)`: Extracts function signatures from a node
- `extract_classes(node, parser)`: Extracts class signatures from a node

## Functions

### extract_python_parameters

Parses parameters from a function definition node.

**Parameters:**
- `node`: Tree-sitter node representing a function definition
- `parser`: [CodeParser](../core/parser.md) instance for text extraction

**Returns:**
- List of Parameter objects

### extract_python_return_type

Extracts the return type annotation from a function definition node.

**Parameters:**
- `node`: Tree-sitter node representing a function definition
- `parser`: [CodeParser](../core/parser.md) instance for text extraction

**Returns:**
- Return type annotation as string or None

### extract_python_decorators

Extracts decorators from a function or class definition node.

**Parameters:**
- `node`: Tree-sitter node representing a function or class definition
- `parser`: [CodeParser](../core/parser.md) instance for text extraction

**Returns:**
- List of decorator strings

### extract_python_docstring

Extracts docstring content from a function or class definition node.

**Parameters:**
- `node`: Tree-sitter node representing a function or class definition
- `parser`: [CodeParser](../core/parser.md) instance for text extraction

**Returns:**
- Docstring content as string or None

### parse_google_docstring

Parses Google-style docstrings into structured format.

**Parameters:**
- `docstring`: Raw docstring text
- `parser`: [CodeParser](../core/parser.md) instance for text extraction

**Returns:**
- Dictionary containing parsed docstring components

### parse_num

Parses numeric values from strings.

**Parameters:**
- `value`: String representation of a number
- `default`: Default value to return if parsing fails

**Returns:**
- Parsed numeric value or default

## Usage Examples

### Basic Usage

```python
from local_deepwiki.generators.api_docs import APIDocExtractor
from local_deepwiki.core.parser import CodeParser

# Initialize parser and extractor
parser = CodeParser(Language.PYTHON)
extractor = APIDocExtractor(parser)

# Extract documentation from a file
doc = extractor.extract_from_file("path/to/module.py")
```

### Extracting Function Signatures

```python
from local_deepwiki.generators.api_docs import FunctionSignature
from local_deepwiki.core.parser import CodeParser

parser = CodeParser(Language.PYTHON)

# Parse function signature
code = """
def example_function(param1: str, param2: int = 0) -> bool:
    \"\"\"Example function documentation.\"\"\"
    return True
"""

# Extract function signature
function_node = parser.parse(code).root_node
signature = FunctionSignature.from_node(function_node, parser)

print(f"Function name: {signature.name}")
print(f"Parameters: {len(signature.parameters)}")
print(f"Return type: {signature.return_type}")
```

### Working with Class Signatures

```python
from local_deepwiki.generators.api_docs import ClassSignature
from local_deepwiki.core.parser import CodeParser

parser = CodeParser(Language.PYTHON)

# Parse class signature
code = """
class ExampleClass:
    def method(self, param: str) -> None:
        \"\"\"Example method.\"\"\"
        pass
"""

class_node = parser.parse(code).root_node
class_signature = ClassSignature.from_node(class_node, parser)

print(f"Class name: {class_signature.name}")
print(f"Methods: {len(class_signature.methods)}")
```

## Related Components

This module works with [CodeParser](../core/parser.md) to analyze source code and extract information from tree-sitter nodes. It integrates with the chunker module to identify function and class nodes, and relies on the [Language](../models.md) enum from models to determine parsing strategies. The extracted documentation is used by other components in the documentation generation pipeline to create comprehensive API documentation.

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
| `language` | [`Language`](../models.md) | - | Programming language. |
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
| `language` | [`Language`](../models.md) | - | Programming language. |

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

## See Also

- [wiki](wiki.md) - uses this
- [test_api_docs](../../../tests/test_api_docs.md) - uses this
- [chunker](../core/chunker.md) - dependency
- [models](../models.md) - dependency
- [parser](../core/parser.md) - dependency
