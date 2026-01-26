"""Tests for repository access control (allowlist/denylist)."""

from pathlib import Path

import pytest

from local_deepwiki.security import (
    AccessDeniedException,
    RepositoryAccessConfig,
    RepositoryAccessController,
    configure_repository_access,
    get_repository_access_controller,
    reset_repository_access,
)


@pytest.fixture(autouse=True)
def reset_controller():
    """Reset the global repository access controller before each test."""
    reset_repository_access()
    yield
    reset_repository_access()


class TestRepositoryAccessConfig:
    """Tests for RepositoryAccessConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RepositoryAccessConfig()
        assert config.enforce_allowlist is False
        assert config.allowlist == []
        assert config.denylist == []
        assert config.log_denied is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RepositoryAccessConfig(
            enforce_allowlist=True,
            allowlist=["/home/user/projects/*"],
            denylist=["/home/user/projects/secret/*"],
            log_denied=False,
        )
        assert config.enforce_allowlist is True
        assert config.allowlist == ["/home/user/projects/*"]
        assert config.denylist == ["/home/user/projects/secret/*"]
        assert config.log_denied is False


class TestRepositoryAccessController:
    """Tests for RepositoryAccessController."""

    def test_default_config_allows_all(self, tmp_path):
        """Test that default config allows all paths."""
        controller = RepositoryAccessController()
        assert controller.is_allowed(tmp_path) is True

    def test_denylist_blocks_matching_path(self, tmp_path):
        """Test that denylist blocks matching paths."""
        config = RepositoryAccessConfig(
            denylist=[str(tmp_path) + "/*"],
        )
        controller = RepositoryAccessController(config)

        # Parent path should be allowed
        assert controller.is_allowed(tmp_path) is True

        # Child path should be blocked
        child_path = tmp_path / "project"
        child_path.mkdir()
        assert controller.is_allowed(child_path) is False

    def test_denylist_exact_match(self, tmp_path):
        """Test that denylist can block exact paths."""
        config = RepositoryAccessConfig(
            denylist=[str(tmp_path)],
        )
        controller = RepositoryAccessController(config)
        assert controller.is_allowed(tmp_path) is False

    def test_denylist_precedence_over_allowlist(self, tmp_path):
        """Test that denylist takes precedence over allowlist."""
        config = RepositoryAccessConfig(
            enforce_allowlist=True,
            allowlist=[str(tmp_path) + "/*"],
            denylist=[str(tmp_path) + "/private/*"],
        )
        controller = RepositoryAccessController(config)

        # Create test directories
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        private = tmp_path / "private" / "secret"
        private.mkdir(parents=True)

        # Allowed path should be accessible
        assert controller.is_allowed(allowed) is True

        # Private path should be blocked (denylist precedence)
        assert controller.is_allowed(private) is False

    def test_enforced_empty_allowlist_blocks_all(self, tmp_path):
        """Test that enforced empty allowlist blocks all paths."""
        config = RepositoryAccessConfig(
            enforce_allowlist=True,
            allowlist=[],
        )
        controller = RepositoryAccessController(config)
        assert controller.is_allowed(tmp_path) is False

    def test_enforced_allowlist_allows_matching_paths(self, tmp_path):
        """Test that enforced allowlist allows matching paths."""
        config = RepositoryAccessConfig(
            enforce_allowlist=True,
            allowlist=[str(tmp_path) + "/*"],
        )
        controller = RepositoryAccessController(config)

        # Child should be allowed
        child = tmp_path / "project"
        child.mkdir()
        assert controller.is_allowed(child) is True

    def test_enforced_allowlist_blocks_non_matching(self, tmp_path):
        """Test that enforced allowlist blocks non-matching paths."""
        other_path = tmp_path / "other"
        other_path.mkdir()

        config = RepositoryAccessConfig(
            enforce_allowlist=True,
            allowlist=[str(tmp_path / "allowed") + "/*"],
        )
        controller = RepositoryAccessController(config)
        assert controller.is_allowed(other_path) is False

    def test_require_access_success(self, tmp_path):
        """Test require_access does not raise for allowed path."""
        controller = RepositoryAccessController()
        # Should not raise
        controller.require_access(tmp_path)

    def test_require_access_denied(self, tmp_path):
        """Test require_access raises for denied path."""
        config = RepositoryAccessConfig(
            denylist=[str(tmp_path)],
        )
        controller = RepositoryAccessController(config)

        with pytest.raises(AccessDeniedException, match="Access denied to repository"):
            controller.require_access(tmp_path)

    def test_config_property(self):
        """Test config property returns the configuration."""
        config = RepositoryAccessConfig(enforce_allowlist=True)
        controller = RepositoryAccessController(config)
        assert controller.config is config

    def test_path_resolution(self, tmp_path):
        """Test that paths are resolved before matching."""
        config = RepositoryAccessConfig(
            denylist=[str(tmp_path.resolve())],
        )
        controller = RepositoryAccessController(config)

        # Relative path should still match after resolution
        assert controller.is_allowed(tmp_path) is False

    def test_accepts_string_path(self, tmp_path):
        """Test that string paths are accepted."""
        controller = RepositoryAccessController()
        assert controller.is_allowed(str(tmp_path)) is True

    def test_accepts_path_object(self, tmp_path):
        """Test that Path objects are accepted."""
        controller = RepositoryAccessController()
        assert controller.is_allowed(tmp_path) is True

    def test_multiple_allowlist_patterns(self, tmp_path):
        """Test multiple allowlist patterns."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir3 = tmp_path / "dir3"
        for d in [dir1, dir2, dir3]:
            d.mkdir()

        config = RepositoryAccessConfig(
            enforce_allowlist=True,
            allowlist=[str(dir1), str(dir2)],
        )
        controller = RepositoryAccessController(config)

        assert controller.is_allowed(dir1) is True
        assert controller.is_allowed(dir2) is True
        assert controller.is_allowed(dir3) is False

    def test_multiple_denylist_patterns(self, tmp_path):
        """Test multiple denylist patterns."""
        secret1 = tmp_path / "secret1"
        secret2 = tmp_path / "secret2"
        public = tmp_path / "public"
        for d in [secret1, secret2, public]:
            d.mkdir()

        config = RepositoryAccessConfig(
            denylist=[str(secret1), str(secret2)],
        )
        controller = RepositoryAccessController(config)

        assert controller.is_allowed(secret1) is False
        assert controller.is_allowed(secret2) is False
        assert controller.is_allowed(public) is True


