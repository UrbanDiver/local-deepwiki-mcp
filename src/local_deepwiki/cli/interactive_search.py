"""Interactive search CLI for local-deepwiki.

Provides a keyboard-navigable interface for searching code with filters and previews.
"""

import argparse
import asyncio
import fnmatch
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from local_deepwiki.config import get_config
from local_deepwiki.core.vectorstore import VectorStore
from local_deepwiki.logging import get_logger
from local_deepwiki.models import ChunkType, Language, SearchResult
from local_deepwiki.providers.embeddings import get_embedding_provider

logger = get_logger(__name__)


# Language extension to Pygments lexer mapping
LANGUAGE_LEXERS = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "tsx": "tsx",
    "go": "go",
    "rust": "rust",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "swift": "swift",
    "ruby": "ruby",
    "php": "php",
    "kotlin": "kotlin",
    "csharp": "csharp",
}


@dataclass
class SearchFilters:
    """Filters to apply to search results."""

    language: str | None = None
    chunk_type: str | None = None  # function, class, method, etc.
    file_pattern: str | None = None
    min_similarity: float = 0.0

    def matches(self, result: SearchResult) -> bool:
        """Check if a result matches all active filters.

        Args:
            result: The search result to check.

        Returns:
            True if the result passes all filters.
        """
        # Check language filter
        if self.language and result.chunk.language.value != self.language:
            return False

        # Check chunk type filter
        if self.chunk_type and result.chunk.chunk_type.value != self.chunk_type:
            return False

        # Check file pattern filter
        if self.file_pattern:
            if not fnmatch.fnmatch(result.chunk.file_path, self.file_pattern):
                return False

        # Check minimum similarity
        if result.score < self.min_similarity:
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert filters to a dictionary for display.

        Returns:
            Dictionary of active filters.
        """
        active = {}
        if self.language:
            active["language"] = self.language
        if self.chunk_type:
            active["type"] = self.chunk_type
        if self.file_pattern:
            active["path"] = self.file_pattern
        if self.min_similarity > 0:
            active["min_score"] = f"{self.min_similarity:.2f}"
        return active

    def clear(self) -> None:
        """Clear all filters."""
        self.language = None
        self.chunk_type = None
        self.file_pattern = None
        self.min_similarity = 0.0


@dataclass
class SearchState:
    """Current state of the interactive search session."""

    query: str = ""
    results: list[SearchResult] = field(default_factory=list)
    filtered_results: list[SearchResult] = field(default_factory=list)
    selected_index: int = 0
    filters: SearchFilters = field(default_factory=SearchFilters)
    show_preview: bool = False
    preview_context_lines: int = 3
    input_mode: str = (
        "search"  # search, filter_language, filter_type, filter_path, filter_score
    )
    error_message: str | None = None
    search_complete: bool = False

    def apply_filters(self) -> None:
        """Apply current filters to results."""
        self.filtered_results = [r for r in self.results if self.filters.matches(r)]
        # Reset selection if it's out of bounds
        if self.selected_index >= len(self.filtered_results):
            self.selected_index = max(0, len(self.filtered_results) - 1)

    def move_selection(self, delta: int) -> None:
        """Move the selection by delta positions.

        Args:
            delta: Number of positions to move (positive = down, negative = up).
        """
        if not self.filtered_results:
            return
        self.selected_index = max(
            0, min(len(self.filtered_results) - 1, self.selected_index + delta)
        )

    def get_selected_result(self) -> SearchResult | None:
        """Get the currently selected search result.

        Returns:
            The selected result, or None if no results.
        """
        if not self.filtered_results or self.selected_index >= len(
            self.filtered_results
        ):
            return None
        return self.filtered_results[self.selected_index]


class InteractiveSearch:
    """Interactive search interface using rich."""

    def __init__(self, vector_store: VectorStore, repo_path: Path):
        """Initialize the interactive search.

        Args:
            vector_store: The vector store to search.
            repo_path: Path to the repository root for context.
        """
        self._store = vector_store
        self._repo_path = repo_path
        self._console = Console()
        self._state = SearchState()

    async def search(self, query: str, limit: int = 20) -> None:
        """Execute a search query.

        Args:
            query: The search query.
            limit: Maximum number of results to retrieve.
        """
        self._state.query = query
        self._state.error_message = None
        self._state.search_complete = False

        if not query.strip():
            self._state.results = []
            self._state.filtered_results = []
            return

        try:
            # Search with optional language/type filters from VectorStore
            self._state.results = await self._store.search(
                query=query,
                limit=limit,
                language=self._state.filters.language,
                chunk_type=self._state.filters.chunk_type,
            )
            self._state.apply_filters()
            self._state.search_complete = True
        except (RuntimeError, OSError, ValueError, KeyError) as e:
            # RuntimeError: Vector search/LanceDB failures
            # OSError: Network/file system issues
            # ValueError: Invalid search parameters
            # KeyError: Missing data during search
            logger.exception(f"Search error: {e}")
            self._state.error_message = f"Search error: {e}"
            self._state.results = []
            self._state.filtered_results = []

    def _build_results_table(self) -> Table:
        """Build the results table display.

        Returns:
            Rich Table with search results.
        """
        table = Table(
            title=f"Results for: {self._state.query}"
            if self._state.query
            else "Enter a search query",
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )

        table.add_column("#", style="dim", width=4)
        table.add_column("Score", width=6)
        table.add_column("Type", width=10)
        table.add_column("Name", width=25)
        table.add_column("File", width=40)
        table.add_column("Lines", width=10)

        for i, result in enumerate(self._state.filtered_results):
            chunk = result.chunk

            # Highlight selected row
            is_selected = i == self._state.selected_index
            row_style = Style(bgcolor="blue") if is_selected else None

            # Format score with color
            score_text = f"{result.score:.3f}"
            if result.score >= 0.8:
                score_style = "green"
            elif result.score >= 0.5:
                score_style = "yellow"
            else:
                score_style = "red"

            # Format name (truncate if too long)
            name = chunk.name or "[unnamed]"
            if len(name) > 23:
                name = name[:20] + "..."

            # Format file path (show relative path)
            file_path = chunk.file_path
            if len(file_path) > 38:
                file_path = "..." + file_path[-35:]

            # Format line numbers
            lines = f"{chunk.start_line}-{chunk.end_line}"

            table.add_row(
                str(i + 1),
                Text(score_text, style=score_style),
                chunk.chunk_type.value,
                name,
                file_path,
                lines,
                style=row_style,
            )

        return table

    def _build_filters_panel(self) -> Panel:
        """Build the filters display panel.

        Returns:
            Rich Panel showing active filters.
        """
        filters = self._state.filters.to_dict()

        if not filters:
            content = Text("No filters active", style="dim")
        else:
            lines = []
            for key, value in filters.items():
                lines.append(f"  {key}: {value}")
            content = Text("\n".join(lines))

        return Panel(
            content,
            title="Active Filters",
            border_style="green" if filters else "dim",
        )

    def _build_help_panel(self) -> Panel:
        """Build the keyboard help panel.

        Returns:
            Rich Panel with keyboard shortcuts.
        """
        help_text = Text()
        shortcuts = [
            ("Up/Down", "Navigate"),
            ("Enter", "Show preview"),
            ("l", "Filter language"),
            ("t", "Filter type"),
            ("f", "Filter file"),
            ("s", "Filter score"),
            ("c", "Clear filters"),
            ("/", "New search"),
            ("q", "Quit"),
        ]

        for i, (key, action) in enumerate(shortcuts):
            if i > 0:
                help_text.append("  ")
            help_text.append(key, style="bold cyan")
            help_text.append(f":{action}")

        return Panel(help_text, title="Keyboard Shortcuts", border_style="dim")

    def _build_preview_panel(self) -> Panel | None:
        """Build the code preview panel for the selected result.

        Returns:
            Rich Panel with syntax-highlighted code, or None if no selection.
        """
        result = self._state.get_selected_result()
        if not result:
            return None

        chunk = result.chunk

        # Get syntax highlighting lexer
        lexer = LANGUAGE_LEXERS.get(chunk.language.value, "text")

        # Build the code content with context lines
        code_lines = chunk.content.split("\n")

        # Create syntax highlighted view
        syntax = Syntax(
            chunk.content,
            lexer,
            line_numbers=True,
            start_line=chunk.start_line,
            highlight_lines=set(range(chunk.start_line, chunk.end_line + 1)),
            theme="monokai",
        )

        # Build title with file info
        title = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
        if chunk.name:
            title = f"{chunk.name} - {title}"

        # Add docstring if present
        if chunk.docstring:
            doc_text = Text(
                f"Docstring: {chunk.docstring[:200]}...", style="italic dim"
            )
            content = Group(doc_text, syntax)
        else:
            content = syntax

        return Panel(
            content,
            title=title,
            subtitle=f"Score: {result.score:.3f} | Type: {chunk.chunk_type.value} | Lang: {chunk.language.value}",
            border_style="green",
        )

    def _build_input_prompt(self) -> Panel:
        """Build the input prompt panel.

        Returns:
            Rich Panel for current input mode.
        """
        mode = self._state.input_mode

        if mode == "search":
            prompt = f"Search: {self._state.query}"
            style = "cyan"
        elif mode == "filter_language":
            languages = [lang.value for lang in Language]
            prompt = f"Enter language ({', '.join(languages[:5])}...): "
            style = "yellow"
        elif mode == "filter_type":
            types = [ct.value for ct in ChunkType]
            prompt = f"Enter type ({', '.join(types)}): "
            style = "yellow"
        elif mode == "filter_path":
            prompt = "Enter file pattern (e.g., src/**/*.py): "
            style = "yellow"
        elif mode == "filter_score":
            prompt = "Enter minimum score (0.0-1.0): "
            style = "yellow"
        else:
            prompt = "Search: "
            style = "cyan"

        return Panel(
            Text(prompt, style=style),
            border_style=style,
        )

    def _build_layout(self) -> Layout:
        """Build the complete display layout.

        Returns:
            Rich Layout with all components.
        """
        layout = Layout()

        # Error message if present
        if self._state.error_message:
            error_panel = Panel(
                Text(self._state.error_message, style="bold red"),
                title="Error",
                border_style="red",
            )

        # Build main layout
        if self._state.show_preview and self._state.get_selected_result():
            # Show results on left, preview on right
            layout.split_column(
                Layout(name="top", ratio=1),
                Layout(name="input", size=3),
                Layout(name="help", size=3),
            )

            layout["top"].split_row(
                Layout(name="results", ratio=1),
                Layout(name="preview", ratio=1),
            )

            layout["results"].split_column(
                Layout(self._build_results_table(), name="table", ratio=4),
                Layout(self._build_filters_panel(), name="filters", size=6),
            )
            layout["preview"].update(self._build_preview_panel())
        else:
            # Results only view
            layout.split_column(
                Layout(name="main", ratio=1),
                Layout(name="filters", size=6),
                Layout(name="input", size=3),
                Layout(name="help", size=3),
            )

            layout["main"].update(self._build_results_table())
            layout["filters"].update(self._build_filters_panel())

        layout["input"].update(self._build_input_prompt())
        layout["help"].update(self._build_help_panel())

        return layout

    def display_results(self) -> None:
        """Display the current search results (non-interactive mode)."""
        self._console.print(self._build_results_table())

        if self._state.filters.to_dict():
            self._console.print(self._build_filters_panel())

    def display_preview(self, result: SearchResult) -> None:
        """Display a detailed preview of a search result.

        Args:
            result: The search result to preview.
        """
        self._state.selected_index = (
            self._state.filtered_results.index(result)
            if result in self._state.filtered_results
            else 0
        )
        preview = self._build_preview_panel()
        if preview:
            self._console.print(preview)

    async def run(self, initial_query: str | None = None) -> None:
        """Run the interactive search session.

        Args:
            initial_query: Optional initial search query.
        """
        # Import here to avoid issues when stdin is not a TTY
        try:
            import readchar
        except ImportError:
            self._console.print(
                "[yellow]Interactive mode requires 'readchar' package.[/yellow]"
            )
            self._console.print("Install with: pip install readchar")
            self._console.print("Or use non-interactive mode with --query")
            return

        if initial_query:
            await self.search(initial_query)

        self._console.clear()

        running = True
        while running:
            # Display current state
            self._console.clear()
            self._console.print(self._build_layout())

            # Get user input
            try:
                key = readchar.readkey()
            except KeyboardInterrupt:
                running = False
                continue

            # Handle input based on current mode
            if self._state.input_mode == "search":
                running = await self._handle_search_mode(key)
            else:
                await self._handle_filter_mode(key)

        self._console.clear()
        self._console.print("[dim]Search session ended.[/dim]")

    async def _handle_search_mode(self, key: str) -> bool:
        """Handle keyboard input in search mode.

        Args:
            key: The key pressed.

        Returns:
            False if the session should end, True otherwise.
        """
        try:
            import readchar
        except ImportError:
            return False

        if key == "q":
            return False
        elif key == readchar.key.UP:
            self._state.move_selection(-1)
        elif key == readchar.key.DOWN:
            self._state.move_selection(1)
        elif key == readchar.key.ENTER:
            self._state.show_preview = not self._state.show_preview
        elif key == "l":
            self._state.input_mode = "filter_language"
        elif key == "t":
            self._state.input_mode = "filter_type"
        elif key == "f":
            self._state.input_mode = "filter_path"
        elif key == "s":
            self._state.input_mode = "filter_score"
        elif key == "c":
            self._state.filters.clear()
            self._state.apply_filters()
        elif key == "/":
            # New search - prompt for query
            self._console.clear()
            query = self._console.input("[cyan]Search query: [/cyan]")
            if query:
                await self.search(query)

        return True

    async def _handle_filter_mode(self, key: str) -> None:
        """Handle keyboard input in filter mode.

        Args:
            key: The key pressed.
        """
        try:
            import readchar
        except ImportError:
            return

        if key == readchar.key.ESCAPE:
            self._state.input_mode = "search"
            return

        if key == readchar.key.ENTER:
            # Prompt for filter value based on mode
            mode = self._state.input_mode

            if mode == "filter_language":
                self._console.clear()
                languages = [lang.value for lang in Language]
                self._console.print(f"[dim]Available: {', '.join(languages)}[/dim]")
                value = (
                    self._console.input("[yellow]Language: [/yellow]").strip().lower()
                )
                if value:
                    if value in languages:
                        self._state.filters.language = value
                    else:
                        self._state.error_message = f"Invalid language: {value}"

            elif mode == "filter_type":
                self._console.clear()
                types = [ct.value for ct in ChunkType]
                self._console.print(f"[dim]Available: {', '.join(types)}[/dim]")
                value = self._console.input("[yellow]Type: [/yellow]").strip().lower()
                if value:
                    if value in types:
                        self._state.filters.chunk_type = value
                    else:
                        self._state.error_message = f"Invalid type: {value}"

            elif mode == "filter_path":
                self._console.clear()
                value = self._console.input("[yellow]File pattern: [/yellow]").strip()
                if value:
                    self._state.filters.file_pattern = value

            elif mode == "filter_score":
                self._console.clear()
                value = self._console.input(
                    "[yellow]Minimum score (0.0-1.0): [/yellow]"
                ).strip()
                if value:
                    try:
                        score = float(value)
                        if 0.0 <= score <= 1.0:
                            self._state.filters.min_similarity = score
                        else:
                            self._state.error_message = (
                                "Score must be between 0.0 and 1.0"
                            )
                    except (ValueError, TypeError):
                        # ValueError: Invalid numeric string
                        # TypeError: Invalid input type
                        self._state.error_message = f"Invalid score: {value}"

            # Re-apply filters and re-search if needed
            if self._state.query:
                await self.search(self._state.query)

            self._state.input_mode = "search"


async def run_search(
    repo_path: Path,
    query: str | None = None,
    language: str | None = None,
    chunk_type: str | None = None,
    file_pattern: str | None = None,
    min_score: float = 0.0,
    limit: int = 20,
    interactive: bool = True,
    show_preview: bool = False,
) -> None:
    """Run the search command.

    Args:
        repo_path: Path to the repository.
        query: Initial search query.
        language: Filter by language.
        chunk_type: Filter by chunk type.
        file_pattern: Filter by file path pattern.
        min_score: Minimum similarity score.
        limit: Maximum number of results.
        interactive: Whether to run in interactive mode.
        show_preview: Show preview of first result in non-interactive mode.
    """
    console = Console()

    # Resolve repo path
    repo_path = repo_path.resolve()
    if not repo_path.exists():
        console.print(f"[red]Repository not found: {repo_path}[/red]")
        return

    # Check for vector store
    vector_db_path = repo_path / ".deepwiki" / "vectordb"
    if not vector_db_path.exists():
        console.print(
            f"[red]Repository not indexed. Run: index_repository {repo_path}[/red]"
        )
        return

    # Initialize vector store
    console.print("[dim]Loading vector store...[/dim]")
    config = get_config()
    embedding_provider = get_embedding_provider()
    vector_store = VectorStore(
        db_path=vector_db_path,
        embedding_provider=embedding_provider,
    )

    # Create search instance
    search = InteractiveSearch(vector_store, repo_path)

    # Set initial filters
    search._state.filters = SearchFilters(
        language=language,
        chunk_type=chunk_type,
        file_pattern=file_pattern,
        min_similarity=min_score,
    )

    if interactive and query:
        # Run with initial query in interactive mode
        await search.run(initial_query=query)
    elif interactive:
        # Run fully interactive
        await search.run()
    elif query:
        # Non-interactive mode
        await search.search(query, limit=limit)
        search.display_results()

        if show_preview and search._state.filtered_results:
            console.print()
            search.display_preview(search._state.filtered_results[0])
    else:
        console.print(
            "[red]Query is required in non-interactive mode. Use --query or -q.[/red]"
        )


def main() -> int:
    """Main entry point for the interactive search CLI."""
    parser = argparse.ArgumentParser(
        prog="deepwiki-search",
        description="Interactive code search for local-deepwiki indexed repositories",
    )

    parser.add_argument(
        "repo_path",
        type=Path,
        help="Path to the indexed repository",
    )

    parser.add_argument(
        "-q",
        "--query",
        type=str,
        help="Search query (required for non-interactive mode)",
    )

    parser.add_argument(
        "-l",
        "--language",
        type=str,
        help="Filter by programming language",
    )

    parser.add_argument(
        "-t",
        "--type",
        type=str,
        dest="chunk_type",
        help="Filter by chunk type (function, class, method, etc.)",
    )

    parser.add_argument(
        "-f",
        "--file-pattern",
        type=str,
        help="Filter by file path pattern (e.g., src/**/*.py)",
    )

    parser.add_argument(
        "-s",
        "--min-score",
        type=float,
        default=0.0,
        help="Minimum similarity score (0.0-1.0)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results (default: 20)",
    )

    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive mode (requires --query)",
    )

    parser.add_argument(
        "-p",
        "--preview",
        action="store_true",
        help="Show preview of first result in non-interactive mode",
    )

    args = parser.parse_args()

    # Validate min_score
    if not 0.0 <= args.min_score <= 1.0:
        print("Error: --min-score must be between 0.0 and 1.0", file=sys.stderr)
        return 1

    # Non-interactive mode requires a query
    if args.no_interactive and not args.query:
        print("Error: --query is required when using --no-interactive", file=sys.stderr)
        return 1

    try:
        asyncio.run(
            run_search(
                repo_path=args.repo_path,
                query=args.query,
                language=args.language,
                chunk_type=args.chunk_type,
                file_pattern=args.file_pattern,
                min_score=args.min_score,
                limit=args.limit,
                interactive=not args.no_interactive,
                show_preview=args.preview,
            )
        )
        return 0
    except KeyboardInterrupt:
        print("\nSearch cancelled.")
        return 130
    except (RuntimeError, OSError, ValueError) as e:
        # RuntimeError: Vector store or search failures
        # OSError: File system or database access errors
        # ValueError: Invalid configuration or parameters
        print(f"Error: {e}", file=sys.stderr)
        logger.exception("Search failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
