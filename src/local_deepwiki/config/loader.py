"""Configuration loading, merging, and validation."""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator

import yaml
from pydantic import BaseModel

from local_deepwiki.models.provider_types import EmbeddingProviderType, LLMProviderType

from .models import Config

# Context-local config storage
_config_var: ContextVar[Config | None] = ContextVar("config", default=None)


def get_config() -> Config:
    """Get the configuration instance.

    Returns the context-local config, lazily loading from disk on first access.

    Returns:
        The active configuration instance.
    """
    cfg = _config_var.get()
    if cfg is None:
        cfg = Config.load()
        _config_var.set(cfg)
    return cfg


def set_config(config: Config) -> None:
    """Set the configuration instance.

    Args:
        config: The configuration to set.
    """
    _config_var.set(config)


def reset_config() -> None:
    """Reset the configuration to uninitialized state.

    Useful for testing to ensure a fresh config is loaded.
    """
    _config_var.set(None)


@contextmanager
def config_context(config: Config) -> Generator[Config, None, None]:
    """Context manager for temporary config override.

    Sets a temporary configuration that is restored when the context exits.
    Useful for testing or per-request config.

    Args:
        config: The configuration to use within the context.

    Yields:
        The provided configuration.

    Example:
        with config_context(custom_config):
            # get_config() returns custom_config here
            do_something()
        # get_config() returns previous config again
    """
    token = _config_var.set(config)
    try:
        yield config
    finally:
        _config_var.reset(token)


# ---------------------------------------------------------------------------
# ConfigChange and ConfigDiff classes for tracking configuration changes
# ---------------------------------------------------------------------------


@dataclass
class ConfigChange:
    """Represents a single configuration change.

    Attributes:
        field: The dot-separated path to the changed field (e.g., "llm.provider").
        old_value: The previous value of the field.
        new_value: The new value of the field.
        source: The source of the change ("cli", "env", "file", "default").
    """

    field: str
    old_value: Any
    new_value: Any
    source: str  # "cli", "env", "file", "default"

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        return f"{self.field}: {self.old_value!r} -> {self.new_value!r} (from {self.source})"


@dataclass
class ConfigDiff:
    """Tracks differences between two configurations.

    Useful for understanding what changed between config versions,
    debugging configuration issues, and auditing config changes.

    Example:
        base = Config()
        modified = Config(llm={"provider": "anthropic"})
        diff = ConfigDiff(base, modified)
        for change in diff.get_changes():
            print(f"Changed: {change}")
    """

    base: "Config"
    override: "Config"
    changes: list[ConfigChange] = field(default_factory=list)
    _computed: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        """Compute changes after initialization."""
        if not self._computed:
            self._compute_changes()
            object.__setattr__(self, "_computed", True)

    def _compute_changes(self, source: str = "override") -> None:
        """Compute the differences between base and override configs.

        Args:
            source: The source label for changes (default: "override").
        """
        self._compare_models(self.base, self.override, "", source)

    def _compare_models(
        self,
        base: BaseModel,
        override: BaseModel,
        prefix: str,
        source: str,
    ) -> None:
        """Recursively compare two Pydantic models.

        Args:
            base: The base model to compare from.
            override: The override model to compare to.
            prefix: The current field path prefix.
            source: The source label for changes.
        """
        # Get field names from the class (excluding computed fields)
        for field_name in type(base).model_fields:
            base_value = getattr(base, field_name)
            override_value = getattr(override, field_name)

            field_path = f"{prefix}.{field_name}" if prefix else field_name

            if isinstance(base_value, BaseModel) and isinstance(
                override_value, BaseModel
            ):
                # Recursively compare nested models
                self._compare_models(base_value, override_value, field_path, source)
            elif base_value != override_value:
                self.changes.append(
                    ConfigChange(
                        field=field_path,
                        old_value=base_value,
                        new_value=override_value,
                        source=source,
                    )
                )

    def get_changes(self) -> list[ConfigChange]:
        """Return list of changed fields.

        Returns:
            List of ConfigChange objects representing all differences.
        """
        return self.changes.copy()

    def get_changes_by_source(self, source: str) -> list[ConfigChange]:
        """Return changes from a specific source.

        Args:
            source: The source to filter by ("cli", "env", "file", "default").

        Returns:
            List of ConfigChange objects from the specified source.
        """
        return [c for c in self.changes if c.source == source]

    def has_changes(self) -> bool:
        """Check if there are any changes.

        Returns:
            True if there are any differences between base and override.
        """
        return len(self.changes) > 0

    def summary(self) -> str:
        """Return a human-readable summary of changes.

        Returns:
            A multi-line string summarizing all changes.
        """
        if not self.changes:
            return "No configuration changes"

        lines = [f"Configuration changes ({len(self.changes)} total):"]
        for change in self.changes:
            lines.append(f"  - {change}")
        return "\n".join(lines)

    def apply(self, config: "Config") -> "Config":
        """Apply changes to a config.

        Creates a new config with the changes applied. This is useful
        for applying a diff to a different base config.

        Args:
            config: The config to apply changes to.

        Returns:
            A new Config instance with changes applied.
        """
        if not self.changes:
            return config.model_copy()

        # Build update dict from changes
        updates: dict[str, Any] = {}
        for change in self.changes:
            parts = change.field.split(".")
            _set_nested_value(updates, parts, change.new_value)

        return _apply_nested_updates(config, updates)


