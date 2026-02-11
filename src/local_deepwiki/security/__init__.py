"""Security module for local-deepwiki.

This module provides access control, authorization, and security utilities.
"""

from __future__ import annotations

from local_deepwiki.security.access_control import (
    ROLE_PERMISSIONS,
    AccessController,
    AccessDeniedException,
    AuthenticationException,
    Permission,
    RBACMode,
    Role,
    Subject,
    get_access_controller,
    require_all_permissions,
    require_any_permission,
    require_permission,
    reset_access_controller,
)
from local_deepwiki.security.repository_access import (
    RepositoryAccessConfig,
    RepositoryAccessController,
    configure_repository_access,
    get_repository_access_controller,
    reset_repository_access,
)
from local_deepwiki.security.role_config import (
    RoleAssignment,
    RoleConfig,
    RoleManager,
    configure_roles,
    get_role_manager,
    reset_role_manager,
)

__all__ = [
    # Access control
    "AccessController",
    "AccessDeniedException",
    "AuthenticationException",
    "Permission",
    "RBACMode",
    "Role",
    "ROLE_PERMISSIONS",
    "Subject",
    "get_access_controller",
    "require_all_permissions",
    "require_any_permission",
    "require_permission",
    "reset_access_controller",
    # Repository access
    "RepositoryAccessConfig",
    "RepositoryAccessController",
    "configure_repository_access",
    "get_repository_access_controller",
    "reset_repository_access",
    # Role configuration
    "RoleAssignment",
    "RoleConfig",
    "RoleManager",
    "configure_roles",
    "get_role_manager",
    "reset_role_manager",
]
