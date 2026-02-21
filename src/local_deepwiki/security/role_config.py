"""Role assignment configuration.

This module provides configuration-driven role assignment for subjects,
supporting pattern-based matching and explicit admin identifiers.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
import yaml

from local_deepwiki.security.access_control import Role, Subject


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    """Maps an identifier pattern to a role.

    Attributes:
        pattern: Glob pattern for subject identifier (e.g., "*@admin.com", "service-*").
        role: The role to assign when the pattern matches.
    """

    pattern: str
    role: Role


@dataclass
class RoleConfig:
    """Configuration for role assignments.

    Attributes:
        default_role: Default role for unmatched subjects.
        assignments: Explicit role assignments (checked in order, first match wins).
        admin_identifiers: Admin identifiers (convenience - always get ADMIN role).
    """

    default_role: Role = Role.VIEWER
    assignments: list[RoleAssignment] = field(default_factory=list)
    admin_identifiers: list[str] = field(default_factory=list)


class RoleManager:
    """Manages role assignments for subjects.

    This class provides centralized role assignment based on configuration,
    supporting pattern matching, explicit admin identifiers, and default roles.

    Example:
        config = RoleConfig(
            default_role=Role.VIEWER,
            admin_identifiers=["admin", "root"],
            assignments=[
                RoleAssignment(pattern="*@admin.example.com", role=Role.ADMIN),
                RoleAssignment(pattern="editor-*", role=Role.EDITOR),
            ]
        )
        manager = RoleManager(config)
        subject = manager.create_subject("user@admin.example.com")
        # subject.roles == {Role.ADMIN}
    """

    def __init__(self, config: RoleConfig | None = None):
        """Initialize the role manager.

        Args:
            config: Role configuration. If None, uses default configuration.
        """
        self._config = config or RoleConfig()

    def get_role_for_identifier(self, identifier: str) -> Role:
        """Get the role for a given identifier.

        The matching order is:
        1. Check admin identifiers (exact match)
        2. Check explicit assignments (first pattern match wins)
        3. Return default role

        Args:
            identifier: The subject identifier to match.

        Returns:
            The role assigned to the identifier.
        """
        # Check admin identifiers first (exact match)
        if identifier in self._config.admin_identifiers:
            return Role.ADMIN

        # Check explicit assignments (first match wins)
        for assignment in self._config.assignments:
            if fnmatch.fnmatch(identifier, assignment.pattern):
                return assignment.role

        # Return default role
        return self._config.default_role

    def create_subject(self, identifier: str) -> Subject:
        """Create a Subject with the appropriate role for the identifier.

        Args:
            identifier: The unique identifier for the subject.

        Returns:
            A Subject instance with the appropriate role assigned.
        """
        role = self.get_role_for_identifier(identifier)
        return Subject(identifier=identifier, roles={role})

    @classmethod
    def from_yaml(cls, path: Path) -> "RoleManager":
        """Load role configuration from YAML file.

        The YAML file should have the following structure:
            default_role: viewer
            admin_identifiers:
              - admin
              - root
            assignments:
              - pattern: "*@admin.example.com"
                role: admin
              - pattern: "editor-*"
                role: editor

        Args:
            path: Path to the YAML configuration file.

        Returns:
            A RoleManager instance configured from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file contains invalid YAML.
            ValueError: If the configuration contains invalid role names.
        """
        with open(path) as f:
            data = yaml.safe_load(f)

        if data is None:
            data = {}

        config = RoleConfig(
            default_role=Role(data.get("default_role", "viewer")),
            admin_identifiers=data.get("admin_identifiers", []),
            assignments=[
                RoleAssignment(
                    pattern=a["pattern"],
                    role=Role(a["role"]),
                )
                for a in data.get("assignments", [])
            ],
        )
        return cls(config)

    @property
    def config(self) -> RoleConfig:
        """Get the current role configuration.

        Returns:
            The RoleConfig instance used by this manager.
        """
        return self._config


# Global instance
_role_manager: RoleManager | None = None


def get_role_manager() -> RoleManager:
    """Get the global role manager instance.

    If no role manager has been configured, creates one with default settings.

    Returns:
        The global RoleManager instance.
    """
    global _role_manager
    if _role_manager is None:
        _role_manager = RoleManager()
    return _role_manager


def configure_roles(config: RoleConfig) -> None:
    """Configure the global role manager with the given configuration.

    Args:
        config: The role configuration to use.
    """
    global _role_manager
    _role_manager = RoleManager(config)


def reset_role_manager() -> None:
    """Reset the global role manager (for testing only).

    This clears the global instance, allowing a fresh manager
    to be created on the next call to get_role_manager().
    """
    global _role_manager
    _role_manager = None
