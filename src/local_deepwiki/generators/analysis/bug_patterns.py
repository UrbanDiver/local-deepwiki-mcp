"""Bug pattern detection using tree-sitter AST analysis.

Detects common bug patterns via static AST analysis:
- Mutable default arguments (list, dict, set literals/calls)
- Bare except clauses (catch-all without exception type)
- Comparison to None with == or != (should use is/is not)
- f-strings with no interpolation (unnecessary f-prefix)
- Unreachable code after return/raise statements
- Unused variables assigned but never read
- Exception bound with ``as`` but never referenced in handler
- Missing ``await`` on calls to locally-defined async functions
- Variable shadowed by ``for`` loop iteration variable

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
# Detector: unused variable
# ---------------------------------------------------------------------------
_UNUSED_VAR_SKIP = frozenset({"self", "cls"})


def _detect_unused_variable(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect variables assigned but never read within a function.

    Collects assignment targets (``=`` and ``+=`` etc.), then checks
    whether each name appears as an ``identifier`` outside of an
    assignment target position.  Names starting with ``_`` and
    ``self``/``cls`` are ignored by convention.
    """
    findings: list[BugFinding] = []
    all_nodes = _walk(node)

    # Collect assignment target names and their nodes
    assign_targets: dict[str, Node] = {}
    assign_target_ids: set[int] = set()
    for n in all_nodes:
        if n.type in ("assignment", "augmented_assignment"):
            left = n.children[0] if n.children else None
            if left is not None and left.type == "identifier":
                name = _node_text(left, src_bytes)
                if name not in _UNUSED_VAR_SKIP and not name.startswith("_"):
                    assign_targets[name] = left
                    assign_target_ids.add(id(left))

    # Collect all identifier usages that are NOT assignment targets
    used_names: set[str] = set()
    for n in all_nodes:
        if n.type == "identifier" and id(n) not in assign_target_ids:
            used_names.add(_node_text(n, src_bytes))

    for name, target_node in assign_targets.items():
        if name not in used_names:
            findings.append(
                BugFinding(
                    pattern="unused-variable",
                    file="",
                    line=target_node.start_point[0] + 1,
                    confidence=BugConfidence.MEDIUM.value,
                    message=f"Variable '{name}' is assigned but never used",
                    snippet=_snippet(target_node, src_bytes),
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Detector: exception not used
# ---------------------------------------------------------------------------
def _detect_exception_not_used(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect ``except ... as e`` where *e* is never referenced in the handler.

    Catches the pattern where an exception is bound via ``as`` but the
    bound name never appears in the except block body, suggesting the
    exception is silently swallowed.
    """
    findings: list[BugFinding] = []
    for child in _walk(node):
        if child.type != "except_clause":
            continue

        # Find as_pattern within the except_clause children
        as_pattern = None
        block_node = None
        for c in child.children:
            if c.type == "as_pattern":
                as_pattern = c
            elif c.type == "block":
                block_node = c

        if as_pattern is None or block_node is None:
            continue

        # Extract the bound variable name from as_pattern_target
        bound_name = None
        for c in as_pattern.children:
            if c.type == "as_pattern_target":
                for cc in c.children:
                    if cc.type == "identifier":
                        bound_name = _node_text(cc, src_bytes)
                        break
                break

        if bound_name is None:
            continue

        # Check if the bound name appears in the block body
        block_identifiers = [
            _node_text(n, src_bytes)
            for n in _walk(block_node)
            if n.type == "identifier"
        ]

        if bound_name not in block_identifiers:
            findings.append(
                BugFinding(
                    pattern="exception-not-used",
                    file="",
                    line=child.start_point[0] + 1,
                    confidence=BugConfidence.MEDIUM.value,
                    message=f"Exception bound as '{bound_name}' is caught but never used in handler",
                    snippet=_snippet(child, src_bytes),
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Detector: missing await
# ---------------------------------------------------------------------------
def _detect_missing_await(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect calls to locally-defined async functions without ``await``.

    Only fires inside ``async def`` bodies.  Collects names of
    ``async def`` children defined in the same function scope, then
    checks whether calls to those names have an ``await`` ancestor.
    This is a heuristic — it cannot track async functions imported
    from elsewhere.
    """
    findings: list[BugFinding] = []

    # Only applies to async functions
    node_text = _node_text(node, src_bytes)
    if not node_text.startswith("async"):
        return findings

    all_nodes = _walk(node)

    # Collect names of async def functions defined within this scope
    async_func_names: set[str] = set()
    for n in all_nodes:
        if n.type == "function_definition" and n is not node:
            has_async = any(c.type == "async" for c in n.children)
            if has_async:
                name_node = None
                for c in n.children:
                    if c.type == "identifier":
                        name_node = c
                        break
                if name_node is not None:
                    async_func_names.add(_node_text(name_node, src_bytes))

    if not async_func_names:
        return findings

    # Check each call node
    for n in all_nodes:
        if n.type != "call":
            continue

        # Get the callee name
        callee = n.children[0] if n.children else None
        if callee is None or callee.type != "identifier":
            continue

        callee_name = _node_text(callee, src_bytes)
        if callee_name not in async_func_names:
            continue

        # Check if any ancestor is an 'await' node
        has_await = False
        parent = n.parent
        while parent is not None and parent is not node:
            if parent.type == "await":
                has_await = True
                break
            parent = parent.parent

        if not has_await:
            findings.append(
                BugFinding(
                    pattern="missing-await",
                    file="",
                    line=n.start_point[0] + 1,
                    confidence=BugConfidence.MEDIUM.value,
                    message=f"Call to async function '{callee_name}()' without 'await'",
                    snippet=_snippet(n, src_bytes),
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Detector: shadowed variable
# ---------------------------------------------------------------------------
_SHADOW_SKIP_NAMES = frozenset({"i", "j", "k"})


def _detect_shadowed_variable(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect variables shadowed by ``for`` loop iteration variables.

    Finds names assigned at the function's direct block level that are
    then reused as a ``for`` loop variable, which silently overwrites
    the original value.  Skips ``_``-prefixed names and common loop
    counters (``i``, ``j``, ``k``).
    """
    findings: list[BugFinding] = []

    # Find the function's direct block
    block_node = None
    for c in node.children:
        if c.type == "block":
            block_node = c
            break

    if block_node is None:
        return findings

    # Collect variable names assigned at the direct block level
    outer_vars: dict[str, Node] = {}
    for stmt in block_node.named_children:
        if stmt.type == "expression_statement":
            for c in stmt.children:
                if c.type == "assignment":
                    left = c.children[0] if c.children else None
                    if left is not None and left.type == "identifier":
                        name = _node_text(left, src_bytes)
                        if name not in _SHADOW_SKIP_NAMES and not name.startswith("_"):
                            outer_vars[name] = left

    if not outer_vars:
        return findings

    # Check for_statement iteration variables that shadow outer vars
    for child in _walk(block_node):
        if child.type != "for_statement":
            continue

        # The loop variable is the identifier directly after 'for'
        loop_var = None
        for c in child.children:
            if c.type == "identifier":
                loop_var = c
                break

        if loop_var is None:
            continue

        loop_var_name = _node_text(loop_var, src_bytes)
        if loop_var_name in outer_vars:
            findings.append(
                BugFinding(
                    pattern="shadowed-variable",
                    file="",
                    line=loop_var.start_point[0] + 1,
                    confidence=BugConfidence.MEDIUM.value,
                    message=f"Loop variable '{loop_var_name}' shadows variable assigned at line {outer_vars[loop_var_name].start_point[0] + 1}",
                    snippet=_snippet(child, src_bytes),
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Detector: empty catch block (cross-language)
# ---------------------------------------------------------------------------
def _detect_empty_catch(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect empty catch blocks in JS/TS/Java/C#/Kotlin.

    A ``catch`` clause whose body (``statement_block``) contains no
    statement children silently swallows exceptions — almost always a bug.
    """
    findings: list[BugFinding] = []
    for child in _walk(node):
        if child.type != "catch_clause":
            continue
        # Find the body block (statement_block or block)
        body = None
        for c in child.children:
            if c.type in ("statement_block", "block"):
                body = c
                break
        if body is None:
            continue
        # Empty if no named children (only braces)
        if len(body.named_children) == 0:
            findings.append(
                BugFinding(
                    pattern="empty-catch-block",
                    file="",
                    line=child.start_point[0] + 1,
                    confidence=BugConfidence.HIGH.value,
                    message="Empty catch block silently swallows exceptions",
                    snippet=_snippet(child, src_bytes),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Detector: missing break in switch (cross-language)
# ---------------------------------------------------------------------------
_SWITCH_TERMINAL_TYPES = frozenset(
    {
        "break_statement",
        "return_statement",
        "continue_statement",
        "throw_statement",
        "goto_statement",
    }
)


def _detect_missing_break_in_switch(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect switch case clauses that fall through without break/return.

    Iterates ``case_statement`` nodes inside ``switch_statement`` bodies.
    A case "falls through" when it has statements but does not end with
    ``break``, ``return``, ``continue``, ``throw``, or ``goto``.  The
    last case in the switch is skipped (fall-through at end is harmless),
    and cases with no statements are skipped (intentional grouping).
    """
    findings: list[BugFinding] = []
    for child in _walk(node):
        if child.type != "switch_statement":
            continue
        # Collect case_statement children from the switch body
        body = None
        for c in child.children:
            if c.type in ("compound_statement", "switch_body"):
                body = c
                break
        if body is None:
            continue

        cases = [
            c for c in body.children if c.type in ("case_statement", "switch_case")
        ]
        if len(cases) <= 1:
            continue

        # Check all cases except the last
        for case in cases[:-1]:
            # Collect statement children (skip case/default keyword, value, colon)
            stmts = [
                c
                for c in case.named_children
                if c.type
                not in (
                    "case",
                    "default",
                    "number_literal",
                    "char_literal",
                    "string_literal",
                    "identifier",
                    "qualified_identifier",
                    "scope_resolution",
                    "field_expression",
                )
            ]
            if not stmts:
                # No statements — intentional grouping (case 1: case 2: ...)
                continue
            # Check if last statement is a terminal
            last_stmt = stmts[-1]
            if last_stmt.type in _SWITCH_TERMINAL_TYPES:
                continue
            # Also check recursively — the terminal might be nested (e.g. in a block)
            last_descendants = _walk(last_stmt)
            has_terminal = any(
                n.type in _SWITCH_TERMINAL_TYPES for n in last_descendants
            )
            if has_terminal:
                continue

            findings.append(
                BugFinding(
                    pattern="missing-break-in-switch",
                    file="",
                    line=case.start_point[0] + 1,
                    confidence=BugConfidence.HIGH.value,
                    message="Switch case falls through without break/return",
                    snippet=_snippet(case, src_bytes),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Detector: redundant condition (cross-language)
# ---------------------------------------------------------------------------
def _get_condition_text(if_node: Node, src_bytes: bytes) -> str:
    """Extract the condition text from an if_statement node.

    Handles both Python-style (``condition`` field) and C/JS-style
    (``parenthesized_expression`` child) ASTs.
    """
    cond = if_node.child_by_field_name("condition")
    if cond is not None:
        # JS/C: condition is a parenthesized_expression — unwrap it
        if cond.type == "parenthesized_expression" and cond.named_children:
            return _node_text(cond.named_children[0], src_bytes)
        return _node_text(cond, src_bytes)
    # Fallback: second child (after 'if' keyword) for Python
    children = if_node.children
    if len(children) >= 2:
        return _node_text(children[1], src_bytes)
    return ""


def _detect_redundant_condition(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect nested ``if`` statements that check the exact same condition.

    When an inner ``if`` duplicates the condition of an outer ``if``,
    the inner check is redundant (the condition is already known to be
    truthy at that point).
    """
    findings: list[BugFinding] = []

    def _check_nested(outer: Node, outer_cond_text: str) -> None:
        """Recurse into *outer*'s body looking for redundant inner ifs."""
        for descendant in _walk(outer):
            if descendant is outer:
                continue
            if descendant.type != "if_statement":
                continue
            inner_cond_text = _get_condition_text(descendant, src_bytes)
            if inner_cond_text and inner_cond_text == outer_cond_text:
                findings.append(
                    BugFinding(
                        pattern="redundant-condition",
                        file="",
                        line=descendant.start_point[0] + 1,
                        confidence=BugConfidence.MEDIUM.value,
                        message=f"Redundant condition '{inner_cond_text}' already checked by outer if",
                        snippet=_snippet(descendant, src_bytes),
                    )
                )

    for child in _walk(node):
        if child.type == "if_statement":
            cond_text = _get_condition_text(child, src_bytes)
            if cond_text:
                _check_nested(child, cond_text)

    return findings


# ---------------------------------------------------------------------------
# Detector: reraised without chain (Python)
# ---------------------------------------------------------------------------
def _detect_reraised_without_chain(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect ``raise NewException(...)`` without ``from`` inside except blocks.

    When catching one exception and raising another, PEP 3134 requires
    chaining via ``raise X from Y`` to preserve the original traceback.
    Bare ``raise`` (re-raise) is fine — only new exception instantiations
    without ``from`` are flagged.
    """
    findings: list[BugFinding] = []
    for child in _walk(node):
        if child.type != "except_clause":
            continue
        # Walk inside the except clause for raise_statement nodes
        for descendant in _walk(child):
            if descendant.type != "raise_statement":
                continue
            children = descendant.children
            # Bare raise (just `raise`) has only the keyword — skip
            has_argument = any(c.is_named for c in children)
            if not has_argument:
                continue
            # Check for `from` keyword child
            has_from = any(c.type == "from" for c in children)
            if not has_from:
                findings.append(
                    BugFinding(
                        pattern="reraised-without-chain",
                        file="",
                        line=descendant.start_point[0] + 1,
                        confidence=BugConfidence.MEDIUM.value,
                        message="Exception raised without 'from' — original traceback will be lost",
                        snippet=_snippet(descendant, src_bytes),
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Detector: assignment in condition (cross-language)
# ---------------------------------------------------------------------------
def _detect_assignment_in_condition(node: Node, src_bytes: bytes) -> list[BugFinding]:
    """Detect ``=`` assignment inside ``if``/``while`` conditions (C/C++/JS).

    In C-family languages ``if (x = 5)`` is valid but almost always a
    typo for ``if (x == 5)``.  The tree-sitter AST represents this as
    an ``assignment_expression`` inside a ``parenthesized_expression``.
    """
    findings: list[BugFinding] = []
    _COND_STMT_TYPES = frozenset({"if_statement", "while_statement"})

    for child in _walk(node):
        if child.type not in _COND_STMT_TYPES:
            continue
        # Get the condition node (parenthesized_expression in C/JS)
        cond = child.child_by_field_name("condition")
        if cond is None:
            continue
        # Look for assignment_expression inside the condition
        for cond_child in _walk(cond):
            if cond_child.type == "assignment_expression":
                findings.append(
                    BugFinding(
                        pattern="assignment-in-condition",
                        file="",
                        line=cond_child.start_point[0] + 1,
                        confidence=BugConfidence.MEDIUM.value,
                        message=f"Assignment '{_node_text(cond_child, src_bytes)}' in condition — did you mean '=='?",
                        snippet=_snippet(child, src_bytes),
                    )
                )
                break  # One finding per statement
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
    BugPattern(
        name="unused-variable",
        description="Variable assigned but never read within the function",
        languages=frozenset({"python"}),
        confidence=BugConfidence.MEDIUM,
        detect=_detect_unused_variable,
    ),
    BugPattern(
        name="exception-not-used",
        description="Exception bound with 'as' but never referenced in handler",
        languages=frozenset({"python"}),
        confidence=BugConfidence.MEDIUM,
        detect=_detect_exception_not_used,
    ),
    BugPattern(
        name="missing-await",
        description="Call to locally-defined async function without await",
        languages=frozenset({"python"}),
        confidence=BugConfidence.MEDIUM,
        detect=_detect_missing_await,
    ),
    BugPattern(
        name="shadowed-variable",
        description="Variable shadowed by for loop iteration variable",
        languages=frozenset({"python"}),
        confidence=BugConfidence.MEDIUM,
        detect=_detect_shadowed_variable,
    ),
    # --- Cross-language detectors ---
    BugPattern(
        name="empty-catch-block",
        description="Empty catch block silently swallows exceptions",
        languages=frozenset({"javascript", "typescript", "java", "c_sharp", "kotlin"}),
        confidence=BugConfidence.HIGH,
        detect=_detect_empty_catch,
    ),
    BugPattern(
        name="missing-break-in-switch",
        description="Switch case falls through without break or return",
        languages=frozenset({"c", "cpp", "c_sharp", "java"}),
        confidence=BugConfidence.HIGH,
        detect=_detect_missing_break_in_switch,
    ),
    BugPattern(
        name="redundant-condition",
        description="Nested if checks the exact same condition as outer if",
        languages=frozenset({"python", "javascript", "typescript"}),
        confidence=BugConfidence.MEDIUM,
        detect=_detect_redundant_condition,
    ),
    BugPattern(
        name="reraised-without-chain",
        description="Exception raised without 'from' loses original traceback",
        languages=frozenset({"python"}),
        confidence=BugConfidence.MEDIUM,
        detect=_detect_reraised_without_chain,
    ),
    BugPattern(
        name="assignment-in-condition",
        description="Assignment in if/while condition — likely meant ==",
        languages=frozenset({"c", "cpp", "javascript"}),
        confidence=BugConfidence.MEDIUM,
        detect=_detect_assignment_in_condition,
    ),
]
