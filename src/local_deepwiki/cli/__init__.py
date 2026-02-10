"""CLI utilities for local-deepwiki."""

from local_deepwiki.cli.cache_cli import cmd_cleanup, cmd_clear, cmd_stats
from local_deepwiki.cli.config_cli import ConfigValidator, cmd_show, cmd_validate
from local_deepwiki.cli.interactive_search import (
    InteractiveSearch,
    SearchFilters,
    SearchState,
    run_search,
)
from local_deepwiki.cli.main import SUBCOMMANDS, show_help
from local_deepwiki.cli.profile_cli import (
    cmd_profile_delete,
    cmd_profile_list,
    cmd_profile_save,
    cmd_profile_use,
    dispatch_profile,
    register_profile_subparser,
)

__all__ = [
    # config_cli
    "ConfigValidator",
    "cmd_show",
    "cmd_validate",
    # interactive_search
    "InteractiveSearch",
    "SearchFilters",
    "SearchState",
    "run_search",
    # main dispatcher
    "SUBCOMMANDS",
    "show_help",
    # cache_cli
    "cmd_stats",
    "cmd_clear",
    "cmd_cleanup",
    # profile_cli
    "cmd_profile_save",
    "cmd_profile_use",
    "cmd_profile_list",
    "cmd_profile_delete",
    "dispatch_profile",
    "register_profile_subparser",
]
