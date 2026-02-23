"""Tool response formatting utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent


def wrap_tool_response(
    tool_name: str,
    data: dict[str, Any],
    *,
    hints: dict[str, Any] | None = None,
) -> str:
    """Wrap tool output in a structured JSON envelope.

    Merges ``tool`` (and optionally ``hints``) into the data dict so that
    existing fields like ``status``, ``message``, etc. remain at the top
    level for backward-compatible parsing.

    Args:
        tool_name: Name of the tool that produced this response.
        data: The tool's result payload.
        hints: Optional follow-up suggestions for agents.

    Returns:
        JSON string with standard envelope.
    """
    envelope: dict[str, Any] = {**data, "tool": tool_name}
    if "status" not in envelope:
        envelope["status"] = "success"
    if hints is not None:
        envelope["hints"] = hints
    return json.dumps(envelope, indent=2)


def make_tool_text_content(
    tool_name: str,
    data: dict[str, Any],
    *,
    hints: dict[str, Any] | None = None,
) -> list[TextContent]:
    """Produce a list[TextContent] wrapped in a standard JSON envelope.

    Convenience wrapper combining ``wrap_tool_response`` with the
    ``TextContent`` construction that every handler needs.

    Args:
        tool_name: Name of the tool that produced this response.
        data: The tool's result payload.
        hints: Optional follow-up suggestions for agents.

    Returns:
        Single-element list of TextContent with the JSON envelope.
    """
    return [
        TextContent(type="text", text=wrap_tool_response(tool_name, data, hints=hints))
    ]


def build_wiki_resource_uri(wiki_path: Path, page_relative: str) -> str:
    """Build a deepwiki:// resource URI for a wiki page.

    Args:
        wiki_path: Absolute path to the wiki directory.
        page_relative: Page path relative to wiki root.

    Returns:
        URI string like 'deepwiki:///path/to/.deepwiki/index.md'.
    """
    return f"deepwiki://{wiki_path}/{page_relative}"
