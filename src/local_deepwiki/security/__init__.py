"""Security module for local-deepwiki.

This module provides access control, authorization, and security utilities.
"""

from local_deepwiki.security.access_control import (
    AccessController,
    AccessDeniedException,
    AuthenticationException,
    Permission,
    Role,
    ROLE_PERMISSIONS,
    Subject,
    get_access_controller,
    require_all_permissions,
    require_any_permission,
    require_permission,
    reset_access_controller,
)

__all__ = [
    "AccessController",
    "AccessDeniedException",
    "AuthenticationException",
    "Permission",
    "Role",
    "ROLE_PERMISSIONS",
    "Subject",
    "get_access_controller",
    "require_all_permissions",
    "require_any_permission",
    "require_permission",
    "reset_access_controller",
]
