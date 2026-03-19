"""Configuration validation and display CLI for local-deepwiki."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from local_deepwiki.cli.config_validator import ConfigValidator, ValidationIssue
from local_deepwiki.config import Config
from local_deepwiki.models.provider_types import EmbeddingProviderType, LLMProviderType


# ---------------------------------------------------------------------------
# display_config helpers
# ---------------------------------------------------------------------------


def _format_llm_section(tree: Tree, config: Config) -> None:
    """Add the LLM configuration branch to *tree*."""
    llm_branch = tree.add("[bold cyan]LLM[/bold cyan]")
    llm_branch.add(f"Provider: [green]{config.llm.provider}[/green]")
    if config.llm.provider == LLMProviderType.OLLAMA:
        llm_branch.add(f"Model: {config.llm.ollama.model}")
        llm_branch.add(f"Base URL: {config.llm.ollama.base_url}")
    elif config.llm.provider == LLMProviderType.ANTHROPIC:
        llm_branch.add(f"Model: {config.llm.anthropic.model}")
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        llm_branch.add(
            f"API Key: {'[green]set[/green]' if key else '[red]not set[/red]'}"
        )
    elif config.llm.provider == LLMProviderType.OPENAI:
        llm_branch.add(f"Model: {config.llm.openai.model}")
        key = os.environ.get("OPENAI_API_KEY", "")
        llm_branch.add(
            f"API Key: {'[green]set[/green]' if key else '[red]not set[/red]'}"
        )


def _format_embedding_section(tree: Tree, config: Config) -> None:
    """Add the Embedding configuration branch to *tree*."""
    embed_branch = tree.add("[bold cyan]Embedding[/bold cyan]")
    embed_branch.add(f"Provider: [green]{config.embedding.provider}[/green]")
    if config.embedding.provider == EmbeddingProviderType.LOCAL:
        embed_branch.add(f"Model: {config.embedding.local.model}")
    else:
        embed_branch.add(f"Model: {config.embedding.openai.model}")


def _format_parsing_section(tree: Tree, config: Config) -> None:
    """Add the Parsing configuration branch to *tree*."""
    parse_branch = tree.add("[bold cyan]Parsing[/bold cyan]")
    parse_branch.add(f"Languages: {len(config.parsing.languages)} configured")
    parse_branch.add(
        f"Max file size: {config.parsing.max_file_size / 1024 / 1024:.1f} MB"
    )
    parse_branch.add(f"Exclude patterns: {len(config.parsing.exclude_patterns)}")


def _format_chunking_section(tree: Tree, config: Config) -> None:
    """Add the Chunking configuration branch to *tree*."""
    chunk_branch = tree.add("[bold cyan]Chunking[/bold cyan]")
    chunk_branch.add(f"Max tokens: {config.chunking.max_chunk_tokens}")
    chunk_branch.add(f"Overlap: {config.chunking.overlap_tokens}")
    chunk_branch.add(f"Parallel workers: {config.chunking.parallel_workers}")
    chunk_branch.add(f"Batch size: {config.chunking.batch_size}")


def _format_wiki_section(tree: Tree, config: Config) -> None:
    """Add the Wiki Generation configuration branch to *tree*."""
    wiki_branch = tree.add("[bold cyan]Wiki Generation[/bold cyan]")
    wiki_branch.add(f"Max file docs: {config.wiki.max_file_docs or 'unlimited'}")
    wiki_branch.add(f"Concurrent LLM calls: {config.wiki.max_concurrent_llm_calls}")
    wiki_branch.add(f"Cloud for GitHub: {config.wiki.use_cloud_for_github}")
    wiki_branch.add(f"Chat provider: {config.wiki.chat_llm_provider}")


def _format_research_section(tree: Tree, config: Config) -> None:
    """Add the Deep Research configuration branch to *tree*."""
    research_branch = tree.add("[bold cyan]Deep Research[/bold cyan]")
    research_branch.add(f"Max sub-questions: {config.deep_research.max_sub_questions}")
    research_branch.add(
        f"Chunks per question: {config.deep_research.chunks_per_subquestion}"
    )
    research_branch.add(f"Max total chunks: {config.deep_research.max_total_chunks}")


def _format_cache_section(tree: Tree, config: Config) -> None:
    """Add the Caching configuration branch to *tree*."""
    cache_branch = tree.add("[bold cyan]Caching[/bold cyan]")
    embed_cache = config.embedding_cache
    cache_branch.add(
        f"Embedding cache: {'[green]enabled[/green]' if embed_cache.enabled else '[yellow]disabled[/yellow]'}"
    )
    if embed_cache.enabled:
        cache_branch.add(f"  TTL: {embed_cache.ttl_seconds // 3600} hours")
        cache_branch.add(f"  Max entries: {embed_cache.max_entries:,}")

    llm_cache = config.llm_cache
    cache_branch.add(
        f"LLM cache: {'[green]enabled[/green]' if llm_cache.enabled else '[yellow]disabled[/yellow]'}"
    )
    if llm_cache.enabled:
        cache_branch.add(f"  TTL: {llm_cache.ttl_seconds // 3600} hours")
        cache_branch.add(f"  Similarity threshold: {llm_cache.similarity_threshold}")


def _format_output_section(tree: Tree, config: Config) -> None:
    """Add the Output configuration branch to *tree*."""
    output_branch = tree.add("[bold cyan]Output[/bold cyan]")
    output_branch.add(f"Wiki directory: {config.output.wiki_dir}")
    output_branch.add(f"Vector DB: {config.output.vector_db_name}")


def display_config(config: Config, console: Console) -> None:
    """Display the effective configuration using rich formatting."""
    tree = Tree("[bold blue]Configuration[/bold blue]")

    _format_llm_section(tree, config)
    _format_embedding_section(tree, config)
    _format_parsing_section(tree, config)
    _format_chunking_section(tree, config)
    _format_wiki_section(tree, config)
    _format_research_section(tree, config)
    _format_cache_section(tree, config)
    _format_output_section(tree, config)

    console.print(tree)


def display_issues(issues: list[ValidationIssue], console: Console) -> None:
    """Display validation issues in a formatted table."""
    if not issues:
        console.print(
            Panel(
                "[green]No validation issues found[/green]", title="Validation Result"
            )
        )
        return

    table = Table(title="Validation Issues", show_header=True, header_style="bold")
    table.add_column("Level", style="bold", width=8)
    table.add_column("Category", width=18)
    table.add_column("Message", width=45)
    table.add_column("Suggestion", width=35)

    for issue in issues:
        level_style = "red" if issue.level == "error" else "yellow"
        table.add_row(
            f"[{level_style}]{issue.level.upper()}[/{level_style}]",
            issue.category,
            issue.message,
            issue.suggestion or "",
        )

    console.print(table)

    # Summary
    errors = sum(1 for i in issues if i.level == "error")
    warnings = sum(1 for i in issues if i.level == "warning")

    if errors > 0:
        console.print(f"\n[red bold]Found {errors} error(s)[/red bold]", end="")
    if warnings > 0:
        if errors > 0:
            console.print(" and ", end="")
        else:
            console.print("\n", end="")
        console.print(f"[yellow]{warnings} warning(s)[/yellow]", end="")
    console.print()


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate configuration command."""
    console = Console()

    config_path = Path(args.config) if args.config else None
    validator = ConfigValidator(config_path)

    console.print("\n[bold]Validating configuration...[/bold]\n")

    if validator.config_path:
        console.print(f"Config file: [cyan]{validator.config_path}[/cyan]\n")
    else:
        console.print("Config file: [dim]Using defaults (no config file found)[/dim]\n")

    is_valid = validator.validate()
    display_issues(validator.issues, console)

    if is_valid:
        console.print("\n[green bold]Configuration is valid[/green bold]\n")
        return 0
    else:
        console.print("\n[red bold]Configuration has errors[/red bold]\n")
        return 1


