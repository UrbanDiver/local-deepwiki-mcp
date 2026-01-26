"""Comprehensive tests for the role_config module.

Tests cover:
- RoleAssignment dataclass
- RoleConfig dataclass with defaults
- RoleManager class (pattern matching, admin identifiers, YAML loading)
- Global singleton pattern (get_role_manager, configure_roles, reset_role_manager)
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from local_deepwiki.security.access_control import Role
from local_deepwiki.security.role_config import (
    RoleAssignment,
    RoleConfig,
    RoleManager,
    configure_roles,
    get_role_manager,
    reset_role_manager,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_global_manager():
    """Reset the global role manager before and after each test."""
    reset_role_manager()
    yield
    reset_role_manager()


@pytest.fixture
def basic_config():
    """Create a basic role configuration for testing."""
    return RoleConfig(
        default_role=Role.VIEWER,
        admin_identifiers=["admin", "root", "superuser"],
        assignments=[
            RoleAssignment(pattern="*@admin.example.com", role=Role.ADMIN),
            RoleAssignment(pattern="editor-*", role=Role.EDITOR),
            RoleAssignment(pattern="guest-*", role=Role.GUEST),
        ],
    )


@pytest.fixture
def manager_with_config(basic_config):
    """Create a RoleManager with basic configuration."""
    return RoleManager(basic_config)


@pytest.fixture
def yaml_config_path():
    """Create a temporary YAML config file for testing."""
    config_data = {
        "default_role": "viewer",
        "admin_identifiers": ["admin", "root"],
        "assignments": [
            {"pattern": "*@admin.example.com", "role": "admin"},
            {"pattern": "editor-*", "role": "editor"},
            {"pattern": "*@guest.example.com", "role": "guest"},
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(config_data, f)
        return Path(f.name)


# =============================================================================
# RoleAssignment Dataclass Tests
# =============================================================================


class TestRoleAssignment:
    """Tests for the RoleAssignment dataclass."""

    def test_role_assignment_creation(self):
        """Verify RoleAssignment can be created with pattern and role."""
        assignment = RoleAssignment(pattern="*@admin.com", role=Role.ADMIN)
        assert assignment.pattern == "*@admin.com"
        assert assignment.role == Role.ADMIN

    def test_role_assignment_with_different_roles(self):
        """Verify RoleAssignment works with all role types."""
        for role in Role:
            assignment = RoleAssignment(pattern=f"test-{role.value}-*", role=role)
            assert assignment.role == role

    def test_role_assignment_equality(self):
        """Verify RoleAssignment equality is based on pattern and role."""
        a1 = RoleAssignment(pattern="test-*", role=Role.EDITOR)
        a2 = RoleAssignment(pattern="test-*", role=Role.EDITOR)
        assert a1 == a2

    def test_role_assignment_inequality(self):
        """Verify RoleAssignment inequality for different patterns or roles."""
        a1 = RoleAssignment(pattern="test-*", role=Role.EDITOR)
        a2 = RoleAssignment(pattern="test-*", role=Role.ADMIN)
        a3 = RoleAssignment(pattern="other-*", role=Role.EDITOR)
        assert a1 != a2
        assert a1 != a3


# =============================================================================
# RoleConfig Dataclass Tests
# =============================================================================


class TestRoleConfig:
    """Tests for the RoleConfig dataclass."""

    def test_default_role_config(self):
        """Verify RoleConfig default values."""
        config = RoleConfig()
        assert config.default_role == Role.VIEWER
        assert config.assignments == []
        assert config.admin_identifiers == []

    def test_role_config_with_custom_default_role(self):
        """Verify RoleConfig can set a custom default role."""
        config = RoleConfig(default_role=Role.GUEST)
        assert config.default_role == Role.GUEST

    def test_role_config_with_admin_identifiers(self):
        """Verify RoleConfig stores admin identifiers."""
        identifiers = ["admin", "root", "superuser"]
        config = RoleConfig(admin_identifiers=identifiers)
        assert config.admin_identifiers == identifiers

    def test_role_config_with_assignments(self):
        """Verify RoleConfig stores role assignments."""
        assignments = [
            RoleAssignment(pattern="*@admin.com", role=Role.ADMIN),
            RoleAssignment(pattern="guest-*", role=Role.GUEST),
        ]
        config = RoleConfig(assignments=assignments)
        assert config.assignments == assignments
        assert len(config.assignments) == 2

    def test_role_config_full_configuration(self, basic_config):
        """Verify RoleConfig with all fields set."""
        assert basic_config.default_role == Role.VIEWER
        assert "admin" in basic_config.admin_identifiers
        assert len(basic_config.assignments) == 3


# =============================================================================
# RoleManager Initialization Tests
# =============================================================================


class TestRoleManagerInit:
    """Tests for RoleManager initialization."""

    def test_role_manager_default_config(self):
        """Verify RoleManager uses default config when none provided."""
        manager = RoleManager()
        assert manager.config.default_role == Role.VIEWER
        assert manager.config.assignments == []
        assert manager.config.admin_identifiers == []

    def test_role_manager_with_none_config(self):
        """Verify RoleManager handles None config by using defaults."""
        manager = RoleManager(config=None)
        assert manager.config is not None
        assert manager.config.default_role == Role.VIEWER

    def test_role_manager_with_custom_config(self, basic_config):
        """Verify RoleManager uses provided config."""
        manager = RoleManager(config=basic_config)
        assert manager.config == basic_config
        assert manager.config.default_role == Role.VIEWER
        assert len(manager.config.assignments) == 3

    def test_role_manager_config_property(self, manager_with_config, basic_config):
        """Verify config property returns the configuration."""
        assert manager_with_config.config == basic_config


# =============================================================================
# RoleManager.get_role_for_identifier Tests
# =============================================================================


class TestGetRoleForIdentifier:
    """Tests for RoleManager.get_role_for_identifier method."""

    def test_admin_identifier_exact_match(self, manager_with_config):
        """Verify admin identifiers get ADMIN role via exact match."""
        assert manager_with_config.get_role_for_identifier("admin") == Role.ADMIN
        assert manager_with_config.get_role_for_identifier("root") == Role.ADMIN
        assert manager_with_config.get_role_for_identifier("superuser") == Role.ADMIN

    def test_admin_identifier_case_sensitive(self, manager_with_config):
        """Verify admin identifier matching is case-sensitive."""
        # "Admin" is not the same as "admin"
        assert manager_with_config.get_role_for_identifier("Admin") != Role.ADMIN
        assert manager_with_config.get_role_for_identifier("ADMIN") != Role.ADMIN

    def test_pattern_matching_email_domain(self, manager_with_config):
        """Verify pattern matching for email domains."""
        assert manager_with_config.get_role_for_identifier("john@admin.example.com") == Role.ADMIN
        assert manager_with_config.get_role_for_identifier("jane@admin.example.com") == Role.ADMIN
        assert manager_with_config.get_role_for_identifier("x@admin.example.com") == Role.ADMIN

    def test_pattern_matching_prefix(self, manager_with_config):
        """Verify pattern matching for identifier prefixes."""
        assert manager_with_config.get_role_for_identifier("editor-1") == Role.EDITOR
        assert manager_with_config.get_role_for_identifier("editor-john") == Role.EDITOR
        assert manager_with_config.get_role_for_identifier("editor-") == Role.EDITOR

    def test_pattern_matching_guest(self, manager_with_config):
        """Verify pattern matching for guest identifiers."""
        assert manager_with_config.get_role_for_identifier("guest-user") == Role.GUEST
        assert manager_with_config.get_role_for_identifier("guest-123") == Role.GUEST

    def test_default_role_for_unmatched_identifier(self, manager_with_config):
        """Verify default role is returned for unmatched identifiers."""
        assert manager_with_config.get_role_for_identifier("random-user") == Role.VIEWER
        assert manager_with_config.get_role_for_identifier("user@other.com") == Role.VIEWER
        assert manager_with_config.get_role_for_identifier("unknown") == Role.VIEWER

    def test_first_match_wins(self):
        """Verify first matching pattern wins when multiple patterns match."""
        config = RoleConfig(
            assignments=[
                RoleAssignment(pattern="*", role=Role.GUEST),
                RoleAssignment(pattern="admin*", role=Role.ADMIN),
            ]
        )
        manager = RoleManager(config)
        # "*" matches first, so GUEST role is returned
        assert manager.get_role_for_identifier("admin-user") == Role.GUEST

    def test_admin_identifier_takes_priority_over_patterns(self):
        """Verify admin identifiers are checked before pattern assignments."""
        config = RoleConfig(
            admin_identifiers=["special-admin"],
            assignments=[
                RoleAssignment(pattern="special-*", role=Role.EDITOR),
            ],
        )
        manager = RoleManager(config)
        # admin identifier check happens before pattern matching
        assert manager.get_role_for_identifier("special-admin") == Role.ADMIN
        # But other "special-*" identifiers get EDITOR
        assert manager.get_role_for_identifier("special-user") == Role.EDITOR

    def test_empty_config_returns_default_role(self):
        """Verify empty config returns default role for any identifier."""
        manager = RoleManager(RoleConfig())
        assert manager.get_role_for_identifier("any-user") == Role.VIEWER
        assert manager.get_role_for_identifier("admin") == Role.VIEWER

    def test_custom_default_role(self):
        """Verify custom default role is returned for unmatched identifiers."""
        config = RoleConfig(default_role=Role.GUEST)
        manager = RoleManager(config)
        assert manager.get_role_for_identifier("any-user") == Role.GUEST


# =============================================================================
# RoleManager.create_subject Tests
# =============================================================================


class TestCreateSubject:
    """Tests for RoleManager.create_subject method."""

    def test_create_subject_with_admin_identifier(self, manager_with_config):
        """Verify create_subject creates admin subject for admin identifier."""
        subject = manager_with_config.create_subject("admin")
        assert subject.identifier == "admin"
        assert subject.roles == {Role.ADMIN}

    def test_create_subject_with_pattern_match(self, manager_with_config):
        """Verify create_subject creates subject with matched role."""
        subject = manager_with_config.create_subject("editor-john")
        assert subject.identifier == "editor-john"
        assert subject.roles == {Role.EDITOR}

    def test_create_subject_with_default_role(self, manager_with_config):
        """Verify create_subject creates subject with default role."""
        subject = manager_with_config.create_subject("random-user")
        assert subject.identifier == "random-user"
        assert subject.roles == {Role.VIEWER}

    def test_create_subject_preserves_identifier(self):
        """Verify create_subject preserves exact identifier."""
        manager = RoleManager()
        subject = manager.create_subject("User@Example.COM")
        assert subject.identifier == "User@Example.COM"

    def test_create_subject_has_single_role(self, manager_with_config):
        """Verify created subjects have exactly one role."""
        subject = manager_with_config.create_subject("admin")
        assert len(subject.roles) == 1


# =============================================================================
# RoleManager.from_yaml Tests
# =============================================================================


class TestFromYaml:
    """Tests for RoleManager.from_yaml class method."""

    def test_from_yaml_loads_config(self, yaml_config_path):
        """Verify from_yaml loads configuration from YAML file."""
        manager = RoleManager.from_yaml(yaml_config_path)
        assert manager.config.default_role == Role.VIEWER
        assert "admin" in manager.config.admin_identifiers
        assert "root" in manager.config.admin_identifiers
        assert len(manager.config.assignments) == 3

    def test_from_yaml_pattern_matching_works(self, yaml_config_path):
        """Verify loaded config performs pattern matching correctly."""
        manager = RoleManager.from_yaml(yaml_config_path)
        assert manager.get_role_for_identifier("admin") == Role.ADMIN
        assert manager.get_role_for_identifier("user@admin.example.com") == Role.ADMIN
        assert manager.get_role_for_identifier("editor-1") == Role.EDITOR
        assert manager.get_role_for_identifier("user@guest.example.com") == Role.GUEST
        assert manager.get_role_for_identifier("unknown") == Role.VIEWER

    def test_from_yaml_file_not_found(self):
        """Verify from_yaml raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            RoleManager.from_yaml(Path("/nonexistent/path/config.yaml"))

    def test_from_yaml_empty_file(self):
        """Verify from_yaml handles empty YAML file gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")  # Empty file
            path = Path(f.name)

        manager = RoleManager.from_yaml(path)
        # Should use defaults
        assert manager.config.default_role == Role.VIEWER
        assert manager.config.admin_identifiers == []
        assert manager.config.assignments == []

    def test_from_yaml_minimal_config(self):
        """Verify from_yaml handles minimal YAML configuration."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"default_role": "editor"}, f)
            path = Path(f.name)

        manager = RoleManager.from_yaml(path)
        assert manager.config.default_role == Role.EDITOR
        assert manager.config.admin_identifiers == []
        assert manager.config.assignments == []

    def test_from_yaml_only_admin_identifiers(self):
        """Verify from_yaml handles config with only admin identifiers."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"admin_identifiers": ["superadmin"]}, f)
            path = Path(f.name)

        manager = RoleManager.from_yaml(path)
        assert manager.config.admin_identifiers == ["superadmin"]
        assert manager.get_role_for_identifier("superadmin") == Role.ADMIN

    def test_from_yaml_only_assignments(self):
        """Verify from_yaml handles config with only assignments."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(
                {
                    "assignments": [
                        {"pattern": "dev-*", "role": "editor"},
                    ]
                },
                f,
            )
            path = Path(f.name)

        manager = RoleManager.from_yaml(path)
        assert len(manager.config.assignments) == 1
        assert manager.get_role_for_identifier("dev-user") == Role.EDITOR

    def test_from_yaml_invalid_role_raises_value_error(self):
        """Verify from_yaml raises ValueError for invalid role names."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump({"default_role": "superadmin"}, f)  # Invalid role
            path = Path(f.name)

        with pytest.raises(ValueError):
            RoleManager.from_yaml(path)

    def test_from_yaml_invalid_assignment_role(self):
        """Verify from_yaml raises ValueError for invalid assignment role."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(
                {
                    "assignments": [
                        {"pattern": "test-*", "role": "invalid_role"},
                    ]
                },
                f,
            )
            path = Path(f.name)

        with pytest.raises(ValueError):
            RoleManager.from_yaml(path)

    def test_from_yaml_invalid_yaml_syntax(self):
        """Verify from_yaml raises yaml.YAMLError for invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: syntax: [")
            path = Path(f.name)

        with pytest.raises(yaml.YAMLError):
            RoleManager.from_yaml(path)

    def test_from_yaml_all_role_types(self):
        """Verify from_yaml correctly parses all role types."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(
                {
                    "default_role": "guest",
                    "assignments": [
                        {"pattern": "admin-*", "role": "admin"},
                        {"pattern": "editor-*", "role": "editor"},
                        {"pattern": "viewer-*", "role": "viewer"},
                    ],
                },
                f,
            )
            path = Path(f.name)

        manager = RoleManager.from_yaml(path)
        assert manager.config.default_role == Role.GUEST
        assert manager.get_role_for_identifier("admin-1") == Role.ADMIN
        assert manager.get_role_for_identifier("editor-1") == Role.EDITOR
        assert manager.get_role_for_identifier("viewer-1") == Role.VIEWER


