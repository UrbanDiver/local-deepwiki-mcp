"""In-process session state for the MCP server.

Tracks which repositories have been indexed during the current server
session so that tools like ``suggest_next_actions`` can give
context-aware suggestions without re-checking the filesystem.
"""

from __future__ import annotations

from typing import Any


_session_state: dict[str, Any] = {
    "indexed_repos": {},  # repo_path (str) -> wiki_path (str)
    "tool_call_count": 0,
    "last_tool": None,
}


def record_index(repo_path: str, wiki_path: str) -> None:
    """Record that a repository was successfully indexed.

    Args:
        repo_path: Absolute path to the repository.
        wiki_path: Absolute path to the generated wiki directory.
    """
    _session_state["indexed_repos"][repo_path] = wiki_path


def record_tool_call(tool_name: str) -> None:
    """Record that a tool was called during this session.

    Args:
        tool_name: Name of the tool that was invoked.
    """
    _session_state["tool_call_count"] += 1
    _session_state["last_tool"] = tool_name


def is_repo_indexed(repo_path: str) -> bool:
    """Check whether a repository was indexed in this session.

    Args:
        repo_path: Absolute path to the repository.

    Returns:
        True if the repo was indexed during this session.
    """
    return repo_path in _session_state["indexed_repos"]


def get_session_state() -> dict[str, Any]:
    """Return a snapshot of the current session state.

    Returns:
        Dict with ``indexed_repos``, ``tool_call_count``, and ``last_tool``.
    """
    return {
        "indexed_repos": dict(_session_state["indexed_repos"]),
        "tool_call_count": _session_state["tool_call_count"],
        "last_tool": _session_state["last_tool"],
    }