def cmd_show(args: argparse.Namespace) -> int:
    """Show effective configuration command."""
    console = Console()

    config_path = Path(args.config) if args.config else None

    try:
        config = Config.load(config_path)
    except Exception as e:  # noqa: BLE001 — CLI top-level handler: config load errors shown to user
        console.print(f"[red]Error loading config: {e}[/red]")
        return 1

    if config_path and config_path.exists():
        console.print(f"\nConfig file: [cyan]{config_path}[/cyan]\n")
    else:
        # Check which default was used
        default_paths = [
            Path.home() / ".config" / "local-deepwiki" / "config.yaml",
            Path.home() / ".local-deepwiki.yaml",
        ]
        found = None
        for path in default_paths:
            if path.exists():
                found = path
                break
        if found:
            console.print(f"\nConfig file: [cyan]{found}[/cyan]\n")
        else:
            console.print(
                "\n[dim]Using default configuration (no config file found)[/dim]\n"
            )

    display_config(config, console)

    if args.raw:
        console.print("\n[bold]Raw Configuration:[/bold]\n")
        console.print_json(data=config.model_dump())

    return 0


# ---------------------------------------------------------------------------
# cmd_health_check helpers
# ---------------------------------------------------------------------------

_CheckResult = dict  # {"name": str, "passed": bool, "details": str, "requirement": str, "suggestion": str | None}


