# Glossary Generator Module

## File Overview

This module provides functionality for generating a glossary/index page from codebase entities. It collects classes, functions, and methods from indexed files and formats them into a structured markdown document. The module depends on [`VectorStore`](../core/vectorstore.md) for retrieving code chunks and [`IndexStatus`](../models.md) for file information.

## Classes

### EntityEntry

An entry in the glossary.

**Attributes**:
- `name`: str - The name of the entity.
- `entity_type`: str - Type of entity, e.g., 'class', 'function', 'method'.
- `file_path`: str - Path to the source file.
- `parent_name`: str | None - Name of the parent class or module, if applicable.
- `docstring`: str | None - The docstring of the entity.
- `parameter_types`: dict[str, str] | None - Mapping of parameter names to their types.
- `return_type`: str | None - The return type annotation.
- `is_async`: bool - Whether the entity is asynchronous.
- `raises`: list[str] | None - List of exceptions raised by the entity.

## Functions

### collect_all_entities

Collect all classes, functions, and methods from the codebase.

**Parameters**:
- `index_status`: [IndexStatus](../models.md) - Index status with file information.
- `vector_store`: [VectorStore](../core/vectorstore.md) - Vector store with code chunks.

**Returns**:
- List of `EntityEntry` objects sorted alphabetically by name.

### group_entities_by_letter

Group entities by their first letter.

**Parameters**:
- `entities`: list[EntityEntry] - List of entities (should be pre-sorted).

**Returns**:
- Dictionary mapping letter to list of entities.

### _get_wiki_link

Convert a source file path to a wiki link.

**Parameters**:
- `file_path`: str - Source file path like 'src/module/file.py'.

**Returns**:
- Wiki link like 'files/src/module/file.md'.

### _get_brief_description

Extract a brief description from a docstring.

**Parameters**:
- `docstring`: str | None - Full docstring or None.
- `max_length`: int - Maximum length of the description.

**Returns**:
- Brief description string.

### _format_signature

Format a compact function/method signature showing types.

**Parameters**:
- `entity`: EntityEntry - The entity entry with type information.
- `max_params`: int - Maximum number of parameters to show before truncating.

**Returns**:
- Formatted signature string like "(x: int, y: str) -> bool" or empty string.

### generate_glossary_page

Generate the glossary/index page content.

**Parameters**:
- `index_status`: [IndexStatus](../models.md) - Index status with file information.
- `vector_store`: [VectorStore](../core/vectorstore.md) - Vector store with code chunks.

**Returns**:
- Markdown content for the glossary page, or None if no entities found.

## Integration

This module is used by the `test_wiki_coverage` test suite and integrates with the [`VectorStore`](../core/vectorstore.md) and [`IndexStatus`](../models.md) components. It is called by the `group_entities_by_letter` function from `test_glossary` and by `_get_wiki_link` from `coverage`. The module forms part of the documentation generation pipeline, working closely with [`WikiGenerator`](wiki.md) and `SourceRefsGenerator`.

## Usage Examples

```python
# Collect all entities from the codebase
entities = await collect_all_entities(index_status, vector_store)

# Group entities by first letter
grouped_entities = group_entities_by_letter(entities)

# Generate a glossary page
glossary_content = await generate_glossary_page(index_status, vector_store)
```

## API Reference

### class `EntityEntry`

An entry in the glossary.

---


<details>
<summary>View Source (lines 11-24) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/glossary.py#L11-L24">GitHub</a></summary>

```python
class EntityEntry:
    """An entry in the glossary."""

    name: str
    entity_type: str  # 'class', 'function', 'method'
    file_path: str
    parent_name: str | None = None
    docstring: str | None = None
    # Type annotation metadata
    parameter_types: dict[str, str] | None = None
    return_type: str | None = None
    is_async: bool = False
    # Exception metadata
    raises: list[str] | None = None
```

</details>

### Functions

#### `collect_all_entities`

```python
async def collect_all_entities(index_status: IndexStatus, vector_store: VectorStore) -> list[EntityEntry]
```

Collect all classes, functions, and methods from the codebase.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `index_status` | [`IndexStatus`](../models.md) | - | Index status with file information. |
| `vector_store` | [`VectorStore`](../core/vectorstore.md) | - | Vector store with code chunks. |

**Returns:** `list[EntityEntry]`



<details>
<summary>View Source (lines 27-92) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/glossary.py#L27-L92">GitHub</a></summary>

