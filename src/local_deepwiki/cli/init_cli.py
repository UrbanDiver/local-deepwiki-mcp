"""Interactive init wizard for local-deepwiki.

Guides new users through provider selection, language detection, and
config file creation:

    deepwiki init [REPO_PATH] [--non-interactive] [--force] [--provider ...] [--embedding ...] [--config PATH]
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Literal

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from local_deepwiki.config import Config

# ── Directories to skip during language scanning ──────────────────────
_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        "venv",
        ".venv",
        "dist",
        "build",
        ".next",
        "target",
        "vendor",
        "htmlcov",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "coverage",
    }
)

# Static extension→language map (independent of installed grammars)
_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".swift": "swift",
    ".rb": "ruby",
    ".rake": "ruby",
    ".gemspec": "ruby",
    ".php": "php",
    ".phtml": "php",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
}

# Canonical order for display
_ALL_LANGUAGES = [
    "python",
    "typescript",
    "javascript",
    "go",
    "rust",
    "java",
    "c",
    "cpp",
    "swift",
    "ruby",
    "php",
    "kotlin",
    "csharp",
]

# Config file search order (matches Config.load and ConfigValidator)
_CONFIG_SEARCH_PATHS = [
    Path.cwd() / "config.yaml",
    Path.cwd() / ".local-deepwiki.yaml",
    Path.home() / ".config" / "local-deepwiki" / "config.yaml",
    Path.home() / ".local-deepwiki.yaml",
]

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "local-deepwiki" / "config.yaml"

_MAX_FILES_SCAN = 10_000


# ── Step helpers ──────────────────────────────────────────────────────


def find_existing_config() -> Path | None:
    """Return the first existing config file path, or None."""
    for path in _CONFIG_SEARCH_PATHS:
        if path.exists():
            return path
    return None


def detect_languages(repo_path: Path) -> dict[str, int]:
    """Scan *repo_path* for source files and return {language: file_count}.

    Skips common non-source directories and caps the scan at
    ``_MAX_FILES_SCAN`` files for speed.
    """
    counts: Counter[str] = Counter()
    scanned = 0

    for item in repo_path.rglob("*"):
        if scanned >= _MAX_FILES_SCAN:
            break
        # Skip excluded directories
        if any(part in _SKIP_DIRS for part in item.parts):
            continue
        if not item.is_file():
            continue
        scanned += 1
        lang = _EXTENSION_TO_LANGUAGE.get(item.suffix.lower())
        if lang is not None:
            counts[lang] += 1

    # Return sorted by count descending
    return dict(counts.most_common())


def detect_ollama(base_url: str = "http://localhost:11434") -> bool:
    """Return True if Ollama is reachable at *base_url*."""
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2):
            return True
    except Exception:  # noqa: BLE001 — CLI top-level handler: network probe must not crash init wizard
        return False


def detect_api_key(env_var: str) -> bool:
    """Return True if *env_var* is set and non-empty."""
    return bool(os.environ.get(env_var))


def _provider_status(available: bool) -> str:
    if available:
        return "[green]detected[/green]"
    return "[dim]not detected[/dim]"


def detect_providers() -> dict[str, bool]:
    """Detect which LLM providers are available.

    Returns:
        Dict mapping provider name to availability boolean.
    """
    return {
        "ollama": detect_ollama(),
        "anthropic": detect_api_key("ANTHROPIC_API_KEY"),
        "openai": detect_api_key("OPENAI_API_KEY"),
    }


def build_config(
    llm_provider: Literal["ollama", "anthropic", "openai"],
    embedding_provider: Literal["local", "openai"],
    languages: list[str],
) -> Config:
    """Build a Config object from wizard selections."""
    from local_deepwiki.config.models import ParsingConfig

    base = Config()
    config = base.with_llm_provider(llm_provider)
    config = config.with_embedding_provider(embedding_provider)

    # Set detected languages if different from default
    if sorted(languages) != sorted(base.parsing.languages):
        new_parsing = ParsingConfig(languages=languages)
        config = config.model_copy(update={"parsing": new_parsing})

    return config


def config_to_minimal_dict(config: Config) -> dict:
    """Dump only the fields that differ from defaults for a cleaner YAML."""
    defaults = Config()
    full = config.model_dump(
        exclude={
            "effective_embedding_batch_size",
            "effective_max_workers",
            "effective_llm_concurrency",
        }
    )
    default_full = defaults.model_dump(
        exclude={
            "effective_embedding_batch_size",
            "effective_max_workers",
            "effective_llm_concurrency",
        }
    )

    def _diff(current: dict, default: dict) -> dict:
        result: dict = {}
        for key, value in current.items():
            default_value = default.get(key)
            if isinstance(value, dict) and isinstance(default_value, dict):
                nested = _diff(value, default_value)
                if nested:
                    result[key] = nested
            elif value != default_value:
                result[key] = value
        return result

    return _diff(full, default_full)


def write_config(config_dict: dict, dest: Path) -> None:
    """Write *config_dict* as YAML to *dest*, creating parent dirs."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.dump(config_dict, default_flow_style=False, sort_keys=False))


# ── Main wizard flow ─────────────────────────────────────────────────


