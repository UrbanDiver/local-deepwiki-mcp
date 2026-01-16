"""Search index generator for wiki pages.

This module generates a JSON search index that enables client-side
full-text search across wiki documentation. Includes both page-level
and entity-level (function/class/method) search entries.
"""

import json
import re
from pathlib import Path

from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.models import ChunkType, IndexStatus, WikiPage


def extract_headings(content: str) -> list[str]:
    """Extract all headings from markdown content.

    Args:
        content: Markdown content.

    Returns:
        List of heading texts (without # prefixes).
    """
    headings = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("#"):
            # Remove # prefix and clean up
            heading = re.sub(r"^#+\s*", "", line)
            # Remove markdown formatting like ** or `
            heading = re.sub(r"[*`]", "", heading)
            if heading:
                headings.append(heading)
    return headings


def extract_code_terms(content: str) -> list[str]:
    """Extract code terms (class names, function names) from content.

    Args:
        content: Markdown content.

    Returns:
        List of code terms found in backticks.
    """
    terms = set()
    # Match inline code: `term`
    for match in re.finditer(r"`([^`]+)`", content):
        term = match.group(1)
        # Skip code that looks like a full statement or has spaces
        if len(term) < 50 and "\n" not in term:
            # Extract the main identifier if it's a qualified name
            parts = term.split(".")
            if parts:
                terms.add(parts[-1])  # Last part of qualified name
            if len(parts) > 1:
                terms.add(term)  # Also add full qualified name
    return list(terms)


def extract_snippet(content: str, max_length: int = 200) -> str:
    """Extract a text snippet from markdown content.

    Args:
        content: Markdown content.
        max_length: Maximum snippet length.

    Returns:
        Plain text snippet.
    """
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", content)
    # Remove headings
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)
    # Remove links but keep text: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove markdown formatting
    text = re.sub(r"[*_`]", "", text)
    # Collapse whitespace
    text = " ".join(text.split())

    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "..."

    return text.strip()


def generate_search_entry(page: WikiPage) -> dict:
    """Generate a search index entry for a wiki page.

    Args:
        page: The wiki page.

    Returns:
        Dictionary with searchable fields.
    """
    headings = extract_headings(page.content)
    terms = extract_code_terms(page.content)
    snippet = extract_snippet(page.content)

    return {
        "path": page.path,
        "title": page.title,
        "headings": headings,
        "terms": terms,
        "snippet": snippet,
    }


def generate_search_index(pages: list[WikiPage]) -> list[dict]:
    """Generate a search index from wiki pages.

    Args:
        pages: List of wiki pages.

    Returns:
        List of search entries.
    """
    return [generate_search_entry(page) for page in pages]


async def generate_entity_entries(
    index_status: IndexStatus,
    vector_store: VectorStore,
) -> list[dict]:
    """Generate search entries for individual code entities.

    Creates searchable entries for each function, class, and method
    with type information for filtering.

    Args:
        index_status: Index status with file information.
        vector_store: Vector store with code chunks.

    Returns:
        List of entity search entries.
    """
    entries: list[dict] = []

    for file_info in index_status.files:
        chunks = await vector_store.get_chunks_by_file(file_info.path)

        for chunk in chunks:
            if chunk.chunk_type not in (ChunkType.CLASS, ChunkType.FUNCTION, ChunkType.METHOD):
                continue

            # Determine entity type
            entity_type = chunk.chunk_type.value  # 'class', 'function', 'method'

            # Build display name
            if chunk.chunk_type == ChunkType.METHOD and chunk.parent_name:
                display_name = f"{chunk.parent_name}.{chunk.name}"
            else:
                display_name = chunk.name or "Unknown"

            # Extract metadata
            metadata = chunk.metadata or {}
            param_types = metadata.get("parameter_types", {})
            return_type = metadata.get("return_type")
            raises = metadata.get("raises", [])
            is_async = metadata.get("is_async", False)

            # Build signature preview
            signature = ""
            if entity_type != "class":
                params = list(param_types.keys())[:3]
                if len(param_types) > 3:
                    params.append("...")
                signature = f"({', '.join(params)})"
                if return_type:
                    signature += f" → {return_type}"

            # Build brief description from docstring
            description = ""
            if chunk.docstring:
                first_line = chunk.docstring.split("\n")[0].strip()
                if len(first_line) > 80:
                    description = first_line[:77] + "..."
                else:
                    description = first_line

            # Build wiki path
            wiki_path = f"files/{file_info.path}".replace(".py", ".md")

            entry = {
                "type": "entity",
                "entity_type": entity_type,
                "name": chunk.name or "Unknown",
                "display_name": display_name,
                "path": wiki_path,
                "file": file_info.path,
                "signature": signature,
                "description": description,
                "is_async": is_async,
                "raises": raises,
                # Keywords for search matching
                "keywords": _build_keywords(chunk.name, param_types, return_type, raises),
            }
            entries.append(entry)

    # Sort by name for consistent output
    entries.sort(key=lambda e: e["display_name"].lower())
    return entries