def _set_nested_value(d: dict[str, Any], path: list[str], value: Any) -> None:
    """Set a nested value in a dictionary using a path.

    Args:
        d: The dictionary to update.
        path: List of keys representing the path.
        value: The value to set.
    """
    for key in path[:-1]:
        if key not in d:
            d[key] = {}
        d = d[key]
    d[path[-1]] = value


def _apply_nested_updates(config: "Config", updates: dict[str, Any]) -> "Config":
    """Apply nested updates to a config.

    Args:
        config: The config to update.
        updates: Dictionary of updates to apply.

    Returns:
        A new Config with updates applied.
    """
    model_updates: dict[str, Any] = {}

    for key, value in updates.items():
        if isinstance(value, dict):
            # Nested update
            current = getattr(config, key, None)
            if current is not None and isinstance(current, BaseModel):
                # Recursively apply to nested model
                nested_updates = {}
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, dict):
                        nested_current = getattr(current, nested_key, None)
                        if nested_current is not None and isinstance(
                            nested_current, BaseModel
                        ):
                            nested_updates[nested_key] = nested_current.model_copy(
                                update=nested_value
                            )
                        else:
                            nested_updates[nested_key] = nested_value
                    else:
                        nested_updates[nested_key] = nested_value
                model_updates[key] = current.model_copy(update=nested_updates)
            else:
                model_updates[key] = value
        else:
            model_updates[key] = value

    return config.model_copy(update=model_updates)


# ---------------------------------------------------------------------------
# Config merge with hierarchy
# ---------------------------------------------------------------------------