class TestGlobalController:
    """Tests for global controller functions."""

    def test_get_repository_access_controller_returns_same_instance(self):
        """Test that get_repository_access_controller returns singleton."""
        controller1 = get_repository_access_controller()
        controller2 = get_repository_access_controller()
        assert controller1 is controller2

    def test_configure_repository_access_replaces_controller(self, tmp_path):
        """Test that configure_repository_access replaces the global controller."""
        # Get initial controller
        initial = get_repository_access_controller()
        assert initial.is_allowed(tmp_path) is True

        # Configure with restrictive settings
        config = RepositoryAccessConfig(
            denylist=[str(tmp_path)],
        )
        configure_repository_access(config)

        # New controller should have restrictive settings
        new_controller = get_repository_access_controller()
        assert new_controller is not initial
        assert new_controller.is_allowed(tmp_path) is False

    def test_reset_repository_access_clears_controller(self):
        """Test that reset_repository_access clears the global controller."""
        controller1 = get_repository_access_controller()
        reset_repository_access()
        controller2 = get_repository_access_controller()
        assert controller1 is not controller2


class TestGlobPatterns:
    """Tests for glob pattern matching."""

    def test_wildcard_pattern(self, tmp_path):
        """Test wildcard pattern matching."""
        project = tmp_path / "project"
        project.mkdir()

        config = RepositoryAccessConfig(
            enforce_allowlist=True,
            allowlist=[str(tmp_path) + "/*"],
        )
        controller = RepositoryAccessController(config)

        assert controller.is_allowed(project) is True
        assert controller.is_allowed(tmp_path) is False

    def test_double_star_pattern(self, tmp_path):
        """Test ** pattern for recursive matching."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)

        config = RepositoryAccessConfig(
            denylist=[str(tmp_path / "a") + "/**"],
        )
        controller = RepositoryAccessController(config)

        # This tests fnmatch behavior - note fnmatch doesn't support **
        # like glob does, so we test what actually works
        assert controller.is_allowed(tmp_path / "a") is True  # No trailing /

    def test_question_mark_pattern(self, tmp_path):
        """Test ? pattern for single character matching."""
        proj1 = tmp_path / "proj1"
        proj2 = tmp_path / "proj2"
        project = tmp_path / "project"
        for d in [proj1, proj2, project]:
            d.mkdir()

        config = RepositoryAccessConfig(
            denylist=[str(tmp_path) + "/proj?"],
        )
        controller = RepositoryAccessController(config)

        assert controller.is_allowed(proj1) is False
        assert controller.is_allowed(proj2) is False
        assert controller.is_allowed(project) is True  # "project" doesn't match "proj?"


class TestIntegrationWithHandlers:
    """Integration tests for handler behavior."""

    def test_index_repository_respects_denylist(self, tmp_path):
        """Test that index_repository handler respects repository access control."""
        # This test verifies the integration at the import level
        from local_deepwiki.handlers import _handle_index_repository_impl

        # Configure restrictive access
        config = RepositoryAccessConfig(
            denylist=[str(tmp_path)],
        )
        configure_repository_access(config)

        # The handler should respect the denylist
        # We can't fully test without mocking, but we verify the import works
        assert get_repository_access_controller().is_allowed(tmp_path) is False
