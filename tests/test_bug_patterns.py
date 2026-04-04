"""Tests for bug pattern data types and detectors."""

from __future__ import annotations

import textwrap

from local_deepwiki.core.parser import CodeParser
from local_deepwiki.generators.analysis.bug_patterns import (
    CONFIDENCE_ORDER,
    PATTERNS,
    BugConfidence,
    BugPattern,
)
from local_deepwiki.models import Language


def _parse_python(source: str):
    """Parse Python source, return (root_node, src_bytes)."""
    parser = CodeParser()
    src_bytes = textwrap.dedent(source).encode()
    tree = parser._get_parser(Language.PYTHON).parse(src_bytes)
    return tree.root_node, src_bytes


def _find_functions(root_node):
    """Collect all function_definition nodes."""
    funcs: list = []

    def _walk(node):
        if node.type == "function_definition":
            funcs.append(node)
        for child in node.children:
            _walk(child)

    _walk(root_node)
    return funcs


# ---------------------------------------------------------------------------
# Data type tests
# ---------------------------------------------------------------------------
def test_bug_confidence_ordering():
    """BugConfidence enum has HIGH, MEDIUM, LOW values."""
    assert BugConfidence.HIGH.value == "high"
    assert BugConfidence.MEDIUM.value == "medium"
    assert BugConfidence.LOW.value == "low"
    assert CONFIDENCE_ORDER[BugConfidence.HIGH] > CONFIDENCE_ORDER[BugConfidence.MEDIUM]
    assert CONFIDENCE_ORDER[BugConfidence.MEDIUM] > CONFIDENCE_ORDER[BugConfidence.LOW]


def test_bug_pattern_is_frozen():
    """PATTERNS entries are frozen BugPattern dataclasses with correct types."""
    pat = PATTERNS[0]
    assert isinstance(pat, BugPattern)
    assert isinstance(pat.name, str)
    assert isinstance(pat.description, str)
    assert isinstance(pat.languages, frozenset)
    assert isinstance(pat.confidence, BugConfidence)
    assert callable(pat.detect)


def test_patterns_registry_not_empty():
    """PATTERNS registry is non-empty with unique names."""
    assert len(PATTERNS) >= 5
    names = [p.name for p in PATTERNS]
    assert len(names) == len(set(names)), f"Duplicate pattern names: {names}"


# ---------------------------------------------------------------------------
# Mutable default argument
# ---------------------------------------------------------------------------
def test_detect_mutable_default_list():
    """Detect mutable default: def f(x=[])."""
    root, src = _parse_python(
        """\
        def f(x=[]):
            pass
        """
    )
    funcs = _find_functions(root)
    assert len(funcs) == 1
    pat = next(p for p in PATTERNS if p.name == "mutable-default-argument")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 1
    assert findings[0]["pattern"] == "mutable-default-argument"
    assert findings[0]["confidence"] == "high"
    assert findings[0]["line"] >= 1


