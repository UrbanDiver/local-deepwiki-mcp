"""Glossary and index generation for wiki documentation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from local_deepwiki.core.path_utils import is_test_file
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.generators.wiki.utils import file_path_to_wiki_path, has_wiki_page
from local_deepwiki.models import ChunkType, IndexStatus


@dataclass(frozen=True, slots=True)
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

    # Use bulk chunk-type queries (3 queries) instead of N per-file queries
    type_to_entity = {
        "class": ChunkType.CLASS,
        "function": ChunkType.FUNCTION,
        "method": ChunkType.METHOD,
    }

    for entity_type_str, chunk_type_enum in type_to_entity.items():
        for chunk in vector_store.get_all_chunks(chunk_type=entity_type_str):
            if is_test_file(chunk.file_path):
                continue
            metadata = chunk.metadata or {}
            param_types = metadata.get("parameter_types")
            return_type = metadata.get("return_type")
            is_async = metadata.get("is_async", False)
            raises = metadata.get("raises")

            entry_kwargs: dict = {
                "name": chunk.name or "Unknown",
                "entity_type": entity_type_str,
                "file_path": chunk.file_path,
                "docstring": chunk.docstring,
            }

            if entity_type_str in ("function", "method"):
                entry_kwargs.update(
                    parameter_types=param_types,
                    return_type=return_type,
                    is_async=is_async,
                    raises=raises,
                )
            if entity_type_str == "method":
                entry_kwargs["parent_name"] = chunk.parent_name

            entities.append(EntityEntry(**entry_kwargs))

    # Sort alphabetically by name (case-insensitive)
    entities = sorted(entities, key=lambda e: e.name.lower())
    return entities


def group_entities_by_letter(
    entities: list[EntityEntry],
) -> dict[str, list[EntityEntry]]:
    """Group entities by their first letter.

    Args:
        entities: List of entities (should be pre-sorted).

    Returns:
        Dictionary mapping letter to list of entities.
    """
    grouped: dict[str, list[EntityEntry]] = defaultdict(list)

    for entity in entities:
        first_char = entity.name[0].upper() if entity.name else "#"
        if not first_char.isalpha():
            first_char = "#"  # Group non-alphabetic under #
        grouped[first_char].append(entity)

    return grouped


_get_wiki_link = file_path_to_wiki_path


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


_TYPE_BADGES: dict[str, str] = {
    "class": "🔷",
    "function": "🔹",
    "method": "▪️",
}


def _entity_type_badge(entity: "EntityEntry") -> str:
    """Return the type badge string (with async marker if applicable)."""
    base_badge = _TYPE_BADGES.get(entity.entity_type, "")
    async_marker = "⚡" if entity.is_async else ""
    return f"{base_badge}{async_marker}"


def _entity_raises_part(entity: "EntityEntry") -> str:
    """Return a raises indicator string, or empty string if no raises."""
    if not entity.raises:
        return ""
    exc_list = ", ".join(entity.raises[:3])
    if len(entity.raises) > 3:
        exc_list += f", +{len(entity.raises) - 3}"
    return f" ⚠️`{exc_list}`"


def _format_entity_line(entity: "EntityEntry") -> str:
    """Render a single glossary entry as a markdown list item."""
    if entity.entity_type == "method" and entity.parent_name:
        display_name = f"{entity.parent_name}.{entity.name}"
    else:
        display_name = entity.name

    wiki_link = (
        _get_wiki_link(entity.file_path) if has_wiki_page(entity.file_path) else ""
    )
    file_name = Path(entity.file_path).name
    type_badge = _entity_type_badge(entity)
    signature = _format_signature(entity)
    sig_part = f" `{signature}`" if signature else ""
    raises_part = _entity_raises_part(entity)
    desc = _get_brief_description(entity.docstring)
    desc_part = f" - {desc}" if desc else ""

    if wiki_link:
        name_part = f"**[`{display_name}`]({wiki_link})**"
    else:
        name_part = f"**`{display_name}`**"
    return (
        f"- {type_badge} {name_part}{sig_part}{raises_part} (`{file_name}`){desc_part}"
    )


def _render_letter_section(
    letter: str, letter_entities: list["EntityEntry"]
) -> list[str]:
    """Render a collapsible <details> section for one letter group."""
    count = len(letter_entities)
    section: list[str] = [
        f'<details id="{letter.lower()}" markdown="1">',
        f"<summary><strong>{letter}</strong> — {count} entities</summary>",
        "",
    ]
    for entity in letter_entities:
        section.append(_format_entity_line(entity))
    section.extend(["", "</details>", ""])
    return section


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

    grouped = group_entities_by_letter(entities)
    letters = sorted(grouped.keys())

    class_count = sum(1 for e in entities if e.entity_type == "class")
    func_count = sum(1 for e in entities if e.entity_type == "function")
    method_count = sum(1 for e in entities if e.entity_type == "method")

    nav_links = " | ".join(f"[{letter}](#{letter.lower()})" for letter in letters)

    lines = [
        "# Glossary",
        "",
        "Alphabetical index of all classes, functions, and methods in the codebase.",
        "",
        f"**Quick Navigation:** {nav_links}",
        "",
        f"**Total:** {len(entities)} entities "
        f"({class_count} classes, {func_count} functions, {method_count} methods)",
        "",
        "---",
        "",
        "<p>"
        '<a href="#" onclick="document.querySelectorAll(\'details\').forEach(d=>d.open=true);return false">Expand All</a>'
        " | "
        '<a href="#" onclick="document.querySelectorAll(\'details\').forEach(d=>d.open=false);return false">Collapse All</a>'
        "</p>",
        "",
    ]

    for letter in letters:
        lines.extend(_render_letter_section(letter, grouped[letter]))

    lines.extend(
        [
            "---",
            "",
            "**Legend:** 🔷 Class | 🔹 Function | ▪️ Method | ⚡ Async | ⚠️ Raises exceptions",
            "",
        ]
    )

    return "\n".join(lines)
