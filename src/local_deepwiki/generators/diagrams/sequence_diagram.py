"""Sequence diagram generation using Mermaid."""

from __future__ import annotations

from ._utils import sanitize_mermaid_name


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

    # Find entry point if not specified
    if not entry_point:
        # Find function with most outgoing calls
        entry_point = max(
            call_graph.keys(), key=lambda k: len(call_graph.get(k, [])), default=None
        )

    if not entry_point or entry_point not in call_graph:
        return None

    # Build sequence
    lines = ["```mermaid", "sequenceDiagram"]

    # Collect participants
    participants: set[str] = {entry_point}

    def collect_participants(func: str, depth: int) -> None:
        if depth > max_depth:
            return
        for callee in call_graph.get(func, []):
            participants.add(callee)
            collect_participants(callee, depth + 1)

    collect_participants(entry_point, 0)

    # Add participants
    for p in sorted(participants):
        safe_name = sanitize_mermaid_name(p)
        display = p.split(".")[-1] if "." in p else p
        lines.append(f"    participant {safe_name} as {display}")

    # Add calls
    visited: set[tuple[str, str]] = set()

    def add_calls(caller: str, depth: int) -> None:
        if depth > max_depth:
            return
        safe_caller = sanitize_mermaid_name(caller)
        for callee in call_graph.get(caller, []):
            if (caller, callee) in visited:
                continue
            visited.add((caller, callee))

            safe_callee = sanitize_mermaid_name(callee)
            lines.append(f"    {safe_caller}->>+{safe_callee}: call")

            # Recurse
            if callee in call_graph:
                add_calls(callee, depth + 1)

            lines.append(f"    {safe_callee}-->>-{safe_caller}: return")

    add_calls(entry_point, 0)

    if len(lines) <= 3:  # Only header and participants
        return None

    lines.append("```")

    return "\n".join(lines)
