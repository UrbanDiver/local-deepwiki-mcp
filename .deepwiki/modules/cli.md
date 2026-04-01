# CLI Module Documentation

## Module Purpose

The CLI module provides command-line interface functionality for the Local DeepWiki MCP Server. It handles user interactions through various commands for configuration management, repository indexing, wiki generation, and system status monitoring.

## Key Classes and Functions

### `ValidationIssue`
Represents a configuration validation issue with properties:
- `level`: Either "error" or "warning"
- `category`: Issue category (e.g., "File", "Schema")
- `message`: Descriptive error/warning message
- `suggestion`: Optional remediation suggestion

### `ConfigValidator`
Validates configuration files against pydantic schema and performs semantic checks:
- `__init__(config_path: Path | None = None)`: Initialize validator with optional config path
- `validate() -> bool`: Run all validations and return True if no errors
- `_load_config() -> bool`: Load and parse the config file
- `_validate_schema() -> bool`: Validate against pydantic schema
- `_validate_llm_provider() -> None`: Check LLM provider configuration
- `_validate_embedding_provider() -> None`: Check embedding provider configuration
- `_validate_wiki_settings() -> None`: Validate wiki generation settings
- `_validate_paths() -> None`: Validate path-related settings
- `_validate_performance_settings() -> None`: Validate performance-related settings

### `display_config`
Displays the current configuration in a formatted table.

### `cmd_validate`
Validates the configuration file and displays any issues found.

### `cmd_show`
Shows the current configuration.

### `cmd_health_check`
Performs health checks on the configuration.

### `main`
Main entry point for CLI commands.

## How Components Interact

The CLI module orchestrates user interactions with the Local DeepWiki system through several command subcommands:
1. Configuration management (`config show`, `config validate`, `config health-check`)
2. Repository indexing and wiki generation (`update`)
3. System status monitoring (`status`)
4. Profile management (`profile`)

The [`ConfigValidator`](../files/src/local_deepwiki/cli/config_validator.md) class is used across multiple commands to validate configuration files, ensuring proper setup before system operations. The validation process includes schema checking with pydantic and semantic validations for LLM providers, embedding providers, and performance settings.

## Usage Examples
```bash
# Show current configuration
deepwiki config show

# Validate configuration file
deepwiki config validate

# Run system health check
deepwiki config health-check

# Update repository index and regenerate wiki
deepwiki update

# Show index status
deepwiki status

# List available profiles
deepwiki profile list
```
## Dependencies

- `argparse`: Command-line argument parsing
- `asyncio`: Asynchronous operations for indexing
- `dataclasses`: Data structure definitions
- `pathlib`: Path manipulation utilities
- `yaml`: YAML parsing for configuration files
- `pydantic`: Schema validation
- `rich`: Terminal formatting and display
- `local_deepwiki.config`: Configuration model definitions
- `local_deepwiki.cli.status_cli`: Status reporting functions
- `local_deepwiki.cli.profile_cli`: Profile management commands
- `local_deepwiki.cli.update_cli`: Update command implementation
- `local_deepwiki.core.index_manager`: Index status management
- `local_deepwiki.core.indexer`: Repository indexing functionality
- `local_deepwiki.generators.wiki`: Wiki generation functions

## Relevant Source Files

The following source files were used to generate this documentation:

- [`src/local_deepwiki/cli/config_validator.py:17-23`](../files/src/local_deepwiki/cli/config_validator.md)
- [`src/local_deepwiki/cli/update_cli.py:21-93`](../files/src/local_deepwiki/cli/update_cli.md)
- [`src/local_deepwiki/cli/config_cli.py:21-105`](../files/src/local_deepwiki/cli/config_cli.md)
- `src/local_deepwiki/cli/__init__.py`
- [`src/local_deepwiki/cli/status_cli.py:22-33`](../files/src/local_deepwiki/cli/status_cli.md)
- [`src/local_deepwiki/cli/init_cli.py:113-118`](../files/src/local_deepwiki/cli/init_cli.md)
- [`src/local_deepwiki/cli/cache_cli.py:26-35`](../files/src/local_deepwiki/cli/cache_cli.md)
- [`src/local_deepwiki/cli/interactive_search.py:45-524`](../files/src/local_deepwiki/cli/interactive_search.md)
- [`src/local_deepwiki/cli/profile_cli.py:26-40`](../files/src/local_deepwiki/cli/profile_cli.md)
- [`src/local_deepwiki/cli/main.py:52-85`](../files/src/local_deepwiki/cli/main.md)


*Showing 10 of 11 source files.*
