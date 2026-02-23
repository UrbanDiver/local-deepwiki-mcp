"""Export path validation and forbidden directory checks."""

from __future__ import annotations

from pathlib import Path

from local_deepwiki.errors import ValidationError

# Forbidden directories for export operations (security: prevent writing to sensitive locations)
# Note: /var and /private/var are excluded because temp directories live there
FORBIDDEN_EXPORT_DIRS = frozenset(
    {
        "/etc",
        "/usr",
        "/bin",
        "/sbin",
        "/System",
        "/Library",
        "/private/etc",
        str(Path.home() / ".ssh"),
    }
)

# Additional forbidden prefixes under /var that should be blocked
# (but not /var/folders or /var/tmp which are user temp directories)
FORBIDDEN_VAR_SUBDIRS = frozenset(
    {
        "/var/log",
        "/var/db",
        "/var/root",
        "/var/run",
        "/private/var/log",
        "/private/var/db",
        "/private/var/root",
        "/private/var/run",
    }
)


def _check_forbidden_dirs(
    resolved_str: str,
    dirs: frozenset[str],
    output_path: Path,
    label: str = "system directory",
) -> None:
    """Raise ValidationError if resolved_str is inside any forbidden directory.

    Args:
        resolved_str: Resolved absolute path as string.
        dirs: Set of forbidden directory paths.
        output_path: Original output path (for error context).
        label: Label for error messages (e.g., "system directory").
    """
    for forbidden in dirs:
        if resolved_str == forbidden or resolved_str.startswith(forbidden + "/"):
            raise ValidationError(
                message=f"Cannot export to {label}: {forbidden}",
                hint="Choose an output path in your project or home directory.",
                field="output_path",
                value=str(output_path),
            )


def _validate_export_path(output_path: Path, wiki_path: Path) -> Path:
    """Validate that export output path is not in a sensitive system directory.

    Args:
        output_path: The requested output path (must be resolved to absolute).
        wiki_path: The source wiki path (for context in error messages).

    Returns:
        The validated output path.

    Raises:
        ValidationError: If the output path is in a forbidden directory.
    """
    resolved = output_path.resolve()
    resolved_str = str(resolved)

    _check_forbidden_dirs(resolved_str, FORBIDDEN_EXPORT_DIRS, output_path)
    _check_forbidden_dirs(
        resolved_str, FORBIDDEN_VAR_SUBDIRS, output_path, label="system directory"
    )

    # Check for ~/.config (allow only ~/.config/local-deepwiki)
    config_dir = Path.home() / ".config"
    local_deepwiki_config = config_dir / "local-deepwiki"
    if resolved_str.startswith(str(config_dir) + "/"):
        if (
            not resolved_str.startswith(str(local_deepwiki_config) + "/")
            and resolved != local_deepwiki_config
        ):
            raise ValidationError(
                message=f"Cannot export to config directory: {config_dir}",
                hint="Choose an output path in your project or home directory.",
                field="output_path",
                value=str(output_path),
            )

    # Ensure parent directory exists or can be created
    parent = resolved.parent
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise ValidationError(
                message=f"Cannot create output directory: {parent}",
                hint="Ensure you have write permissions to the parent directory.",
                field="output_path",
                value=str(output_path),
            ) from e
        except OSError as e:
            raise ValidationError(
                message=f"Failed to create output directory: {e}",
                hint="Check that the path is valid and accessible.",
                field="output_path",
                value=str(output_path),
            ) from e

    return resolved
