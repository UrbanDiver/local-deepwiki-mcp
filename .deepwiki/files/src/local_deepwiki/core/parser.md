# Parser Module Documentation

## File Overview

The `src/local_deepwiki/core/parser.py` file provides core parsing functionality for source code analysis. It implements a language-agnostic parser that can analyze code files using Tree-sitter parsers for multiple programming languages. The module serves as the foundation for code understanding and semantic analysis within the DeepWiki system.

## Dependencies

This file imports the following dependencies:

- Standard library modules: `hashlib`, `pathlib`, `typing`
- Tree-sitter language parsers: `tree_sitter_python`, `tree_sitter_javascript`, `tree_sitter_typescript`, `tree_sitter_go`, `tree_sitter_rust`, `tree_sitter_java`, `tree_sitter_c`, `tree_sitter_cpp`
- Tree-sitter core classes: `Language`, `Parser`, `Node`
- Local models: `Language` enum and `FileInfo` class

## Classes

### ParserManager

**Purpose**: Manages language-specific Tree-sitter parsers and provides unified parsing functionality across multiple programming languages.

**Key Methods**:
- `__init__(self)`: Initializes the parser manager with language-specific parsers
- `parse(self, file_path: Path, language: LangEnum) -> Node`: Parses a file and returns the Tree-sitter AST node
- `get_language_parser(self, language: LangEnum) -> Parser`: Retrieves the appropriate parser for a given language

**Usage**: The ParserManager is responsible for creating and maintaining parsers for different programming languages, enabling cross-language code analysis.

## Functions

### parse_file

**Purpose**: Parses a source code file and returns structured information about it.

**Parameters**:
- `file_path: Path` - Path to the source code file to parse
- `language: LangEnum` - Enum indicating the programming language of the file

**Return Value**: `FileInfo` object containing parsed information about the file

**Usage Example**:
```python
from pathlib import Path
from local_deepwiki.core.parser import parse_file
from local_deepwiki.models import Language

file_info = parse_file(Path("example.py"), Language.PYTHON)
```

### get_file_hash

**Purpose**: Generates a SHA-256 hash of a file's content for identification and caching purposes.

**Parameters**:
- `file_path: Path` - Path to the file to hash

**Return Value**: String containing the SHA-256 hash of the file content

**Usage Example**:
```python
from pathlib import Path
from local_deepwiki.core.parser import get_file_hash

file_hash = get_file_hash(Path("example.py"))
```

## Usage Examples

### Basic Parsing Usage

```python
from pathlib import Path
from local_deepwiki.core.parser import parse_file
from local_deepwiki.models import Language

# Parse a Python file
file_path = Path("src/main.py")
file_info = parse_file(file_path, Language.PYTHON)

# Parse a JavaScript file
js_file_path = Path("src/app.js")
js_file_info = parse_file(js_file_path, Language.JAVASCRIPT)
```

### Parser Manager Usage

```python
from local_deepwiki.core.parser import ParserManager
from local_deepwiki.models import Language
from pathlib import Path

# Initialize parser manager
parser_manager = ParserManager()

# Parse a file using the manager
node = parser_manager.parse(Path("example.go"), Language.GO)
```

### File Hash Generation

```python
from pathlib import Path
from local_deepwiki.core.parser import get_file_hash

# Generate hash for a file
file_hash = get_file_hash(Path("src/main.py"))
print(f"File hash: {file_hash}")
```

## Implementation Details

The module initializes language-specific Tree-sitter parsers for Python, JavaScript, TypeScript, Go, Rust, Java, C, and C++. These parsers are used to construct Abstract Syntax Trees (ASTs) for code analysis. The `ParserManager` class serves as a central hub for managing these parsers and provides a unified interface for parsing code files regardless of their programming language.

The module supports the `FileInfo` model for structured representation of parsed file information and uses the `Language` enum to specify the programming language of files being parsed.