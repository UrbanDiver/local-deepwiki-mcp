"""Configuration validation and display CLI for local-deepwiki."""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from local_deepwiki.config import Config


@dataclass
class ValidationIssue:
    """Represents a configuration validation issue."""

    level: str  # "error" or "warning"
    category: str
    message: str
    suggestion: str | None = None


class ConfigValidator:
    """Validates local-deepwiki configuration."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path
        self.issues: list[ValidationIssue] = []
        self.config: Config | None = None
        self.raw_config: dict[str, Any] | None = None

    def validate(self) -> bool:
        """Run all validations and return True if config is valid (no errors)."""
        self.issues = []

        # Step 1: Find and parse config file
        if not self._load_config():
            return False

        # Step 2: Validate with Pydantic
        if not self._validate_schema():
            return False

        # Step 3: Semantic validations
        self._validate_llm_provider()
        self._validate_embedding_provider()
        self._validate_wiki_settings()
        self._validate_paths()
        self._validate_performance_settings()

        # Return True if no errors (warnings are OK)
        return not any(issue.level == "error" for issue in self.issues)

    def _load_config(self) -> bool:
        """Load and parse the config file."""
        config_locations = []

        if self.config_path:
            config_locations.append(self.config_path)
        else:
            # Check default locations
            config_locations = [
                Path.cwd() / "config.yaml",
                Path.cwd() / ".local-deepwiki.yaml",
                Path.home() / ".config" / "local-deepwiki" / "config.yaml",
                Path.home() / ".local-deepwiki.yaml",
            ]

        found_path = None
        for path in config_locations:
            if path.exists():
                found_path = path
                break

        if found_path is None:
            if self.config_path:
                self.issues.append(
                    ValidationIssue(
                        level="error",
                        category="File",
                        message=f"Config file not found: {self.config_path}",
                        suggestion="Check the file path or create a config file",
                    )
                )
            else:
                # No config file is OK - will use defaults
                self.config = Config()
                self.raw_config = {}
                return True
            return False

        self.config_path = found_path

        try:
            with open(found_path) as f:
                content = f.read()
                if not content.strip():
                    # Empty file - use defaults
                    self.config = Config()
                    self.raw_config = {}
                    return True
                self.raw_config = yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            self.issues.append(
                ValidationIssue(
                    level="error",
                    category="YAML Syntax",
                    message=f"Invalid YAML syntax: {e}",
                    suggestion="Check YAML formatting (indentation, colons, etc.)",
                )
            )
            return False
        except OSError as e:
            self.issues.append(
                ValidationIssue(
                    level="error",
                    category="File",
                    message=f"Cannot read config file: {e}",
                )
            )
            return False

        return True

    def _validate_schema(self) -> bool:
        """Validate config against Pydantic schema."""
        try:
            self.config = Config.model_validate(self.raw_config)
            return True
        except ValidationError as e:
            for error in e.errors():
                location = " -> ".join(str(loc) for loc in error["loc"])
                self.issues.append(
                    ValidationIssue(
                        level="error",
                        category="Schema",
                        message=f"{location}: {error['msg']}",
                        suggestion=f"Expected type: {error.get('type', 'unknown')}",
                    )
                )
            return False

    def _validate_llm_provider(self) -> None:
        """Validate LLM provider configuration."""
        if self.config is None:
            return

        provider = self.config.llm.provider

        if provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                self.issues.append(
                    ValidationIssue(
                        level="error",
                        category="LLM Provider",
                        message="ANTHROPIC_API_KEY environment variable not set",
                        suggestion="Set ANTHROPIC_API_KEY or switch to 'ollama' provider",
                    )
                )
            elif not api_key.startswith("sk-ant-"):
                self.issues.append(
                    ValidationIssue(
                        level="warning",
                        category="LLM Provider",
                        message="ANTHROPIC_API_KEY does not match expected format (sk-ant-...)",
                        suggestion="Verify your API key is correct",
                    )
                )

        elif provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.issues.append(
                    ValidationIssue(
                        level="error",
                        category="LLM Provider",
                        message="OPENAI_API_KEY environment variable not set",
                        suggestion="Set OPENAI_API_KEY or switch to 'ollama' provider",
                    )
                )
            elif not api_key.startswith("sk-"):
                self.issues.append(
                    ValidationIssue(
                        level="warning",
                        category="LLM Provider",
                        message="OPENAI_API_KEY does not match expected format (sk-...)",
                        suggestion="Verify your API key is correct",
                    )
                )

        elif provider == "ollama":
            base_url = self.config.llm.ollama.base_url
            # Check if Ollama is likely accessible
            if "localhost" in base_url or "127.0.0.1" in base_url:
                self.issues.append(
                    ValidationIssue(
                        level="warning",
                        category="LLM Provider",
                        message=f"Ollama configured at {base_url}",
                        suggestion="Ensure Ollama is running: `ollama serve`",
                    )
                )

    def _validate_embedding_provider(self) -> None:
        """Validate embedding provider configuration."""
        if self.config is None:
            return

        provider = self.config.embedding.provider

        if provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.issues.append(
                    ValidationIssue(
                        level="error",
                        category="Embedding Provider",
                        message="OPENAI_API_KEY environment variable not set",
                        suggestion="Set OPENAI_API_KEY or switch to 'local' embedding provider",
                    )
                )

        elif provider == "local":
            model = self.config.embedding.local.model
            # Check for common model names
            if model not in [
                "all-MiniLM-L6-v2",
                "all-mpnet-base-v2",
                "paraphrase-multilingual-MiniLM-L12-v2",
            ]:
                self.issues.append(
                    ValidationIssue(
                        level="warning",
                        category="Embedding Provider",
                        message=f"Using custom embedding model: {model}",
                        suggestion="Ensure this model is available from sentence-transformers",
                    )
                )

    def _validate_wiki_settings(self) -> None:
        """Validate wiki generation settings."""
        if self.config is None:
            return

        wiki = self.config.wiki

        # Check cloud provider for GitHub
        if wiki.use_cloud_for_github:
            if wiki.github_llm_provider == "anthropic":
                if not os.environ.get("ANTHROPIC_API_KEY"):
                    self.issues.append(
                        ValidationIssue(
                            level="error",
                            category="Wiki Settings",
                            message="use_cloud_for_github enabled but ANTHROPIC_API_KEY not set",
                            suggestion="Set ANTHROPIC_API_KEY or disable use_cloud_for_github",
                        )
                    )
            elif wiki.github_llm_provider == "openai":
                if not os.environ.get("OPENAI_API_KEY"):
                    self.issues.append(
                        ValidationIssue(
                            level="error",
                            category="Wiki Settings",
                            message="use_cloud_for_github enabled but OPENAI_API_KEY not set",
                            suggestion="Set OPENAI_API_KEY or disable use_cloud_for_github",
                        )
                    )

        # Check chat provider
        chat_provider = wiki.chat_llm_provider
        if chat_provider not in ("default", self.config.llm.provider):
            if chat_provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
                self.issues.append(
                    ValidationIssue(
                        level="error",
                        category="Wiki Settings",
                        message=f"chat_llm_provider is '{chat_provider}' but API key not set",
                        suggestion="Set ANTHROPIC_API_KEY or use 'default' provider",
                    )
                )
            elif chat_provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
                self.issues.append(
                    ValidationIssue(
                        level="error",
                        category="Wiki Settings",
                        message=f"chat_llm_provider is '{chat_provider}' but API key not set",
                        suggestion="Set OPENAI_API_KEY or use 'default' provider",
                    )
                )

        # Performance warnings
        if wiki.max_concurrent_llm_calls > 10:
            self.issues.append(
                ValidationIssue(
                    level="warning",
                    category="Wiki Settings",
                    message=f"max_concurrent_llm_calls is {wiki.max_concurrent_llm_calls}",
                    suggestion="High values may cause rate limiting or memory issues",
                )
            )

    def _validate_paths(self) -> None:
        """Validate path-related settings."""
        if self.config is None:
            return

        # Check exclude patterns for common issues
        exclude_patterns = self.config.parsing.exclude_patterns
        if not any("node_modules" in p for p in exclude_patterns):
            self.issues.append(
                ValidationIssue(
                    level="warning",
                    category="Parsing",
                    message="node_modules not in exclude_patterns",
                    suggestion="Add 'node_modules/**' to avoid indexing dependencies",
                )
            )

        if not any(".git" in p for p in exclude_patterns):
            self.issues.append(
                ValidationIssue(
                    level="warning",
                    category="Parsing",
                    message=".git not in exclude_patterns",
                    suggestion="Add '.git/**' to avoid indexing git objects",
                )
            )

    def _validate_performance_settings(self) -> None:
        """Validate performance-related settings."""
        if self.config is None:
            return

        chunking = self.config.chunking

        # Check parallel workers
        cpu_count = os.cpu_count() or 4
        if chunking.parallel_workers > cpu_count * 2:
            self.issues.append(
                ValidationIssue(
                    level="warning",
                    category="Performance",
                    message=f"parallel_workers ({chunking.parallel_workers}) > 2x CPU count ({cpu_count})",
                    suggestion=f"Consider reducing to {cpu_count} for optimal performance",
                )
            )

        # Check chunk sizes
        if chunking.max_chunk_tokens > 1024:
            self.issues.append(
                ValidationIssue(
                    level="warning",
                    category="Performance",
                    message=f"max_chunk_tokens is {chunking.max_chunk_tokens}",
                    suggestion="Large chunks may reduce search quality. Consider 512-1024 tokens.",
                )
            )

        # Check cache settings
        if not self.config.embedding_cache.enabled:
            self.issues.append(
                ValidationIssue(
                    level="warning",
                    category="Performance",
                    message="Embedding cache is disabled",
                    suggestion="Enable caching for faster repeated operations",
                )
            )

        if not self.config.llm_cache.enabled:
            self.issues.append(
                ValidationIssue(
                    level="warning",
                    category="Performance",
                    message="LLM cache is disabled",
                    suggestion="Enable caching to reduce API costs and latency",
                )
            )


def display_config(config: Config, console: Console) -> None:
    """Display the effective configuration using rich formatting."""
    tree = Tree("[bold blue]Configuration[/bold blue]")

    # LLM Settings
    llm_branch = tree.add("[bold cyan]LLM[/bold cyan]")
    llm_branch.add(f"Provider: [green]{config.llm.provider}[/green]")
    if config.llm.provider == "ollama":
        llm_branch.add(f"Model: {config.llm.ollama.model}")
        llm_branch.add(f"Base URL: {config.llm.ollama.base_url}")
    elif config.llm.provider == "anthropic":
        llm_branch.add(f"Model: {config.llm.anthropic.model}")
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        llm_branch.add(
            f"API Key: {'[green]set[/green]' if key else '[red]not set[/red]'}"
        )
    elif config.llm.provider == "openai":
        llm_branch.add(f"Model: {config.llm.openai.model}")
        key = os.environ.get("OPENAI_API_KEY", "")
        llm_branch.add(
            f"API Key: {'[green]set[/green]' if key else '[red]not set[/red]'}"
        )

    # Embedding Settings
    embed_branch = tree.add("[bold cyan]Embedding[/bold cyan]")
    embed_branch.add(f"Provider: [green]{config.embedding.provider}[/green]")
    if config.embedding.provider == "local":
        embed_branch.add(f"Model: {config.embedding.local.model}")
    else:
        embed_branch.add(f"Model: {config.embedding.openai.model}")

    # Parsing Settings
    parse_branch = tree.add("[bold cyan]Parsing[/bold cyan]")
    parse_branch.add(f"Languages: {len(config.parsing.languages)} configured")
    parse_branch.add(
        f"Max file size: {config.parsing.max_file_size / 1024 / 1024:.1f} MB"
    )
    parse_branch.add(f"Exclude patterns: {len(config.parsing.exclude_patterns)}")

    # Chunking Settings
    chunk_branch = tree.add("[bold cyan]Chunking[/bold cyan]")
    chunk_branch.add(f"Max tokens: {config.chunking.max_chunk_tokens}")
    chunk_branch.add(f"Overlap: {config.chunking.overlap_tokens}")
    chunk_branch.add(f"Parallel workers: {config.chunking.parallel_workers}")
    chunk_branch.add(f"Batch size: {config.chunking.batch_size}")

    # Wiki Settings
    wiki_branch = tree.add("[bold cyan]Wiki Generation[/bold cyan]")
    wiki_branch.add(f"Max file docs: {config.wiki.max_file_docs or 'unlimited'}")
    wiki_branch.add(f"Concurrent LLM calls: {config.wiki.max_concurrent_llm_calls}")
    wiki_branch.add(f"Cloud for GitHub: {config.wiki.use_cloud_for_github}")
    wiki_branch.add(f"Chat provider: {config.wiki.chat_llm_provider}")

    # Deep Research Settings
    research_branch = tree.add("[bold cyan]Deep Research[/bold cyan]")
    research_branch.add(f"Max sub-questions: {config.deep_research.max_sub_questions}")
    research_branch.add(
        f"Chunks per question: {config.deep_research.chunks_per_subquestion}"
    )
    research_branch.add(f"Max total chunks: {config.deep_research.max_total_chunks}")

    # Cache Settings
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

    # Output Settings
    output_branch = tree.add("[bold cyan]Output[/bold cyan]")
    output_branch.add(f"Wiki directory: {config.output.wiki_dir}")
    output_branch.add(f"Vector DB: {config.output.vector_db_name}")

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
    except Exception as e:
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


def cmd_health_check(args: argparse.Namespace) -> int:
    """Health check command to verify system readiness."""
    console = Console()

    console.print("\n[bold]Running system health checks...[/bold]\n")

    checks = []
    all_passed = True

    # Check 1: Python version
    import sys

    py_version = sys.version_info
    py_check_passed = py_version >= (3, 10)
    checks.append(
        {
            "name": "Python version",
            "passed": py_check_passed,
            "details": f"{py_version.major}.{py_version.minor}.{py_version.micro}",
            "requirement": ">=3.10",
            "suggestion": "Upgrade to Python 3.10 or higher"
            if not py_check_passed
            else None,
        }
    )
    if not py_check_passed:
        all_passed = False

    # Check 2: Required packages
    required_packages = {
        "lancedb": "lancedb",
        "tree_sitter": "tree-sitter",
        "sentence_transformers": "sentence-transformers",
    }

    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
            checks.append(
                {
                    "name": f"Package: {package_name}",
                    "passed": True,
                    "details": "installed",
                    "requirement": "required",
                    "suggestion": None,
                }
            )
        except ImportError:
            checks.append(
                {
                    "name": f"Package: {package_name}",
                    "passed": False,
                    "details": "not found",
                    "requirement": "required",
                    "suggestion": f"Install with: pip install {package_name}",
                }
            )
            all_passed = False

    # Check 3: LLM provider configuration
    config_path = Path(args.config) if args.config else None
    try:
        config = Config.load(config_path)
        llm_provider = config.llm.provider

        if llm_provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                checks.append(
                    {
                        "name": "LLM provider (Anthropic)",
                        "passed": True,
                        "details": "API key configured",
                        "requirement": "required",
                        "suggestion": None,
                    }
                )
            else:
                checks.append(
                    {
                        "name": "LLM provider (Anthropic)",
                        "passed": False,
                        "details": "API key not set",
                        "requirement": "required",
                        "suggestion": "Set ANTHROPIC_API_KEY environment variable",
                    }
                )
                all_passed = False
        elif llm_provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                checks.append(
                    {
                        "name": "LLM provider (OpenAI)",
                        "passed": True,
                        "details": "API key configured",
                        "requirement": "required",
                        "suggestion": None,
                    }
                )
            else:
                checks.append(
                    {
                        "name": "LLM provider (OpenAI)",
                        "passed": False,
                        "details": "API key not set",
                        "requirement": "required",
                        "suggestion": "Set OPENAI_API_KEY environment variable",
                    }
                )
                all_passed = False
        else:  # ollama
            checks.append(
                {
                    "name": "LLM provider (Ollama)",
                    "passed": True,
                    "details": f"configured at {config.llm.ollama.base_url}",
                    "requirement": "required",
                    "suggestion": "Ensure Ollama is running: ollama serve",
                }
            )
    except Exception as e:
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
        config = None

    # Check 4: Embedding provider
    if config:
        embed_provider = config.embedding.provider

        if embed_provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                checks.append(
                    {
                        "name": "Embedding provider (OpenAI)",
                        "passed": True,
                        "details": "API key configured",
                        "requirement": "required",
                        "suggestion": None,
                    }
                )
            else:
                checks.append(
                    {
                        "name": "Embedding provider (OpenAI)",
                        "passed": False,
                        "details": "API key not set",
                        "requirement": "required",
                        "suggestion": "Set OPENAI_API_KEY or switch to local embeddings",
                    }
                )
                all_passed = False
        else:  # local
            try:
                __import__("sentence_transformers")
                checks.append(
                    {
                        "name": "Embedding provider (local)",
                        "passed": True,
                        "details": f"model: {config.embedding.local.model}",
                        "requirement": "required",
                        "suggestion": None,
                    }
                )
            except ImportError:
                checks.append(
                    {
                        "name": "Embedding provider (local)",
                        "passed": False,
                        "details": "sentence-transformers not installed",
                        "requirement": "required",
                        "suggestion": "Install with: pip install sentence-transformers",
                    }
                )
                all_passed = False

    # Check 5: Config file validity
    config_locations = []
    if config_path:
        config_locations.append(config_path)
    else:
        config_locations = [
            Path.cwd() / "config.yaml",
            Path.cwd() / ".local-deepwiki.yaml",
            Path.home() / ".config" / "local-deepwiki" / "config.yaml",
            Path.home() / ".local-deepwiki.yaml",
        ]

    found_config = None
    for path in config_locations:
        if path.exists():
            found_config = path
            break

    if found_config:
        try:
            with open(found_config) as f:
                content = f.read()
                if content.strip():
                    yaml.safe_load(content)
                    checks.append(
                        {
                            "name": "Config file",
                            "passed": True,
                            "details": f"valid at {found_config}",
                            "requirement": "optional",
                            "suggestion": None,
                        }
                    )
                else:
                    checks.append(
                        {
                            "name": "Config file",
                            "passed": True,
                            "details": f"empty (using defaults) at {found_config}",
                            "requirement": "optional",
                            "suggestion": None,
                        }
                    )
        except yaml.YAMLError as e:
            checks.append(
                {
                    "name": "Config file",
                    "passed": False,
                    "details": f"invalid YAML: {e}",
                    "requirement": "optional",
                    "suggestion": "Fix YAML syntax errors in config file",
                }
            )
            all_passed = False
        except OSError as e:
            checks.append(
                {
                    "name": "Config file",
                    "passed": False,
                    "details": f"cannot read: {e}",
                    "requirement": "optional",
                    "suggestion": "Check file permissions",
                }
            )
            all_passed = False
    else:
        checks.append(
            {
                "name": "Config file",
                "passed": True,
                "details": "not found (will use defaults)",
                "requirement": "optional",
                "suggestion": None,
            }
        )

    # Check 6: Write permissions on default wiki output directory
    if config:
        wiki_dir = Path(config.output.wiki_dir)
        try:
            # Try to create the directory if it doesn't exist
            wiki_dir.mkdir(parents=True, exist_ok=True)
            # Try to write a test file
            test_file = wiki_dir / ".deepwiki_health_check"
            test_file.write_text("health check")
            test_file.unlink()
            checks.append(
                {
                    "name": "Wiki output directory",
                    "passed": True,
                    "details": f"writable at {wiki_dir}",
                    "requirement": "required",
                    "suggestion": None,
                }
            )
        except OSError as e:
            checks.append(
                {
                    "name": "Wiki output directory",
                    "passed": False,
                    "details": f"not writable: {e}",
                    "requirement": "required",
                    "suggestion": f"Check permissions on {wiki_dir}",
                }
            )
            all_passed = False
    else:
        # If config failed to load, skip this check
        checks.append(
            {
                "name": "Wiki output directory",
                "passed": False,
                "details": "cannot verify (config not loaded)",
                "requirement": "required",
                "suggestion": "Fix configuration first",
            }
        )
        all_passed = False

    # Display results
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

    # Summary
    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    console.print(f"\n[bold]Summary:[/bold] {passed}/{total} checks passed\n")

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
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="Path to config file (default: search standard locations)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.set_defaults(func=cmd_validate)

    # show command
    show_parser = subparsers.add_parser("show", help="Show effective configuration")
    show_parser.add_argument(
        "--raw",
        action="store_true",
        help="Also show raw JSON configuration",
    )
    show_parser.set_defaults(func=cmd_show)

    # health-check command
    health_parser = subparsers.add_parser(
        "health-check", help="Verify system is properly configured and ready to use"
    )
    health_parser.set_defaults(func=cmd_health_check)

    args = parser.parse_args()

    if args.command is None:
        # Default to validate if no command specified
        args.func = cmd_validate

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
