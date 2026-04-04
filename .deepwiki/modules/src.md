# Module: local_deepwiki.core.parser.docstrings

## Module Purpose

The `local_deepwiki.core.parser.docstrings` module provides language-specific functionality for extracting docstrings from tree-sitter AST nodes. It handles various documentation formats across multiple programming languages including Python, JavaScript, Java, Swift, and others, enabling the extraction of rich documentation content from code during the parsing and indexing process.

## Key Classes and Functions

### Functions

- **_collect_preceding_comments**
  - Collects all consecutive preceding comment lines before a given tree-sitter node
  - Parameters:
    - `node`: The tree-sitter node to look before
    - `source`: The original source bytes
    - `comment_types`: Set of comment node type names
    - `prefix`: Optional prefix that comments must start with
  - Returns: List of comment text lines in order (first comment first)

- **_strip_line_comment_prefix**
  - Strips prefix from comment lines and joins them
  - Parameters:
    - `lines`: List of comment lines
    - `prefix`: The prefix to strip (e.g., "//", "///", "#")
  - Returns: Joined docstring with prefixes removed

- **_get_python_docstring**
  - Extracts Python docstring from function/class body
  - Parameters:
    - `node`: The tree-sitter node
    - `source`: The original source bytes
  - Returns: The docstring or None if not found

- **_get_jsdoc_or_line_comments**
  - Extracts JSDoc (/** */) or multi-line // comments
  - Parameters:
    - `node`: The tree-sitter node
    - `source`: The original source bytes
  - Returns: The docstring or None if not found

- **_get_line_comments**
  - Extracts multi-line comments with a specific prefix
  - Parameters:
    - `node`: The tree-sitter node
    - `source`: The original source bytes
    - `comment_type`: The type of comment node
    - `prefix`: The prefix to strip
  - Returns: The docstring or None if not found

- **_get_javadoc_or_doxygen**
  - Extracts Javadoc/Doxygen (/** */) or /// comments
  - Parameters:
    - `node`: The tree-sitter node
    - `source`: The original source bytes
  - Returns: The docstring or None if not found

- **_get_swift_docstring**
  - Extracts Swift /// comments or /** */ block
  - Parameters:
    - `node`: The tree-sitter node
    - `source`: The original source bytes
  - Returns: The docstring or None if not found

- **_get_block_comment**
  - Extracts /** */ block comment of specified type
  - Parameters:
    - `node`: The tree-sitter node
    - `source`: The original source bytes
    - `comment_type`: The type of comment node
  - Returns: The docstring or None if not found

- **[get_docstring](../files/src/local_deepwiki/core/parser/docstrings.md)**
  - Extracts docstring from a function/class node
  - Parameters:
    - `node`: The tree-sitter node
    - `source`: The original source bytes
    - `language`: The programming language
  - Returns: The docstring or None if not found

## How Components Interact

The module works by using language-specific extractor functions that are mapped to each supported programming language. The [`get_docstring`](../files/src/local_deepwiki/core/parser/docstrings.md) function serves as the main entry point, which dispatches to the appropriate language-specific extractor based on the provided language parameter. The helper functions like `_collect_preceding_comments` and `_strip_line_comment_prefix` are used by the language-specific extractors to gather and process comment text from the AST.

## Usage Examples

```python
from local_deepwiki.core.parser.docstrings import get_docstring
from local_deepwiki.models import Language as LangEnum
from tree_sitter import Node

# Extract docstring from a Python function node
docstring = get_docstring(node, source_bytes, LangEnum.PYTHON)

# Extract docstring from a JavaScript function node
docstring = get_docstring(node, source_bytes, LangEnum.JAVASCRIPT)
```

## Dependencies

- `collections.deque`
- `functools.partial`
- `typing.Any`
- `typing.cast`
- `tree-sitter.Node`
- [`local_deepwiki.core.parser.ast_utils.get_node_text`](../files/src/local_deepwiki/core/parser/ast_utils.md)
- [`local_deepwiki.models.Language`](../files/src/local_deepwiki/models/foundation.md)

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/core/parser/docstrings.py:15-44`](../files/src/local_deepwiki/core/parser/docstrings.md)
- [`src/local_deepwiki/core/parser/languages.py`](../files/src/local_deepwiki/core/parser/languages.md)
- [`src/local_deepwiki/models/foundation.py:16-31`](../files/src/local_deepwiki/models/foundation.md)
- [`src/local_deepwiki/logging.py:28-83`](../files/src/local_deepwiki/logging.md)
- [`src/local_deepwiki/server.py:92-94`](../files/src/local_deepwiki/server.md)
- [`src/local_deepwiki/cli_progress.py:147-199`](../files/src/local_deepwiki/cli_progress.md)
- [`src/local_deepwiki/events.py:35-63`](../files/src/local_deepwiki/events.md)
- `src/local_deepwiki/__init__.py`
- [`src/local_deepwiki/prompts.py:28-72`](../files/src/local_deepwiki/prompts.md)
- [`src/local_deepwiki/error_factories.py:47-83`](../files/src/local_deepwiki/error_factories.md)


*Showing 10 of 263 source files.*
