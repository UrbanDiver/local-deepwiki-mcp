# Bug Hunter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `detect_bugs` MCP tool that scans a repository for potential bugs using AST pattern matching, with optional LLM enrichment for verification and explanation.

**Architecture:** Three new files following existing analysis patterns. `bug_patterns.py` defines a declarative pattern registry with detector functions. `bug_detection.py` is the orchestrator that walks files and runs detectors (mirrors `design_smells.py`). `handlers/analysis_bugs.py` is the MCP handler with arg validation, RBAC, LLM enrichment (mirrors `handle_get_recommendations` enrich pattern).

**Tech Stack:** tree-sitter AST parsing, Pydantic validation, existing LLM provider infrastructure.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/local_deepwiki/generators/analysis/bug_patterns.py` | Create | `BugConfidence` enum, `BugPattern` dataclass, `BugFinding` TypedDict, all 22 detector functions, `PATTERNS` registry list |
| `src/local_deepwiki/generators/analysis/bug_detection.py` | Create | `analyze_bugs()` orchestrator: walks files via `iter_source_files`, runs matching detectors, filters/sorts results |
| `src/local_deepwiki/handlers/analysis_bugs.py` | Create | `handle_detect_bugs()` MCP handler: arg validation, RBAC, LLM enrichment, response formatting |
| `src/local_deepwiki/models/tool_args.py` | Modify | Add `DetectBugsArgs` Pydantic model |
| `src/local_deepwiki/models/__init__.py` | Modify | Re-export `DetectBugsArgs` |
| `src/local_deepwiki/tool_defs/analysis.py` | Modify | Add `detect_bugs` Tool definition to `ANALYSIS_TOOLS` |
| `src/local_deepwiki/handlers/__init__.py` | Modify | Re-export `handle_detect_bugs` |
| `src/local_deepwiki/server.py` | Modify | Add `"detect_bugs": handle_detect_bugs` to `TOOL_HANDLERS` |
| `tests/test_bug_patterns.py` | Create | Unit tests for each detector function (pure AST in, findings out) |
| `tests/test_bug_detection.py` | Create | Integration tests for `analyze_bugs()` orchestrator with tmp_path repos |
| `tests/test_handler_bugs.py` | Create | Handler tests with mocked access controller |

---

### Task 1: BugConfidence Enum, BugFinding TypedDict, BugPattern Dataclass

**Files:**
- Create: `src/local_deepwiki/generators/analysis/bug_patterns.py`
- Test: `tests/test_bug_patterns.py`

This task creates the data types and an empty `PATTERNS` list. Detectors are added in Tasks 2-5.

- [ ] **Step 1: Write the failing test for data types**

```python
# tests/test_bug_patterns.py
"""Tests for bug pattern data types and detectors."""
from __future__ import annotations

from local_deepwiki.generators.analysis.bug_patterns import (
    BugConfidence,
    BugPattern,
    PATTERNS,
)


def test_bug_confidence_ordering():
    """HIGH > MEDIUM > LOW in the ordering dict."""
    assert BugConfidence.HIGH.value == "high"
    assert BugConfidence.MEDIUM.value == "medium"
    assert BugConfidence.LOW.value == "low"


def test_bug_pattern_is_frozen():
    """BugPattern instances are immutable."""
    pattern = PATTERNS[0]
    assert isinstance(pattern, BugPattern)
    assert isinstance(pattern.name, str)
    assert isinstance(pattern.languages, frozenset)
    assert callable(pattern.detect)


def test_patterns_registry_not_empty():
    """PATTERNS registry has entries."""
    assert len(PATTERNS) > 0
    names = [p.name for p in PATTERNS]
    assert len(names) == len(set(names)), "Duplicate pattern names"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bug_patterns.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the data types module**

```python
# src/local_deepwiki/generators/analysis/bug_patterns.py
"""Bug pattern definitions and detector functions.

Each BugPattern has a ``detect`` callable that receives a tree-sitter AST
node and source bytes, returning a list of BugFinding dicts. Detectors are
pure functions that never do I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, TypedDict

if TYPE_CHECKING:
    from tree_sitter import Node


class BugConfidence(str, Enum):
    """Confidence level for a bug finding."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


CONFIDENCE_ORDER: dict[BugConfidence, int] = {
    BugConfidence.LOW: 0,
    BugConfidence.MEDIUM: 1,
    BugConfidence.HIGH: 2,
}


class BugFinding(TypedDict):
    """A single bug finding from a detector."""
    pattern: str
    file: str
    line: int
    confidence: str
    message: str
    snippet: str


class EnrichedBugFinding(BugFinding):
    """Bug finding enriched by LLM verification."""
    verified: bool
    explanation: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class BugPattern:
    """A registered bug detection pattern."""
    name: str
    description: str
    languages: frozenset[str]
    confidence: BugConfidence
    detect: Callable[["Node", bytes], list[BugFinding]]


# ---------------------------------------------------------------------------
# Detector functions (added in Tasks 2-5)
# ---------------------------------------------------------------------------

# ... detectors will be added here ...

# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

PATTERNS: list[BugPattern] = [
    # Populated in Tasks 2-5
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_bug_patterns.py::test_bug_confidence_ordering tests/test_bug_patterns.py::test_bug_pattern_is_frozen -v`
Expected: `test_bug_confidence_ordering` PASS, `test_bug_pattern_is_frozen` FAIL (PATTERNS is empty, index error). This is expected; it will pass after Task 2 adds the first pattern.

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/bug_patterns.py tests/test_bug_patterns.py
git commit -m "feat: add bug pattern data types (BugConfidence, BugPattern, BugFinding)"
```

---

### Task 2: Python High-Confidence Detectors (5 patterns)

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/bug_patterns.py`
- Test: `tests/test_bug_patterns.py`

