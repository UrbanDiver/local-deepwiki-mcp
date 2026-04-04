"""Bug pattern detection using tree-sitter AST analysis.

Detects common bug patterns via static AST analysis:
- Mutable default arguments (list, dict, set literals/calls)
- Bare except clauses (catch-all without exception type)
- Comparison to None with == or != (should use is/is not)
- f-strings with no interpolation (unnecessary f-prefix)
- Unreachable code after return/raise statements

No LLM or external service calls — pure AST analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable, TypedDict

if TYPE_CHECKING:
    from tree_sitter import Node


# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------
class BugConfidence(str, Enum):
    """Confidence level for a detected bug pattern."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


CONFIDENCE_ORDER: dict[BugConfidence, int] = {
    BugConfidence.LOW: 0,
    BugConfidence.MEDIUM: 1,
    BugConfidence.HIGH: 2,
}


# ---------------------------------------------------------------------------
# Finding types
# ---------------------------------------------------------------------------
class BugFinding(TypedDict):
    """A single bug pattern match."""

    pattern: str
    file: str
    line: int
    confidence: str
    message: str
    snippet: str


class EnrichedBugFinding(BugFinding):
    """Bug finding enriched with LLM verification."""

    verified: bool
    explanation: str
    suggestion: str


# ---------------------------------------------------------------------------
# BugPattern dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class BugPattern:
    """Definition of a detectable bug pattern."""

    name: str
    description: str
    languages: frozenset[str]
    confidence: BugConfidence
    detect: Callable[[Node, bytes], list[BugFinding]]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _node_text(node: Node, src_bytes: bytes) -> str:
    """Extract the text content of an AST node."""
    return src_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _snippet(node: Node, src_bytes: bytes, context_lines: int = 2) -> str:
    """Extract surrounding source lines for a node.

    Returns up to *context_lines* lines before and after the node's
    start line, providing context for the finding.
    """
    lines = src_bytes.decode("utf-8", errors="replace").splitlines()
    start = max(0, node.start_point[0] - context_lines)
    end = min(len(lines), node.start_point[0] + context_lines + 1)
    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# Tree walker
# ---------------------------------------------------------------------------
def _walk(node: Node) -> list[Node]:
    """Collect all descendant nodes via depth-first traversal."""
    result: list[Node] = []

    def _visit(n: Node) -> None:
        result.append(n)
        for child in n.children:
            _visit(child)

    _visit(node)
    return result


# ---------------------------------------------------------------------------
# Detector: mutable default arguments
# ---------------------------------------------------------------------------
_MUTABLE_LITERAL_TYPES = frozenset({"list", "dictionary", "set"})
_MUTABLE_CALL_NAMES = frozenset({"list", "dict", "set"})


