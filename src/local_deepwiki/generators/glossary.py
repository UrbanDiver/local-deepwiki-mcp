"""Glossary and index generation for wiki documentation."""

from dataclasses import dataclass
from pathlib import Path

from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.models import ChunkType, IndexStatus


@dataclass
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
                    )
                )

    # Sort alphabetically by name (case-insensitive)
    entities.sort(key=lambda e: e.name.lower())
    return entities


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

            # Brief description
            desc = _get_brief_description(entity.docstring)
            desc_part = f" - {desc}" if desc else ""

            lines.append(
                f"- {type_badge} **[`{display_name}`]({wiki_link})**{sig_part} "
                f"(`{file_name}`){desc_part}"
            )

        lines.append("")

    # Add legend
    lines.append("---")
    lines.append("")
    lines.append("**Legend:** 🔷 Class | 🔹 Function | ▪️ Method | ⚡ Async")
    lines.append("")

    return "\n".join(lines)