def _check_python_version() -> tuple[_CheckResult, bool]:
    """Check that Python >= 3.10 is in use."""
    py_version = sys.version_info
    passed = py_version >= (3, 10)
    result: _CheckResult = {
        "name": "Python version",
        "passed": passed,
        "details": f"{py_version.major}.{py_version.minor}.{py_version.micro}",
        "requirement": ">=3.10",
        "suggestion": "Upgrade to Python 3.10 or higher" if not passed else None,
    }
    return result, passed


def _check_required_packages() -> tuple[list[_CheckResult], bool]:
    """Check that required packages are importable."""
    required_packages = {
        "lancedb": "lancedb",
        "tree_sitter": "tree-sitter",
        "sentence_transformers": "sentence-transformers",
    }
    results: list[_CheckResult] = []
    all_passed = True

    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
            results.append(
                {
                    "name": f"Package: {package_name}",
                    "passed": True,
                    "details": "installed",
                    "requirement": "required",
                    "suggestion": None,
                }
            )
        except ImportError:
            results.append(
                {
                    "name": f"Package: {package_name}",
                    "passed": False,
                    "details": "not found",
                    "requirement": "required",
                    "suggestion": f"Install with: pip install {package_name}",
                }
            )
            all_passed = False

    return results, all_passed


def _check_llm_provider(config: Config) -> tuple[_CheckResult, bool]:
    """Check the configured LLM provider is accessible."""
    llm_provider = config.llm.provider

    if llm_provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        passed = bool(api_key)
        return (
            {
                "name": "LLM provider (Anthropic)",
                "passed": passed,
                "details": "API key configured" if passed else "API key not set",
                "requirement": "required",
                "suggestion": None
                if passed
                else "Set ANTHROPIC_API_KEY environment variable",
            },
            passed,
        )

    if llm_provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        passed = bool(api_key)
        return (
            {
                "name": "LLM provider (OpenAI)",
                "passed": passed,
                "details": "API key configured" if passed else "API key not set",
                "requirement": "required",
                "suggestion": None
                if passed
                else "Set OPENAI_API_KEY environment variable",
            },
            passed,
        )

    # ollama
    return (
        {
            "name": "LLM provider (Ollama)",
            "passed": True,
            "details": f"configured at {config.llm.ollama.base_url}",
            "requirement": "required",
            "suggestion": "Ensure Ollama is running: ollama serve",
        },
        True,
    )


