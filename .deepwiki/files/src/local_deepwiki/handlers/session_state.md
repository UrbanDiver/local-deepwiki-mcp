# File: `src/local_deepwiki/handlers/session_state.py`

## File Overview

This module provides in-process session state management for the MCP server. It tracks which repositories have been indexed during the current server session, enabling context-aware tool behavior without repeatedly checking the filesystem. The session state is stored in a global `_session_state` dictionary and is updated through a set of utility functions.

## Key Concepts

The core abstraction in this file is a global session state dictionary (`_session_state`) that maintains:

1. **Indexed Repositories**: A mapping of repository paths to their corresponding wiki directory paths, allowing tools to quickly check if a repo has already been processed.
2. **Tool Call Tracking**: A count of tool invocations and the last tool called, which helps in providing contextual feedback or logging.

These concepts were chosen to support a lightweight, in-memory session tracking system that avoids the overhead of persistent storage while enabling efficient state queries for tools like `suggest_next_actions`.

## Integration

This module is part of the `src/local_deepwiki/handlers` package and is designed to be used by other modules in the same package. It imports `Any` from the `typing` module for type hinting and is closely related to:

- `src/local_deepwiki/handlers/types.py` (likely defines types used in session state)
- `src/local_deepwiki/generators/analysis/api_docs.py` (may use session state to avoid re-processing repos)
- `src/local_deepwiki/validation.py` (could rely on session state for validation logic)

The functions in this module are called by tools and handlers within the MCP server to update and query the session state, ensuring that expensive operations like repository indexing are not repeated unnecessarily.

## Design Notes

- **In-Memory State**: The session state is stored in a global variable (`_session_state`), which implies that it is reset on each server restart. This design choice prioritizes simplicity and performance over persistence.
- **Thread Safety**: No thread-safety mechanisms are implemented, which assumes that the MCP server operates in a single-threaded context or that concurrent access is managed externally.
- **State Snapshotting**: The `get_session_state` function returns a copy of the internal state to prevent accidental mutation from outside the module.
- **Tool Call Tracking**: The `record_tool_call` function updates both a count and the last tool name, enabling simple analytics or debugging without requiring complex state tracking.

The module is intentionally minimal and focused, avoiding features like state persistence or complex state transitions to keep the session management lightweight and predictable.

## API Reference

### Functions

#### `record_index`

```python
def record_index(repo_path: str, wiki_path: str) -> None
```

Record that a repository was successfully indexed.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `str` | - | Absolute path to the repository. |
| `wiki_path` | `str` | - | Absolute path to the generated wiki directory. |

**Returns:** `None`



<details>
<summary>View Source (lines 20-27) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/handlers/session_state.py#L20-L27">GitHub</a></summary>

```python
def record_index(repo_path: str, wiki_path: str) -> None:
    """Record that a repository was successfully indexed.

    Args:
        repo_path: Absolute path to the repository.
        wiki_path: Absolute path to the generated wiki directory.
    """
    _session_state["indexed_repos"][repo_path] = wiki_path
```

</details>

#### `record_tool_call`

```python
def record_tool_call(tool_name: str) -> None
```

Record that a tool was called during this session.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tool_name` | `str` | - | Name of the tool that was invoked. |

**Returns:** `None`



<details>
<summary>View Source (lines 30-37) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/handlers/session_state.py#L30-L37">GitHub</a></summary>

```python
def record_tool_call(tool_name: str) -> None:
    """Record that a tool was called during this session.

    Args:
        tool_name: Name of the tool that was invoked.
    """
    _session_state["tool_call_count"] += 1
    _session_state["last_tool"] = tool_name
```

</details>

#### `is_repo_indexed`

```python
def is_repo_indexed(repo_path: str) -> bool
```

Check whether a repository was indexed in this session.


| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `repo_path` | `str` | - | Absolute path to the repository. |

**Returns:** `bool`



<details>
<summary>View Source (lines 40-49) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/handlers/session_state.py#L40-L49">GitHub</a></summary>

```python
def is_repo_indexed(repo_path: str) -> bool:
    """Check whether a repository was indexed in this session.

    Args:
        repo_path: Absolute path to the repository.

    Returns:
        True if the repo was indexed during this session.
    """
    return repo_path in _session_state["indexed_repos"]
```

</details>

#### `get_session_state`

```python
def get_session_state() -> dict[str, Any]
```

Return a snapshot of the current session state.

**Returns:** `dict[str, Any]`




<details>
<summary>View Source (lines 52-62) | <a href="https://github.com/UrbanDiver/local-deepwiki-mcp/blob/main/src/local_deepwiki/handlers/session_state.py#L52-L62">GitHub</a></summary>

```python
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
```

</details>

## Last Modified

| Entity | Type | Author | Date | Commit |
|--------|------|--------|------|--------|
| `record_index` | function | Brian Breidenbach | Feb 14, 2026 | `2732638` feat: agent UX improvements... |
| `record_tool_call` | function | Brian Breidenbach | Feb 14, 2026 | `2732638` feat: agent UX improvements... |
| `is_repo_indexed` | function | Brian Breidenbach | Feb 14, 2026 | `2732638` feat: agent UX improvements... |
| `get_session_state` | function | Brian Breidenbach | Feb 14, 2026 | `2732638` feat: agent UX improvements... |

## Relevant Source Files

- `src/local_deepwiki/handlers/session_state.py:20-27`