def _build_keywords(
    name: str | None,
    param_types: dict[str, str],
    return_type: str | None,
    raises: list[str],
) -> list[str]:
    """Build search keywords from entity metadata.

    Args:
        name: Entity name.
        param_types: Parameter types mapping.
        return_type: Return type string.
        raises: List of exception types.

    Returns:
        List of searchable keywords.
    """
    keywords: set[str] = set()

    # Add name parts (split on underscore and camelCase)
    if name:
        keywords.add(name.lower())
        # Split on underscores
        for part in name.split("_"):
            if len(part) > 2:
                keywords.add(part.lower())
        # Split camelCase
        camel_parts = re.findall(r"[A-Z][a-z]+|[a-z]+", name)
        for part in camel_parts:
            if len(part) > 2:
                keywords.add(part.lower())

    # Add type keywords
    for type_str in param_types.values():
        if type_str:
            # Extract base type (e.g., "list" from "list[str]")
            base_type = re.split(r"[\[\]|,\s]", type_str)[0].lower()
            if base_type:
                keywords.add(base_type)

    if return_type:
        base_return = re.split(r"[\[\]|,\s]", return_type)[0].lower()
        if base_return:
            keywords.add(base_return)

    # Add exception keywords
    for exc in raises:
        keywords.add(exc.lower())
        # Also add without "Error" suffix for easier search
        if exc.endswith("Error"):
            keywords.add(exc[:-5].lower())

    return list(keywords)


async def generate_full_search_index(
    pages: list[WikiPage],
    index_status: IndexStatus | None = None,
    vector_store: VectorStore | None = None,
) -> dict:
    """Generate a comprehensive search index with pages and entities.

    Args:
        pages: List of wiki pages.
        index_status: Optional index status for entity extraction.
        vector_store: Optional vector store for entity extraction.

    Returns:
        Dictionary with 'pages' and 'entities' lists.
    """
    page_entries = generate_search_index(pages)

    entity_entries: list[dict] = []
    if index_status and vector_store:
        entity_entries = await generate_entity_entries(index_status, vector_store)

    return {
        "pages": page_entries,
        "entities": entity_entries,
        "meta": {
            "total_pages": len(page_entries),
            "total_entities": len(entity_entries),
        },
    }


def write_search_index(wiki_path: Path, pages: list[WikiPage]) -> Path:
    """Generate and write search index to disk (legacy page-only version).

    Args:
        wiki_path: Path to wiki directory.
        pages: List of wiki pages.

    Returns:
        Path to the generated search.json file.
    """
    index = generate_search_index(pages)
    index_path = wiki_path / "search.json"
    index_path.write_text(json.dumps(index, indent=2))
    return index_path


async def write_full_search_index(
    wiki_path: Path,
    pages: list[WikiPage],
    index_status: IndexStatus,
    vector_store: VectorStore,
) -> Path:
    """Generate and write comprehensive search index to disk.

    Includes both page-level and entity-level search entries.

    Args:
        wiki_path: Path to wiki directory.
        pages: List of wiki pages.
        index_status: Index status with file information.
        vector_store: Vector store with code chunks.

    Returns:
        Path to the generated search.json file.
    """
    index = await generate_full_search_index(pages, index_status, vector_store)
    index_path = wiki_path / "search.json"
    index_path.write_text(json.dumps(index, indent=2))
    return index_path
