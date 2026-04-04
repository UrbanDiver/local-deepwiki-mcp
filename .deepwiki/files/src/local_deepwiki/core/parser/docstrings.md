# File: `src/local_deepwiki/core/parser/docstrings.py`

## File Overview

This file provides language-specific logic for extracting docstrings from tree-sitter AST nodes. It serves as a core utility for parsing documentation comments and string literals that represent docstrings in various programming languages, such as Python, JavaScript, Java, Swift, and others.

The design rationale centers on supporting multiple programming languages with distinct comment syntaxes and docstring formats. It uses a modular approach where each language has its own extractor function, and a dispatcher (`get_docstring`) routes to the appropriate one based on the language.

## Key Concepts

### Language-Specific Extractors
The module implements specialized functions to extract docstrings from different languages:
- Python: Extracts docstrings from string literals in the first statement of a function or class body.
- JavaScript: Supports both JSDoc (`/** */`) and multi-line `//` comments.
- Java/Javadoc/Doxygen: Supports both block comments (`/** */`) and line comments (`///`).
- Swift: Supports both `///` line comments and `/** */` block comments.

These extractors are designed to handle common patterns in each language's documentation style, ensuring accurate extraction of meaningful documentation.

### Comment Collection and Processing
A key abstraction is `_collect_preceding_comments`, which traverses AST nodes backwards to [collect](../../web/routes_chat.md) consecutive comment lines. This function respects comment type and optional prefix filtering, allowing for precise selection of relevant documentation.

The `_strip_line_comment_prefix` function then normalizes these comments by removing prefixes and joining them into a single string, preparing them for use as docstrings.

### Dispatch Pattern
The `get_docstring` function implements a simple dispatcher pattern, using a dictionary mapping language enums to extractor functions. This pattern allows for easy extension with new languages by adding new entries to `_DOCSTRING_EXTRACTORS`.

## Integration

This file integrates closely with:
- `local_deepwiki.core.parser.ast_utils`: Uses [`get_node_text`](ast_utils.md) to extract text from tree-sitter nodes.
- [`local_deepwiki.models.Language`](../../models/foundation.md): Provides language identifiers for dispatching to the correct extractor.
- The parser and discovery modules: Called by `discovery` to extract documentation during code analysis.

It is also directly tested by:
- `test_parser_docstrings`
- `test_parser_node_utils`
- `test_test_examples`

These test files validate that docstrings are correctly extracted across various languages and node types.

## Design Notes

### Handling of Comment Prefixes
The module handles comment prefixes explicitly in functions like `_get_javadoc_or_doxygen` and `_get_swift_docstring`. This ensures that only relevant comments (e.g., doc comments) are collected, avoiding noise from regular comments.

### Extraction Order and Node Traversal
Functions like `_get_python_docstring` rely on the structure of the AST (e.g., function/class bodies) to locate docstrings. For example, it checks the first child of a function body to find a string literal representing the docstring.

### Extensibility
The use of a dictionary (`_DOCSTRING_EXTRACTORS`) makes it easy to add new language support. Each new language can be added with a dedicated extractor function, and the dispatcher will route to it automatically.

### Edge Cases
- The module gracefully handles missing nodes or unexpected node types by returning `None`.
- It strips leading and trailing whitespace from extracted docstrings for consistency.
- It ensures that only comments that match a given prefix are considered, allowing for mixed comment types in source code.

This design ensures robustness in parsing across different languages and codebases.

## API Reference

### Functions

#### `get_docstring`

```python
def get_docstring(node: Node, source: bytes, language: LangEnum) -> str | None
```

Extract docstring from a function/class node.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | - | The tree-sitter node. |
| `source` | `bytes` | - | The original source bytes. |
| `language` | `LangEnum` | - | The programming language. |

**Returns:** `str | None`




<details>
<summary>View Source (lines 173-186) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser/docstrings.py#L173-L186">GitHub</a></summary>

```python
def get_docstring(node: Node, source: bytes, language: LangEnum) -> str | None:
    """Extract docstring from a function/class node.

    Args:
        node: The tree-sitter node.
        source: The original source bytes.
        language: The programming language.

    Returns:
        The docstring or None if not found.
    """
    if extractor := _DOCSTRING_EXTRACTORS.get(language):
        return cast(str | None, extractor(node, source))
    return None
```

</details>

## Call Graph