def _detect_mutable_defaults(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect mutable default argument values in function definitions.

    Flags ``list``, ``dict``, and ``set`` literals (``[]``, ``{}``,
    ``{1,2}``) as well as ``list()``, ``dict()``, and ``set()`` calls
    used as parameter defaults.
    """
    findings: list[BugFinding] = []
    for child in _walk(node):
        if child.type != "default_parameter":
            continue
        # The value is the last named child (after `=`)
        value = child.child_by_field_name("value")
        if value is None:
            # Fallback: pick the child after the `=` sign
            for i, c in enumerate(child.children):
                if c.type == "=":
                    value = (
                        child.children[i + 1] if i + 1 < len(child.children) else None
                    )
                    break
        if value is None:
            continue

        is_mutable = False
        if value.type in _MUTABLE_LITERAL_TYPES:
            is_mutable = True
        elif value.type == "call":
            func_node = value.children[0] if value.children else None
            if (
                func_node is not None
                and _node_text(func_node, src_bytes) in _MUTABLE_CALL_NAMES
            ):
                is_mutable = True

        if is_mutable:
            param_name = ""
            name_node = child.child_by_field_name("name")
            if name_node is not None:
                param_name = _node_text(name_node, src_bytes)

            findings.append(
                BugFinding(
                    pattern="mutable-default-argument",
                    file="",
                    line=child.start_point[0] + 1,
                    confidence=BugConfidence.HIGH.value,
                    message=f"Mutable default argument '{param_name}={_node_text(value, src_bytes)}' — shared across calls",
                    snippet=_snippet(child, src_bytes),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Detector: bare except
# ---------------------------------------------------------------------------
def _detect_bare_except(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect bare ``except:`` clauses with no exception type.

    A bare except catches *all* exceptions including ``KeyboardInterrupt``
    and ``SystemExit``, which is almost never the intended behaviour.
    """
    findings: list[BugFinding] = []
    for child in _walk(node):
        if child.type != "except_clause":
            continue
        # A bare except has no identifier/type between 'except' and ':'
        has_type = False
        for c in child.children:
            if c.type not in ("except", ":", "block", "comment"):
                has_type = True
                break
        if not has_type:
            findings.append(
                BugFinding(
                    pattern="bare-except",
                    file="",
                    line=child.start_point[0] + 1,
                    confidence=BugConfidence.HIGH.value,
                    message="Bare 'except:' catches all exceptions including KeyboardInterrupt and SystemExit",
                    snippet=_snippet(child, src_bytes),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Detector: comparison to None
# ---------------------------------------------------------------------------
def _detect_comparison_to_none(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect ``== None`` or ``!= None`` comparisons.

    PEP 8 requires ``is None`` / ``is not None`` for singleton checks.
    Using ``==`` or ``!=`` can be overridden by ``__eq__`` and give
    surprising results.
    """
    findings: list[BugFinding] = []
    for child in _walk(node):
        if child.type != "comparison_operator":
            continue
        children = child.children
        has_none = any(c.type == "none" for c in children)
        if not has_none:
            continue
        has_eq_neq = any(c.type in ("==", "!=") for c in children)
        if has_eq_neq:
            findings.append(
                BugFinding(
                    pattern="comparison-to-none",
                    file="",
                    line=child.start_point[0] + 1,
                    confidence=BugConfidence.HIGH.value,
                    message=f"Use 'is None' or 'is not None' instead of '{_node_text(child, src_bytes)}'",
                    snippet=_snippet(child, src_bytes),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Detector: f-string with no expression
# ---------------------------------------------------------------------------
def _detect_fstring_no_expression(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect f-strings that contain no interpolation expressions.

    An f-string without ``{}`` placeholders is identical to a regular
    string and the ``f`` prefix is unnecessary noise.
    """
    findings: list[BugFinding] = []
    for child in _walk(node):
        if child.type != "string":
            continue
        # Check if this is an f-string by looking at string_start
        start_node = None
        for c in child.children:
            if c.type == "string_start":
                start_node = c
                break
        if start_node is None:
            continue
        start_text = _node_text(start_node, src_bytes).lower()
        if not start_text.startswith("f"):
            continue
        # Check for interpolation children
        has_interpolation = any(c.type == "interpolation" for c in child.children)
        if not has_interpolation:
            findings.append(
                BugFinding(
                    pattern="f-string-no-expression",
                    file="",
                    line=child.start_point[0] + 1,
                    confidence=BugConfidence.HIGH.value,
                    message=f"f-string has no interpolation: {_node_text(child, src_bytes)!r}",
                    snippet=_snippet(child, src_bytes),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Detector: unreachable code
# ---------------------------------------------------------------------------
_TERMINAL_TYPES = frozenset({"return_statement", "raise_statement"})


def _detect_unreachable_code(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect statements after ``return`` or ``raise`` in the same block.

    Any statement following an unconditional ``return`` or ``raise``
    within the same block is unreachable dead code.
    """
    findings: list[BugFinding] = []
    for child in _walk(node):
        if child.type != "block":
            continue
        stmts = child.named_children
        for i, stmt in enumerate(stmts):
            if stmt.type in _TERMINAL_TYPES and i + 1 < len(stmts):
                unreachable = stmts[i + 1]
                findings.append(
                    BugFinding(
                        pattern="unreachable-code",
                        file="",
                        line=unreachable.start_point[0] + 1,
                        confidence=BugConfidence.HIGH.value,
                        message=f"Unreachable code after '{stmt.type.replace('_', ' ')}'",
                        snippet=_snippet(unreachable, src_bytes),
                    )
                )
                # Only report the first unreachable statement per block
                break
    return findings


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------
PATTERNS: list[BugPattern] = [
    BugPattern(
        name="mutable-default-argument",
        description="Mutable default argument shared across function calls",
        languages=frozenset({"python"}),
        confidence=BugConfidence.HIGH,
        detect=_detect_mutable_defaults,
    ),
    BugPattern(
        name="bare-except",
        description="Bare except clause catches all exceptions including SystemExit",
        languages=frozenset({"python"}),
        confidence=BugConfidence.HIGH,
        detect=_detect_bare_except,
    ),
    BugPattern(
        name="comparison-to-none",
        description="Comparison to None using == or != instead of is/is not",
        languages=frozenset({"python"}),
        confidence=BugConfidence.HIGH,
        detect=_detect_comparison_to_none,
    ),
    BugPattern(
        name="f-string-no-expression",
        description="f-string contains no interpolation expressions",
        languages=frozenset({"python"}),
        confidence=BugConfidence.HIGH,
        detect=_detect_fstring_no_expression,
    ),
    BugPattern(
        name="unreachable-code",
        description="Code after return or raise is unreachable",
        languages=frozenset({"python"}),
        confidence=BugConfidence.HIGH,
        detect=_detect_unreachable_code,
    ),
]
