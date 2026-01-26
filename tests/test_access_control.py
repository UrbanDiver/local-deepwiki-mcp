"""Comprehensive tests for the RBAC (Role-Based Access Control) system.

Tests cover:
- Permission enum
- Role enum
- ROLE_PERMISSIONS mapping
- Subject class
- AccessController class
- Decorators (require_permission, require_any_permission, require_all_permissions)
- Global singleton pattern
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from local_deepwiki.security.access_control import (
    ROLE_PERMISSIONS,
    AccessController,
    AccessDeniedException,
    AuthenticationException,
    Permission,
    Role,
    Subject,
    get_access_controller,
    require_all_permissions,
    require_any_permission,
    require_permission,
    reset_access_controller,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_controller():
    """Reset the global access controller before and after each test."""
    reset_access_controller()
    yield
    reset_access_controller()


@pytest.fixture
def admin_subject():
    """Create an admin subject for testing."""
    return Subject(identifier="admin-user", roles={Role.ADMIN})


@pytest.fixture
def editor_subject():
    """Create an editor subject for testing."""
    return Subject(identifier="editor-user", roles={Role.EDITOR})


@pytest.fixture
def viewer_subject():
    """Create a viewer subject for testing."""
    return Subject(identifier="viewer-user", roles={Role.VIEWER})


@pytest.fixture
def guest_subject():
    """Create a guest subject for testing."""
    return Subject(identifier="guest-user", roles={Role.GUEST})


@pytest.fixture
def multi_role_subject():
    """Create a subject with multiple roles for testing."""
    return Subject(identifier="multi-role-user", roles={Role.VIEWER, Role.EDITOR})


@pytest.fixture
def controller():
    """Create a fresh AccessController instance."""
    return AccessController()


# =============================================================================
# Permission Enum Tests
# =============================================================================


class TestPermissionEnum:
    """Tests for the Permission enum."""

    def test_all_permission_values_exist(self):
        """Verify all expected permission values are defined."""
        expected_permissions = [
            "INDEX_READ",
            "INDEX_WRITE",
            "INDEX_DELETE",
            "CONFIG_READ",
            "CONFIG_WRITE",
            "QUERY_SEARCH",
            "QUERY_DEEP_RESEARCH",
            "EXPORT_HTML",
            "EXPORT_PDF",
            "SYSTEM_ADMIN",
        ]
        for perm_name in expected_permissions:
            assert hasattr(Permission, perm_name), f"Permission.{perm_name} should exist"

    def test_permission_string_representation(self):
        """Verify permission string values are formatted correctly."""
        assert Permission.INDEX_READ == "index:read"
        assert Permission.INDEX_WRITE == "index:write"
        assert Permission.INDEX_DELETE == "index:delete"
        assert Permission.CONFIG_READ == "config:read"
        assert Permission.CONFIG_WRITE == "config:write"
        assert Permission.QUERY_SEARCH == "query:search"
        assert Permission.QUERY_DEEP_RESEARCH == "query:deep_research"
        assert Permission.EXPORT_HTML == "export:html"
        assert Permission.EXPORT_PDF == "export:pdf"
        assert Permission.SYSTEM_ADMIN == "system:admin"

    def test_permission_is_string_enum(self):
        """Verify Permission inherits from str for easy string operations."""
        assert isinstance(Permission.INDEX_READ, str)
        # Direct comparison works because Permission inherits from str
        assert Permission.INDEX_READ == "index:read"
        assert Permission.INDEX_READ.value == "index:read"

    def test_permission_count(self):
        """Verify the total number of permissions."""
        assert len(Permission) == 10


# =============================================================================
# Role Enum Tests
# =============================================================================


class TestRoleEnum:
    """Tests for the Role enum."""

    def test_all_role_values_exist(self):
        """Verify all expected role values are defined."""
        expected_roles = ["ADMIN", "EDITOR", "VIEWER", "GUEST"]
        for role_name in expected_roles:
            assert hasattr(Role, role_name), f"Role.{role_name} should exist"

    def test_role_string_representation(self):
        """Verify role string values are lowercase."""
        assert Role.ADMIN == "admin"
        assert Role.EDITOR == "editor"
        assert Role.VIEWER == "viewer"
        assert Role.GUEST == "guest"

    def test_role_is_string_enum(self):
        """Verify Role inherits from str for easy string operations."""
        assert isinstance(Role.ADMIN, str)
        # Direct comparison works because Role inherits from str
        assert Role.ADMIN == "admin"
        assert Role.ADMIN.value == "admin"

    def test_role_count(self):
        """Verify the total number of roles."""
        assert len(Role) == 4


# =============================================================================
# ROLE_PERMISSIONS Mapping Tests
# =============================================================================


class TestRolePermissionsMapping:
    """Tests for the ROLE_PERMISSIONS mapping."""

    def test_admin_has_all_permissions(self):
        """Verify ADMIN role has all permissions in the system."""
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        all_perms = set(Permission)
        assert admin_perms == all_perms, "ADMIN should have all permissions"

    def test_editor_permissions_subset(self):
        """Verify EDITOR permissions are a subset of ADMIN permissions."""
        editor_perms = ROLE_PERMISSIONS[Role.EDITOR]
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert editor_perms < admin_perms, "EDITOR should have fewer permissions than ADMIN"

    def test_editor_specific_permissions(self):
        """Verify EDITOR has expected permissions."""
        editor_perms = ROLE_PERMISSIONS[Role.EDITOR]
        expected = {
            Permission.INDEX_READ,
            Permission.INDEX_WRITE,
            Permission.CONFIG_READ,
            Permission.QUERY_SEARCH,
            Permission.QUERY_DEEP_RESEARCH,
            Permission.EXPORT_HTML,
            Permission.EXPORT_PDF,
        }
        assert editor_perms == expected

    def test_viewer_permissions_subset(self):
        """Verify VIEWER permissions are a subset of EDITOR permissions."""
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        editor_perms = ROLE_PERMISSIONS[Role.EDITOR]
        assert viewer_perms < editor_perms, "VIEWER should have fewer permissions than EDITOR"

    def test_viewer_specific_permissions(self):
        """Verify VIEWER has expected permissions."""
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        expected = {
            Permission.INDEX_READ,
            Permission.QUERY_SEARCH,
            Permission.QUERY_DEEP_RESEARCH,
            Permission.EXPORT_HTML,
        }
        assert viewer_perms == expected

    def test_guest_has_minimal_permissions(self):
        """Verify GUEST has only minimal permissions."""
        guest_perms = ROLE_PERMISSIONS[Role.GUEST]
        assert guest_perms == {Permission.QUERY_SEARCH}

    def test_permission_hierarchy(self):
        """Verify permission hierarchy: ADMIN > EDITOR > VIEWER > GUEST."""
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        editor_perms = ROLE_PERMISSIONS[Role.EDITOR]
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        guest_perms = ROLE_PERMISSIONS[Role.GUEST]

        assert len(admin_perms) > len(editor_perms)
        assert len(editor_perms) > len(viewer_perms)
        assert len(viewer_perms) > len(guest_perms)

        # Verify containment
        assert editor_perms.issubset(admin_perms)
        assert viewer_perms.issubset(editor_perms)
        assert guest_perms.issubset(viewer_perms)

    def test_all_roles_have_mapping(self):
        """Verify every role has a permission mapping."""
        for role in Role:
            assert role in ROLE_PERMISSIONS, f"Role {role} should have a permission mapping"


# =============================================================================
# Subject Class Tests
# =============================================================================


class TestSubject:
    """Tests for the Subject class."""

    def test_has_permission_with_single_role(self, admin_subject):
        """Verify has_permission works with a single role."""
        assert admin_subject.has_permission(Permission.SYSTEM_ADMIN)
        assert admin_subject.has_permission(Permission.INDEX_READ)
        assert admin_subject.has_permission(Permission.INDEX_WRITE)

    def test_has_permission_with_multiple_roles(self, multi_role_subject):
        """Verify has_permission aggregates permissions from multiple roles."""
        # From EDITOR role
        assert multi_role_subject.has_permission(Permission.INDEX_WRITE)
        # From VIEWER role (also in EDITOR, but verifies union)
        assert multi_role_subject.has_permission(Permission.QUERY_SEARCH)
        assert multi_role_subject.has_permission(Permission.EXPORT_HTML)

    def test_has_permission_returns_false_for_missing(self, guest_subject):
        """Verify has_permission returns False for missing permissions."""
        assert not guest_subject.has_permission(Permission.INDEX_READ)
        assert not guest_subject.has_permission(Permission.SYSTEM_ADMIN)
        assert not guest_subject.has_permission(Permission.CONFIG_WRITE)

    def test_has_permission_viewer_limitations(self, viewer_subject):
        """Verify VIEWER lacks write and admin permissions."""
        assert not viewer_subject.has_permission(Permission.INDEX_WRITE)
        assert not viewer_subject.has_permission(Permission.INDEX_DELETE)
        assert not viewer_subject.has_permission(Permission.CONFIG_WRITE)
        assert not viewer_subject.has_permission(Permission.SYSTEM_ADMIN)

    def test_get_all_permissions_single_role(self, editor_subject):
        """Verify get_all_permissions returns correct set for single role."""
        perms = editor_subject.get_all_permissions()
        assert perms == ROLE_PERMISSIONS[Role.EDITOR]

    def test_get_all_permissions_multiple_roles(self, multi_role_subject):
        """Verify get_all_permissions aggregates from multiple roles."""
        perms = multi_role_subject.get_all_permissions()
        expected = ROLE_PERMISSIONS[Role.VIEWER] | ROLE_PERMISSIONS[Role.EDITOR]
        assert perms == expected

    def test_subject_with_empty_roles(self):
        """Verify subject with empty roles has no permissions."""
        subject = Subject(identifier="no-roles", roles=set())
        assert not subject.has_permission(Permission.QUERY_SEARCH)
        assert subject.get_all_permissions() == set()

    def test_subject_identifier(self, admin_subject):
        """Verify subject identifier is stored correctly."""
        assert admin_subject.identifier == "admin-user"

    def test_subject_roles_attribute(self, multi_role_subject):
        """Verify subject roles are stored correctly."""
        assert multi_role_subject.roles == {Role.VIEWER, Role.EDITOR}


# =============================================================================
# AccessController Tests
# =============================================================================


class TestAccessController:
    """Tests for the AccessController class."""

    def test_set_subject_with_valid_subject(self, controller, admin_subject):
        """Verify set_subject works with a valid subject."""
        controller.set_subject(admin_subject)
        assert controller.get_current_subject() == admin_subject

    def test_set_subject_with_no_identifier(self, controller):
        """Verify set_subject raises exception for subject without identifier."""
        subject = Subject(identifier="", roles={Role.GUEST})
        with pytest.raises(AuthenticationException, match="identifier is required"):
            controller.set_subject(subject)

    def test_set_subject_with_none_subject(self, controller):
        """Verify set_subject raises exception for None subject."""
        with pytest.raises(AuthenticationException, match="identifier is required"):
            controller.set_subject(None)

    def test_set_subject_with_no_roles(self, controller):
        """Verify set_subject raises exception for subject without roles."""
        subject = Subject(identifier="user", roles=set())
        with pytest.raises(AuthenticationException, match="at least one role is required"):
            controller.set_subject(subject)

    def test_clear_subject(self, controller, admin_subject):
        """Verify clear_subject removes the current subject."""
        controller.set_subject(admin_subject)
        assert controller.get_current_subject() is not None
        controller.clear_subject()
        assert controller.get_current_subject() is None

    def test_get_current_subject_initially_none(self, controller):
        """Verify get_current_subject returns None initially."""
        assert controller.get_current_subject() is None

    def test_require_permission_success(self, controller, admin_subject):
        """Verify require_permission succeeds with valid permission."""
        controller.set_subject(admin_subject)
        # Should not raise
        controller.require_permission(Permission.SYSTEM_ADMIN)

    def test_require_permission_access_denied(self, controller, guest_subject):
        """Verify require_permission raises AccessDeniedException when lacking permission."""
        controller.set_subject(guest_subject)
        with pytest.raises(AccessDeniedException, match="lacks permission"):
            controller.require_permission(Permission.INDEX_READ)

    def test_require_permission_not_authenticated(self, controller):
        """Verify require_permission raises AuthenticationException when not authenticated."""
        with pytest.raises(AuthenticationException, match="No subject authenticated"):
            controller.require_permission(Permission.QUERY_SEARCH)

    def test_require_any_permission_success(self, controller, viewer_subject):
        """Verify require_any_permission succeeds when subject has one of the permissions."""
        controller.set_subject(viewer_subject)
        # Viewer has QUERY_SEARCH but not INDEX_WRITE
        controller.require_any_permission(Permission.QUERY_SEARCH, Permission.INDEX_WRITE)

    def test_require_any_permission_failure(self, controller, guest_subject):
        """Verify require_any_permission fails when subject lacks all permissions."""
        controller.set_subject(guest_subject)
        with pytest.raises(AccessDeniedException, match="lacks any of"):
            controller.require_any_permission(Permission.INDEX_READ, Permission.INDEX_WRITE)

    def test_require_any_permission_not_authenticated(self, controller):
        """Verify require_any_permission raises when not authenticated."""
        with pytest.raises(AuthenticationException, match="No subject authenticated"):
            controller.require_any_permission(Permission.QUERY_SEARCH)

    def test_require_all_permissions_success(self, controller, admin_subject):
        """Verify require_all_permissions succeeds when subject has all permissions."""
        controller.set_subject(admin_subject)
        controller.require_all_permissions(
            Permission.INDEX_READ, Permission.INDEX_WRITE, Permission.SYSTEM_ADMIN
        )

    def test_require_all_permissions_failure(self, controller, editor_subject):
        """Verify require_all_permissions fails when subject lacks one permission."""
        controller.set_subject(editor_subject)
        with pytest.raises(AccessDeniedException, match="lacks permission"):
            controller.require_all_permissions(Permission.INDEX_READ, Permission.SYSTEM_ADMIN)

    def test_require_all_permissions_not_authenticated(self, controller):
        """Verify require_all_permissions raises when not authenticated."""
        with pytest.raises(AuthenticationException, match="No subject authenticated"):
            controller.require_all_permissions(Permission.QUERY_SEARCH)

    def test_has_permission_returns_true(self, controller, admin_subject):
        """Verify has_permission returns True for valid permission."""
        controller.set_subject(admin_subject)
        assert controller.has_permission(Permission.SYSTEM_ADMIN) is True

    def test_has_permission_returns_false(self, controller, guest_subject):
        """Verify has_permission returns False for missing permission."""
        controller.set_subject(guest_subject)
        assert controller.has_permission(Permission.INDEX_READ) is False

    def test_has_permission_not_authenticated(self, controller):
        """Verify has_permission returns False when not authenticated."""
        assert controller.has_permission(Permission.QUERY_SEARCH) is False


# =============================================================================
# Decorator Tests
# =============================================================================


class TestRequirePermissionDecorator:
    """Tests for the @require_permission decorator."""

    def test_sync_function_success(self, admin_subject):
        """Verify decorator allows sync function with valid permission."""
        controller = get_access_controller()
        controller.set_subject(admin_subject)

        @require_permission(Permission.SYSTEM_ADMIN)
        def protected_function():
            return "success"

        assert protected_function() == "success"

    def test_sync_function_access_denied(self, guest_subject):
        """Verify decorator blocks sync function without permission."""
        controller = get_access_controller()
        controller.set_subject(guest_subject)

        @require_permission(Permission.SYSTEM_ADMIN)
        def protected_function():
            return "success"

        with pytest.raises(AccessDeniedException):
            protected_function()

    def test_sync_function_not_authenticated(self):
        """Verify decorator blocks sync function when not authenticated."""

        @require_permission(Permission.QUERY_SEARCH)
        def protected_function():
            return "success"

        with pytest.raises(AuthenticationException):
            protected_function()

    async def test_async_function_success(self, admin_subject):
        """Verify decorator allows async function with valid permission."""
        controller = get_access_controller()
        controller.set_subject(admin_subject)

        @require_permission(Permission.SYSTEM_ADMIN)
        async def protected_async_function():
            return "async_success"

        result = await protected_async_function()
        assert result == "async_success"

    async def test_async_function_access_denied(self, guest_subject):
        """Verify decorator blocks async function without permission."""
        controller = get_access_controller()
        controller.set_subject(guest_subject)

        @require_permission(Permission.SYSTEM_ADMIN)
        async def protected_async_function():
            return "async_success"

        with pytest.raises(AccessDeniedException):
            await protected_async_function()

    def test_decorator_preserves_function_metadata(self):
        """Verify decorator preserves function name and docstring."""

        @require_permission(Permission.QUERY_SEARCH)
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


class TestRequireAnyPermissionDecorator:
    """Tests for the @require_any_permission decorator."""

    def test_sync_function_success(self, viewer_subject):
        """Verify decorator allows when subject has any permission."""
        controller = get_access_controller()
        controller.set_subject(viewer_subject)

        @require_any_permission(Permission.QUERY_SEARCH, Permission.SYSTEM_ADMIN)
        def protected_function():
            return "success"

        assert protected_function() == "success"

    def test_sync_function_failure(self, guest_subject):
        """Verify decorator blocks when subject lacks all permissions."""
        controller = get_access_controller()
        controller.set_subject(guest_subject)

        @require_any_permission(Permission.INDEX_READ, Permission.SYSTEM_ADMIN)
        def protected_function():
            return "success"

        with pytest.raises(AccessDeniedException):
            protected_function()

    async def test_async_function_success(self, editor_subject):
        """Verify decorator allows async function with any permission."""
        controller = get_access_controller()
        controller.set_subject(editor_subject)

        @require_any_permission(Permission.INDEX_WRITE, Permission.SYSTEM_ADMIN)
        async def protected_async_function():
            return "async_success"

        result = await protected_async_function()
        assert result == "async_success"

    async def test_async_function_failure(self, guest_subject):
        """Verify decorator blocks async function without permissions."""
        controller = get_access_controller()
        controller.set_subject(guest_subject)

        @require_any_permission(Permission.INDEX_READ, Permission.INDEX_WRITE)
        async def protected_async_function():
            return "async_success"

        with pytest.raises(AccessDeniedException):
            await protected_async_function()

    def test_decorator_preserves_function_metadata(self):
        """Verify decorator preserves function name and docstring."""

        @require_any_permission(Permission.QUERY_SEARCH, Permission.INDEX_READ)
        def another_function():
            """Another docstring."""
            pass

        assert another_function.__name__ == "another_function"
        assert another_function.__doc__ == "Another docstring."


class TestRequireAllPermissionsDecorator:
    """Tests for the @require_all_permissions decorator."""

    def test_sync_function_success(self, admin_subject):
        """Verify decorator allows when subject has all permissions."""
        controller = get_access_controller()
        controller.set_subject(admin_subject)

        @require_all_permissions(Permission.INDEX_READ, Permission.INDEX_WRITE, Permission.SYSTEM_ADMIN)
        def protected_function():
            return "success"

        assert protected_function() == "success"

    def test_sync_function_failure(self, editor_subject):
        """Verify decorator blocks when subject lacks one permission."""
        controller = get_access_controller()
        controller.set_subject(editor_subject)

        @require_all_permissions(Permission.INDEX_READ, Permission.SYSTEM_ADMIN)
        def protected_function():
            return "success"

        with pytest.raises(AccessDeniedException):
            protected_function()

    async def test_async_function_success(self, admin_subject):
        """Verify decorator allows async function with all permissions."""
        controller = get_access_controller()
        controller.set_subject(admin_subject)

        @require_all_permissions(Permission.QUERY_SEARCH, Permission.EXPORT_HTML)
        async def protected_async_function():
            return "async_success"

        result = await protected_async_function()
        assert result == "async_success"

    async def test_async_function_failure(self, viewer_subject):
        """Verify decorator blocks async function without all permissions."""
        controller = get_access_controller()
        controller.set_subject(viewer_subject)

        @require_all_permissions(Permission.INDEX_READ, Permission.INDEX_WRITE)
        async def protected_async_function():
            return "async_success"

        with pytest.raises(AccessDeniedException):
            await protected_async_function()

    def test_decorator_preserves_function_metadata(self):
        """Verify decorator preserves function name and docstring."""

        @require_all_permissions(Permission.QUERY_SEARCH, Permission.INDEX_READ)
        def yet_another_function():
            """Yet another docstring."""
            pass

        assert yet_another_function.__name__ == "yet_another_function"
        assert yet_another_function.__doc__ == "Yet another docstring."


# =============================================================================
# Global Singleton Tests
# =============================================================================


class TestGlobalSingleton:
    """Tests for the global access controller singleton pattern."""

    def test_get_access_controller_returns_same_instance(self):
        """Verify get_access_controller returns the same instance."""
        controller1 = get_access_controller()
        controller2 = get_access_controller()
        assert controller1 is controller2

    def test_reset_access_controller_clears_instance(self):
        """Verify reset_access_controller creates a new instance."""
        controller1 = get_access_controller()
        reset_access_controller()
        controller2 = get_access_controller()
        assert controller1 is not controller2

    def test_reset_clears_subject(self, admin_subject):
        """Verify reset clears the current subject state."""
        controller = get_access_controller()
        controller.set_subject(admin_subject)
        assert controller.get_current_subject() is not None

        reset_access_controller()

        new_controller = get_access_controller()
        assert new_controller.get_current_subject() is None

    def test_thread_safety_basic(self):
        """Basic test for thread-safe singleton creation."""
        controllers = []

        def get_controller():
            controllers.append(get_access_controller())

        threads = [threading.Thread(target=get_controller) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same instance
        assert len(controllers) == 10
        assert all(c is controllers[0] for c in controllers)


# =============================================================================
# Exception Tests
# =============================================================================


class TestExceptions:
    """Tests for access control exceptions."""

    def test_access_denied_exception(self):
        """Verify AccessDeniedException can be raised and caught."""
        with pytest.raises(AccessDeniedException):
            raise AccessDeniedException("Test access denied")

    def test_authentication_exception(self):
        """Verify AuthenticationException can be raised and caught."""
        with pytest.raises(AuthenticationException):
            raise AuthenticationException("Test authentication failed")

    def test_exception_messages(self):
        """Verify exception messages are preserved."""
        try:
            raise AccessDeniedException("Custom message")
        except AccessDeniedException as e:
            assert "Custom message" in str(e)


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and integration scenarios."""

    def test_subject_replacement(self, controller, admin_subject, guest_subject):
        """Verify setting a new subject replaces the old one."""
        controller.set_subject(admin_subject)
        assert controller.get_current_subject() == admin_subject

        controller.set_subject(guest_subject)
        assert controller.get_current_subject() == guest_subject

    def test_multiple_role_permission_union(self):
        """Verify permissions are unioned across multiple roles."""
        # Create subject with GUEST and VIEWER roles
        subject = Subject(identifier="test", roles={Role.GUEST, Role.VIEWER})

        # Should have permissions from both roles
        perms = subject.get_all_permissions()
        expected = ROLE_PERMISSIONS[Role.GUEST] | ROLE_PERMISSIONS[Role.VIEWER]
        assert perms == expected

    def test_require_permission_error_message_contains_subject(self, controller, guest_subject):
        """Verify error messages include the subject identifier."""
        controller.set_subject(guest_subject)
        with pytest.raises(AccessDeniedException) as exc_info:
            controller.require_permission(Permission.SYSTEM_ADMIN)
        assert "guest-user" in str(exc_info.value)

    def test_require_any_permission_error_message_lists_permissions(self, controller, guest_subject):
        """Verify require_any error messages list the required permissions."""
        controller.set_subject(guest_subject)
        with pytest.raises(AccessDeniedException) as exc_info:
            controller.require_any_permission(Permission.INDEX_READ, Permission.INDEX_WRITE)
        error_msg = str(exc_info.value)
        # Error message includes permission enum names
        assert "INDEX_READ" in error_msg or "INDEX_WRITE" in error_msg

    def test_decorator_on_method(self, admin_subject):
        """Verify decorators work on class methods."""
        controller = get_access_controller()
        controller.set_subject(admin_subject)

        class MyClass:
            @require_permission(Permission.SYSTEM_ADMIN)
            def protected_method(self):
                return "method_success"

        obj = MyClass()
        assert obj.protected_method() == "method_success"

    async def test_decorator_on_async_method(self, admin_subject):
        """Verify decorators work on async class methods."""
        controller = get_access_controller()
        controller.set_subject(admin_subject)

        class MyAsyncClass:
            @require_permission(Permission.SYSTEM_ADMIN)
            async def protected_async_method(self):
                return "async_method_success"

        obj = MyAsyncClass()
        result = await obj.protected_async_method()
        assert result == "async_method_success"

    def test_empty_require_any_permissions(self, controller, admin_subject):
        """Verify require_any_permission with no args raises AccessDeniedException.

        With an empty permissions list, there's no permission to satisfy,
        so the check fails (the subject lacks any of an empty set).
        """
        controller.set_subject(admin_subject)
        # Empty permissions list - raises because no permission can be matched
        with pytest.raises(AccessDeniedException, match="lacks any of"):
            controller.require_any_permission()

    def test_empty_require_all_permissions(self, controller, guest_subject):
        """Verify require_all_permissions with no args succeeds (vacuous truth)."""
        controller.set_subject(guest_subject)
        # Empty permissions list - should succeed (all zero permissions are satisfied)
        controller.require_all_permissions()

    def test_single_permission_in_any(self, controller, viewer_subject):
        """Verify require_any works with a single permission."""
        controller.set_subject(viewer_subject)
        controller.require_any_permission(Permission.QUERY_SEARCH)

    def test_single_permission_in_all(self, controller, viewer_subject):
        """Verify require_all works with a single permission."""
        controller.set_subject(viewer_subject)
        controller.require_all_permissions(Permission.QUERY_SEARCH)
