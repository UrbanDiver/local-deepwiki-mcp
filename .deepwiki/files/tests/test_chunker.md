# Test Code Chunker Documentation

## File Overview

This file contains unit tests for the `CodeChunker` class, which is responsible for breaking down source code files into logical chunks (functions, classes, etc.). The tests verify that the chunker correctly identifies code elements, extracts their names and documentation, and assigns proper metadata like line numbers and unique IDs.

## Classes

### `TestCodeChunker`

**Purpose**: A pytest class containing unit tests for the `CodeChunker` functionality.

**Key Methods**:
- `setup_method`: Initializes the test fixture by creating a `CodeChunker` instance
- `test_chunk_python_file`: Tests chunking of Python files
- `test_chunk_extracts_function_names`: Verifies function name extraction
- `test_chunk_extracts_class_names`: Verifies class name extraction
- `test_chunk_extracts_docstrings`: Verifies docstring extraction
- `test_chunk_javascript_file`: Tests chunking of JavaScript files
- `test_chunk_sets_line_numbers`: Verifies correct line number assignment
- `test_chunk_generates_unique_ids`: Ensures unique chunk IDs are generated
- `test_chunk_unsupported_file_returns_empty`: Tests behavior with unsupported file types

## Functions

### `setup_method`
- **Parameters**: `self` (instance of `TestCodeChunker`)
- **Return Value**: None
- **Purpose**: Initializes the test fixture by creating a `CodeChunker` instance to be used in all tests

### `test_chunk_python_file`
- **Parameters**: `self`, `tmp_path` (pytest fixture)
- **Return Value**: None
- **Purpose**: Tests that Python files are correctly chunked into functions and classes

### `test_chunk_extracts_function_names`
- **Parameters**: `self`, `tmp_path` (pytest fixture)
- **Return Value**: None
- **Purpose**: Verifies that function names are properly extracted from code chunks

### `test_chunk_extracts_class_names`
- **Parameters**: `self`, `tmp_path` (pytest fixture)
- **Return Value**: None
- **Purpose**: Verifies that class names are properly extracted from code chunks

### `test_chunk_extracts_docstrings`
- **Parameters**: `self`, `tmp_path` (pytest fixture)
- **Return Value**: None
- **Purpose**: Verifies that docstrings are properly extracted from functions

### `test_chunk_javascript_file`
- **Parameters**: `self`, `tmp_path` (pytest fixture)
- **Return Value**: None
- **Purpose**: Tests that JavaScript files are correctly chunked

### `test_chunk_sets_line_numbers`
- **Parameters**: `self`, `tmp_path` (pytest fixture)
- **Return Value**: None
- **Purpose**: Verifies that line numbers are correctly assigned to chunks

### `test_chunk_generates_unique_ids`
- **Parameters**: `self`, `tmp_path` (pytest fixture)
- **Return Value**: None
- **Purpose**: Ensures that each chunk receives a unique identifier

### `test_chunk_unsupported_file_returns_empty`
- **Parameters**: `self`, `tmp_path` (pytest fixture)
- **Return Value**: None
- **Purpose**: Tests that unsupported file types return no chunks

## Usage Examples

```python
# Run all tests
pytest tests/test_chunker.py

# Run a specific test
pytest tests/test_chunker.py::TestCodeChunker::test_chunk_python_file

# Example of using CodeChunker directly (not in tests)
from local_deepwiki.core.chunker import CodeChunker
chunker = CodeChunker()
chunks = list(chunker.chunk_file("example.py", "/path/to/project"))
```

## Dependencies

This file imports:
- `Path` from `pathlib` - for handling file paths
- `pytest` - for testing framework
- `CodeChunker` from `local_deepwiki.core.chunker` - the main class being tested
- `ChunkType` and `Language` from `local_deepwiki.models` - for chunk metadata

## Test Structure

The tests follow a pattern of:
1. Creating a temporary file with test code
2. Calling `chunker.chunk_file()` on that file
3. Asserting expected properties of the returned chunks

Example test structure:
```python
def test_something(self, tmp_path):
    test_file = tmp_path / "test.py"
    test_file.write_text("def my_func(): pass")
    
    chunks = list(self.chunker.chunk_file(test_file, tmp_path))
    # Assertions about chunks
```