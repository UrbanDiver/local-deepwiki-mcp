"""MCP Resource handlers for exposing wiki pages as browsable resources."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import AnyUrl, Resource, ResourceTemplate

from local_deepwiki.core.path_utils import find_deepwiki_dirs, validate_sub_path
from local_deepwiki.errors import ValidationError
from local_deepwiki.logging import get_logger

if TYPE_CHECKING:
    from mcp.server import Server

logger = get_logger(__name__)

# URI scheme for deepwiki resources
DEEPWIKI_SCHEME = "deepwiki"


def _find_wiki_directories() -> list[Path]:
    """Find .deepwiki directories under the current working directory."""
    return find_deepwiki_dirs()


def build_resource_uri(wiki_path: Path, page_relative: str) -> str:
    """Build a deepwiki:// URI for a wiki page.

    Args:
        wiki_path: Absolute path to the wiki directory.
        page_relative: Page path relative to wiki root (e.g., 'index.md').

    Returns:
        URI string like 'deepwiki:///path/to/.deepwiki/index.md'.
    """
    return f"{DEEPWIKI_SCHEME}://{wiki_path}/{page_relative}"


def _parse_deepwiki_uri(uri_str: str) -> tuple[Path, str]:
    """Parse a deepwiki:// URI into (wiki_path, page_relative).

    Args:
        uri_str: The full URI string.

    Returns:
        Tuple of resolved wiki Path and the page-relative path string.

    Raises:
        ValidationError: If the URI scheme or structure is invalid.
    """
    if not uri_str.startswith(f"{DEEPWIKI_SCHEME}://"):
        raise ValidationError(
            message=f"Invalid URI scheme: expected {DEEPWIKI_SCHEME}://",
            hint="Use a deepwiki:// URI returned by list_resources.",
            field="uri",
            value=uri_str,
        )

    raw_path = uri_str[len(f"{DEEPWIKI_SCHEME}://") :]

    deepwiki_marker = "/.deepwiki/"
    marker_idx = raw_path.find(deepwiki_marker)
    if marker_idx == -1:
        deepwiki_marker_alt = ".deepwiki/"
        if raw_path.startswith(deepwiki_marker_alt):
            wiki_path = Path(raw_path[: len(".deepwiki")]).resolve()
            page_relative = raw_path[len(deepwiki_marker_alt) :]
        else:
            raise ValidationError(
                message="Cannot parse wiki path from URI",
                hint="URI must contain a .deepwiki directory path.",
                field="uri",
                value=uri_str,
            )
    else:
        wiki_path = Path(raw_path[: marker_idx + len("/.deepwiki")]).resolve()
        page_relative = raw_path[marker_idx + len(deepwiki_marker) :]

    if not page_relative:
        raise ValidationError(
            message="No page path specified in URI",
            hint="Include a page path after the wiki directory, e.g., deepwiki:///path/.deepwiki/index.md",
            field="uri",
            value=uri_str,
        )

    return wiki_path, page_relative


async def _try_lazy_generate_page(
    wiki_path: Path,
    page_relative: str,
) -> list[ReadResourceContents]:
    """Attempt lazy generation for a missing page.

    Args:
        wiki_path: Path to the .deepwiki directory.
        page_relative: Page path relative to wiki root.

    Returns:
        List containing the generated page content.

    Raises:
        FileNotFoundError: If lazy generation is not possible.
    """
    entity_reg = wiki_path / "entity_registry.json"
    index_status_file = wiki_path / "index_status.json"
    if entity_reg.exists() or index_status_file.exists():
        from local_deepwiki.generators.lazy_generator import get_lazy_generator

        generator = get_lazy_generator(wiki_path)
        content = await generator.get_page(page_relative)
        return [ReadResourceContents(content=content, mime_type="text/markdown")]
    raise FileNotFoundError(f"Wiki page not found: {page_relative}")


def _discover_wiki_pages(wiki_dir: Path) -> list[Resource]:
    """Discover markdown wiki pages in a .deepwiki directory.

    Args:
        wiki_dir: Path to the .deepwiki directory.

    Returns:
        List of Resource objects for each markdown page.
    """
    resources: list[Resource] = []
    for md_file in sorted(wiki_dir.rglob("*.md")):
        if not md_file.is_file():
            continue

        rel_path = str(md_file.relative_to(wiki_dir))
        uri = build_resource_uri(wiki_dir, rel_path)

        title = rel_path
        try:
            first_line = md_file.read_text(encoding="utf-8").split("\n", 1)[0]
            if first_line.startswith("#"):
                title = first_line.lstrip("#").strip()
        except (OSError, UnicodeDecodeError):
            pass

        resources.append(
            Resource(
                uri=AnyUrl(uri),
                name=title,
                description=f"Wiki page: {rel_path} in {wiki_dir.parent.name}",
                mimeType="text/markdown",
            )
        )
    return resources


def _discover_llms_txt(wiki_dir: Path) -> list[Resource]:
    """Discover llms.txt and llms-full.txt resources.

    Args:
        wiki_dir: Path to the .deepwiki directory.

    Returns:
        List of Resource objects for each discovered txt file.
    """
    resources: list[Resource] = []
    for txt_name, txt_desc in (
        ("llms.txt", "LLM-friendly project summary (llmstxt.org)"),
        ("llms-full.txt", "Full documentation for LLM consumption"),
    ):
        txt_path = wiki_dir / txt_name
        if txt_path.is_file():
            uri = build_resource_uri(wiki_dir, txt_name)
            resources.append(
                Resource(
                    uri=AnyUrl(uri),
                    name=txt_name,
                    description=f"{txt_desc} in {wiki_dir.parent.name}",
                    mimeType="text/plain",
                )
            )
    return resources


def register_resource_handlers(server: Server) -> None:
    """Register MCP Resource protocol handlers on the server.

    Args:
        server: The MCP Server instance to register handlers on.
    """

    @server.list_resource_templates()
    async def list_resource_templates() -> list[ResourceTemplate]:
        """Return URI templates for deepwiki resources."""
        return [
            ResourceTemplate(
                uriTemplate=f"{DEEPWIKI_SCHEME}://{{wiki_path}}/{{page}}",
                name="DeepWiki Page",
                description="A wiki documentation page generated by local-deepwiki",
                mimeType="text/markdown",
            )
        ]

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """Discover all available wiki page resources."""
        resources: list[Resource] = []
        for wiki_dir in _find_wiki_directories():
            resources.extend(_discover_wiki_pages(wiki_dir))
            resources.extend(_discover_llms_txt(wiki_dir))
        return resources

    @server.read_resource()
    async def read_resource(
        uri: AnyUrl,
    ) -> str | bytes | Iterable[ReadResourceContents]:
        """Read a wiki page by its deepwiki:// URI.

        Args:
            uri: The deepwiki:// URI to read.

        Returns:
            The markdown content of the wiki page.

        Raises:
            ValidationError: If the URI is invalid or path traversal is detected.
            FileNotFoundError: If the page does not exist.
        """
        uri_str = str(uri)
        wiki_path, page_relative = _parse_deepwiki_uri(uri_str)

        page_path = validate_sub_path(
            wiki_path,
            page_relative,
            field="uri",
            value=uri_str,
            hint="The page path must be within the wiki directory.",
        )

        if not page_path.exists():
            return await _try_lazy_generate_page(wiki_path, page_relative)

        mime = "text/plain" if page_path.suffix == ".txt" else "text/markdown"
        content = page_path.read_text(encoding="utf-8")
        return [ReadResourceContents(content=content, mime_type=mime)]
