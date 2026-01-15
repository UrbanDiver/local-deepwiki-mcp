# test_examples.py

## File Overview

This module extracts usage examples from test files to generate documentation examples. It analyzes test code to [find](manifest.md) meaningful usage patterns that can be included in generated documentation, helping developers understand how to use various code components through real test examples.

## Classes

### UsageExample

A dataclass that represents a usage example extracted from test code.

## Functions

### find_test_file

Locates the corresponding test file for a given source file.

### _get_node_text

Extracts the text content from a tree-sitter Node.

### _find_test_functions

Identifies test functions within the parsed code tree.

### walk

Traverses nodes in a tree structure, likely for AST navigation.

### _get_function_name

Retrieves the name of a function from its AST node.

### _get_docstring

Extracts the docstring from a function node.

### _get_function_body

Gets the body content of a function from its AST representation.

### _is_mock_heavy

Determines if a test function contains excessive mocking that would make it unsuitable as a usage example.

### _extract_usage_snippet

Extracts a clean, usable code snippet from a test function.

### extract_examples_for_entities

Finds and extracts usage examples for specific code entities from their corresponding test files.

### format_examples_markdown

Formats extracted usage examples into markdown format for documentation.

### get_file_examples

Retrieves all usage examples from a specific test file.

## Related Components

This module works with several other components:

- [CodeParser](../core/parser.md): Used for parsing source code files
- [Language](../models.md): Enum for specifying programming languages
- Node: Tree-sitter node type for AST manipulation
- Logger: For logging operations during example extraction

The module integrates with the broader documentation generation system by providing real-world usage examples extracted from test files, making the generated documentation more practical and helpful for developers.

## API Reference

### class `UsageExample`

A usage example extracted from a test file.

---

### Functions

#### `find_test_file`

```python
def find_test_file(source_file: Path, repo_root: Path) -> Path | None
```

Find the corresponding test file for a source file.  Tries multiple strategies: 1. Direct match: src/.../foo.py -> tests/test_foo.py 2. Nested match: src/pkg/mod/foo.py -> tests/test_foo.py


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_file` | `Path` | - | Path to the source file. |
| `repo_root` | `Path` | - | Root directory of the repository. |

**Returns:** `Path | None`


#### `walk`

```python
def walk(node: Node) -> None
```


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | - | - |

**Returns:** `None`


#### `extract_examples_for_entities`

```python
def extract_examples_for_entities(test_file: Path, entity_names: list[str], max_examples_per_entity: int = 2) -> list[UsageExample]
```

Extract usage examples from a test file for given entities.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `test_file` | `Path` | - | Path to the test file. |
| `entity_names` | `list[str]` | - | Names of functions/classes to [find](manifest.md) examples for. |
| `max_examples_per_entity` | `int` | `2` | Maximum examples per entity. |

**Returns:** `list[UsageExample]`


#### `format_examples_markdown`

```python
def format_examples_markdown(examples: list[UsageExample], max_examples: int = 5) -> str
```

Format usage examples as markdown.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `examples` | `list[UsageExample]` | - | List of UsageExample objects. |
| `max_examples` | `int` | `5` | Maximum examples to include. |

**Returns:** `str`


#### `get_file_examples`

```python
def get_file_examples(source_file: Path, repo_root: Path, entity_names: list[str], max_examples: int = 5) -> str | None
```

Get formatted usage examples for a source file.  This is the [main](../export/pdf.md) entry point for the wiki generator.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_file` | `Path` | - | Path to the source file being documented. |
| `repo_root` | `Path` | - | Root directory of the repository. |
| `entity_names` | `list[str]` | - | Names of functions/classes in the source file. |
| `max_examples` | `int` | `5` | Maximum examples to include. |

**Returns:** `str | None`



## Class Diagram

```mermaid
classDiagram
    class UsageExample {
        +entity_name: str  # Name of the function/class being demonstrated
        +test_name: str  # Name of the test function
        +test_file: str  # Path to the test file
        +code: str  # Extracted code snippet
        +description: str | None  # From test docstring
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[CodeParser]
    N1[UsageExample]
    N2[_extract_usage_snippet]
    N3[_find_test_functions]
    N4[_get_docstring]
    N5[_get_function_body]
    N6[_get_function_name]
    N7[_get_node_text]
    N8[_is_mock_heavy]
    N9[child_by_field_name]
    N10[decode]
    N11[dedent]
    N12[exists]
    N13[extract_examples_for_entities]
    N14[find_test_file]
    N15[format_examples_markdown]
    N16[get_file_examples]
    N17[parse_source]
    N18[read_bytes]
    N19[walk]
    N14 --> N12
    N7 --> N10
    N3 --> N9
    N3 --> N10
    N3 --> N19
    N19 --> N9
    N19 --> N10
    N19 --> N19
    N6 --> N9
    N6 --> N7
    N4 --> N9
    N4 --> N7
    N5 --> N9
    N5 --> N7
    N2 --> N5
    N2 --> N11
    N13 --> N0
    N13 --> N18
    N13 --> N17
    N13 --> N3
    N13 --> N5
    N13 --> N8
    N13 --> N2
    N13 --> N6
    N13 --> N4
    N13 --> N1
    N16 --> N14
    N16 --> N13
    N16 --> N15
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16,N17,N18,N19 func
```

## Relevant Source Files

- `src/local_deepwiki/generators/test_examples.py:22-29`

## See Also

- [logging](../logging.md) - dependency
- [models](../models.md) - dependency
- [chunker](../core/chunker.md) - shares 5 dependencies
- [api_docs](api_docs.md) - shares 5 dependencies
