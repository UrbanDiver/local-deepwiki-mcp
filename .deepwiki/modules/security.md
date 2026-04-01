# Security Module Documentation

## Module Purpose

The security module provides access control, authorization, and security utilities for the Local DeepWiki MCP Server. It implements Role-Based Access Control (RBAC) to manage permissions for different user roles and system operations. The module handles authentication, permission checking, and repository-level access control.

## Key Classes and Functions

### RBACMode
An enumeration defining the RBAC enforcement modes:
- `DISABLED`: No permission checks
- `PERMISSIVE`: Check if subject set, allow if not (default)
- `ENFORCED`: Always require authenticated subject

### Permission
An enumeration of available permissions in the system:
- `INDEX_READ`, `INDEX_WRITE`, `INDEX_DELETE`: Index management permissions
- `CONFIG_READ`, `CONFIG_WRITE`: Configuration permissions
- `QUERY_SEARCH`, `QUERY_DEEP_RESEARCH`: Query operations permissions
- `EXPORT_HTML`, `EXPORT_PDF`: Export operations permissions
- `SYSTEM_ADMIN`: System operations permissions

### Role
An enumeration of predefined roles in the system:
- `ADMIN`: Administrative role with full access
- `EDITOR`: Editor role with read/write access
- `VIEWER`: Viewer role with read-only access
- `GUEST`: Guest role with minimal access

### AccessDeniedException
Raised when access is denied due to insufficient permissions.

### AuthenticationException
Raised when authentication fails.

### Subject
Represents a user or service making a request. Contains:
- `identifier`: Unique identifier for the subject
- `roles`: Set of roles assigned to the subject
- `has_permission()`: Check if subject has required permission
- `get_all_permissions()`: Get all permissions granted through assigned roles

### AccessController
Main class implementing access control logic:
- `__init__()`: Initialize with RBAC mode
- `mode()`: Get current RBAC mode
- `set_mode()`: Set RBAC enforcement mode
- `set_subject()`: Set current subject for access checks
- `clear_subject()`: Clear current subject
- `get_current_subject()`: Get currently authenticated subject
- `require_permission()`: Check if current subject has required permission
- `require_any_permission()`: Check if subject has any of specified permissions
- `require_all_permissions()`: Check if subject has all specified permissions
- `has_permission()`: Check if current subject has required permission (returns boolean)

### RepositoryAccessConfig
Configuration class for repository access control.

### RepositoryAccessController
Controller for managing repository-level access control.

### RoleAssignment
Class defining role assignments for subjects.

### RoleConfig
Class defining role configurations.

### RoleManager
Manages role configurations and assignments.

### Utility Functions
- `_rbac_mode_from_env()`: Read RBAC mode from environment variable
- `get_access_controller()`: Get global access controller instance
- `reset_access_controller()`: Reset the global access controller
- `configure_repository_access()`: Configure repository access control
- `get_repository_access_controller()`: Get repository access controller
- `reset_repository_access()`: Reset repository access controller
- `configure_roles()`: Configure role management
- `get_role_manager()`: Get role manager instance
- `reset_role_manager()`: Reset role manager
- `require_permission()`: Decorator function for permission checking
- `require_any_permission()`: Decorator function for any permission checking
- `require_all_permissions()`: Decorator function for all permissions checking

## How Components Interact

The security module implements a layered access control system:

1. **[AccessController](../files/src/local_deepwiki/security/access_control.md)** manages the global RBAC state and performs permission checks based on current mode (DISABLED, PERMISSIVE, ENFORCED)
2. **[Subject](../files/src/local_deepwiki/security/access_control.md)** objects represent authenticated users/services with associated roles
3. **Role** definitions map to sets of permissions via the **ROLE_PERMISSIONS** mapping
4. **[RepositoryAccessController](../files/src/local_deepwiki/security/repository_access.md)** handles repository-level access control configurations
5. **[RoleManager](../files/src/local_deepwiki/security/role_config.md)** manages role configurations and assignments for subjects
6. The system reads RBAC mode from environment variables (`DEEPWIKI_RBAC_MODE`)
7. [Permission](../files/src/local_deepwiki/security/access_control.md) checking is performed through [decorator](../files/src/local_deepwiki/providers/base.md) functions or direct method calls on [AccessController](../files/src/local_deepwiki/security/access_control.md)

## Usage Examples

### Basic Access Control Usage```python
from local_deepwiki.security import (
    AccessController,
    Subject,
    Role,
    Permission,
    require_permission
)

# Create access controller and subject
controller = AccessController()
subject = Subject(identifier="user123", roles={Role.ADMIN})

# Set current subject
controller.set_subject(subject)

# Check permissions
controller.require_permission(Permission.INDEX_READ)  # Raises if not allowed

# Using decorators
@require_permission(Permission.INDEX_WRITE)
def update_index():
    pass
```
### Repository Access Control Configuration```python
from local_deepwiki.security import (
    RepositoryAccessConfig,
    configure_repository_access
)

# Configure repository access
config = RepositoryAccessConfig(
    allowed_paths=["/path/to/repo1", "/path/to/repo2"],
    blocked_paths=[]
)
configure_repository_access(config)
```
### Role Management```python
from local_deepwiki.security import (
    RoleAssignment,
    configure_roles,
    get_role_manager
)

# Configure roles
assignments = [
    RoleAssignment(subject="user123", roles=[Role.EDITOR]),
    RoleAssignment(subject="user456", roles=[Role.VIEWER])
]
configure_roles(assignments)

# Get role manager
manager = get_role_manager()
```
## Dependencies

This module depends on:
- `asyncio` - For asynchronous operations
- `collections.abc` - For Callable type hints
- `contextvars` - For thread-local access controller storage
- `dataclasses` - For [Subject](../files/src/local_deepwiki/security/access_control.md) dataclass definition
- `enum` - For StrEnum-based enumerations ([RBACMode](../files/src/local_deepwiki/security/access_control.md), [Permission](../files/src/local_deepwiki/security/access_control.md), Role)
- `functools` - For function wrapping utilities
- `typing` - For type hints
- `os` - For environment variable access

The module re-exports components from:
- `local_deepwiki.security.access_control`
- `local_deepwiki.security.repository_access`
- `local_deepwiki.security.role_config`

## Relevant Source Files

The following source files were used to generate this documentation:

- `src/local_deepwiki/security/__init__.py`
- [`src/local_deepwiki/security/access_control.py:21-26`](../files/src/local_deepwiki/security/access_control.md)
- [`src/local_deepwiki/security/role_config.py:20-29`](../files/src/local_deepwiki/security/role_config.md)
- [`src/local_deepwiki/security/repository_access.py:19-32`](../files/src/local_deepwiki/security/repository_access.md)