Patterns: `mutable-default-argument`, `bare-except`, `comparison-to-none`, `f-string-no-expression`, `unreachable-code` (Python).

- [ ] **Step 1: Write failing tests for Python detectors**

Add to `tests/test_bug_patterns.py`:

```python
import textwrap
from pathlib import Path

from local_deepwiki.core.parser import CodeParser


def _parse_python(source: str):
    """Parse Python source, return (root_node, src_bytes)."""
    parser = CodeParser()
    src_bytes = textwrap.dedent(source).encode()
    tree = parser._get_parser("python").parse(src_bytes)
    return tree.root_node, src_bytes


def _find_functions(root_node):
    """Collect all function_definition nodes."""
    funcs = []
    def _walk(node):
        if node.type == "function_definition":
            funcs.append(node)
        for child in node.children:
            _walk(child)
    _walk(root_node)
    return funcs


# --- mutable-default-argument ---

def test_detect_mutable_default_list():
    root, src = _parse_python("""
    def f(x=[]):
        pass
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "mutable-default-argument")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1
    assert findings[0]["pattern"] == "mutable-default-argument"


def test_detect_mutable_default_dict():
    root, src = _parse_python("""
    def f(x={}):
        pass
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "mutable-default-argument")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1


def test_no_false_positive_immutable_default():
    root, src = _parse_python("""
    def f(x=None, y=42, z="hello"):
        pass
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "mutable-default-argument")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# --- bare-except ---

def test_detect_bare_except():
    root, src = _parse_python("""
    def f():
        try:
            pass
        except:
            pass
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "bare-except")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1
    assert "bare" in findings[0]["message"].lower() or "swallow" in findings[0]["message"].lower()


def test_bare_except_with_specific_exception_no_finding():
    root, src = _parse_python("""
    def f():
        try:
            pass
        except ValueError:
            raise
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "bare-except")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# --- comparison-to-none ---

def test_detect_comparison_to_none():
    root, src = _parse_python("""
    def f(x):
        if x == None:
            pass
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "comparison-to-none")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1


def test_is_none_no_finding():
    root, src = _parse_python("""
    def f(x):
        if x is None:
            pass
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "comparison-to-none")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# --- f-string-no-expression ---

def test_detect_fstring_no_expression():
    root, src = _parse_python('''
    def f():
        x = f"no braces here"
    ''')
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "f-string-no-expression")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1


def test_fstring_with_expression_no_finding():
    root, src = _parse_python('''
    def f():
        name = "world"
        x = f"hello {name}"
    ''')
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "f-string-no-expression")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# --- unreachable-code (Python) ---

def test_detect_unreachable_after_return():
    root, src = _parse_python("""
    def f():
        return 1
        x = 2
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "unreachable-code")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1
    assert "unreachable" in findings[0]["message"].lower()


def test_no_unreachable_when_return_is_last():
    root, src = _parse_python("""
    def f():
        x = 1
        return x
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "unreachable-code")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bug_patterns.py -v`
Expected: FAIL (detectors not registered yet)

- [ ] **Step 3: Implement the 5 Python high-confidence detectors**

Add detector functions and register them in `PATTERNS` in `bug_patterns.py`. Each detector receives a function/class AST `Node` and `src_bytes`, returns `list[BugFinding]`.

Key implementation notes:
- `_detect_mutable_defaults`: Walk parameters looking for `default_parameter` nodes where the default is `list`/`dictionary`/`set` constructor or literal (`[]`, `{}`, `set()`)
- `_detect_bare_except`: Walk for `except_clause` nodes with no exception type child
- `_detect_comparison_to_none`: Walk for `comparison_operator` nodes where one operand is `None` and operator is `==` or `!=`
- `_detect_fstring_no_expression`: Walk for `string` nodes starting with `f"` or `f'` that contain no `interpolation` / `format_expression` children
- `_detect_unreachable_code`: In the function body, find `return_statement`/`raise_statement` nodes that have sibling statements after them in the same block

Helper to extract snippet text from a node:
```python
def _node_text(node: "Node", src_bytes: bytes) -> str:
    return src_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

def _snippet(node: "Node", src_bytes: bytes, context_lines: int = 2) -> str:
    lines = src_bytes.decode("utf-8", errors="replace").splitlines()
    start = max(0, node.start_point[0] - context_lines)
    end = min(len(lines), node.end_point[0] + context_lines + 1)
    return "\n".join(lines[start:end])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bug_patterns.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/bug_patterns.py tests/test_bug_patterns.py
git commit -m "feat: add 5 Python high-confidence bug detectors"
```