def _check_embedding_provider(config: Config) -> tuple[_CheckResult, bool]:
    """Check the configured embedding provider is accessible."""
    embed_provider = config.embedding.provider

    if embed_provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        passed = bool(api_key)
        return (
            {
                "name": "Embedding provider (OpenAI)",
                "passed": passed,
                "details": "API key configured" if passed else "API key not set",
                "requirement": "required",
                "suggestion": None
                if passed
                else "Set OPENAI_API_KEY or switch to local embeddings",
            },
            passed,
        )

    # local
    try:
        __import__("sentence_transformers")
        return (
            {
                "name": "Embedding provider (local)",
                "passed": True,
                "details": f"model: {config.embedding.local.model}",
                "requirement": "required",
                "suggestion": None,
            },
            True,
        )
    except ImportError:
        return (
            {
                "name": "Embedding provider (local)",
                "passed": False,
                "details": "sentence-transformers not installed",
                "requirement": "required",
                "suggestion": "Install with: pip install sentence-transformers",
            },
            False,
        )


def _check_config_file(config_path: Path | None) -> tuple[_CheckResult, bool]:
    """Check that the config file (if found) is valid YAML."""
    config_locations: list[Path] = []
    if config_path:
        config_locations.append(config_path)
    else:
        config_locations = [
            Path.cwd() / "config.yaml",
            Path.cwd() / ".local-deepwiki.yaml",
            Path.home() / ".config" / "local-deepwiki" / "config.yaml",
            Path.home() / ".local-deepwiki.yaml",
        ]

    found_config: Path | None = None
    for path in config_locations:
        if path.exists():
            found_config = path
            break

    if found_config is None:
        return (
            {
                "name": "Config file",
                "passed": True,
                "details": "not found (will use defaults)",
                "requirement": "optional",
                "suggestion": None,
            },
            True,
        )

    try:
        with open(found_config) as f:
            content = f.read()
            if content.strip():
                yaml.safe_load(content)
                details = f"valid at {found_config}"
            else:
                details = f"empty (using defaults) at {found_config}"
        return (
            {
                "name": "Config file",
                "passed": True,
                "details": details,
                "requirement": "optional",
                "suggestion": None,
            },
            True,
        )
    except yaml.YAMLError as e:
        return (
            {
                "name": "Config file",
                "passed": False,
                "details": f"invalid YAML: {e}",
                "requirement": "optional",
                "suggestion": "Fix YAML syntax errors in config file",
            },
            False,
        )
    except OSError as e:
        return (
            {
                "name": "Config file",
                "passed": False,
                "details": f"cannot read: {e}",
                "requirement": "optional",
                "suggestion": "Check file permissions",
            },
            False,
        )


def _check_wiki_output_dir(config: Config | None) -> tuple[_CheckResult, bool]:
    """Check that the wiki output directory is writable."""
    if config is None:
        return (
            {
                "name": "Wiki output directory",
                "passed": False,
                "details": "cannot verify (config not loaded)",
                "requirement": "required",
                "suggestion": "Fix configuration first",
            },
            False,
        )

    wiki_dir = Path(config.output.wiki_dir)
    try:
        wiki_dir.mkdir(parents=True, exist_ok=True)
        test_file = wiki_dir / ".deepwiki_health_check"
        test_file.write_text("health check")
        test_file.unlink()
        return (
            {
                "name": "Wiki output directory",
                "passed": True,
                "details": f"writable at {wiki_dir}",
                "requirement": "required",
                "suggestion": None,
            },
            True,
        )
    except OSError as e:
        return (
            {
                "name": "Wiki output directory",
                "passed": False,
                "details": f"not writable: {e}",
                "requirement": "required",
                "suggestion": f"Check permissions on {wiki_dir}",
            },
            False,
        )


def _display_health_results(checks: list[_CheckResult], console: Console) -> None:
    """Render the health-check table and summary."""
    table = Table(title="Health Check Results", show_header=True, header_style="bold")
    table.add_column("Status", style="bold", width=8)
    table.add_column("Check", width=25)
    table.add_column("Details", width=35)
    table.add_column("Requirement", width=10)
    table.add_column("Suggestion", width=40)

    for check in checks:
        status = "[green]✓ PASS[/green]" if check["passed"] else "[red]✗ FAIL[/red]"
        table.add_row(
            status,
            check["name"],
            check["details"],
            check["requirement"],
            check["suggestion"] or "",
        )

    console.print(table)

    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    console.print(f"\n[bold]Summary:[/bold] {passed}/{total} checks passed\n")