def merge_configs(
    cli_config: dict[str, Any] | None = None,
    env_config: dict[str, Any] | None = None,
    file_config: dict[str, Any] | None = None,
    defaults: Config | None = None,
) -> tuple[Config, ConfigDiff]:
    """Merge configs with CLI > env > file > defaults priority.

    Creates a merged configuration by layering config sources in priority
    order, where CLI arguments have the highest priority and defaults
    have the lowest.

    Args:
        cli_config: Configuration from command-line arguments.
        env_config: Configuration from environment variables.
        file_config: Configuration from config file.
        defaults: Default configuration (if None, uses Config()).

    Returns:
        A tuple of (merged_config, diff) where diff shows all changes
        from defaults.

    Example:
        cli = {"llm": {"provider": "anthropic"}}
        env = {"embedding": {"provider": "openai"}}
        file = {"chunking": {"max_chunk_tokens": 1024}}

        config, diff = merge_configs(cli, env, file)
        print(diff.summary())
    """
    if defaults is None:
        defaults = Config()

    # Start with defaults
    merged_data: dict[str, Any] = defaults.model_dump()

    # Track sources for diff
    change_sources: dict[str, str] = {}

    # Apply file config (lowest priority of overrides)
    if file_config:
        _deep_merge(merged_data, file_config)
        _track_sources(file_config, "", change_sources, "file")

    # Apply env config (medium priority)
    if env_config:
        _deep_merge(merged_data, env_config)
        _track_sources(env_config, "", change_sources, "env")

    # Apply CLI config (highest priority)
    if cli_config:
        _deep_merge(merged_data, cli_config)
        _track_sources(cli_config, "", change_sources, "cli")

    # Create the merged config
    merged = Config.model_validate(merged_data)

    # Compute diff with source tracking
    diff = ConfigDiff(defaults, merged)

    # Update change sources in the diff
    for change in diff.changes:
        if change.field in change_sources:
            change.source = change_sources[change.field]

    return merged, diff


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    """Deep merge override into base dictionary.

    Args:
        base: The base dictionary to merge into (modified in-place).
        override: The dictionary to merge from.
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _track_sources(
    config: dict[str, Any],
    prefix: str,
    sources: dict[str, str],
    source: str,
) -> None:
    """Track the source of each config field.

    Args:
        config: The config dictionary.
        prefix: Current field path prefix.
        sources: Dictionary mapping field paths to sources.
        source: The source label for this config.
    """
    for key, value in config.items():
        field_path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _track_sources(value, field_path, sources, source)
        else:
            sources[field_path] = source


# ---------------------------------------------------------------------------
# Config validation summary
# ---------------------------------------------------------------------------


def validate_config(config: Config) -> list[str]:
    """Return list of validation warnings/errors.

    Performs comprehensive validation of a configuration and returns
    a list of any warnings or potential issues found.

    Args:
        config: The configuration to validate.

    Returns:
        List of warning/error messages. Empty list means config is valid.

    Example:
        config = Config()
        warnings = validate_config(config)
        if warnings:
            for warning in warnings:
                print(f"Warning: {warning}")
    """
    warnings: list[str] = []

    # Check embedding configuration
    if config.embedding.provider == EmbeddingProviderType.OPENAI:
        if not os.environ.get("OPENAI_API_KEY"):
            warnings.append(
                "OpenAI embedding provider selected but OPENAI_API_KEY not set"
            )

    # Check LLM configuration
    if config.llm.provider == LLMProviderType.ANTHROPIC:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            warnings.append(
                "Anthropic LLM provider selected but ANTHROPIC_API_KEY not set"
            )
    elif config.llm.provider == LLMProviderType.OPENAI:
        if not os.environ.get("OPENAI_API_KEY"):
            warnings.append("OpenAI LLM provider selected but OPENAI_API_KEY not set")

    # Check for potential performance issues
    if config.chunking.parallel_workers > (os.cpu_count() or 4):
        warnings.append(
            f"parallel_workers ({config.chunking.parallel_workers}) exceeds "
            f"CPU count ({os.cpu_count() or 4}), may cause contention"
        )

    if config.embedding_batch.batch_size > 100 and config.embedding.provider != "local":
        warnings.append(
            f"Large embedding batch_size ({config.embedding_batch.batch_size}) "
            "with API provider may cause rate limiting"
        )

    # Check for memory concerns
    if config.deep_research.max_total_chunks > 50:
        warnings.append(
            f"Large max_total_chunks ({config.deep_research.max_total_chunks}) "
            "may cause high memory usage during research"
        )

    # Check cache configurations
    if config.embedding_cache.enabled and config.embedding_cache.max_entries > 500000:
        warnings.append(
            f"Very large embedding cache max_entries "
            f"({config.embedding_cache.max_entries}) may cause high memory usage"
        )

    # Check wiki configuration consistency
    if config.wiki.use_cloud_for_github:
        provider = config.wiki.github_llm_provider
        if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
            warnings.append(
                "use_cloud_for_github enabled with anthropic but "
                "ANTHROPIC_API_KEY not set"
            )
        elif provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            warnings.append(
                "use_cloud_for_github enabled with openai but OPENAI_API_KEY not set"
            )

    # Check plugin configuration
    if config.plugins.enabled and config.plugins.custom_dir:
        custom_path = Path(config.plugins.custom_dir)
        if not custom_path.exists():
            warnings.append(f"Custom plugins directory does not exist: {custom_path}")

    # Check hooks configuration
    if config.hooks.enabled and config.hooks.scripts_dir:
        scripts_path = Path(config.hooks.scripts_dir)
        if not scripts_path.exists():
            warnings.append(f"Hook scripts directory does not exist: {scripts_path}")

    return warnings


def load_config_from_env() -> dict[str, Any]:
    """Load configuration overrides from environment variables.

    Environment variables follow the pattern:
        DEEPWIKI_<SECTION>_<FIELD>=value

    For example:
        DEEPWIKI_LLM_PROVIDER=anthropic
        DEEPWIKI_EMBEDDING_PROVIDER=openai
        DEEPWIKI_CHUNKING_MAX_CHUNK_TOKENS=1024

    Returns:
        Dictionary of configuration overrides from environment.
    """
    env_config: dict[str, Any] = {}
    prefix = "DEEPWIKI_"

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Parse the key: DEEPWIKI_SECTION_FIELD -> section.field
        parts = key[len(prefix) :].lower().split("_", 1)
        if len(parts) != 2:
            continue

        section, field = parts

        # Convert value to appropriate type
        parsed_value: Any
        if value.lower() in ("true", "false"):
            parsed_value = value.lower() == "true"
        elif value.isdigit():
            parsed_value = int(value)
        elif _is_float(value):
            parsed_value = float(value)
        else:
            parsed_value = value

        # Build nested dict
        if section not in env_config:
            env_config[section] = {}
        env_config[section][field] = parsed_value

    return env_config


def _is_float(s: str) -> bool:
    """Check if string can be converted to float.

    Args:
        s: The string to check.

    Returns:
        True if the string represents a float.
    """
    try:
        float(s)
        return "." in s  # Only consider it float if it has a decimal point
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Config profile management
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".config" / "local-deepwiki"
PROFILES_DIR = CONFIG_DIR / "profiles"
ACTIVE_PROFILE_FILE = CONFIG_DIR / "active_profile"


def list_profiles() -> list[str]:
    """List all saved configuration profile names.

    Returns:
        Sorted list of profile names (without .yaml extension).
    """
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def get_active_profile_name() -> str | None:
    """Get the name of the currently active profile.

    Returns:
        The active profile name, or None if no profile is active.
    """
    if not ACTIVE_PROFILE_FILE.exists():
        return None
    name = ACTIVE_PROFILE_FILE.read_text().strip()
    if not name:
        return None
    # Verify the profile still exists
    profile_path = PROFILES_DIR / f"{name}.yaml"
    if not profile_path.exists():
        return None
    return name


def save_profile(name: str, config_path: Path | None = None) -> Path:
    """Save current configuration as a named profile.

    Args:
        name: Profile name (alphanumeric, hyphens, underscores).
        config_path: Path to config file to snapshot. If None, uses default location.

    Returns:
        Path to the saved profile file.

    Raises:
        ValueError: If name contains invalid characters.
        FileNotFoundError: If no config file is found to snapshot.
    """
    import re
    import shutil

    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError(
            f"Invalid profile name '{name}': use only letters, numbers, hyphens, underscores"
        )

    # Find config file to snapshot
    if config_path is None:
        search_paths = [
            Path.cwd() / "config.yaml",
            Path.cwd() / ".local-deepwiki.yaml",
            CONFIG_DIR / "config.yaml",
            Path.home() / ".local-deepwiki.yaml",
        ]
        config_path = next((p for p in search_paths if p.exists()), None)

    if config_path is None or not config_path.exists():
        # No config file found - save defaults
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        profile_path = PROFILES_DIR / f"{name}.yaml"
        default_config = Config()
        profile_path.write_text(
            yaml.dump(default_config.model_dump(), default_flow_style=False)
        )
        return profile_path

    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = PROFILES_DIR / f"{name}.yaml"
    shutil.copy2(config_path, profile_path)
    return profile_path


def activate_profile(name: str) -> None:
    """Activate a saved configuration profile.

    Copies the profile's YAML to the main config location and records
    the active profile name.

    Args:
        name: Profile name to activate.

    Raises:
        FileNotFoundError: If the profile does not exist.
    """
    import shutil

    profile_path = PROFILES_DIR / f"{name}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile '{name}' not found")

    config_dest = CONFIG_DIR / "config.yaml"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(profile_path, config_dest)
    ACTIVE_PROFILE_FILE.write_text(name)

    # Reset cached config so next get_config() loads the new profile
    reset_config()


def delete_profile(name: str) -> bool:
    """Delete a saved configuration profile.

    Args:
        name: Profile name to delete.

    Returns:
        True if the profile was deleted, False if it didn't exist.
    """
    profile_path = PROFILES_DIR / f"{name}.yaml"
    if not profile_path.exists():
        return False

    # Check if this is the active profile BEFORE deleting
    active_name = get_active_profile_name()

    profile_path.unlink()

    # Clear active profile marker if this was the active one
    if active_name == name:
        if ACTIVE_PROFILE_FILE.exists():
            ACTIVE_PROFILE_FILE.unlink()

    return True