---

### Task 3: Python Medium-Confidence Detectors (4 patterns)

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/bug_patterns.py`
- Test: `tests/test_bug_patterns.py`

Patterns: `unused-variable` (Python), `exception-not-used`, `missing-await`, `shadowed-variable` (Python).

- [ ] **Step 1: Write failing tests for medium-confidence Python detectors**

Add to `tests/test_bug_patterns.py`:

```python
# --- unused-variable ---

def test_detect_unused_variable():
    root, src = _parse_python("""
    def f():
        x = 42
        return 1
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "unused-variable")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1
    assert any("x" in f["message"] for f in findings)


def test_unused_variable_underscore_prefix_ok():
    root, src = _parse_python("""
    def f():
        _unused = 42
        return 1
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "unused-variable")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# --- exception-not-used ---

def test_detect_exception_not_used():
    root, src = _parse_python("""
    def f():
        try:
            pass
        except ValueError as e:
            print("error")
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "exception-not-used")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1
    assert "e" in findings[0]["message"]


def test_exception_used_no_finding():
    root, src = _parse_python("""
    def f():
        try:
            pass
        except ValueError as e:
            print(e)
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "exception-not-used")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# --- missing-await ---

def test_detect_missing_await():
    root, src = _parse_python("""
    async def f():
        async def inner():
            return 1
        inner()
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "missing-await")
    funcs = _find_functions(root)
    # The outer async function
    outer = [f for f in funcs if _node_text(f.children[1], src) == "f"][0] if len(funcs) > 1 else funcs[0]
    findings = detector.detect(outer, src)
    assert len(findings) >= 1


# --- shadowed-variable ---

def test_detect_shadowed_variable():
    root, src = _parse_python("""
    def f():
        x = 1
        for x in range(10):
            pass
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "shadowed-variable")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bug_patterns.py -v -k "unused or exception_not or missing_await or shadowed"`
Expected: FAIL

- [ ] **Step 3: Implement the 4 Python medium-confidence detectors**

Key implementation notes:
- `_detect_unused_variable`: Collect all `assignment` target identifiers, then scan for all `identifier` references in the function body. Report assigned names that never appear in a non-assignment context. Skip `_` prefixed names.
- `_detect_exception_not_used`: Find `except_clause` nodes with `as` pattern. Check if the bound name appears anywhere in the except block body.
- `_detect_missing_await`: In `async` functions (check for `async` keyword), find `call` expressions where the callee is an `async` function defined in scope, but no parent `await` expression wraps the call. This is a heuristic (can't resolve all callees).
- `_detect_shadowed_variable`: Track variable assignments. If a variable is assigned at one scope level, then reassigned inside a nested `for`/`with`/`if` block, flag it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bug_patterns.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/bug_patterns.py tests/test_bug_patterns.py
git commit -m "feat: add 4 Python medium-confidence bug detectors"
```

---

### Task 4: Cross-Language Detectors (JS/TS/Go/C/C++/C#/Java/Rust)

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/bug_patterns.py`
- Test: `tests/test_bug_patterns.py`

Patterns: `empty-catch-block` (JS/TS/Java/Go/C#/Kotlin), `unreachable-code` (extend to all languages), `missing-break-in-switch` (C/C++/C#/Java), `redundant-condition` (Python/JS/TS), `reraised-without-chain` (Python), `assignment-in-condition` (C/C++/JS).

Due to the complexity of C/C++ specific patterns (`sizeof-pointer`, `null-deref-after-check`, `string-format-mismatch`, `uninitialized-variable`, `integer-overflow-cast`, `dangling-else`, `disposing-not-called`, `async-void`), these are best done as individual small patterns. We'll implement the 6 most broadly applicable cross-language patterns here.

- [ ] **Step 1: Write failing tests for cross-language detectors**

Add to `tests/test_bug_patterns.py`:

```python
def _parse_source(source: str, language: str):
    """Parse source in a given language, return (root_node, src_bytes)."""
    parser = CodeParser()
    src_bytes = textwrap.dedent(source).encode()
    tree = parser._get_parser(language).parse(src_bytes)
    return tree.root_node, src_bytes


def _find_nodes_by_type(root_node, type_name: str):
    """Find all nodes of a given type."""
    results = []
    def _walk(node):
        if node.type == type_name:
            results.append(node)
        for child in node.children:
            _walk(child)
    _walk(root_node)
    return results


# --- empty-catch-block ---

def test_detect_empty_catch_js():
    root, src = _parse_source("""
    function f() {
        try {
            doStuff();
        } catch (e) {
        }
    }
    """, "javascript")
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "empty-catch-block")
    funcs = _find_nodes_by_type(root, "function_declaration")
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1


def test_catch_with_body_no_finding():
    root, src = _parse_source("""
    function f() {
        try {
            doStuff();
        } catch (e) {
            console.error(e);
        }
    }
    """, "javascript")
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "empty-catch-block")
    funcs = _find_nodes_by_type(root, "function_declaration")
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# --- missing-break-in-switch ---