```mermaid
flowchart TD
    N0[_collect_preceding_comments]
    N1[_get_block_comment]
    N2[_get_javadoc_or_doxygen]
    N3[_get_jsdoc_or_line_comments]
    N4[_get_line_comments]
    N5[_get_python_docstring]
    N6[_get_swift_docstring]
    N7[_strip_line_comment_prefix]
    N8[appendleft]
    N9[cast]
    N10[child_by_field_name]
    N11[deque]
    N12[extractor]
    N13[get_docstring]
    N14[get_node_text]
    N0 --> N11
    N0 --> N14
    N0 --> N8
    N5 --> N10
    N5 --> N14
    N3 --> N14
    N3 --> N0
    N3 --> N7
    N4 --> N0
    N4 --> N7
    N2 --> N14
    N2 --> N0
    N2 --> N7
    N6 --> N0
    N6 --> N7
    N6 --> N14
    N1 --> N14
    N13 --> N9
    N13 --> N12
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14 func
```

## Used By

Functions and methods in this file and their callers:

- **`_collect_preceding_comments`**: called by `_get_javadoc_or_doxygen`, `_get_jsdoc_or_line_comments`, `_get_line_comments`, `_get_swift_docstring`
- **`_strip_line_comment_prefix`**: called by `_get_javadoc_or_doxygen`, `_get_jsdoc_or_line_comments`, `_get_line_comments`, `_get_swift_docstring`
- **`appendleft`**: called by `_collect_preceding_comments`
- **`cast`**: called by `get_docstring`
- **`child_by_field_name`**: called by `_get_python_docstring`
- **`deque`**: called by `_collect_preceding_comments`
- **`extractor`**: called by `get_docstring`
- **[`get_node_text`](ast_utils.md)**: called by `_collect_preceding_comments`, `_get_block_comment`, `_get_javadoc_or_doxygen`, `_get_jsdoc_or_line_comments`, `_get_python_docstring`, `_get_swift_docstring`

## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `_collect_preceding_comments` | function | Brian Breidenbach | Feb 21, 2026 | `e45a53a` refactor: apply Pythonic id... |
| `get_docstring` | function | Brian Breidenbach | Feb 21, 2026 | `e45a53a` refactor: apply Pythonic id... |
| `_strip_line_comment_prefix` | function | Brian Breidenbach | Feb 09, 2026 | `99410a9` refactor: split 4 large fil... |
| `_get_python_docstring` | function | Brian Breidenbach | Feb 09, 2026 | `99410a9` refactor: split 4 large fil... |
| `_get_jsdoc_or_line_comments` | function | Brian Breidenbach | Feb 09, 2026 | `99410a9` refactor: split 4 large fil... |
| `_get_line_comments` | function | Brian Breidenbach | Feb 09, 2026 | `99410a9` refactor: split 4 large fil... |
| `_get_javadoc_or_doxygen` | function | Brian Breidenbach | Feb 09, 2026 | `99410a9` refactor: split 4 large fil... |
| `_get_swift_docstring` | function | Brian Breidenbach | Feb 09, 2026 | `99410a9` refactor: split 4 large fil... |
| `_get_block_comment` | function | Brian Breidenbach | Feb 09, 2026 | `99410a9` refactor: split 4 large fil... |

## Additional Source Code

Source code for functions and methods not listed in the API Reference above.

#### `_collect_preceding_comments`

<details>
<summary>View Source (lines 15-44) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser/docstrings.py#L15-L44">GitHub</a></summary>

```python
def _collect_preceding_comments(
    node: Node,
    source: bytes,
    comment_types: set[str],
    prefix: str | None = None,
) -> list[str]:
    """Collect all consecutive preceding comment lines.

    Args:
        node: The tree-sitter node to look before.
        source: The original source bytes.
        comment_types: Set of comment node type names (e.g., {"comment", "line_comment"}).
        prefix: Optional prefix that comments must start with (e.g., "///" for doc comments).

    Returns:
        List of comment text lines in order (first comment first).
    """
    comments: deque[str] = deque()
    prev = node.prev_sibling

    while prev and prev.type in comment_types:
        text = get_node_text(prev, source)
        if prefix is None or text.startswith(prefix):
            comments.appendleft(text)
            prev = prev.prev_sibling
        else:
            # Stop at non-matching comment (e.g., regular // after ///)
            break

    return list(comments)
```

</details>


#### `_strip_line_comment_prefix`

<details>
<summary>View Source (lines 47-64) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser/docstrings.py#L47-L64">GitHub</a></summary>