# =============================================================================
# Global Singleton Functions Tests
# =============================================================================


class TestGlobalSingletonFunctions:
    """Tests for global role manager singleton functions."""

    def test_get_role_manager_returns_instance(self):
        """Verify get_role_manager returns a RoleManager instance."""
        manager = get_role_manager()
        assert isinstance(manager, RoleManager)

    def test_get_role_manager_returns_same_instance(self):
        """Verify get_role_manager returns the same instance on multiple calls."""
        manager1 = get_role_manager()
        manager2 = get_role_manager()
        assert manager1 is manager2

    def test_get_role_manager_creates_default_config(self):
        """Verify get_role_manager creates manager with default config."""
        manager = get_role_manager()
        assert manager.config.default_role == Role.VIEWER
        assert manager.config.assignments == []
        assert manager.config.admin_identifiers == []

    def test_configure_roles_sets_global_manager(self, basic_config):
        """Verify configure_roles sets the global role manager."""
        configure_roles(basic_config)
        manager = get_role_manager()
        assert manager.config == basic_config

    def test_configure_roles_replaces_existing_manager(self):
        """Verify configure_roles replaces any existing manager."""
        # First get the default manager
        default_manager = get_role_manager()

        # Configure with new config
        new_config = RoleConfig(default_role=Role.GUEST)
        configure_roles(new_config)

        # Get manager again - should be different
        new_manager = get_role_manager()
        assert new_manager is not default_manager
        assert new_manager.config.default_role == Role.GUEST

    def test_reset_role_manager_clears_global(self):
        """Verify reset_role_manager clears the global manager."""
        # Configure a manager
        config = RoleConfig(default_role=Role.ADMIN)
        configure_roles(config)
        manager1 = get_role_manager()

        # Reset
        reset_role_manager()

        # Get manager again - should be a new default instance
        manager2 = get_role_manager()
        assert manager2 is not manager1
        assert manager2.config.default_role == Role.VIEWER  # Back to default

    def test_reset_role_manager_allows_reconfiguration(self, basic_config):
        """Verify reset allows clean reconfiguration."""
        configure_roles(basic_config)
        reset_role_manager()

        # Can configure fresh
        new_config = RoleConfig(admin_identifiers=["new-admin"])
        configure_roles(new_config)

        manager = get_role_manager()
        assert manager.get_role_for_identifier("new-admin") == Role.ADMIN
        # Old config should not apply
        assert manager.get_role_for_identifier("admin") == Role.VIEWER


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for role_config module."""

    def test_full_workflow(self, yaml_config_path):
        """Test complete workflow: load YAML, configure, use global manager."""
        # Load from YAML
        manager = RoleManager.from_yaml(yaml_config_path)

        # Configure global
        configure_roles(manager.config)

        # Use global manager
        global_manager = get_role_manager()

        # Create subjects
        admin_subject = global_manager.create_subject("admin")
        editor_subject = global_manager.create_subject("editor-john")
        viewer_subject = global_manager.create_subject("regular-user")

        # Verify roles
        assert admin_subject.roles == {Role.ADMIN}
        assert editor_subject.roles == {Role.EDITOR}
        assert viewer_subject.roles == {Role.VIEWER}

    def test_pattern_priority_order(self):
        """Test that patterns are matched in declaration order."""
        config = RoleConfig(
            assignments=[
                RoleAssignment(pattern="admin-*", role=Role.ADMIN),
                RoleAssignment(pattern="admin-editor-*", role=Role.EDITOR),
            ]
        )
        manager = RoleManager(config)

        # "admin-editor-user" matches both patterns, but "admin-*" comes first
        assert manager.get_role_for_identifier("admin-editor-user") == Role.ADMIN

    def test_complex_pattern_matching(self):
        """Test various glob patterns work correctly."""
        config = RoleConfig(
            assignments=[
                RoleAssignment(pattern="user-[0-9]*", role=Role.VIEWER),
                RoleAssignment(pattern="service-??", role=Role.EDITOR),
                RoleAssignment(pattern="*@*.org", role=Role.ADMIN),
            ]
        )
        manager = RoleManager(config)

        # fnmatch patterns
        assert manager.get_role_for_identifier("user-123") == Role.VIEWER
        assert manager.get_role_for_identifier("service-ab") == Role.EDITOR
        assert manager.get_role_for_identifier("test@example.org") == Role.ADMIN

        # Non-matching
        assert manager.get_role_for_identifier("user-abc") == Role.VIEWER  # Default, not match
        assert manager.get_role_for_identifier("service-abc") == Role.VIEWER  # Too long for ??

    def test_subject_has_correct_permissions(self, manager_with_config):
        """Test that created subjects have expected permissions from their role."""
        from local_deepwiki.security.access_control import ROLE_PERMISSIONS, Permission

        admin_subject = manager_with_config.create_subject("admin")
        editor_subject = manager_with_config.create_subject("editor-1")
        viewer_subject = manager_with_config.create_subject("user")

        # Verify permissions match role
        assert admin_subject.has_permission(Permission.SYSTEM_ADMIN)
        assert editor_subject.has_permission(Permission.INDEX_WRITE)
        assert not viewer_subject.has_permission(Permission.INDEX_WRITE)
        assert viewer_subject.has_permission(Permission.QUERY_SEARCH)