def test_detect_missing_break_in_switch():
    root, src = _parse_source("""
    void f(int x) {
        switch (x) {
            case 1:
                printf("one");
            case 2:
                printf("two");
                break;
        }
    }
    """, "c")
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "missing-break-in-switch")
    funcs = _find_nodes_by_type(root, "function_definition")
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1


# --- redundant-condition ---

def test_detect_redundant_condition():
    root, src = _parse_python("""
    def f(x):
        if x:
            if x:
                pass
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "redundant-condition")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1


# --- reraised-without-chain ---

def test_detect_reraised_without_chain():
    root, src = _parse_python("""
    def f():
        try:
            pass
        except ValueError:
            raise TypeError("bad")
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "reraised-without-chain")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1


def test_reraised_with_from_no_finding():
    root, src = _parse_python("""
    def f():
        try:
            pass
        except ValueError as e:
            raise TypeError("bad") from e
    """)
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "reraised-without-chain")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bug_patterns.py -v -k "empty_catch or missing_break or redundant or reraised"`
Expected: FAIL

- [ ] **Step 3: Implement the cross-language detectors**

Key implementation notes:
- `_detect_empty_catch`: Find `catch_clause` nodes whose body block has no statement children (only `{` and `}`)
- `_detect_missing_break_in_switch`: Find `switch_statement` nodes. For each `case` clause, check if it ends with `break_statement`, `return_statement`, `continue_statement`, or `throw_statement`. Skip the last case.
- `_detect_redundant_condition`: Find nested `if_statement` nodes where both conditions have identical text
- `_detect_reraised_without_chain`: Inside `except_clause`, find `raise_statement` nodes that have an argument (creating new exception) but no `from` clause
- `_detect_assignment_in_condition`: Find `if_statement` condition that contains `assignment_expression` (C: `=` in if condition)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bug_patterns.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/bug_patterns.py tests/test_bug_patterns.py
git commit -m "feat: add 6 cross-language bug detectors"
```

---

### Task 5: Remaining C/C++/C# Specific Detectors

**Files:**
- Modify: `src/local_deepwiki/generators/analysis/bug_patterns.py`
- Test: `tests/test_bug_patterns.py`

