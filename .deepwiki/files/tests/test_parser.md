# Test Parser Documentation

## File Overview

This file contains test suites for the `CodeParser` class and related node helper functions. It ensures the correct functionality of language detection, code parsing, and node text/name extraction for different programming languages.

## Classes

### `TestCodeParser`

Test suite for the `CodeParser` class, focusing on language detection capabilities.

**Key Methods:**
- `setup_method()`: Initializes a `CodeParser` instance for each test
- `test_detect_language_python()`: Tests detection of Python files (.py, .pyi extensions)
- `test_detect_language_javascript()`: Tests detection of JavaScript files (.js extension)

**Usage:**
```python
# Run tests using pytest
pytest tests/test_parser.py::TestCodeParser
```

### `TestNodeHelpers`

Test suite for node helper functions that extract information from parsed code trees.

**Key Methods:**
- `setup_method()`: Initializes a `CodeParser` instance for each test
- `test_get_node_text()`: Tests extracting text content from AST nodes
- `test_get_node_name_python_function()`: Tests extracting function names from Python code

**Usage:**
```python
# Run tests using pytest
pytest tests/test_parser.py::TestNodeHelpers
```

## Functions

### `get_node_text(node, code_bytes)`

Extracts the text content from a tree-sitter AST node.

**Parameters:**
- `node`: Tree-sitter AST node
- `code_bytes`: Source code as bytes

**Return Value:**
- String containing the text content of the node

### `get_node_name(node)`

Extracts the name from a tree-sitter AST node.

**Parameters:**
- `node`: Tree-sitter AST node

**Return Value:**
- String containing the node's name

## Usage Examples

### Running Tests
```bash
# Run all parser tests
pytest tests/test_parser.py

# Run specific test class
pytest tests/test_parser.py::TestCodeParser

# Run specific test method
pytest tests/test_parser.py::TestCodeParser::test_detect_language_python
```

### Basic Parser Usage
```python
from local_deepwiki.core.parser import CodeParser
from local_deepwiki.models import Language

parser = CodeParser()
code = b"def hello(): return 'world'"
root = parser.parse_source(code, Language.PYTHON)
```

## Dependencies

This file imports:
- `tempfile` - For temporary file handling
- `pathlib.Path` - For path manipulation
- `pytest` - Testing framework
- `local_deepwiki.core.parser`: 
  - `CodeParser` - Main parser class
  - `get_node_text` - Function to extract node text
  - `get_node_name` - Function to extract node names
- `local_deepwiki.models.Language` - Enum for programming languages

**Note:** The code appears to be incomplete, with a truncated test method (`ass` in line 27 of TestCodeParser class). This should be completed for full test coverage.