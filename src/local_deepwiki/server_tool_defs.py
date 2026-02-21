"""MCP tool definitions — re-export shim.

All definitions have moved to the ``tool_defs`` package.
This module re-exports everything for backward compatibility.
"""

from __future__ import annotations

from local_deepwiki.tool_defs import (  # noqa: F401
    TOOL_DEFINITIONS,
    _READ_ONLY,
    _SIDE_EFFECT,
    _STATEFUL,
    _WRITE_SAFE,
)