def cmd_health_check(args: argparse.Namespace) -> int:
    """Health check command to verify system readiness."""
    console = Console()
    console.print("\n[bold]Running system health checks...[/bold]\n")

    checks: list[_CheckResult] = []
    all_passed = True

    # Check 1: Python version
    py_result, py_ok = _check_python_version()
    checks.append(py_result)
    if not py_ok:
        all_passed = False

    # Check 2: Required packages
    pkg_results, pkgs_ok = _check_required_packages()
    checks.extend(pkg_results)
    if not pkgs_ok:
        all_passed = False

    # Check 3: LLM provider
    config_path = Path(args.config) if args.config else None
    config: Config | None = None
    try:
        config = Config.load(config_path)
        llm_result, llm_ok = _check_llm_provider(config)
        checks.append(llm_result)
        if not llm_ok:
            all_passed = False
    except Exception as e:  # noqa: BLE001 — CLI top-level handler: config errors shown as health-check results
        checks.append(
            {
                "name": "LLM provider",
                "passed": False,
                "details": f"config error: {e}",
                "requirement": "required",
                "suggestion": "Fix configuration file or create one",
            }
        )
        all_passed = False

    # Check 4: Embedding provider
    if config is not None:
        embed_result, embed_ok = _check_embedding_provider(config)
        checks.append(embed_result)
        if not embed_ok:
            all_passed = False

    # Check 5: Config file validity
    cfg_result, cfg_ok = _check_config_file(config_path)
    checks.append(cfg_result)
    if not cfg_ok:
        all_passed = False

    # Check 6: Wiki output directory
    wiki_result, wiki_ok = _check_wiki_output_dir(config)
    checks.append(wiki_result)
    if not wiki_ok:
        all_passed = False

    _display_health_results(checks, console)

    if all_passed:
        console.print(
            Panel(
                "[green bold]System is ready to use![/green bold]",
                title="Health Check Result",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                "[red bold]System is not ready. Please fix the issues above.[/red bold]",
                title="Health Check Result",
            )
        )
        return 1


def main() -> int:
    """Main entry point for the config CLI."""
    parser = argparse.ArgumentParser(
        prog="deepwiki-config",
        description="Validate and display local-deepwiki configuration",
        epilog=(
            "examples:\n"
            "  deepwiki config                    Validate current config\n"
            "  deepwiki config show               Show effective configuration tree\n"
            "  deepwiki config show --raw         Show config with raw JSON\n"
            "  deepwiki config validate -c my.yaml  Validate a specific config file\n"
            "  deepwiki config health-check       Check providers and system readiness\n"
            "  deepwiki config profile list       List saved config profiles\n"
            "  deepwiki config profile save dev   Save current config as 'dev' profile\n"
            "  deepwiki config profile use prod   Switch to 'prod' profile\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="Path to config file (default: search standard locations)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate configuration",
        description="Check config file for syntax errors, invalid values, and missing providers.",
    )
    validate_parser.set_defaults(func=cmd_validate)

    # show command
    show_parser = subparsers.add_parser(
        "show",
        help="Show effective configuration",
        description="Display the merged configuration tree (defaults + config file + env vars).",
    )
    show_parser.add_argument(
        "--raw",
        action="store_true",
        help="Also show raw JSON configuration",
    )
    show_parser.set_defaults(func=cmd_show)

    # health-check command
    health_parser = subparsers.add_parser(
        "health-check",
        help="Verify system is properly configured and ready to use",
        description="Test connectivity to LLM and embedding providers, check dependencies.",
    )
    health_parser.set_defaults(func=cmd_health_check)

    # profile subcommand
    from local_deepwiki.cli.profile_cli import (
        dispatch_profile,
        register_profile_subparser,
    )

    register_profile_subparser(subparsers)

    args = parser.parse_args()

    if args.command is None:
        # Default to validate if no command specified
        args.func = cmd_validate
    elif args.command == "profile":
        return dispatch_profile(args)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