```python
async def collect_all_entities(
    index_status: IndexStatus,
    vector_store: VectorStore,
) -> list[EntityEntry]:
    """Collect all classes, functions, and methods from the codebase.

    Args:
        index_status: Index status with file information.
        vector_store: Vector store with code chunks.

    Returns:
        List of EntityEntry objects sorted alphabetically by name.
    """
    entities: list[EntityEntry] = []

    for file_info in index_status.files:
        chunks = await vector_store.get_chunks_by_file(file_info.path)

        for chunk in chunks:
            # Extract type annotation metadata if available
            metadata = chunk.metadata or {}
            param_types = metadata.get("parameter_types")
            return_type = metadata.get("return_type")
            is_async = metadata.get("is_async", False)
            raises = metadata.get("raises")

            if chunk.chunk_type == ChunkType.CLASS:
                entities.append(
                    EntityEntry(
                        name=chunk.name or "Unknown",
                        entity_type="class",
                        file_path=file_info.path,
                        docstring=chunk.docstring,
                    )
                )
            elif chunk.chunk_type == ChunkType.FUNCTION:
                entities.append(
                    EntityEntry(
                        name=chunk.name or "Unknown",
                        entity_type="function",
                        file_path=file_info.path,
                        docstring=chunk.docstring,
                        parameter_types=param_types,
                        return_type=return_type,
                        is_async=is_async,
                        raises=raises,
                    )
                )
            elif chunk.chunk_type == ChunkType.METHOD:
                entities.append(
                    EntityEntry(
                        name=chunk.name or "Unknown",
                        entity_type="method",
                        file_path=file_info.path,
                        parent_name=chunk.parent_name,
                        docstring=chunk.docstring,
                        parameter_types=param_types,
                        return_type=return_type,
                        is_async=is_async,
                        raises=raises,
                    )
                )

    # Sort alphabetically by name (case-insensitive)
    entities.sort(key=lambda e: e.name.lower())
    return entities
```

</details>

#### `group_entities_by_letter`

```python
def group_entities_by_letter(entities: list[EntityEntry]) -> dict[str, list[EntityEntry]]
```

Group entities by their first letter.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `entities` | `list[EntityEntry]` | - | List of entities (should be pre-sorted). |

**Returns:** `dict[str, list[EntityEntry]]`



<details>
<summary>View Source (lines 95-115) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/glossary.py#L95-L115">GitHub</a></summary>

```python
def group_entities_by_letter(entities: list[EntityEntry]) -> dict[str, list[EntityEntry]]:
    """Group entities by their first letter.

    Args:
        entities: List of entities (should be pre-sorted).

    Returns:
        Dictionary mapping letter to list of entities.
    """
    grouped: dict[str, list[EntityEntry]] = {}

    for entity in entities:
        first_char = entity.name[0].upper() if entity.name else "#"
        if not first_char.isalpha():
            first_char = "#"  # Group non-alphabetic under #

        if first_char not in grouped:
            grouped[first_char] = []
        grouped[first_char].append(entity)

    return grouped
```

</details>

#### `generate_glossary_page`

```python
async def generate_glossary_page(index_status: IndexStatus, vector_store: VectorStore) -> str | None
```

Generate the glossary/index page content.


| [Parameter](api_docs.md) | Type | Default | Description |
|-----------|------|---------|-------------|
| `index_status` | [`IndexStatus`](../models.md) | - | Index status with file information. |
| `vector_store` | [`VectorStore`](../core/vectorstore.md) | - | Vector store with code chunks. |

**Returns:** `str | None`




<details>
<summary>View Source (lines 202-303) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/glossary.py#L202-L303">GitHub</a></summary>