def run_wizard(
    repo_path: Path,
    console: Console,
    *,
    non_interactive: bool = False,
    force: bool = False,
    provider_flag: str | None = None,
    embedding_flag: str | None = None,
    config_dest: Path | None = None,
) -> int:
    """Run the init wizard and return an exit code (0 = success)."""

    console.print("\n[bold]deepwiki init[/bold] - project configuration wizard\n")

    # ── Step 1: Check for existing config ─────────────────────────
    existing = find_existing_config()
    if existing is not None:
        console.print(f"[yellow]Existing config found:[/yellow] {existing}")
        if non_interactive and not force:
            console.print(
                "[red]Aborting (--non-interactive, will not overwrite). Use --force to overwrite.[/red]"
            )
            return 1
        if non_interactive and force:
            console.print("[yellow]--force: overwriting existing config.[/yellow]")
        else:
            overwrite = Prompt.ask("Overwrite?", choices=["yes", "no"], default="no")
            if overwrite != "yes":
                console.print("[dim]Aborted.[/dim]")
                return 1

    # ── Step 2: Detect languages ──────────────────────────────────
    console.print(f"[bold]Scanning[/bold] {repo_path.resolve()} for source files...")
    lang_counts = detect_languages(repo_path)

    if lang_counts:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Language", style="green", width=15)
        table.add_column("Files", justify="right", width=8)
        for lang, count in lang_counts.items():
            table.add_row(lang, str(count))
        console.print(table)
    else:
        console.print("[dim]No recognised source files found.[/dim]")

    detected_languages = list(lang_counts.keys()) if lang_counts else _ALL_LANGUAGES

    # ── Step 3: Choose LLM provider ──────────────────────────────
    providers = detect_providers()

    console.print("\n[bold]LLM providers:[/bold]")
    for name, available in providers.items():
        console.print(f"  {name}: {_provider_status(available)}")

    if non_interactive:
        if provider_flag:
            llm_provider = provider_flag
        else:
            # Pick first available, preferring ollama → anthropic → openai
            llm_provider = next(
                (p for p in ("ollama", "anthropic", "openai") if providers.get(p)),
                "ollama",
            )
    else:
        # Build default from first available provider
        default_provider = next(
            (p for p in ("ollama", "anthropic", "openai") if providers.get(p)),
            "ollama",
        )
        llm_provider = Prompt.ask(
            "\nLLM provider",
            choices=["ollama", "anthropic", "openai"],
            default=default_provider,
        )

    # ── Step 4: Choose embedding provider ─────────────────────────
    if non_interactive:
        embedding_provider = embedding_flag or "local"
    else:
        console.print("\n[bold]Embedding providers:[/bold]")
        console.print("  local: sentence-transformers (free, slower first run)")
        console.print("  openai: OpenAI embeddings (fast, costs money)")
        embedding_provider = Prompt.ask(
            "\nEmbedding provider",
            choices=["local", "openai"],
            default="local",
        )

    # ── Step 5: Build config ──────────────────────────────────────
    config = build_config(llm_provider, embedding_provider, detected_languages)  # type: ignore[arg-type]

    # ── Step 6: Write config ──────────────────────────────────────
    dest = config_dest or _DEFAULT_CONFIG_PATH
    minimal = config_to_minimal_dict(config)

    if not minimal:
        # All defaults — write a comment-only file so the path exists
        minimal = {"llm": {"provider": llm_provider}}

    write_config(minimal, dest)
    console.print(f"\n[green]Config written to:[/green] {dest}")

    # ── Step 7: Summary & next steps ──────────────────────────────
    summary_lines = [
        f"[bold]Config path:[/bold]  {dest}",
        f"[bold]LLM provider:[/bold] {llm_provider}",
        f"[bold]Embedding:[/bold]    {embedding_provider}",
        f"[bold]Languages:[/bold]    {', '.join(detected_languages[:8])}{'...' if len(detected_languages) > 8 else ''}",
    ]
    console.print(
        Panel(
            "\n".join(summary_lines),
            title="Setup Complete",
            border_style="green",
        )
    )
    console.print("[bold]Next steps:[/bold]")
    console.print(
        "  deepwiki mcp                  Start MCP server (for IDE integration)"
    )
    console.print(
        "  deepwiki serve .deepwiki       Browse wiki at http://localhost:8080"
    )
    console.print("  deepwiki config health-check   Verify providers are working")
    console.print()

    return 0


# ── CLI entry point ──────────────────────────────────────────────────


def main() -> int:
    """Main entry point for ``deepwiki init``."""
    parser = argparse.ArgumentParser(
        prog="deepwiki init",
        description="Initialize local-deepwiki configuration with a guided wizard",
        epilog=(
            "examples:\n"
            "  deepwiki init                              Interactive wizard\n"
            "  deepwiki init /path/to/repo                Scan a specific repo\n"
            "  deepwiki init --non-interactive             Use auto-detected defaults\n"
            "  deepwiki init --provider anthropic          Pre-select LLM provider\n"
            "  deepwiki init --non-interactive --force     Overwrite existing config\n"
            "  deepwiki init --config ./my-config.yaml     Write to custom path\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Repository path to scan for languages (default: current directory)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip all prompts, use detected defaults and flags",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config without prompting (use with --non-interactive)",
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "anthropic", "openai"],
        help="LLM provider (used with --non-interactive)",
    )
    parser.add_argument(
        "--embedding",
        choices=["local", "openai"],
        help="Embedding provider (used with --non-interactive)",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Config file destination (default: ~/.config/local-deepwiki/config.yaml)",
    )

    args = parser.parse_args()
    console = Console()

    repo = Path(args.repo_path)
    if not repo.is_dir():
        console.print(f"[red]Not a directory: {repo}[/red]")
        return 1

    config_dest = Path(args.config) if args.config else None

    return run_wizard(
        repo,
        console,
        non_interactive=args.non_interactive,
        force=args.force,
        provider_flag=args.provider,
        embedding_flag=args.embedding,
        config_dest=config_dest,
    )


if __name__ == "__main__":
    sys.exit(main())