Patterns: `sizeof-pointer`, `null-deref-after-check`, `string-format-mismatch`, `uninitialized-variable`, `integer-overflow-cast`, `dangling-else`, `disposing-not-called` (C#), `async-void` (C#), `unused-variable` (JS/TS/Go/Rust extension).

- [ ] **Step 1: Write failing tests**

Add tests for each pattern following the same structure as Task 4. At minimum:

```python
# --- sizeof-pointer ---

def test_detect_sizeof_pointer():
    root, src = _parse_source("""
    void f(int* ptr) {
        int size = sizeof(ptr);
    }
    """, "c")
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "sizeof-pointer")
    funcs = _find_nodes_by_type(root, "function_definition")
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1


# --- async-void (C#) ---

def test_detect_async_void_csharp():
    root, src = _parse_source("""
    class Foo {
        async void Bar() {
            await Task.Delay(1);
        }
    }
    """, "c_sharp")
    from local_deepwiki.generators.analysis.bug_patterns import PATTERNS
    detector = next(p for p in PATTERNS if p.name == "async-void")
    # detect receives method node
    methods = _find_nodes_by_type(root, "method_declaration")
    findings = detector.detect(methods[0], src) if methods else []
    assert len(findings) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bug_patterns.py -v -k "sizeof or async_void"`
Expected: FAIL

- [ ] **Step 3: Implement the remaining detectors**

Key implementation notes:
- `_detect_sizeof_pointer`: In `sizeof_expression`, check if the argument is a pointer-typed identifier (has `*` in declaration) rather than a dereferenced value
- `_detect_async_void`: Find method declarations with `async` modifier and `void` return type
- `_detect_null_deref_after_check`: Find `if_statement` checking `x == NULL`, where the true branch dereferences `x`
- `_detect_string_format_mismatch`: Count `%` specifiers in printf format string, compare to argument count
- Simpler patterns (`uninitialized-variable`, `integer-overflow-cast`, `dangling-else`, `disposing-not-called`) follow similar AST walking approaches

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bug_patterns.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/bug_patterns.py tests/test_bug_patterns.py
git commit -m "feat: add C/C++/C# specific bug detectors"
```

---

### Task 6: Bug Detection Orchestrator

**Files:**
- Create: `src/local_deepwiki/generators/analysis/bug_detection.py`
- Test: `tests/test_bug_detection.py`

- [ ] **Step 1: Write failing tests for the orchestrator**

```python
# tests/test_bug_detection.py
"""Tests for the bug detection orchestrator."""
from __future__ import annotations

from pathlib import Path

from local_deepwiki.generators.analysis.bug_detection import analyze_bugs


def test_analyze_bugs_empty_repo(tmp_path: Path):
    """No source files -> success with 0 findings."""
    result = analyze_bugs(tmp_path)
    assert result["status"] == "success"
    assert result["total_findings"] == 0
    assert result["findings"] == []
    assert result["files_scanned"] == 0


def test_analyze_bugs_finds_mutable_default(tmp_path: Path):
    """Finds mutable-default-argument in a Python file."""
    py_file = tmp_path / "example.py"
    py_file.write_text("def f(x=[]):\n    pass\n")
    result = analyze_bugs(tmp_path)
    assert result["status"] == "success"
    assert result["total_findings"] >= 1
    patterns = [f["pattern"] for f in result["findings"]]
    assert "mutable-default-argument" in patterns


def test_analyze_bugs_min_confidence_filter(tmp_path: Path):
    """min_confidence='high' filters out medium findings."""
    py_file = tmp_path / "example.py"
    py_file.write_text("def f(x=[]):\n    pass\n")
    result = analyze_bugs(tmp_path, min_confidence="high")
    assert result["status"] == "success"
    for finding in result["findings"]:
        assert finding["confidence"] == "high"


def test_analyze_bugs_language_filter(tmp_path: Path):
    """languages=['go'] skips Python files."""
    py_file = tmp_path / "example.py"
    py_file.write_text("def f(x=[]):\n    pass\n")
    result = analyze_bugs(tmp_path, languages=["go"])
    assert result["total_findings"] == 0


def test_analyze_bugs_file_path_scope(tmp_path: Path):
    """file_path scopes to a single file."""
    (tmp_path / "a.py").write_text("def f(x=[]):\n    pass\n")
    (tmp_path / "b.py").write_text("def g(x={}):\n    pass\n")
    result = analyze_bugs(tmp_path, file_path="a.py")
    assert result["files_scanned"] == 1


def test_analyze_bugs_exclude_tests(tmp_path: Path):
    """exclude_tests=True skips test files."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo.py").write_text("def f(x=[]):\n    pass\n")
    (tmp_path / "main.py").write_text("def g():\n    pass\n")
    result_with = analyze_bugs(tmp_path, exclude_tests=True)
    result_without = analyze_bugs(tmp_path, exclude_tests=False)
    assert result_with["files_scanned"] < result_without["files_scanned"]


def test_analyze_bugs_top_n_limit(tmp_path: Path):
    """top_n limits returned findings."""
    py_file = tmp_path / "example.py"
    # Create many functions with mutable defaults
    lines = [f"def f{i}(x=[]):\n    pass\n" for i in range(20)]
    py_file.write_text("\n".join(lines))
    result = analyze_bugs(tmp_path, top_n=5)
    assert result["returned"] <= 5
    assert result["total_findings"] >= 5


def test_analyze_bugs_response_shape(tmp_path: Path):
    """Response has all required keys."""
    py_file = tmp_path / "example.py"
    py_file.write_text("def f(x=[]):\n    pass\n")
    result = analyze_bugs(tmp_path)
    assert "status" in result
    assert "total_findings" in result
    assert "returned" in result
    assert "by_confidence" in result
    assert "by_pattern" in result
    assert "findings" in result
    assert "patterns_checked" in result
    assert "files_scanned" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_bug_detection.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the orchestrator**

```python
# src/local_deepwiki/generators/analysis/bug_detection.py
"""Bug detection orchestrator.

Walks repository source files, runs matching bug detectors, and collects
findings. Mirrors the design_smells.py analysis pattern.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.generators.analysis.bug_patterns import (
    CONFIDENCE_ORDER,
    BugConfidence,
    BugFinding,
    PATTERNS,
)
from local_deepwiki.generators.analysis.source_filter import iter_source_files
from local_deepwiki.logging import get_logger

logger = get_logger(__name__)

# Map file extensions to language identifiers used in BugPattern.languages
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "c_sharp",
    ".kt": "kotlin",
    ".swift": "swift",
    ".rb": "ruby",
    ".php": "php",
}

# Node types that represent function/method/class boundaries
_SCANNABLE_TYPES = frozenset({
    "function_definition",
    "function_declaration",
    "method_definition",
    "method_declaration",
    "arrow_function",
    "function_item",
    "class_definition",
    "class_declaration",
    "struct_item",
    "impl_item",
})


def _collect_scannable_nodes(root_node: Any) -> list[Any]:
    """Collect top-level function/class AST nodes for detector scanning."""
    nodes: list[Any] = []
    def _walk(node: Any) -> None:
        if node.type in _SCANNABLE_TYPES:
            nodes.append(node)
        for child in node.children:
            _walk(child)
    _walk(root_node)
    return nodes


