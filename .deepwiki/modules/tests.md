**Tests Module Documentation**
=====================================

### Overview

The `tests` module is a collection of test suites for various components of the local_deepwiki project. The primary focus of this module is to ensure that the parser, chunker, and configuration classes are functioning correctly.

### Classes and Functions

#### 1. TestCodeParser (tests/test_parser.py)

*   **Purpose**: Tests the functionality of the `CodeParser` class.
*   **Responsibilities**:
    *   Verifies language detection for Python files.
    *   Checks that the parser returns the correct language type.

#### 2. TestConfig (tests/test_config.py)

*   **Purpose**: Tests the functionality of the `Config` class.
*   **Responsibilities**:
    *   Verifies default configuration values.
    *   Checks that the embedding provider is set to "local".
    *   Verifies that the LLM provider is set to "ollama".

#### 3. TestCodeChunker (tests/test_chunker.py)

*   **Purpose**: Tests the functionality of the `CodeChunker` class.
*   **Responsibilities**:
    *   Verifies chunking of Python files.
    *   Checks that function names are extracted correctly.

### Usage Examples

#### 1. Running tests for CodeParser

```python
from tests.test_parser import TestCodeParser

# Create an instance of TestCodeParser
parser = TestCodeParser()

# Run the test suite
parser.run_test_suite()
```

#### 2. Verifying default configuration values

```python
import pytest
from tests.test_config import TestConfig

# Create an instance of TestConfig
config = TestConfig()

# Run the test suite
config.run_test_suite()
```

### Dependencies

*   `local_deepwiki.core.parser`: Provides the `CodeParser` class.
*   `local_deepwiki.models`: Provides the `Language`, `ChunkType`, and other related models.
*   `tempfile`: Used for creating temporary files during testing.

Note: This documentation assumes that the tests are being run using a testing framework like Pytest.