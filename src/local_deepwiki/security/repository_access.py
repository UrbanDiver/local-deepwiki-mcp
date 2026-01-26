"""Repository access control for allowlist/denylist.

This module provides the ability to restrict which repositories can be indexed
using configurable allowlist and denylist patterns.
"""

import fnmatch
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from local_deepwiki.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RepositoryAccessConfig:
    """Configuration for repository access control.

    Attributes:
        enforce_allowlist: If True, only repos matching allowlist patterns can be indexed.
        allowlist: Glob patterns for allowed repositories (e.g., "/home/user/projects/*").
        denylist: Glob patterns for denied repositories (checked before allowlist).
        log_denied: If True, log denied access attempts.
    """

    enforce_allowlist: bool = False
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    log_denied: bool = True


class RepositoryAccessController:
    """Controls which repositories can be indexed.

    This controller implements a deny-first access control model:
    1. Check denylist first - deny takes precedence
    2. If allowlist is not enforced, allow all non-denied paths
    3. If allowlist is enforced and empty, deny all paths
    4. If allowlist is enforced, check if path matches any allowlist pattern

    Example usage:
        config = RepositoryAccessConfig(
            enforce_allowlist=True,
            allowlist=["/home/user/projects/*", "/opt/repos/*"],
            denylist=["/home/user/projects/private/*"],
        )
        controller = RepositoryAccessController(config)

        if controller.is_allowed("/home/user/projects/my-app"):
            # Safe to index
            pass
    """

    def __init__(self, config: Optional[RepositoryAccessConfig] = None):
        """Initialize the repository access controller.

        Args:
            config: Repository access configuration. If None, uses permissive defaults.
        """
        self._config = config or RepositoryAccessConfig()

    def is_allowed(self, repo_path: str | Path) -> bool:
        """Check if repository path is allowed for indexing.

        Args:
            repo_path: Path to the repository to check.

        Returns:
            True if the repository is allowed for indexing, False otherwise.
        """
        resolved = Path(repo_path).resolve()
        path_str = str(resolved)

        # Check denylist first (deny takes precedence)
        for pattern in self._config.denylist:
            if fnmatch.fnmatch(path_str, pattern):
                if self._config.log_denied:
                    logger.warning(
                        f"Repository access denied (denylist match): {path_str} "
                        f"matches pattern '{pattern}'"
                    )
                return False

        # If allowlist is not enforced, allow all non-denied
        if not self._config.enforce_allowlist:
            return True

        # If allowlist is empty and enforced, deny all
        if not self._config.allowlist:
            if self._config.log_denied:
                logger.warning(f"Repository access denied (empty allowlist): {path_str}")
            return False

        # Check allowlist
        for pattern in self._config.allowlist:
            if fnmatch.fnmatch(path_str, pattern):
                return True

        # No allowlist match
        if self._config.log_denied:
            logger.warning(f"Repository access denied (no allowlist match): {path_str}")
        return False

    def require_access(self, repo_path: str | Path) -> None:
        """Require access to repository, raising if denied.

        Args:
            repo_path: Path to the repository to check.

        Raises:
            AccessDeniedException: If access to the repository is denied.
        """
        if not self.is_allowed(repo_path):
            from local_deepwiki.security.access_control import AccessDeniedException

            raise AccessDeniedException(f"Access denied to repository: {repo_path}")

    @property
    def config(self) -> RepositoryAccessConfig:
        """Get the current configuration.

        Returns:
            The RepositoryAccessConfig instance.
        """
        return self._config


# Thread-safe global instance management
_repo_access_controller: Optional[RepositoryAccessController] = None
_repo_access_controller_lock = threading.Lock()


def get_repository_access_controller() -> RepositoryAccessController:
    """Get the global repository access controller instance (thread-safe).

    Returns:
        The global RepositoryAccessController instance.
    """
    global _repo_access_controller
    if _repo_access_controller is None:
        with _repo_access_controller_lock:
            # Double-check locking pattern
            if _repo_access_controller is None:
                _repo_access_controller = RepositoryAccessController()
    return _repo_access_controller


def configure_repository_access(config: RepositoryAccessConfig) -> None:
    """Configure the global repository access controller.

    Args:
        config: The RepositoryAccessConfig to use.
    """
    global _repo_access_controller
    with _repo_access_controller_lock:
        _repo_access_controller = RepositoryAccessController(config)


def reset_repository_access() -> None:
    """Reset the global repository access controller (for testing only).

    This clears the global instance, allowing a fresh controller
    to be created on the next call to get_repository_access_controller().
    """
    global _repo_access_controller
    with _repo_access_controller_lock:
        _repo_access_controller = None
