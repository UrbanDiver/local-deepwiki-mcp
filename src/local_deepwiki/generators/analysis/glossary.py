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

    # Expand/Collapse all controls
    lines.append(
        "<p>"
        '<a href="#" onclick="document.querySelectorAll(\'details\').forEach(d=>d.open=true);return false">Expand All</a>'
        " | "
        '<a href="#" onclick="document.querySelectorAll(\'details\').forEach(d=>d.open=false);return false">Collapse All</a>'
        "</p>"
    )
    lines.append("")

    # Generate collapsible sections for each letter
    for letter in letters:
        count = len(grouped[letter])
        lines.append(f'<details id="{letter.lower()}" markdown="1">')
        lines.append(f"<summary><strong>{letter}</strong> — {count} entities</summary>")
        lines.append("")

        for entity in grouped[letter]:
            # Build the display name
            if entity.entity_type == "method" and entity.parent_name:
                display_name = f"{entity.parent_name}.{entity.name}"
            else:
                display_name = entity.name

            # Get wiki link (only if the file has a wiki page)
            wiki_link = (
                _get_wiki_link(entity.file_path)
                if has_wiki_page(entity.file_path)
                else ""
            )
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

            if wiki_link:
                name_part = f"**[`{display_name}`]({wiki_link})**"
            else:
                name_part = f"**`{display_name}`**"
            lines.append(
                f"- {type_badge} {name_part}{sig_part}{raises_part} "
                f"(`{file_name}`){desc_part}"
            )

        lines.append("")
        lines.append("</details>")
        lines.append("")

    # Add legend
    lines.append("---")
    lines.append("")
    lines.append(
        "**Legend:** 🔷 Class | 🔹 Function | ▪️ Method | ⚡ Async | ⚠️ Raises exceptions"
    )
    lines.append("")

    return "\n".join(lines)