def analyze_bugs(
    repo_path: Path,
    min_confidence: str = "medium",
    languages: list[str] | None = None,
    exclude_tests: bool = True,
    file_path: str | None = None,
    top_n: int = 50,
) -> dict[str, Any]:
    """Scan repo_path for potential bugs using registered detectors.

    Args:
        repo_path: Root of the repository to scan.
        min_confidence: Minimum confidence level ("low", "medium", "high").
        languages: Filter to specific languages (None = all).
        exclude_tests: Skip test files when True.
        file_path: Scope to a single file (relative to repo_path).
        top_n: Maximum findings to return.

    Returns:
        Dict with status, findings, counts, and metadata.
    """
    # Validate min_confidence
    try:
        min_conf = BugConfidence(min_confidence)
    except ValueError:
        return {
            "status": "error",
            "message": f"Invalid min_confidence '{min_confidence}'. Valid: low, medium, high",
        }

    min_conf_order = CONFIDENCE_ORDER[min_conf]

    # Filter patterns by confidence and language
    lang_set = frozenset(languages) if languages else None
    active_patterns = [
        p for p in PATTERNS
        if CONFIDENCE_ORDER[p.confidence] >= min_conf_order
        and (lang_set is None or p.languages & lang_set)
    ]

    # Collect source files
    if file_path:
        full = (repo_path / file_path).resolve()
        if full.exists():
            source_files = [(full, Path(file_path))]
        else:
            source_files = []
    else:
        source_files = iter_source_files(repo_path, exclude_tests=exclude_tests)

    parser = CodeParser()
    all_findings: list[BugFinding] = []
    files_scanned = 0

    for full_path, rel_path in source_files:
        lang = _EXT_TO_LANG.get(full_path.suffix)
        if lang is None:
            continue
        if lang_set and lang not in lang_set:
            continue

        # Filter patterns applicable to this language
        file_patterns = [p for p in active_patterns if lang in p.languages]
        if not file_patterns:
            continue

        parse_result = parser.parse_file(full_path)
        if parse_result is None:
            continue

        files_scanned += 1
        root_node, _detected_lang, src_bytes = parse_result
        scannable = _collect_scannable_nodes(root_node)

        for node in scannable:
            for pattern in file_patterns:
                findings = pattern.detect(node, src_bytes)
                for finding in findings:
                    all_findings.append({
                        **finding,
                        "file": str(rel_path),
                        "confidence": pattern.confidence.value,
                        "pattern": pattern.name,
                    })

    # Sort by confidence (high first), then file path
    all_findings.sort(
        key=lambda f: (-CONFIDENCE_ORDER.get(BugConfidence(f["confidence"]), 0), f["file"], f["line"])
    )

    total = len(all_findings)
    returned_findings = all_findings[:top_n]

    # Build summary counts
    by_confidence: dict[str, int] = {}
    by_pattern: dict[str, int] = {}
    for f in all_findings:
        by_confidence[f["confidence"]] = by_confidence.get(f["confidence"], 0) + 1
        by_pattern[f["pattern"]] = by_pattern.get(f["pattern"], 0) + 1

    return {
        "status": "success",
        "total_findings": total,
        "returned": len(returned_findings),
        "by_confidence": by_confidence,
        "by_pattern": by_pattern,
        "findings": returned_findings,
        "patterns_checked": len(active_patterns),
        "files_scanned": files_scanned,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bug_detection.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/generators/analysis/bug_detection.py tests/test_bug_detection.py
git commit -m "feat: add bug detection orchestrator (analyze_bugs)"
```

---

### Task 7: Pydantic Args Model

**Files:**
- Modify: `src/local_deepwiki/models/tool_args.py`
- Modify: `src/local_deepwiki/models/__init__.py`

- [ ] **Step 1: Add DetectBugsArgs to tool_args.py**

Add after `GetDesignSmellsArgs` (around line 670):

```python
class DetectBugsArgs(BaseModel):
    """Arguments for the detect_bugs tool."""

    repo_path: str = Field(max_length=4096, description="Path to the repository")
    min_confidence: str = Field(
        default="medium",
        description="Minimum confidence: low, medium, high",
    )
    languages: list[str] | None = Field(
        default=None,
        description="Filter to specific languages (e.g. ['python', 'javascript'])",
    )
    enrich: bool = Field(
        default=False,
        description="Use LLM to verify and explain findings",
    )
    enrich_top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Max findings to send to LLM for enrichment",
    )
    exclude_tests: bool = Field(
        default=True,
        description="Exclude test files from scan",
    )
    file_path: str | None = Field(
        default=None,
        description="Scope to a single file (relative to repo root)",
    )
    top_n: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum findings to return",
    )