```python
async def generate_glossary_page(
    index_status: IndexStatus,
    vector_store: VectorStore,
) -> str | None:
    """Generate the glossary/index page content.

    Args:
        index_status: Index status with file information.
        vector_store: Vector store with code chunks.

    Returns:
        Markdown content for the glossary page, or None if no entities found.
    """
    entities = await collect_all_entities(index_status, vector_store)

    if not entities:
        return None

    lines = [
        "# Glossary",
        "",
        "Alphabetical index of all classes, functions, and methods in the codebase.",
        "",
    ]

    # Add quick navigation
    grouped = group_entities_by_letter(entities)
    letters = sorted(grouped.keys())

    # Letter navigation bar
    nav_links = " | ".join(f"[{letter}](#{letter.lower()})" for letter in letters)
    lines.append(f"**Quick Navigation:** {nav_links}")
    lines.append("")

    # Summary stats
    class_count = sum(1 for e in entities if e.entity_type == "class")
    func_count = sum(1 for e in entities if e.entity_type == "function")
    method_count = sum(1 for e in entities if e.entity_type == "method")

    lines.append(
        f"**Total:** {len(entities)} entities "
        f"({class_count} classes, {func_count} functions, {method_count} methods)"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Generate sections for each letter
    for letter in letters:
        lines.append(f"## {letter}")
        lines.append("")

        for entity in grouped[letter]:
            # Build the display name
            if entity.entity_type == "method" and entity.parent_name:
                display_name = f"{entity.parent_name}.{entity.name}"
            else:
                display_name = entity.name

            # Get wiki link
            wiki_link = _get_wiki_link(entity.file_path)
            file_name = Path(entity.file_path).name

            # Type badge (with async indicator)
            base_badge = {
                "class": "🔷",
                "function": "🔹",
                "method": "▪️",
            }.get(entity.entity_type, "")
            async_marker = "⚡" if entity.is_async else ""
            type_badge = f"{base_badge}{async_marker}"

            # Type signature for functions/methods
            signature = _format_signature(entity)
            sig_part = f" `{signature}`" if signature else ""

            # Raises indicator
            raises_part = ""
            if entity.raises:
                exc_list = ", ".join(entity.raises[:3])
                if len(entity.raises) > 3:
                    exc_list += f", +{len(entity.raises) - 3}"
                raises_part = f" ⚠️`{exc_list}`"

            # Brief description
            desc = _get_brief_description(entity.docstring)
            desc_part = f" - {desc}" if desc else ""

            lines.append(
                f"- {type_badge} **[`{display_name}`]({wiki_link})**{sig_part}{raises_part} "
                f"(`{file_name}`){desc_part}"
            )

        lines.append("")

    # Add legend
    lines.append("---")
    lines.append("")
    lines.append("**Legend:** 🔷 Class | 🔹 Function | ▪️ Method | ⚡ Async | ⚠️ Raises exceptions")
    lines.append("")

    return "\n".join(lines)
```

</details>

## Class Diagram

```mermaid
classDiagram
    class EntityEntry {
        +name: str
        +entity_type: str  # 'class', 'function', 'method'
        +file_path: str
        +parent_name: str | None
        +docstring: str | None
        +parameter_types: dict[str, str] | None
        +return_type: str | None
        +is_async: bool
        +raises: list[str] | None
    }
```

## Call Graph

```mermaid
flowchart TD
    N0[EntityEntry]
    N1[Path]
    N2[_format_signature]
    N3[_get_brief_description]
    N4[_get_wiki_link]
    N5[collect_all_entities]
    N6[generate_glossary_page]
    N7[get_chunks_by_file]
    N8[group_entities_by_letter]
    N9[isalpha]
    N10[sort]
    N5 --> N7
    N5 --> N0
    N5 --> N10
    N8 --> N9
    N6 --> N5
    N6 --> N8
    N6 --> N4
    N6 --> N1
    N6 --> N2
    N6 --> N3
    classDef func fill:#e1f5fe
    class N0,N1,N2,N3,N4,N5,N6,N7,N8,N9,N10 func
```

## Used By

Functions and methods in this file and their callers:

- **`EntityEntry`**: called by `collect_all_entities`
- **`Path`**: called by `generate_glossary_page`
- **`_format_signature`**: called by `generate_glossary_page`
- **`_get_brief_description`**: called by `generate_glossary_page`
- **`_get_wiki_link`**: called by `generate_glossary_page`
- **`collect_all_entities`**: called by `generate_glossary_page`
- **`get_chunks_by_file`**: called by `collect_all_entities`
- **`group_entities_by_letter`**: called by `generate_glossary_page`
- **`isalpha`**: called by `group_entities_by_letter`
- **`sort`**: called by `collect_all_entities`

## Usage Examples

*Examples extracted from test files*

### Test creating a function entry

From `test_glossary.py::TestEntityEntry::test_creates_function_entry`:

```python
entry = EntityEntry(
    name="my_function",
    entity_type="function",
    file_path="src/module.py",
)
assert entry.name == "my_function"
assert entry.entity_type == "function"
```

### Test creating a method entry with parent class

From `test_glossary.py::TestEntityEntry::test_creates_method_entry_with_parent`:

```python
entry = EntityEntry(
    name="my_method",
    entity_type="method",
    file_path="src/module.py",
    parent_name="MyClass",
    docstring="A method docstring.",
)
assert entry.parent_name == "MyClass"
assert entry.docstring == "A method docstring."
```

### Test that entities are grouped by first letter

From `test_glossary.py::TestGroupEntitiesByLetter::test_groups_alphabetically`:

```python
entities = [
    EntityEntry("apple", "function", "a.py"),
    EntityEntry("apricot", "function", "a.py"),
    EntityEntry("banana", "class", "b.py"),
]
grouped = group_entities_by_letter(entities)
assert "A" in grouped
assert "B" in grouped
assert len(grouped["A"]) == 2
assert len(grouped["B"]) == 1
```

### Test that grouping is case-insensitive

From `test_glossary.py::TestGroupEntitiesByLetter::test_case_insensitive_grouping`:

```python
entities = [
    EntityEntry("Apple", "function", "a.py"),
    EntityEntry("apple", "function", "a.py"),
]
grouped = group_entities_by_letter(entities)
assert "A" in grouped
assert len(grouped["A"]) == 2
```

### Test simple file path conversion

From `test_glossary.py::TestGetWikiLink::test_simple_path`:

```python
result = _get_wiki_link("src/module.py")
assert result == "files/src/module.md"
```


## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `EntityEntry` | class | Brian Breidenbach | 3 weeks ago | `202b96d` Add exception documentation... |
| `collect_all_entities` | function | Brian Breidenbach | 3 weeks ago | `202b96d` Add exception documentation... |
| `generate_glossary_page` | function | Brian Breidenbach | 3 weeks ago | `202b96d` Add exception documentation... |
| `_format_signature` | function | Brian Breidenbach | 3 weeks ago | `ce066c4` Add type annotation extract... |
| `group_entities_by_letter` | function | Brian Breidenbach | 3 weeks ago | `8d2ab68` Add inheritance trees, glos... |
| `_get_wiki_link` | function | Brian Breidenbach | 3 weeks ago | `8d2ab68` Add inheritance trees, glos... |
| `_get_brief_description` | function | Brian Breidenbach | 3 weeks ago | `8d2ab68` Add inheritance trees, glos... |

## Additional Source Code

Source code for functions and methods not listed in the API Reference above.

#### `_get_wiki_link`

<details>
<summary>View Source (lines 118-129) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/glossary.py#L118-L129">GitHub</a></summary>

```python
def _get_wiki_link(file_path: str) -> str:
    """Convert a source file path to a wiki link.

    Args:
        file_path: Source file path like 'src/module/file.py'.

    Returns:
        Wiki link like 'files/src/module/file.md'.
    """
    # Replace .py extension with .md and prepend files/
    wiki_path = file_path.replace(".py", ".md")
    return f"files/{wiki_path}"
```

</details>


#### `_get_brief_description`

<details>
<summary>View Source (lines 132-157) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/glossary.py#L132-L157">GitHub</a></summary>

```python
def _get_brief_description(docstring: str | None, max_length: int = 60) -> str:
    """Extract a brief description from a docstring.

    Args:
        docstring: Full docstring or None.
        max_length: Maximum length of the description.

    Returns:
        Brief description string.
    """
    if not docstring:
        return ""

    # Get first line
    first_line = docstring.split("\n")[0].strip()

    # Remove common prefixes
    for prefix in ["Args:", "Returns:", "Raises:", "Example:", "Note:"]:
        if first_line.startswith(prefix):
            return ""

    # Truncate if needed
    if len(first_line) > max_length:
        return first_line[: max_length - 3] + "..."

    return first_line
```

</details>


#### `_format_signature`

<details>
<summary>View Source (lines 160-199) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/[main](../export/pdf.md)/src/local_deepwiki/generators/glossary.py#L160-L199">GitHub</a></summary>

```python
def _format_signature(entity: EntityEntry, max_params: int = 3) -> str:
    """Format a compact function/method signature showing types.

    Args:
        entity: The entity entry with type information.
        max_params: Maximum number of parameters to show before truncating.

    Returns:
        Formatted signature string like "(x: int, y: str) -> bool" or empty string.
    """
    if entity.entity_type == "class":
        return ""

    parts = []

    # Format parameters
    if entity.parameter_types:
        param_strs = []
        param_items = list(entity.parameter_types.items())
        shown_params = param_items[:max_params]
        remaining = len(param_items) - max_params

        for name, type_hint in shown_params:
            if type_hint:
                param_strs.append(f"{name}: {type_hint}")
            else:
                param_strs.append(name)

        if remaining > 0:
            param_strs.append(f"...+{remaining}")

        parts.append(f"({', '.join(param_strs)})")
    else:
        parts.append("(...)")

    # Add return type
    if entity.return_type:
        parts.append(f" → {entity.return_type}")

    return "".join(parts)
```

</details>

## Relevant Source Files

- `src/local_deepwiki/generators/glossary.py:11-24`