def test_detect_mutable_default_dict():
    """Detect mutable default: def f(x={})."""
    root, src = _parse_python(
        """\
        def f(x={}):
            pass
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "mutable-default-argument")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 1
    assert "x={}" in findings[0]["message"]


def test_no_false_positive_immutable_default():
    """No finding for immutable defaults: None, int, str."""
    root, src = _parse_python(
        """\
        def f(x=None, y=42, z="hello"):
            pass
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "mutable-default-argument")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Bare except
# ---------------------------------------------------------------------------
def test_detect_bare_except():
    """Detect bare except: clause."""
    root, src = _parse_python(
        """\
        def f():
            try:
                pass
            except:
                pass
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "bare-except")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 1
    assert findings[0]["pattern"] == "bare-except"


def test_bare_except_with_specific_exception_no_finding():
    """No finding when except specifies a type."""
    root, src = _parse_python(
        """\
        def f():
            try:
                pass
            except ValueError:
                raise
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "bare-except")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Comparison to None
# ---------------------------------------------------------------------------
def test_detect_comparison_to_none():
    """Detect x == None."""
    root, src = _parse_python(
        """\
        def f(x):
            if x == None:
                pass
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "comparison-to-none")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 1
    assert findings[0]["pattern"] == "comparison-to-none"
    assert "is None" in findings[0]["message"]


def test_is_none_no_finding():
    """No finding for x is None (correct form)."""
    root, src = _parse_python(
        """\
        def f(x):
            if x is None:
                pass
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "comparison-to-none")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# f-string no expression
# ---------------------------------------------------------------------------
def test_detect_fstring_no_expression():
    """Detect f-string with no interpolation."""
    root, src = _parse_python(
        """\
        def f():
            x = f"no braces here"
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "f-string-no-expression")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 1
    assert findings[0]["pattern"] == "f-string-no-expression"


def test_fstring_with_expression_no_finding():
    """No finding for f-string with interpolation."""
    root, src = _parse_python(
        """\
        def f():
            name = "world"
            x = f"hello {name}"
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "f-string-no-expression")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Unreachable code
# ---------------------------------------------------------------------------
def test_detect_unreachable_after_return():
    """Detect code after return statement."""
    root, src = _parse_python(
        """\
        def f():
            return 1
            x = 2
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "unreachable-code")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 1
    assert findings[0]["pattern"] == "unreachable-code"
    assert "return statement" in findings[0]["message"]


def test_no_unreachable_when_return_is_last():
    """No finding when return is the last statement."""
    root, src = _parse_python(
        """\
        def f():
            x = 1
            return x
        """
    )
    funcs = _find_functions(root)
    pat = next(p for p in PATTERNS if p.name == "unreachable-code")
    findings = pat.detect(funcs[0], src)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Unused variable
# ---------------------------------------------------------------------------
def test_detect_unused_variable():
    """Detect variable assigned but never read."""
    root, src = _parse_python(
        """\
        def f():
            x = 42
            return 1
        """
    )
    detector = next(p for p in PATTERNS if p.name == "unused-variable")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1
    assert any("x" in f["message"] for f in findings)


def test_unused_variable_underscore_prefix_ok():
    """No finding for underscore-prefixed names (intentionally unused)."""
    root, src = _parse_python(
        """\
        def f():
            _unused = 42
            return 1
        """
    )
    detector = next(p for p in PATTERNS if p.name == "unused-variable")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Exception not used
# ---------------------------------------------------------------------------
def test_detect_exception_not_used():
    """Detect exception bound with 'as' but never referenced."""
    root, src = _parse_python(
        """\
        def f():
            try:
                pass
            except ValueError as e:
                print("error")
        """
    )
    detector = next(p for p in PATTERNS if p.name == "exception-not-used")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1
    assert "e" in findings[0]["message"]


def test_exception_used_no_finding():
    """No finding when the bound exception is actually used."""
    root, src = _parse_python(
        """\
        def f():
            try:
                pass
            except ValueError as e:
                print(e)
        """
    )
    detector = next(p for p in PATTERNS if p.name == "exception-not-used")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Missing await
# ---------------------------------------------------------------------------
def test_detect_missing_await():
    """Detect call to locally-defined async function without await."""
    root, src = _parse_python(
        """\
        async def f():
            async def inner():
                return 1
            inner()
        """
    )
    detector = next(p for p in PATTERNS if p.name == "missing-await")
    funcs = _find_functions(root)
    # Get the outermost async function
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1


# ---------------------------------------------------------------------------
# Shadowed variable
# ---------------------------------------------------------------------------
def test_detect_shadowed_variable():
    """Detect for-loop variable that shadows an outer assignment."""
    root, src = _parse_python(
        """\
        def f():
            x = 1
            for x in range(10):
                pass
        """
    )
    detector = next(p for p in PATTERNS if p.name == "shadowed-variable")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1


# ---------------------------------------------------------------------------
# Cross-language helpers
# ---------------------------------------------------------------------------
def _parse_source(source: str, language):
    """Parse source in any language, return (root_node, src_bytes)."""
    parser = CodeParser()
    src_bytes = textwrap.dedent(source).encode()
    tree = parser._get_parser(language).parse(src_bytes)
    return tree.root_node, src_bytes


def _find_nodes_by_type(root_node, type_name: str):
    """Find all nodes of a given type."""
    results: list = []

    def _walk(node):
        if node.type == type_name:
            results.append(node)
        for child in node.children:
            _walk(child)

    _walk(root_node)
    return results


# ---------------------------------------------------------------------------
# Empty catch block
# ---------------------------------------------------------------------------
def test_detect_empty_catch_js():
    """Detect empty catch block in JavaScript."""
    root, src = _parse_source(
        """
    function f() {
        try {
            doStuff();
        } catch (e) {
        }
    }
    """,
        Language.JAVASCRIPT,
    )
    detector = next(p for p in PATTERNS if p.name == "empty-catch-block")
    funcs = _find_nodes_by_type(root, "function_declaration")
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1


def test_catch_with_body_no_finding():
    """No finding when catch block has statements."""
    root, src = _parse_source(
        """
    function f() {
        try {
            doStuff();
        } catch (e) {
            console.error(e);
        }
    }
    """,
        Language.JAVASCRIPT,
    )
    detector = next(p for p in PATTERNS if p.name == "empty-catch-block")
    funcs = _find_nodes_by_type(root, "function_declaration")
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Missing break in switch
# ---------------------------------------------------------------------------
def test_detect_missing_break_in_switch():
    """Detect case fall-through without break in C."""
    root, src = _parse_source(
        """
    void f(int x) {
        switch (x) {
            case 1:
                printf("one");
            case 2:
                printf("two");
                break;
        }
    }
    """,
        Language.C,
    )
    detector = next(p for p in PATTERNS if p.name == "missing-break-in-switch")
    funcs = _find_nodes_by_type(root, "function_definition")
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1


# ---------------------------------------------------------------------------
# Redundant condition
# ---------------------------------------------------------------------------
def test_detect_redundant_condition():
    """Detect nested if with same condition as outer if."""
    root, src = _parse_python(
        """\
        def f(x):
            if x:
                if x:
                    pass
        """
    )
    detector = next(p for p in PATTERNS if p.name == "redundant-condition")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1


# ---------------------------------------------------------------------------
# Reraised without chain
# ---------------------------------------------------------------------------
def test_detect_reraised_without_chain():
    """Detect raise without 'from' inside except block."""
    root, src = _parse_python(
        """\
        def f():
            try:
                pass
            except ValueError:
                raise TypeError("bad")
        """
    )
    detector = next(p for p in PATTERNS if p.name == "reraised-without-chain")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 1


def test_reraised_with_from_no_finding():
    """No finding when raise uses 'from' for exception chaining."""
    root, src = _parse_python(
        """\
        def f():
            try:
                pass
            except ValueError as e:
                raise TypeError("bad") from e
        """
    )
    detector = next(p for p in PATTERNS if p.name == "reraised-without-chain")
    funcs = _find_functions(root)
    findings = detector.detect(funcs[0], src)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# Assignment in condition
# ---------------------------------------------------------------------------
def test_detect_assignment_in_condition_c():
    """Detect assignment in if condition in C."""
    root, src = _parse_source(
        """
    void f(int x) {
        if (x = 5) {
            printf("oops");
        }
    }
    """,
        Language.C,
    )
    detector = next(p for p in PATTERNS if p.name == "assignment-in-condition")
    funcs = _find_nodes_by_type(root, "function_definition")
    findings = detector.detect(funcs[0], src)
    assert len(findings) >= 1
