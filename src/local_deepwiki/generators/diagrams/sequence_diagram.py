"""Sequence diagram generation using Mermaid."""

from __future__ import annotations

from ._utils import sanitize_mermaid_name


def _collect_all_participants(
    call_graph: dict[str, list[str]],
    entry_point: str,
    max_depth: int,
) -> set[str]:
    """Collect all functions reachable from *entry_point* up to *max_depth*."""
    participants: set[str] = {entry_point}

    def _recurse(func: str, depth: int) -> None:
        if depth > max_depth:
            return
        for callee in call_graph.get(func, []):
            participants.add(callee)
            _recurse(callee, depth + 1)

    _recurse(entry_point, 0)
    return participants


def _emit_call_arrows(
    call_graph: dict[str, list[str]],
    entry_point: str,
    max_depth: int,
    lines: list[str],
) -> None:
    """Recursively emit Mermaid call/return arrows starting from *entry_point*."""
    visited: set[tuple[str, str]] = set()

    def _recurse(caller: str, depth: int) -> None:
        if depth > max_depth:
            return
        safe_caller = sanitize_mermaid_name(caller)
        for callee in call_graph.get(caller, []):
            if (caller, callee) in visited:
                continue
            visited.add((caller, callee))
            safe_callee = sanitize_mermaid_name(callee)
            lines.append(f"    {safe_caller}->>+{safe_callee}: call")
            if callee in call_graph:
                _recurse(callee, depth + 1)
            lines.append(f"    {safe_callee}-->>-{safe_caller}: return")

    _recurse(entry_point, 0)


def generate_sequence_diagram(
    call_graph: dict[str, list[str]],
    entry_point: str | None = None,
    max_depth: int = 5,
) -> str | None:
    """Generate a sequence diagram from a call graph.

    Shows the sequence of calls starting from an entry point.

    Args:
        call_graph: Mapping of caller to list of callees.
        entry_point: Starting function (if None, uses most-called function).
        max_depth: Maximum call depth to show.

    Returns:
        Mermaid sequence diagram string, or None if empty.
    """
    if not call_graph:
        return None

    if not entry_point:
        entry_point = max(
            call_graph.keys(), key=lambda k: len(call_graph.get(k, [])), default=None
        )

    if not entry_point or entry_point not in call_graph:
        return None

    lines = ["```mermaid", "sequenceDiagram"]

    participants = _collect_all_participants(call_graph, entry_point, max_depth)
    for p in sorted(participants):
        safe_name = sanitize_mermaid_name(p)
        display = p.split(".")[-1] if "." in p else p
        lines.append(f"    participant {safe_name} as {display}")

    _emit_call_arrows(call_graph, entry_point, max_depth, lines)

    if len(lines) <= 3:  # Only header and participants — no actual calls
        return None

    lines.append("```")
    return "\n".join(lines)