```python
def _strip_line_comment_prefix(lines: list[str], prefix: str) -> str:
    """Strip prefix from comment lines and join them.

    Args:
        lines: List of comment lines.
        prefix: The prefix to strip (e.g., "//", "///", "#").

    Returns:
        Joined docstring with prefixes removed.
    """
    stripped = []
    for line in lines:
        # Remove the prefix and optional leading space
        content = line[len(prefix) :]
        if content.startswith(" "):
            content = content[1:]
        stripped.append(content)
    return "\n".join(stripped).strip()
```

</details>


#### `_get_python_docstring`

<details>
<summary>View Source (lines 67-86) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser/docstrings.py#L67-L86">GitHub</a></summary>

```python
def _get_python_docstring(node: Node, source: bytes) -> str | None:
    """Extract Python docstring from function/class body."""
    body = node.child_by_field_name("body")
    if not body or not body.children:
        return None

    first_child = body.children[0]
    if first_child.type != "expression_statement":
        return None

    expr = first_child.children[0] if first_child.children else None
    if not expr or expr.type != "string":
        return None

    text = get_node_text(expr, source)
    if text.startswith('"""') or text.startswith("'''"):
        return text[3:-3].strip()
    if text.startswith('"') or text.startswith("'"):
        return text[1:-1].strip()
    return None
```

</details>


#### `_get_jsdoc_or_line_comments`

<details>
<summary>View Source (lines 89-100) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser/docstrings.py#L89-L100">GitHub</a></summary>

```python
def _get_jsdoc_or_line_comments(node: Node, source: bytes) -> str | None:
    """Extract JSDoc (/** */) or multi-line // comments."""
    prev = node.prev_sibling
    if prev and prev.type == "comment":
        text = get_node_text(prev, source)
        if text.startswith("/**"):
            return text[3:-2].strip()

    comments = _collect_preceding_comments(node, source, {"comment"}, "//")
    if comments:
        return _strip_line_comment_prefix(comments, "//")
    return None
```

</details>


#### `_get_line_comments`

<details>
<summary>View Source (lines 103-110) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser/docstrings.py#L103-L110">GitHub</a></summary>

```python
def _get_line_comments(
    node: Node, source: bytes, comment_type: str, prefix: str
) -> str | None:
    """Extract multi-line comments with a specific prefix."""
    comments = _collect_preceding_comments(node, source, {comment_type}, prefix)
    if comments:
        return _strip_line_comment_prefix(comments, prefix)
    return None
```

</details>


#### `_get_javadoc_or_doxygen`

<details>
<summary>View Source (lines 113-124) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser/docstrings.py#L113-L124">GitHub</a></summary>

```python
def _get_javadoc_or_doxygen(node: Node, source: bytes) -> str | None:
    """Extract Javadoc/Doxygen (/** */) or /// comments."""
    prev = node.prev_sibling
    if prev and prev.type in ("comment", "block_comment"):
        text = get_node_text(prev, source)
        if text.startswith("/**"):
            return text[3:-2].strip()

    comments = _collect_preceding_comments(node, source, {"comment"}, "///")
    if comments:
        return _strip_line_comment_prefix(comments, "///")
    return None
```

</details>


#### `_get_swift_docstring`

<details>
<summary>View Source (lines 127-138) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser/docstrings.py#L127-L138">GitHub</a></summary>

```python
def _get_swift_docstring(node: Node, source: bytes) -> str | None:
    """Extract Swift /// comments or /** */ block."""
    comments = _collect_preceding_comments(node, source, {"comment"}, "///")
    if comments:
        return _strip_line_comment_prefix(comments, "///")

    prev = node.prev_sibling
    if prev and prev.type == "comment":
        text = get_node_text(prev, source)
        if text.startswith("/**"):
            return text[3:-2].strip()
    return None
```

</details>


#### `_get_block_comment`

<details>
<summary>View Source (lines 141-148) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/core/parser/docstrings.py#L141-L148">GitHub</a></summary>

```python
def _get_block_comment(node: Node, source: bytes, comment_type: str) -> str | None:
    """Extract /** */ block comment of specified type."""
    prev = node.prev_sibling
    if prev and prev.type == comment_type:
        text = get_node_text(prev, source)
        if text.startswith("/**"):
            return text[3:-2].strip()
    return None
```

</details>

## Relevant Source Files

- `src/local_deepwiki/core/parser/docstrings.py:15-44`
