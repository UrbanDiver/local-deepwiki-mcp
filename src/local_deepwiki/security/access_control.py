"""Access control and authorization for local-deepwiki operations.

This module provides role-based access control (RBAC) and permission checking
for sensitive operations within the system.
"""

from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Callable, Optional, TypeVar

# Type variable for decorators
F = TypeVar("F", bound=Callable)


class Permission(str, Enum):
    """Available permissions in the system."""

    # Index management
    INDEX_READ = "index:read"
    INDEX_WRITE = "index:write"
    INDEX_DELETE = "index:delete"

    # Configuration
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"

    # Query operations
    QUERY_SEARCH = "query:search"
    QUERY_DEEP_RESEARCH = "query:deep_research"

    # Export operations
    EXPORT_HTML = "export:html"
    EXPORT_PDF = "export:pdf"

    # System operations
    SYSTEM_ADMIN = "system:admin"


class Role(str, Enum):
    """Predefined roles in the system."""

    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    GUEST = "guest"


# Role to permission mapping
ROLE_PERMISSIONS = {
    Role.ADMIN: {
        Permission.INDEX_READ,
        Permission.INDEX_WRITE,
        Permission.INDEX_DELETE,
        Permission.CONFIG_READ,
        Permission.CONFIG_WRITE,
        Permission.QUERY_SEARCH,
        Permission.QUERY_DEEP_RESEARCH,
        Permission.EXPORT_HTML,
        Permission.EXPORT_PDF,
        Permission.SYSTEM_ADMIN,
    },
    Role.EDITOR: {
        Permission.INDEX_READ,
        Permission.INDEX_WRITE,
        Permission.CONFIG_READ,
        Permission.QUERY_SEARCH,
        Permission.QUERY_DEEP_RESEARCH,
        Permission.EXPORT_HTML,
        Permission.EXPORT_PDF,
    },
    Role.VIEWER: {
        Permission.INDEX_READ,
        Permission.QUERY_SEARCH,
        Permission.QUERY_DEEP_RESEARCH,
        Permission.EXPORT_HTML,
    },
    Role.GUEST: {
        Permission.QUERY_SEARCH,
    },
}


class AccessDeniedException(Exception):
    """Raised when access is denied due to insufficient permissions."""

    pass


class AuthenticationException(Exception):
    """Raised when authentication fails."""

    pass


@dataclass
class Subject:
    """Represents a user or service making a request.

    Attributes:
        identifier: Unique identifier for the subject (user ID, service name, etc.)
        roles: Set of roles assigned to the subject.
    """

    identifier: str
    roles: set[Role]

    def has_permission(self, permission: Permission) -> bool:
        """Check if this subject has the required permission.

        Args:
            permission: The permission to check.

        Returns:
            True if the subject has the permission through any of its roles.
        """
        for role in self.roles:
            if permission in ROLE_PERMISSIONS.get(role, set()):
                return True
        return False

    def get_all_permissions(self) -> set[Permission]:
        """Get all permissions for this subject.

        Returns:
            Set of all permissions granted through assigned roles.
        """
        permissions: set[Permission] = set()
        for role in self.roles:
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
        return permissions


class AccessController:
    """Manages access control and authorization.

    This class provides centralized access control for the system,
    allowing permission checks and enforcement of access policies.
    """

    def __init__(self):
        """Initialize the access controller."""
        self._current_subject: Optional[Subject] = None

    def set_subject(self, subject: Subject) -> None:
        """Set the current subject for access checks.

        Args:
            subject: The subject making the request.
        """
        if not subject or not subject.identifier:
            raise AuthenticationException("Invalid subject: identifier is required")
        if not subject.roles:
            raise AuthenticationException("Invalid subject: at least one role is required")
        self._current_subject = subject

    def clear_subject(self) -> None:
        """Clear the current subject."""
        self._current_subject = None

    def get_current_subject(self) -> Optional[Subject]:
        """Get the currently authenticated subject.

        Returns:
            The current subject, or None if no subject is set.
        """
        return self._current_subject

    def require_permission(self, permission: Permission) -> None:
        """Check that the current subject has the required permission.

        Args:
            permission: The required permission.

        Raises:
            AuthenticationException: If no subject is authenticated.
            AccessDeniedException: If the subject lacks the required permission.
        """
        if not self._current_subject:
            raise AuthenticationException("No subject authenticated")

        if not self._current_subject.has_permission(permission):
            raise AccessDeniedException(
                f"Subject '{self._current_subject.identifier}' lacks permission: {permission}"
            )

    def require_any_permission(self, *permissions: Permission) -> None:
        """Check that the current subject has any of the required permissions.

        Args:
            *permissions: One or more permissions, any of which will satisfy the check.

        Raises:
            AuthenticationException: If no subject is authenticated.
            AccessDeniedException: If the subject lacks all specified permissions.
        """
        if not self._current_subject:
            raise AuthenticationException("No subject authenticated")

        for permission in permissions:
            if self._current_subject.has_permission(permission):
                return

        permission_list = ", ".join(str(p) for p in permissions)
        raise AccessDeniedException(
            f"Subject '{self._current_subject.identifier}' lacks any of: {permission_list}"
        )

    def require_all_permissions(self, *permissions: Permission) -> None:
        """Check that the current subject has all required permissions.

        Args:
            *permissions: Permissions that are all required.

        Raises:
            AuthenticationException: If no subject is authenticated.
            AccessDeniedException: If the subject lacks any required permission.
        """
        if not self._current_subject:
            raise AuthenticationException("No subject authenticated")

        for permission in permissions:
            if not self._current_subject.has_permission(permission):
                raise AccessDeniedException(
                    f"Subject '{self._current_subject.identifier}' lacks permission: {permission}"
                )

    def has_permission(self, permission: Permission) -> bool:
        """Check if the current subject has the required permission.

        Args:
            permission: The permission to check.

        Returns:
            True if the current subject has the permission, False otherwise.
            Returns False if no subject is authenticated.
        """
        if not self._current_subject:
            return False
        return self._current_subject.has_permission(permission)


# Global access controller instance
_access_controller: Optional[AccessController] = None


def get_access_controller() -> AccessController:
    """Get the global access controller instance.

    Returns:
        The global AccessController instance.
    """
    global _access_controller
    if _access_controller is None:
        _access_controller = AccessController()
    return _access_controller


def require_permission(permission: Permission) -> Callable[[F], F]:
    """Decorator to require a specific permission for a function.

    Args:
        permission: The required permission.

    Returns:
        A decorator function that checks permissions before execution.

    Raises:
        AccessDeniedException: If the current subject lacks the permission.
        AuthenticationException: If no subject is authenticated.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            controller = get_access_controller()
            controller.require_permission(permission)
            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def require_any_permission(*permissions: Permission) -> Callable[[F], F]:
    """Decorator to require any of the specified permissions.

    Args:
        *permissions: One or more permissions, any of which will satisfy the check.

    Returns:
        A decorator function that checks permissions before execution.

    Raises:
        AccessDeniedException: If the current subject lacks all permissions.
        AuthenticationException: If no subject is authenticated.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            controller = get_access_controller()
            controller.require_any_permission(*permissions)
            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def require_all_permissions(*permissions: Permission) -> Callable[[F], F]:
    """Decorator to require all of the specified permissions.

    Args:
        *permissions: Permissions that are all required.

    Returns:
        A decorator function that checks permissions before execution.

    Raises:
        AccessDeniedException: If the current subject lacks any permission.
        AuthenticationException: If no subject is authenticated.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            controller = get_access_controller()
            controller.require_all_permissions(*permissions)
            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator
