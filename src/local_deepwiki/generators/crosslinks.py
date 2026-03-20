"""Cross-linking functionality for wiki pages.

This module provides functionality to automatically create hyperlinks between
wiki pages when classes, functions, or other documented entities are mentioned.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from local_deepwiki.models import ChunkType, CodeChunk, WikiPage


@dataclass(slots=True)
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
            # Common function/method names that are also English words
            "main",
            "init",
            "start",
            "setup",
            "entry",
            "close",
            "parse",
            "store",
            "cache",
            "build",
            "write",
            "check",
            "fetch",
            "reset",
            "clear",
            "flush",
            "state",
            "event",
            "token",
            "Role",
            # Generic callable names that cause false cross-links
            "run",
            "stop",
            "load",
            "save",
            "send",
            "read",
            "open",
            "update",
            "delete",
            "create",
            "handle",
            "process",
            "format",
            "render",
            "validate",
            "connect",
            "execute",
            "search",
            "filter",
            "sort",
            "merge",
            "split",
            "match",
            "test",
            "debug",
            "trace",
            "walk",
            "visit",
            "emit",
            "wrap",
            "apply",
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

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry to a JSON-compatible dict."""
        entities = {}
        for name, info in self._entities.items():
            entities[name] = {
                "name": info.name,
                "entity_type": info.entity_type.value,
                "wiki_path": info.wiki_path,
                "file_path": info.file_path,
                "parent_name": info.parent_name,
            }
        return {
            "entities": entities,
            "aliases": dict(self._aliases),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityRegistry":
        """Deserialize registry from a dict."""
        registry = cls()
        for _name, info in data.get("entities", {}).items():
            registry.register_entity(
                name=info["name"],
                entity_type=ChunkType(info["entity_type"]),
                wiki_path=info["wiki_path"],
                file_path=info["file_path"],
                parent_name=info.get("parent_name"),
            )
        return registry

    def save(self, path: Path) -> None:
        """Persist registry to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "EntityRegistry":
        """Load registry from a JSON file."""
        data = json.loads(path.read_text())
        return cls.from_dict(data)


def build_entity_registry_from_store(
    chunks_iter: Iterator[CodeChunk],
    significant_paths: set[str],
) -> EntityRegistry:
    """Build an entity registry from a chunk iterator.

    Only registers entities from files in significant_paths (those that
    pass filter_significant_files).

    Args:
        chunks_iter: Iterator of all chunks (e.g. vector_store.get_all_chunks()).
        significant_paths: Set of file paths eligible for wiki pages.

    Returns:
        Populated EntityRegistry.
    """
    from local_deepwiki.generators.wiki.utils import file_path_to_wiki_path

    registry = EntityRegistry()
    for chunk in chunks_iter:
        if chunk.file_path not in significant_paths:
            continue
        if chunk.name and chunk.chunk_type in (ChunkType.CLASS, ChunkType.FUNCTION):
            wiki_path = file_path_to_wiki_path(chunk.file_path)
            registry.register_entity(
                name=chunk.name,
                entity_type=chunk.chunk_type,
                wiki_path=wiki_path,
                file_path=chunk.file_path,
                parent_name=chunk.parent_name,
            )
    return registry


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
        current_page_entities = set(self.registry.get_page_entities(current_page))

        # Build linkable lookup: name -> (display_text, rel_path)
        entities = self.registry.get_all_entities()
        aliases = self.registry.get_all_aliases()

        linkable: dict[str, tuple[str, str]] = {}

        for name, entity in entities.items():
            if name in current_page_entities:
                continue
            rel_path = self._relative_path(current_page, entity.wiki_path)
            linkable[name] = (name, rel_path)

        for alias, canonical_name in aliases.items():
            if canonical_name in current_page_entities:
                continue
            alias_entity = entities.get(canonical_name)
            if not alias_entity:
                continue
            rel_path = self._relative_path(current_page, alias_entity.wiki_path)
            linkable[alias] = (alias, rel_path)

        if not linkable:
            return content

        # Pre-compile one combined regex per match type (longest-first alternation)
        sorted_names = sorted(linkable.keys(), key=len, reverse=True)
        alternation = "|".join(re.escape(n) for n in sorted_names)

        backtick_re = re.compile(
            rf"`(?:(?:[a-zA-Z_][a-zA-Z0-9_]*\.)+)?({alternation})`"
        )
        bold_re = re.compile(rf"\*\*({alternation})\*\*")
        plain_re = re.compile(rf"\b({alternation})\b")

        # Split content into code blocks and non-code sections
        parts = self._split_by_code_blocks(content)
        processed_parts = []

        for part, is_code in parts:
            if is_code:
                processed_parts.append(part)
            else:
                processed_parts.append(
                    self._add_links_to_text(
                        part, linkable, backtick_re, bold_re, plain_re
                    )
                )

        return "".join(processed_parts)

    @staticmethod
    def _split_by_code_blocks(content: str) -> list[tuple[str, bool]]:
        """Split content into code and non-code sections.

        Uses line-by-line parsing to correctly handle inline triple-backticks
        inside code blocks (e.g., Python f-strings containing ```).

        Args:
            content: The markdown content.

        Returns:
            List of (text, is_code) tuples.
        """
        lines = content.split("\n")
        parts: list[tuple[str, bool]] = []
        current_lines: list[str] = []
        in_code_block = False

        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            is_fence = False

            if indent <= 3 and (
                stripped.startswith("```") or stripped.startswith("~~~")
            ):
                if in_code_block:
                    # Closing fence: fence chars with optional trailing whitespace only
                    after = stripped[3:].strip()
                    if not after:
                        is_fence = True
                else:
                    is_fence = True

            if is_fence:
                if in_code_block:
                    # End code block: include the closing fence
                    current_lines.append(line)
                    parts.append(("\n".join(current_lines), True))
                    current_lines = []
                    in_code_block = False
                else:
                    # Start code block: flush non-code text
                    if current_lines:
                        parts.append(("\n".join(current_lines), False))
                        current_lines = []
                    current_lines.append(line)
                    in_code_block = True
            else:
                current_lines.append(line)

        # Flush remaining lines
        if current_lines:
            parts.append(("\n".join(current_lines), in_code_block))

        return parts

    @staticmethod
    def _add_links_to_text(
        text: str,
        linkable: dict[str, tuple[str, str]],
        backtick_re: re.Pattern[str],
        bold_re: re.Pattern[str],
        plain_re: re.Pattern[str],
    ) -> str:
        """Add links to a text section (not code) using single-pass matching.

        Instead of iterating per-entity with 8+ regex ops each, this uses one
        pre-compiled alternation pattern per match type (backtick, bold, plain)
        to process ALL entities in a single pass.

        Args:
            text: The text to process.
            linkable: Map of name -> (display_text, rel_path).
            backtick_re: Compiled pattern for backticked entity matches.
            bold_re: Compiled pattern for bold entity matches.
            plain_re: Compiled pattern for plain word-boundary matches.

        Returns:
            Text with links added.
        """
        protected: list[tuple[str, str]] = []
        counter = 0

        def protect(match: re.Match[str]) -> str:
            nonlocal counter
            placeholder = f"\x00PROTECTED{counter}\x00"
            protected.append((placeholder, match.group(0)))
            counter += 1
            return placeholder

        # 1. Protect existing markdown links
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", protect, text)
        # 2. Protect headings
        text = re.sub(r"^(#{1,6}\s+.+)$", protect, text, flags=re.MULTILINE)
        # 3a. Protect markdown table rows (pipe-delimited lines)
        text = re.sub(r"^\|.+\|$", protect, text, flags=re.MULTILINE)

        # 3. Link backticked entities: `EntityName` or `module.EntityName`
        def backtick_repl(match: re.Match[str]) -> str:
            entity_name = match.group(1)
            full_text = match.group(0)[1:-1]  # Strip surrounding backticks
            _, rel_path = linkable[entity_name]
            display = full_text if full_text != entity_name else entity_name
            return f"[`{display}`]({rel_path})"

        text = backtick_re.sub(backtick_repl, text)

        # 4. Protect backtick links we just created
        text = re.sub(r"\[`[^`]+`\]\([^)]+\)", protect, text)
        # 5. Protect all remaining inline code
        text = re.sub(r"`[^`]+`", protect, text)

        # 6. Link bold entity mentions: **EntityName** -> **[EntityName](path)**
        def bold_repl(match: re.Match[str]) -> str:
            name = match.group(1)
            display, rel_path = linkable[name]
            return f"**[{display}]({rel_path})**"

        text = bold_re.sub(bold_repl, text)

        # 7. Protect links from bold step
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", protect, text)

        # 8. Link plain word-boundary mentions
        def plain_repl(match: re.Match[str]) -> str:
            name = match.group(1)
            display, rel_path = linkable[name]
            return f"[{display}]({rel_path})"

        text = plain_re.sub(plain_repl, text)

        # 9. Restore all protected content (reverse order so outer protections
        # from later steps are unwrapped first, exposing inner placeholders)
        for placeholder, original in reversed(protected):
            text = text.replace(placeholder, original)

        return text

    @staticmethod
    def _relative_path(from_path: str, to_path: str) -> str:
        """Calculate relative path between two wiki pages."""
        from local_deepwiki.generators.wiki.utils import relative_wiki_path

        return relative_wiki_path(from_path, to_path)


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
