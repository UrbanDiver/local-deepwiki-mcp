# Tests Module Documentation

## Overview

The `tests` module contains all unit tests for the `local_deepwiki` package. It ensures the correct functionality of core components including code parsing, chunking, and configuration management.

## Module Structure

```
tests/
├── __init__.py          # Empty package initializer
├── test_parser.py       # Tests for CodeParser and node helper functions
├── test_chunker.py      # Tests for CodeChunker
└── test_config.py       # Tests for Config class
```

## Key Components

### 1. `TestCodeParser` (tests/test_parser.py)

Test suite for the `CodeParser` class responsible for parsing source code and detecting programming languages.

#### Methods:
- `setup_method()`: Initializes a `CodeParser` instance for each test
- `test_detect_language_python()`: Verifies Python language detection
- `test_get_node_text()`: Tests extracting text from AST nodes

### 2. `TestNodeHelpers` (tests/test_parser.py)

Tests for helper functions that work with AST nodes.

#### Methods:
- `setup_method()`: Initializes a `CodeParser` instance
- `test_get_node_text()`: Tests extracting text from nodes

### 3. `TestCodeChunker` (tests/test_chunker.py)

Test suite for the `CodeChunker` class that splits source code into manageable chunks.

#### Methods:
- `setup_method()`: Initializes a `CodeChunker` instance
- `test_chunk_python_file()`: Tests chunking Python files
- `test_chunk_extracts_function_names()`: Verifies function name extraction
- `test_chunk_extracts_class_names()`: Verifies class name extraction
- `test_chunk_extracts_docstrings()`: Tests docstring extraction
- `test_chunk_javascript_file()`: Tests chunking JavaScript files
- `test_chunk_sets_line_numbers()`: Verifies line number assignment
- `test_chunk_generates_unique_ids()`: Tests unique ID generation
- `test_chunk_unsupported_file_returns_empty()`: Tests handling of unsupported files

### 4. `TestConfig` (tests/test_config.py)

Test suite for the `Config` class that manages application configuration.

#### Methods:
- `test_default_config()`: Verifies default configuration values
- `test_embedding_config()`: Tests embedding configuration
- `test_llm_config()`: Tests LLM configuration
- `test_parsing_config()`: Tests parsing configuration
- `test_chunking_config()`: Tests chunking configuration
- `test_get_config()`: Tests configuration retrieval
- `test_set_config()`: Tests configuration setting

## Usage Examples

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_parser.py

# Run specific test class
pytest tests/test_parser.py::TestCodeParser

# Run specific test method
pytest tests/test_parser.py::TestCodeParser::test_detect_language_python
```

### Example Test Structure

```python
def test_chunk_python_file(self, tmp_path):
    """Test chunking a Python file."""
    code = '''"""Module docstring."""

import os
from pathlib import Path

def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

class Greeter:
    """A class that greets people."""

    def __init__(self, prefix: str = "Hello"):
        self.prefix = prefix

    def greet(self, name: str) -> str:
        """Greet someone."""
        return f"{self.prefix}, {name}!"
'''
    
    # Create temporary file
    file_path = tmp_path / "test.py"
    file_path.write_text(code)
    
    # Chunk the file
    chunks = self.chunker.chunk_file(file_path)
    
    # Verify results
    assert len(chunks) > 0
    assert chunks[0].type == ChunkType.FUNCTION
```

## Dependencies

### Internal Dependencies
- `local_deepwiki.core.parser`: `CodeParser` class
- `local_deepwiki.core.chunker`: `CodeChunker` class
- `local_deepwiki.config`: `Config` class
- `local_deepwiki.models`: `Language`, `ChunkType` enums

### External Dependencies
- `pytest`: Testing framework
- `pathlib`: Path handling
- `tempfile`: Temporary file handling

## Test Coverage

The test suite covers:
- Language detection for various file extensions
- AST parsing and node text extraction
- Code chunking with proper function/class identification
- Configuration management and validation
- Edge cases like unsupported file types
- Line number and unique ID assignment
- Documentation string extraction

All tests are designed to be independent and run in any order.