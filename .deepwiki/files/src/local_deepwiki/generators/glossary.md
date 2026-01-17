# Glossary Generator Module

## File Overview

The `glossary.py` module provides functionality for generating glossary pages in the DeepWiki documentation system. It collects entities from a vector store, organizes them alphabetically, and formats them into a comprehensive glossary with links and descriptions.

## Classes

### EntityEntry

A dataclass that represents an entry in the glossary.

```python
@dataclass
class EntityEntry:
    # Implementation details not shown in provided code
```

This class serves as a data container for individual glossary entries, storing the necessary information for each entity that will be displayed in the glossary.

## Functions

### collect_all_entities

Collects all entities from the vector store for glossary generation.

```python
def collect_all_entities(vector_store: VectorStore) -> list[EntityEntry]:
```

**Parameters:**
- `vector_store`: A [VectorStore](../core/vectorstore.md) instance containing the indexed entities

**Returns:**
- A list of EntityEntry objects representing all collected entities

### group_entities_by_letter

Groups the collected entities alphabetically by their first letter.

```python
def group_entities_by_letter(entities: list[EntityEntry]) -> dict[str, list[EntityEntry]]:
```

**Parameters:**
- `entities`: A list of EntityEntry objects to be grouped

**Returns:**
- A dictionary where keys are letters and values are lists of EntityEntry objects starting with that letter

### _get_wiki_link

A private helper function that generates wiki-style links for entities.

```python
def _get_wiki_link(entity: EntityEntry) -> str:
```

**Parameters:**
- `entity`: An EntityEntry object for which to generate a link

**Returns:**
- A string containing the formatted wiki link

### _get_brief_description

A private helper function that extracts or generates brief descriptions for entities.

```python
def _get_brief_description(entity: EntityEntry) -> str:
```

**Parameters:**
- `entity`: An EntityEntry object for which to generate a description

**Returns:**
- A string containing a brief description of the entity

### _format_signature

A private helper function that formats entity signatures for display.

```python
def _format_signature(entity: EntityEntry) -> str:
```

**Parameters:**
- `entity`: An EntityEntry object whose signature needs formatting

**Returns:**
- A formatted string representation of the entity's signature

### generate_glossary_page

The [main](../export/pdf.md) function that generates the complete glossary page.

```python
def generate_glossary_page(vector_store: VectorStore) -> str:
```

**Parameters:**
- `vector_store`: A [VectorStore](../core/vectorstore.md) instance containing the indexed entities

**Returns:**
- A string containing the complete formatted glossary page

## Usage Examples

### Basic Glossary Generation

```python
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.glossary import generate_glossary_page

# Assuming you have a configured vector store
vector_store = VectorStore(...)

# Generate the complete glossary page
glossary_content = generate_glossary_page(vector_store)
```

### Working with Individual Entities

```python
from local_deepwiki.generators.glossary import collect_all_entities, group_entities_by_letter

# Collect all entities
entities = collect_all_entities(vector_store)

# Group them alphabetically
grouped_entities = group_entities_by_letter(entities)

# Access entities by letter
a_entities = grouped_entities.get('A', [])
```

## Related Components

This module integrates with several other components in the DeepWiki system:

- **[VectorStore](../core/vectorstore.md)**: The primary data source for entities, imported from `local_deepwiki.core.vectorstore`
- **[ChunkType](../models.md)**: Used for entity type classification, imported from `local_deepwiki.models`
- **[IndexStatus](../models.md)**: Used for tracking entity indexing status, imported from `local_deepwiki.models`

The module follows a clear separation of concerns, with private helper functions handling specific formatting tasks and public functions providing the [main](../export/pdf.md) API for glossary generation.

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
| `EntityEntry` | class | Brian Breidenbach | today | `202b96d` Add exception documentation... |
| `collect_all_entities` | function | Brian Breidenbach | today | `202b96d` Add exception documentation... |
| `generate_glossary_page` | function | Brian Breidenbach | today | `202b96d` Add exception documentation... |
| `_format_signature` | function | Brian Breidenbach | today | `ce066c4` Add type annotation extract... |
| `group_entities_by_letter` | function | Brian Breidenbach | today | `8d2ab68` Add inheritance trees, glos... |
| `_get_wiki_link` | function | Brian Breidenbach | today | `8d2ab68` Add inheritance trees, glos... |
| `_get_brief_description` | function | Brian Breidenbach | today | `8d2ab68` Add inheritance trees, glos... |

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

## See Also

- [models](../models.md) - dependency
- [vectorstore](../core/vectorstore.md) - dependency
- [coverage](coverage.md) - shares 4 dependencies
- [inheritance](inheritance.md) - shares 4 dependencies
- [crosslinks](crosslinks.md) - shares 3 dependencies
