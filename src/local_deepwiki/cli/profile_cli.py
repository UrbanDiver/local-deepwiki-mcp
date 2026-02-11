"""Configuration profile management CLI for local-deepwiki.

Provides commands to save, activate, list, and delete config profiles:
    deepwiki config profile save <name>
    deepwiki config profile use <name>
    deepwiki config profile list
    deepwiki config profile delete <name>
"""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table

from local_deepwiki.config.loader import (
    activate_profile,
    delete_profile,
    get_active_profile_name,
    list_profiles,
    save_profile,
)


def cmd_profile_save(args: argparse.Namespace) -> int:
    """Save current config as a named profile."""
    console = Console()
    name = args.name

    try:
        path = save_profile(name)
        console.print(f"[green]Profile '{name}' saved to {path}[/green]")
        return 0
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return 1
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        return 1


def cmd_profile_use(args: argparse.Namespace) -> int:
    """Activate a saved profile."""
    console = Console()
    name = args.name

    try:
        activate_profile(name)
        console.print(f"[green]Switched to profile '{name}'[/green]")
        return 0
    except FileNotFoundError:
        console.print(f"[red]Profile '{name}' not found[/red]")
        console.print(
            "Run [bold]deepwiki config profile list[/bold] to see available profiles."
        )
        return 1


def cmd_profile_list(args: argparse.Namespace) -> int:
    """List all saved profiles."""
    console = Console()
    profiles = list_profiles()
    active = get_active_profile_name()

    if not profiles:
        console.print("[dim]No profiles saved yet.[/dim]")
        console.print("Save one with: [bold]deepwiki config profile save <name>[/bold]")
        return 0

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Profile", style="green", width=20)
    table.add_column("Status", width=10)

    for name in profiles:
        status = "[bold yellow]* active[/bold yellow]" if name == active else ""
        table.add_row(name, status)

    console.print(table)
    return 0


def cmd_profile_delete(args: argparse.Namespace) -> int:
    """Delete a saved profile."""
    console = Console()
    name = args.name

    if delete_profile(name):
        console.print(f"[green]Profile '{name}' deleted[/green]")
        return 0
    else:
        console.print(f"[red]Profile '{name}' not found[/red]")
        return 1


def register_profile_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the 'profile' subcommand under the config CLI.

    Args:
        subparsers: The subparsers action from the parent parser.
    """
    profile_parser = subparsers.add_parser(
        "profile", help="Manage configuration profiles"
    )
    profile_subs = profile_parser.add_subparsers(dest="profile_command")

    # save
    save_parser = profile_subs.add_parser(
        "save", help="Save current config as a profile"
    )
    save_parser.add_argument("name", help="Profile name")
    save_parser.set_defaults(func=cmd_profile_save)

    # use
    use_parser = profile_subs.add_parser("use", help="Activate a saved profile")
    use_parser.add_argument("name", help="Profile name to activate")
    use_parser.set_defaults(func=cmd_profile_use)

    # list
    list_parser = profile_subs.add_parser("list", help="List all saved profiles")
    list_parser.set_defaults(func=cmd_profile_list)

    # delete
    delete_parser = profile_subs.add_parser("delete", help="Delete a saved profile")
    delete_parser.add_argument("name", help="Profile name to delete")
    delete_parser.set_defaults(func=cmd_profile_delete)


def dispatch_profile(args: argparse.Namespace) -> int:
    """Dispatch profile subcommand."""
    if not hasattr(args, "profile_command") or args.profile_command is None:
        console = Console()
        console.print("Usage: deepwiki config profile {save|use|list|delete}")
        return 1
    return args.func(args)