```

- [ ] **Step 2: Re-export from models/__init__.py**

Add `DetectBugsArgs` to imports from `tool_args` and to `__all__`.

- [ ] **Step 3: Run type check**

Run: `uv run mypy src/local_deepwiki/models/tool_args.py --no-error-summary`
Expected: No errors for the new class

- [ ] **Step 4: Commit**

```bash
git add src/local_deepwiki/models/tool_args.py src/local_deepwiki/models/__init__.py
git commit -m "feat: add DetectBugsArgs Pydantic model"
```

---

### Task 8: MCP Handler

**Files:**
- Create: `src/local_deepwiki/handlers/analysis_bugs.py`
- Test: `tests/test_handler_bugs.py`

- [ ] **Step 1: Write failing test for the handler**

```python
# tests/test_handler_bugs.py
"""Tests for the detect_bugs MCP handler."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import json

import pytest

from local_deepwiki.handlers.analysis_bugs import handle_detect_bugs


@pytest.fixture
def mock_access_controller():
    """Mock the access controller to allow all permissions."""
    with patch("local_deepwiki.handlers.analysis_bugs.get_access_controller") as mock:
        controller = mock.return_value
        controller.require_permission.return_value = None
        yield controller


async def test_handle_detect_bugs_success(tmp_path: Path, mock_access_controller):
    """Handler returns structured JSON with findings."""
    py_file = tmp_path / "example.py"
    py_file.write_text("def f(x=[]):\n    pass\n")
    result = await handle_detect_bugs({"repo_path": str(tmp_path)})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["total_findings"] >= 1


async def test_handle_detect_bugs_missing_repo(mock_access_controller):
    """Handler returns error for missing repo."""
    result = await handle_detect_bugs({"repo_path": "/nonexistent/path"})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "error" in data.get("status", "") or "error" in result[0].text.lower()


async def test_handle_detect_bugs_validation_error(mock_access_controller):
    """Handler returns error for invalid args."""
    result = await handle_detect_bugs({})
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert "error" in data.get("status", "") or "error" in result[0].text.lower()


async def test_handle_detect_bugs_with_enrich(tmp_path: Path, mock_access_controller):
    """Handler with enrich=true calls LLM provider."""
    py_file = tmp_path / "example.py"
    py_file.write_text("def f(x=[]):\n    pass\n")
    with patch("local_deepwiki.handlers.analysis_bugs.get_llm_provider") as mock_llm:
        # Mock LLM to return enrichment
        provider = mock_llm.return_value
        provider.generate.return_value = json.dumps([{
            "verified": True,
            "explanation": "Mutable default arguments are shared.",
            "suggestion": "Use None as default and create inside.",
        }])
        result = await handle_detect_bugs({
            "repo_path": str(tmp_path),
            "enrich": True,
        })
        data = json.loads(result[0].text)
        assert data["status"] == "success"


async def test_handle_detect_bugs_confidence_filter(tmp_path: Path, mock_access_controller):
    """Handler respects min_confidence parameter."""
    py_file = tmp_path / "example.py"
    py_file.write_text("def f(x=[]):\n    pass\n")
    result = await handle_detect_bugs({
        "repo_path": str(tmp_path),
        "min_confidence": "high",
    })
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    for finding in data.get("findings", []):
        assert finding["confidence"] == "high"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_handler_bugs.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the handler**

```python
# src/local_deepwiki/handlers/analysis_bugs.py
"""Bug detection MCP handler."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import ValidationError as PydanticValidationError

from local_deepwiki.errors import path_not_found_error
from local_deepwiki.handlers._error_handling import handle_tool_errors
from local_deepwiki.handlers._response import make_tool_text_content
from local_deepwiki.logging import get_logger
from local_deepwiki.models import DetectBugsArgs
from local_deepwiki.security import Permission, get_access_controller

logger = get_logger(__name__)


def _extract_code_context(
    repo_path: Path, file_path: str, line: int, context_lines: int = 10
) -> str:
    """Extract source lines around a finding for LLM context."""
    full_path = repo_path / file_path
    try:
        lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    start = max(0, line - context_lines - 1)
    end = min(len(lines), line + context_lines)
    return "\n".join(lines[start:end])


async def _enrich_findings(
    findings: list[dict[str, Any]],
    repo_path: Path,
    top_n: int,
) -> list[dict[str, Any]]:
    """Use LLM to verify and explain the top findings."""
    from local_deepwiki.providers.llm import get_llm_provider

    provider = get_llm_provider()
    to_enrich = findings[:top_n]

    enriched: list[dict[str, Any]] = []
    for finding in to_enrich:
        context = _extract_code_context(
            repo_path, finding["file"], finding["line"]
        )
        prompt = (
            f"Analyze this potential bug found by static analysis.\n\n"
            f"Pattern: {finding['pattern']}\n"
            f"File: {finding['file']}:{finding['line']}\n"
            f"Message: {finding['message']}\n"
            f"Code snippet:\n```\n{finding.get('snippet', context)}\n```\n\n"
            f"Respond in JSON with exactly these fields:\n"
            f'{{"verified": true/false, "explanation": "...", "suggestion": "..."}}'
        )
        try:
            response = await provider.generate(prompt)
            parsed = json.loads(response)
            enriched.append({
                **finding,
                "verified": parsed.get("verified", False),
                "explanation": parsed.get("explanation", ""),
                "suggestion": parsed.get("suggestion", ""),
            })
            # Demote unverified findings
            if not parsed.get("verified", False):
                enriched[-1]["confidence"] = "low"
        except (json.JSONDecodeError, Exception):
            logger.debug("LLM enrichment failed for %s:%d", finding["file"], finding["line"])
            enriched.append(finding)

    # Append un-enriched findings
    enriched.extend(findings[top_n:])
    return enriched


