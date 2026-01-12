"""Table of contents generator with hierarchical numbering."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TocEntry:
    """A single entry in the table of contents."""

    number: str
    title: str
    path: str
    children: list["TocEntry"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "number": self.number,
            "title": self.title,
            "path": self.path,
        }
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        return result


@dataclass
class TableOfContents:
    """Hierarchical table of contents with numbered sections."""

    entries: list[TocEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "entries": [entry.to_dict() for entry in self.entries]
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableOfContents":
        """Create from dictionary."""
        def parse_entry(entry_data: dict[str, Any]) -> TocEntry:
            children = [
                parse_entry(child) for child in entry_data.get("children", [])
            ]
            return TocEntry(
                number=entry_data["number"],
                title=entry_data["title"],
                path=entry_data["path"],
                children=children,
            )

        entries = [parse_entry(e) for e in data.get("entries", [])]
        return cls(entries=entries)

    @classmethod
    def from_json(cls, json_str: str) -> "TableOfContents":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


def generate_toc(pages: list[dict[str, str]]) -> TableOfContents:
    """Generate hierarchical numbered table of contents from wiki pages.

    Args:
        pages: List of dicts with 'path' and 'title' keys.

    Returns:
        TableOfContents with numbered entries.
    """
    # Define the fixed order for root pages
    ROOT_PAGE_ORDER = [
        ("index.md", "Overview"),
        ("architecture.md", "Architecture"),
        ("dependencies.md", "Dependencies"),
    ]

    # Define the fixed order for sections
    SECTION_ORDER = ["modules", "files"]

    entries: list[TocEntry] = []
    current_number = 1

    # First, add root pages in defined order
    root_pages = {p["path"]: p["title"] for p in pages if "/" not in p["path"]}

    for page_path, default_title in ROOT_PAGE_ORDER:
        if page_path in root_pages:
            title = root_pages[page_path]
            # Clean up title if needed
            if title == page_path.replace(".md", ""):
                title = default_title
            entries.append(TocEntry(
                number=str(current_number),
                title=title,
                path=page_path,
            ))
            current_number += 1

    # Now handle sections (modules, files)
    section_pages: dict[str, list[dict[str, str]]] = {}
    for page in pages:
        if "/" in page["path"]:
            parts = Path(page["path"]).parts
            section = parts[0]
            if section not in section_pages:
                section_pages[section] = []
            section_pages[section].append(page)

    # Process sections in defined order
    for section_name in SECTION_ORDER:
        if section_name not in section_pages:
            continue

        section_entry = _build_section_tree(
            section_name,
            section_pages[section_name],
            str(current_number),
        )
        if section_entry:
            entries.append(section_entry)
            current_number += 1

    return TableOfContents(entries=entries)


def _build_section_tree(
    section_name: str,
    pages: list[dict[str, str]],
    base_number: str,
) -> TocEntry | None:
    """Build a hierarchical tree for a section (modules or files).

    Args:
        section_name: Name of the section (e.g., "modules", "files").
        pages: List of pages in this section.
        base_number: The base number for this section (e.g., "4").

    Returns:
        TocEntry for the section with nested children.
    """
    if not pages:
        return None

    # Find the index page for this section
    index_path = f"{section_name}/index.md"
    index_page = next((p for p in pages if p["path"] == index_path), None)

    section_title = section_name.replace("_", " ").title()

    # Build tree structure from file paths
    # Group pages by their immediate parent directory within the section
    tree: dict[str, Any] = {"_pages": [], "_dirs": {}}

    for page in pages:
        if page["path"] == index_path:
            continue  # Skip index page, it's the section root

        # Get path relative to section
        rel_path = page["path"][len(section_name) + 1:]  # Remove "section/"
        parts = Path(rel_path).parts

        current = tree
        for part in parts[:-1]:
            if part not in current["_dirs"]:
                current["_dirs"][part] = {"_pages": [], "_dirs": {}}
            current = current["_dirs"][part]

        # Add page at current level
        current["_pages"].append(page)

    # Convert tree to TocEntry hierarchy
    children = _tree_to_entries(tree, base_number)

    return TocEntry(
        number=base_number,
        title=section_title,
        path=index_path if index_page else "",
        children=children,
    )


def _tree_to_entries(
    tree: dict[str, Any],
    parent_number: str,
) -> list[TocEntry]:
    """Convert a tree structure to TocEntry list with proper numbering.

    Args:
        tree: Tree dict with "_pages" and "_dirs" keys.
        parent_number: Parent's number for prefixing (e.g., "4").

    Returns:
        List of TocEntry objects with hierarchical numbering.
    """
    entries: list[TocEntry] = []
    child_num = 1

    # First add direct pages at this level (sorted by path)
    for page in sorted(tree["_pages"], key=lambda p: p["path"]):
        number = f"{parent_number}.{child_num}"
        entries.append(TocEntry(
            number=number,
            title=page["title"],
            path=page["path"],
        ))
        child_num += 1

    # Then add subdirectories (sorted by name)
    for dir_name in sorted(tree["_dirs"].keys()):
        subtree = tree["_dirs"][dir_name]
        number = f"{parent_number}.{child_num}"

        # Check if this directory has an index page
        dir_index = next(
            (p for p in subtree["_pages"] if Path(p["path"]).stem == "index"),
            None
        )

        # Get children for this directory
        children = _tree_to_entries(subtree, number)

        # Create entry for directory
        dir_title = dir_name.replace("_", " ").replace("-", " ").title()
        entries.append(TocEntry(
            number=number,
            title=dir_title,
            path=dir_index["path"] if dir_index else "",
            children=children,
        ))
        child_num += 1

    return entries


def write_toc(toc: TableOfContents, wiki_path: Path) -> None:
    """Write table of contents to toc.json file.

    Args:
        toc: The TableOfContents to write.
        wiki_path: Path to the wiki directory.
    """
    toc_path = wiki_path / "toc.json"
    toc_path.write_text(toc.to_json())


def read_toc(wiki_path: Path) -> TableOfContents | None:
    """Read table of contents from toc.json file.

    Args:
        wiki_path: Path to the wiki directory.

    Returns:
        TableOfContents if file exists, None otherwise.
    """
    toc_path = wiki_path / "toc.json"
    if not toc_path.exists():
        return None

    try:
        return TableOfContents.from_json(toc_path.read_text())
    except (json.JSONDecodeError, KeyError):
        return None
