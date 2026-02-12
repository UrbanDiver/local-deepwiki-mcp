"""Unified CLI entry point for local-deepwiki.

Provides `deepwiki` command that dispatches to all subcommands:
    deepwiki init         - Initialize project configuration
    deepwiki status       - Show index health and freshness
    deepwiki update       - Index repo and regenerate wiki
    deepwiki mcp          - Start the MCP server
    deepwiki serve        - Serve wiki with web UI
    deepwiki watch        - Watch mode for auto-reindexing
    deepwiki export       - Export wiki to static HTML
    deepwiki export-pdf   - Export wiki to PDF
    deepwiki config       - Configuration management
    deepwiki search       - Interactive code search
    deepwiki cache        - Cache management
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.table import Table

# Subcommand table: name -> (module_path, function_name, description)
SUBCOMMANDS: dict[str, tuple[str, str, str]] = {
    "init": ("local_deepwiki.cli.init_cli", "main", "Initialize project configuration"),
    "status": (
        "local_deepwiki.cli.status_cli",
        "main",
        "Show index health and freshness",
    ),
    "update": (
        "local_deepwiki.cli.update_cli",
        "main",
        "Index repo and regenerate wiki",
    ),
    "mcp": ("local_deepwiki.server", "main", "Start the MCP server"),
    "serve": ("local_deepwiki.web.app", "main", "Serve wiki with web UI"),
    "watch": ("local_deepwiki.watcher", "main", "Watch mode for auto-reindexing"),
    "export": ("local_deepwiki.export.html", "main", "Export wiki to static HTML"),
    "export-pdf": ("local_deepwiki.export.pdf", "main", "Export wiki to PDF"),
    "config": ("local_deepwiki.cli.config_cli", "main", "Configuration management"),
    "search": (
        "local_deepwiki.cli.interactive_search",
        "main",
        "Interactive code search",
    ),
    "cache": ("local_deepwiki.cli.cache_cli", "main", "Cache management"),
}


def show_help() -> None:
    """Display available subcommands using rich Table."""
    console = Console()
    console.print("\n[bold]deepwiki[/bold] - Local DeepWiki documentation tool\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Command", style="green", width=15)
    table.add_column("Description", width=45)

    for name, (_, _, description) in sorted(SUBCOMMANDS.items()):
        table.add_row(name, description)

    console.print(table)
    console.print("\nUsage: [bold]deepwiki <command> [args...][/bold]")
    console.print("\n[bold]Examples:[/bold]")
    console.print(
        "  deepwiki init                    Guided setup wizard for new users"
    )
    console.print("  deepwiki status                  Show index health and freshness")
    console.print("  deepwiki update                  Index repo and regenerate wiki")
    console.print("  deepwiki update --dry-run        Preview what would change")
    console.print(
        "  deepwiki mcp                     Start MCP server (for IDE integration)"
    )
    console.print(
        "  deepwiki serve .deepwiki          Browse wiki at http://localhost:8080"
    )
    console.print("  deepwiki config show              Show current configuration")
    console.print("  deepwiki config health-check      Verify providers are working")
    console.print("  deepwiki cache stats              Show cache hit rates and sizes")
    console.print("  deepwiki export .deepwiki -o html  Export wiki to static HTML")
    console.print("  deepwiki search                   Interactive fuzzy code search")
    console.print("  deepwiki watch /path/to/repo      Auto-reindex on file changes")
    console.print()


def main() -> int:
    """Main entry point for the unified deepwiki CLI."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        show_help()
        return 0

    command = sys.argv[1]

    if command not in SUBCOMMANDS:
        console = Console(stderr=True)
        console.print(f"[red]Unknown command: {command}[/red]")
        console.print("Run [bold]deepwiki --help[/bold] for available commands.")
        return 1

    module_path, func_name, _ = SUBCOMMANDS[command]

    # Strip the subcommand from sys.argv so the delegated module sees correct args
    sys.argv = [f"deepwiki {command}"] + sys.argv[2:]

    # Lazy import and delegate
    import importlib

    module = importlib.import_module(module_path)
    func = getattr(module, func_name)

    result = func()

    # Handle both int returns and None (treat None as success)
    if isinstance(result, int):
        return result
    return 0


if __name__ == "__main__":
    sys.exit(main())
