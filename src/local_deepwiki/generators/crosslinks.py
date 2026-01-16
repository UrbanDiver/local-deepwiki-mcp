"""Cross-linking functionality for wiki pages.

This module provides functionality to automatically create hyperlinks between
wiki pages when classes, functions, or other documented entities are mentioned.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from local_deepwiki.models import ChunkType, CodeChunk, WikiPage


@dataclass
class EntityInfo:
    """Information about a documented entity."""

    name: str
    entity_type: ChunkType
    wiki_path: str
    file_path: str
    parent_name: str | None = None


def camel_to_spaced(name: str) -> str | None:
    """Convert CamelCase to 'Spaced Words'.

    Examples:
        VectorStore -> Vector Store
        WikiGenerator -> Wiki Generator
        LLMProvider -> LLM Provider

    Args:
        name: The CamelCase name.

    Returns:
        Spaced version or None if not applicable.
    """
    if not name or "_" in name or name.islower() or name.isupper():
        return None

    # Insert space before uppercase letters that follow lowercase letters
    # Also handle sequences of uppercase (e.g., LLMProvider -> LLM Provider)
    result = []
    prev_upper = False
    for i, char in enumerate(name):
        if char.isupper():
            if i > 0 and not prev_upper:
                result.append(" ")
            elif i > 0 and prev_upper and i + 1 < len(name) and name[i + 1].islower():
                # Handle LLMProvider -> LLM Provider
                result.append(" ")
            prev_upper = True
        else:
            prev_upper = False
        result.append(char)

    spaced = "".join(result)
    # Only return if actually different
    return spaced if spaced != name else None


class EntityRegistry:
    """Registry of documented entities and their wiki page locations.

    This class maintains a mapping of entity names (classes, functions, etc.)
    to their documentation page paths, enabling cross-linking between pages.
    """

    def __init__(self) -> None:
        """Initialize an empty entity registry."""
        # Map of entity name -> EntityInfo
        self._entities: dict[str, EntityInfo] = {}
        # Map of alias (spaced name) -> canonical name
        self._aliases: dict[str, str] = {}
        # Map of wiki_path -> list of entities defined in that page
        self._page_entities: dict[str, list[str]] = {}
        # Set of common words to exclude from linking
        self._excluded_names: set[str] = {
            # Python builtins and common names
            "self",
            "cls",
            "None",
            "True",
            "False",
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "set",
            "tuple",
            "type",
            "object",
            "Exception",
            "Error",
            "Any",
            "Optional",
            "List",
            "Dict",
            "Set",
            "Tuple",
            "Union",
            "Callable",
            "Type",
            "Path",
            "Field",
            # Common short names that cause false positives
            "id",
            "name",
            "path",
            "data",
            "config",
            "result",
            "value",
            "key",
            "item",
            "index",
            "count",
            "size",
            "length",
            "text",
            "content",
            "status",
            "info",
            "error",
            "message",
            "query",
            "file",
            "line",
            "chunk",
            "page",
            "model",
            "base",
            "test",
        }

    def register_entity(
        self,
        name: str,
        entity_type: ChunkType,
        wiki_path: str,
        file_path: str,
        parent_name: str | None = None,
    ) -> None:
        """Register a documented entity.

        Args:
            name: The entity name (e.g., "WikiGenerator").
            entity_type: The type of entity (class, function, etc.).
            wiki_path: Path to the wiki page documenting this entity.
            file_path: Path to the source file containing this entity.
            parent_name: Parent entity name (e.g., class name for methods).
        """
        if not name or name in self._excluded_names:
            return

        # Skip private/dunder names
        if name.startswith("_"):
            return

        # Skip very short names (likely to cause false positives)
        if len(name) < 4:
            return

        entity = EntityInfo(
            name=name,
            entity_type=entity_type,
            wiki_path=wiki_path,
            file_path=file_path,
            parent_name=parent_name,
        )

        self._entities[name] = entity
        self._page_entities.setdefault(wiki_path, []).append(name)

        # Register spaced alias for CamelCase names
        spaced = camel_to_spaced(name)
        if spaced and spaced not in self._aliases:
            self._aliases[spaced] = name

    def register_from_chunks(
        self,
        chunks: list[CodeChunk],
        wiki_path: str,
    ) -> None:
        """Register entities from a list of code chunks.

        Args:
            chunks: List of code chunks from a file.
            wiki_path: Path to the wiki page for these chunks.
        """
        for chunk in chunks:
            if chunk.name and chunk.chunk_type in (
                ChunkType.CLASS,
                ChunkType.FUNCTION,
            ):
                self.register_entity(
                    name=chunk.name,
                    entity_type=chunk.chunk_type,
                    wiki_path=wiki_path,
                    file_path=chunk.file_path,
                    parent_name=chunk.parent_name,
                )

    def get_entity(self, name: str) -> EntityInfo | None:
        """Get entity info by name.

        Args:
            name: The entity name to look up.

        Returns:
            EntityInfo if found, None otherwise.
        """
        return self._entities.get(name)

    def get_entity_by_alias(self, alias: str) -> tuple[str, EntityInfo] | None:
        """Get entity info by alias (spaced name).

        Args:
            alias: The spaced alias to look up (e.g., "Vector Store").

        Returns:
            Tuple of (canonical_name, EntityInfo) if found, None otherwise.
        """
        canonical = self._aliases.get(alias)
        if canonical:
            entity = self._entities.get(canonical)
            if entity:
                return (canonical, entity)
        return None

    def get_all_aliases(self) -> dict[str, str]:
        """Get all registered aliases.

        Returns:
            Dictionary mapping aliases to canonical names.
        """
        return self._aliases.copy()

    def get_all_entities(self) -> dict[str, EntityInfo]:
        """Get all registered entities.

        Returns:
            Dictionary mapping entity names to EntityInfo.
        """
        return self._entities.copy()

    def get_page_entities(self, wiki_path: str) -> list[str]:
        """Get all entities defined in a specific wiki page.

        Args:
            wiki_path: The wiki page path.

        Returns:
            List of entity names defined in that page.
        """
        return self._page_entities.get(wiki_path, [])


class CrossLinker:
    """Adds cross-links to wiki page content.

    This class processes wiki page content and replaces mentions of
    documented entities with markdown links to their documentation pages.
    """

    def __init__(self, registry: EntityRegistry) -> None:
        """Initialize the cross-linker.

        Args:
            registry: The entity registry to use for lookups.
        """
        self.registry = registry

    def add_links(self, page: WikiPage) -> WikiPage:
        """Add cross-links to a wiki page.

        Args:
            page: The wiki page to process.

        Returns:
            A new WikiPage with cross-links added.
        """
        content = self._process_content(page.content, page.path)

        return WikiPage(
            path=page.path,
            title=page.title,
            content=content,
            generated_at=page.generated_at,
        )

    def _process_content(self, content: str, current_page: str) -> str:
        """Process content to add cross-links.

        Args:
            content: The markdown content to process.
            current_page: Path of the current page (to avoid self-links).

        Returns:
            Content with cross-links added.
        """
        # Get entities on the current page (to avoid self-links)
        current_page_entities = set(self.registry.get_page_entities(current_page))

        # Split content into code blocks and non-code sections
        # We only want to add links in non-code sections
        parts = self._split_by_code_blocks(content)
        processed_parts = []

        for part, is_code in parts:
            if is_code:
                # Don't modify code blocks
                processed_parts.append(part)
            else:
                # Add links to prose sections
                processed_parts.append(
                    self._add_links_to_text(part, current_page, current_page_entities)
                )

        return "".join(processed_parts)

    def _split_by_code_blocks(self, content: str) -> list[tuple[str, bool]]:
        """Split content into code and non-code sections.

        Args:
            content: The markdown content.

        Returns:
            List of (text, is_code) tuples.
        """
        # Match fenced code blocks (``` or ~~~) and inline code (`)
        # We need to handle both
        parts: list[tuple[str, bool]] = []

        # Pattern for fenced code blocks
        fenced_pattern = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~)")

        last_end = 0
        for match in fenced_pattern.finditer(content):
            # Add text before the code block
            if match.start() > last_end:
                parts.append((content[last_end : match.start()], False))
            # Add the code block
            parts.append((match.group(0), True))
            last_end = match.end()

        # Add remaining text
        if last_end < len(content):
            parts.append((content[last_end:], False))

        return parts

    def _add_links_to_text(
        self,
        text: str,
        current_page: str,
        current_page_entities: set[str],
    ) -> str:
        """Add links to a text section (not code).

        Args:
            text: The text to process.
            current_page: Path of the current page.
            current_page_entities: Entities defined on the current page.

        Returns:
            Text with links added.
        """
        entities = self.registry.get_all_entities()
        aliases = self.registry.get_all_aliases()

        if not entities and not aliases:
            return text

        # Sort by name length (longest first) to avoid partial replacements
        sorted_names = sorted(entities.keys(), key=len, reverse=True)

        for name in sorted_names:
            # Skip entities on the current page
            if name in current_page_entities:
                continue

            entity = entities[name]

            # Calculate relative path from current page to target
            rel_path = self._relative_path(current_page, entity.wiki_path)

            # Create the link
            link = f"[{name}]({rel_path})"

            # Replace mentions of the entity with links
            # Use word boundaries to avoid partial matches
            # Also avoid replacing inside existing links or inline code
            text = self._replace_entity_mentions(text, name, link, rel_path)

        # Also try to match aliases (spaced versions like "Vector Store")
        # Sort by length (longest first)
        sorted_aliases = sorted(aliases.keys(), key=len, reverse=True)

        for alias in sorted_aliases:
            canonical_name = aliases[alias]

            # Skip if canonical entity is on current page
            if canonical_name in current_page_entities:
                continue

            alias_entity = entities.get(canonical_name)
            if not alias_entity:
                continue

            # Calculate relative path
            rel_path = self._relative_path(current_page, alias_entity.wiki_path)

            # Create link - use alias as display text
            link = f"[{alias}]({rel_path})"

            # Replace alias mentions
            text = self._replace_entity_mentions(text, alias, link, rel_path)

        return text

    def _replace_entity_mentions(
        self,
        text: str,
        entity_name: str,
        link: str,
        rel_path: str,
    ) -> str:
        """Replace entity mentions with links.

        Args:
            text: The text to process.
            entity_name: The entity name to find.
            link: The markdown link to insert.
            rel_path: The relative path to the entity's wiki page.

        Returns:
            Text with entity mentions replaced.
        """
        # First, protect existing links and headings by replacing them temporarily
        protected: list[tuple[str, str]] = []
        counter = 0

        def protect(match: re.Match) -> str:
            nonlocal counter
            placeholder = f"\x00PROTECTED{counter}\x00"
            protected.append((placeholder, match.group(0)))
            counter += 1
            return placeholder

        # Protect existing markdown links and headings
        temp_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", protect, text)
        temp_text = re.sub(r"^(#{1,6}\s+.+)$", protect, temp_text, flags=re.MULTILINE)

        # Convert backticked entity names to links: `EntityName` -> [`EntityName`](path)
        # Also handle qualified names like `module.EntityName` -> [`EntityName`](path)
        temp_text = self._link_backticked_entities(temp_text, entity_name, rel_path, protect)

        # Protect all remaining inline code (that didn't match entities)
        temp_text = re.sub(r"`[^`]+`", protect, temp_text)

        # Replace bold entity mentions: **EntityName** -> **[EntityName](path)**
        bold_pattern = rf"\*\*{re.escape(entity_name)}\*\*"
        bold_link = f"**[{entity_name}]({rel_path})**"
        temp_text = re.sub(bold_pattern, bold_link, temp_text)

        # Protect links we just created to avoid double-linking
        temp_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", protect, temp_text)

        # Also replace plain entity mentions (but not inside headings to avoid breaking them)
        pattern = rf"\b{re.escape(entity_name)}\b"
        temp_text = re.sub(pattern, link, temp_text)

        # Restore protected content
        for placeholder, original in protected:
            temp_text = temp_text.replace(placeholder, original)

        return temp_text

    def _link_backticked_entities(
        self,
        text: str,
        entity_name: str,
        rel_path: str,
        protect: Callable[[re.Match[str]], str],
    ) -> str:
        """Convert backticked entity names to links.

        Handles:
        - `EntityName` -> [`EntityName`](path)
        - `module.EntityName` -> [`EntityName`](path)
        - `module.submodule.EntityName` -> [`EntityName`](path)

        Args:
            text: The text to process.
            entity_name: The entity name to find.
            rel_path: The relative path to the entity's wiki page.
            protect: Function to protect already-processed content.

        Returns:
            Text with backticked entities converted to links.
        """
        # Pattern for exact match: `EntityName`
        exact_pattern = rf"`{re.escape(entity_name)}`"
        exact_replacement = f"[`{entity_name}`]({rel_path})"
        text = re.sub(exact_pattern, exact_replacement, text)

        # Pattern for qualified names: `something.EntityName` or `a.b.EntityName`
        # Captures the entity name at the end after a dot
        qualified_pattern = rf"`([a-zA-Z_][a-zA-Z0-9_]*\.)+{re.escape(entity_name)}`"

        def qualified_replacement(match: re.Match) -> str:
            # Link just the entity name, showing full qualified name
            full_name = match.group(0)[1:-1]  # Remove backticks
            return f"[`{full_name}`]({rel_path})"

        text = re.sub(qualified_pattern, qualified_replacement, text)

        # Protect the links we just created
        text = re.sub(r"\[`[^`]+`\]\([^)]+\)", protect, text)

        return text

    def _relative_path(self, from_path: str, to_path: str) -> str:
        """Calculate relative path between two wiki pages.

        Args:
            from_path: Path of the source page (e.g., "modules/src.md").
            to_path: Path of the target page (e.g., "files/src/indexer.md").

        Returns:
            Relative path from source to target.
        """
        from_parts = Path(from_path).parts[:-1]  # Directory parts only
        to_parts = Path(to_path).parts

        # Find common prefix
        common_length = 0
        for i in range(min(len(from_parts), len(to_parts) - 1)):
            if from_parts[i] == to_parts[i]:
                common_length = i + 1
            else:
                break

        # Build relative path
        ups = len(from_parts) - common_length
        rel_parts = [".."] * ups + list(to_parts[common_length:])

        return "/".join(rel_parts)


def add_cross_links(
    pages: list[WikiPage],
    registry: EntityRegistry,
) -> list[WikiPage]:
    """Add cross-links to all wiki pages.

    Args:
        pages: List of wiki pages to process.
        registry: Entity registry with documented entities.

    Returns:
        List of wiki pages with cross-links added.
    """
    linker = CrossLinker(registry)
    return [linker.add_links(page) for page in pages]
