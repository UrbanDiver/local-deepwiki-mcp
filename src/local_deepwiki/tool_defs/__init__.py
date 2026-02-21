"""MCP tool definitions for local-deepwiki.

This package contains the Tool objects returned by the server's list_tools handler.
Split into modules by tool group for maintainability.
"""

from __future__ import annotations

from mcp.types import Tool

from local_deepwiki.tool_defs.analysis import ANALYSIS_TOOLS
from local_deepwiki.tool_defs.annotations import (
    _READ_ONLY,
    _SIDE_EFFECT,
    _STATEFUL,
    _WRITE_SAFE,
)
from local_deepwiki.tool_defs.core import CORE_TOOLS
from local_deepwiki.tool_defs.generators import GENERATOR_TOOLS
from local_deepwiki.tool_defs.workflow import WORKFLOW_TOOLS

TOOL_DEFINITIONS: list[Tool] = (
    CORE_TOOLS + GENERATOR_TOOLS + ANALYSIS_TOOLS + WORKFLOW_TOOLS
)

__all__ = [
    "TOOL_DEFINITIONS",
    "CORE_TOOLS",
    "GENERATOR_TOOLS",
    "ANALYSIS_TOOLS",
    "WORKFLOW_TOOLS",
    "_READ_ONLY",
    "_WRITE_SAFE",
    "_STATEFUL",
    "_SIDE_EFFECT",
]