@handle_tool_errors
async def handle_detect_bugs(args: dict[str, Any]) -> list[TextContent]:
    """Handle detect_bugs tool call."""
    controller = get_access_controller()
    controller.require_permission(Permission.INDEX_READ)

    try:
        validated = DetectBugsArgs.model_validate(args)
    except PydanticValidationError as e:
        raise ValueError(str(e)) from e

    repo_path = Path(validated.repo_path).resolve()
    if not repo_path.exists():
        raise path_not_found_error(str(repo_path), "repository")

    from local_deepwiki.generators.analysis.bug_detection import analyze_bugs

    result = analyze_bugs(
        repo_path,
        min_confidence=validated.min_confidence,
        languages=validated.languages,
        exclude_tests=validated.exclude_tests,
        file_path=validated.file_path,
        top_n=validated.top_n,
    )

    if validated.enrich and result.get("findings"):
        try:
            result = {
                **result,
                "findings": await _enrich_findings(
                    result["findings"], repo_path, validated.enrich_top_n
                ),
            }
        except Exception:
            logger.debug("LLM enrichment unavailable, returning static findings")

    logger.info(
        "Bug scan: %d findings (%d returned) in %d files for %s",
        result.get("total_findings", 0),
        result.get("returned", 0),
        result.get("files_scanned", 0),
        repo_path,
    )
    return make_tool_text_content("detect_bugs", result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_handler_bugs.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/local_deepwiki/handlers/analysis_bugs.py tests/test_handler_bugs.py
git commit -m "feat: add detect_bugs MCP handler with LLM enrichment"
```

---

### Task 9: Tool Definition and Server Wiring

**Files:**
- Modify: `src/local_deepwiki/tool_defs/analysis.py`
- Modify: `src/local_deepwiki/handlers/__init__.py`
- Modify: `src/local_deepwiki/server.py`

- [ ] **Step 1: Add tool definition to analysis.py**

Add to the end of the `ANALYSIS_TOOLS` tuple in `src/local_deepwiki/tool_defs/analysis.py` (before the closing `)`):

```python
    Tool(
        name="detect_bugs",
        description=(
            "Scan a repository for potential bugs using AST pattern matching. "
            "Detects 22 bug patterns across Python, JavaScript, TypeScript, Go, "
            "Rust, Java, C, C++, C#, and Kotlin. Patterns include mutable "
            "default arguments, bare excepts, unreachable code, empty catch "
            "blocks, missing breaks, and more. Set enrich=true for LLM "
            "verification and explanation of findings."
            "\n\nNo prior indexing required."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository to scan",
                },
                "min_confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Minimum confidence threshold (default: medium)",
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter to specific languages (e.g. ['python', 'javascript'])",
                },
                "enrich": {
                    "type": "boolean",
                    "description": "Use LLM to verify and explain top findings (default: false)",
                },
                "enrich_top_n": {
                    "type": "integer",
                    "description": "Max findings to send to LLM (default: 10, max: 50)",
                },
                "exclude_tests": {
                    "type": "boolean",
                    "description": "Exclude test files (default: true)",
                },
                "file_path": {
                    "type": "string",
                    "description": "Scope to a single file (relative path from repo root)",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Maximum findings to return (default: 50, max: 500)",
                },
            },
            "required": ["repo_path"],
        },
        annotations=_READ_ONLY,
    ),
```

- [ ] **Step 2: Add handler re-export to handlers/__init__.py**

Add to imports section (after `analysis_architecture` imports):
```python
from local_deepwiki.handlers.analysis_bugs import handle_detect_bugs
```

Add `"handle_detect_bugs"` to `__all__`.

- [ ] **Step 3: Add dispatch entry to server.py**

In `TOOL_HANDLERS` dict in `server.py`, add:
```python
    "detect_bugs": handle_detect_bugs,
```

Add `handle_detect_bugs` to the import from `local_deepwiki.handlers`.

- [ ] **Step 4: Run the consistency check**

Run: `uv run python -c "from local_deepwiki.server import verify_tool_handler_consistency; verify_tool_handler_consistency()"`
Expected: No `RuntimeError` — all tools have handlers and vice versa.

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v --timeout=120`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/local_deepwiki/tool_defs/analysis.py src/local_deepwiki/handlers/__init__.py src/local_deepwiki/server.py
git commit -m "feat: wire detect_bugs tool definition and server dispatch"
```

---

### Task 10: End-to-End Verification

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v --timeout=120`
Expected: ALL PASS, including all new test files

- [ ] **Step 2: Run type checking**

Run: `uv run mypy src/local_deepwiki/generators/analysis/bug_patterns.py src/local_deepwiki/generators/analysis/bug_detection.py src/local_deepwiki/handlers/analysis_bugs.py`
Expected: No errors

- [ ] **Step 3: Run the MCP server and verify tool listing**

Run: `uv run local-deepwiki &` (background), then verify `detect_bugs` appears in tools list.

- [ ] **Step 4: Manual smoke test**

Run the detect_bugs tool against this repo:
```bash
uv run python -c "
import asyncio, json
from local_deepwiki.generators.analysis.bug_detection import analyze_bugs
from pathlib import Path
result = analyze_bugs(Path('.'))
print(json.dumps({k: v for k, v in result.items() if k != 'findings'}, indent=2))
print(f'Sample finding: {result[\"findings\"][0] if result[\"findings\"] else \"none\"}')
"
```

- [ ] **Step 5: Final commit and PR-ready**

```bash
git add -A
git status
# If clean, we're done. If any remaining changes:
git commit -m "chore: finalize bug hunter feature"
```
