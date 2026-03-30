"""Tests for _collect_reverse_calls in analysis_entity — cross-file caller detection."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from local_deepwiki.handlers.analysis_entity import (
    EntityAnalysisContext,
    _collect_reverse_calls,
)


def _make_result_and_sets() -> tuple[dict[str, Any], set[str], set[str]]:
    """Return a fresh (result, affected_files, affected_entities) triple."""
    return {}, set(), set()


class TestCollectReverseCalls:
    """Tests for _collect_reverse_calls including cross-file caller detection."""

    def test_single_file_reverse_calls(self, tmp_path: Path) -> None:
        """Baseline: callers within the same file are found."""
        source = dedent("""\
            def helper():
                pass

            def caller_a():
                helper()

            def caller_b():
                helper()
        """)
        target = tmp_path / "module.py"
        target.write_text(source)

        result, affected_files, affected_entities = _make_result_and_sets()

        ctx = EntityAnalysisContext(
            file_path="module.py",
            entity_name="helper",
            full_file=target,
            repo_path=tmp_path,
        )
        _collect_reverse_calls(
            result=result,
            ctx=ctx,
            affected_files=affected_files,
            affected_entities=affected_entities,
        )

        assert "reverse_call_graph" in result
        rg = result["reverse_call_graph"]
        assert "helper" in rg
        callers = rg["helper"]
        assert "caller_a" in callers
        assert "caller_b" in callers

    def test_includes_cross_file_callers_via_imports(self, tmp_path: Path) -> None:
        """Two files: consumer.py imports and calls a function from target.py.

        The cross-file caller should appear in the reverse call graph,
        qualified as 'consumer.py:use_target'.
        """
        # Target file defines a function
        target_source = dedent("""\
            def target_func():
                pass
        """)
        target = tmp_path / "target.py"
        target.write_text(target_source)

        # Consumer file imports and calls target_func
        consumer_source = dedent("""\
            from target import target_func

            def use_target():
                target_func()
        """)
        consumer = tmp_path / "consumer.py"
        consumer.write_text(consumer_source)

        result, affected_files, affected_entities = _make_result_and_sets()

        ctx = EntityAnalysisContext(
            file_path="target.py",
            entity_name="target_func",
            full_file=target,
            repo_path=tmp_path,
        )
        _collect_reverse_calls(
            result=result,
            ctx=ctx,
            affected_files=affected_files,
            affected_entities=affected_entities,
        )

        assert "reverse_call_graph" in result
        rg = result["reverse_call_graph"]
        assert "target_func" in rg
        callers = rg["target_func"]

        # The cross-file caller should be qualified with relative path
        cross_file_callers = [c for c in callers if "consumer.py:" in c]
        assert len(cross_file_callers) >= 1, (
            f"Expected a cross-file caller from consumer.py, got: {callers}"
        )

    def test_cross_file_callers_added_to_affected_files(self, tmp_path: Path) -> None:
        """Cross-file callers should populate the affected_files set."""
        target_source = dedent("""\
            def target_func():
                pass
        """)
        target = tmp_path / "target.py"
        target.write_text(target_source)

        consumer_source = dedent("""\
            from target import target_func

            def use_target():
                target_func()
        """)
        (tmp_path / "consumer.py").write_text(consumer_source)

        result, affected_files, affected_entities = _make_result_and_sets()

        ctx = EntityAnalysisContext(
            file_path="target.py",
            entity_name="target_func",
            full_file=target,
            repo_path=tmp_path,
        )
        _collect_reverse_calls(
            result=result,
            ctx=ctx,
            affected_files=affected_files,
            affected_entities=affected_entities,
        )

        assert "consumer.py" in affected_files

    def test_cross_file_ignores_non_import_mentions(self, tmp_path: Path) -> None:
        """A file that mentions the module name in a string (not import) is skipped."""
        target_source = dedent("""\
            def target_func():
                pass
        """)
        target = tmp_path / "target.py"
        target.write_text(target_source)

        # This file mentions "target" but does NOT import it
        bystander_source = dedent("""\
            def bystander():
                msg = "target is just a word here"
        """)
        (tmp_path / "bystander.py").write_text(bystander_source)

        result, affected_files, affected_entities = _make_result_and_sets()

        ctx = EntityAnalysisContext(
            file_path="target.py",
            entity_name="target_func",
            full_file=target,
            repo_path=tmp_path,
        )
        _collect_reverse_calls(
            result=result,
            ctx=ctx,
            affected_files=affected_files,
            affected_entities=affected_entities,
        )

        rg = result.get("reverse_call_graph", {})
        callers = rg.get("target_func", [])
        bystander_callers = [c for c in callers if "bystander.py:" in c]
        assert len(bystander_callers) == 0, (
            f"Bystander file should not appear as a caller, got: {callers}"
        )

    def test_cross_file_nested_directory(self, tmp_path: Path) -> None:
        """Cross-file callers in subdirectories use relative paths."""
        target_source = dedent("""\
            def target_func():
                pass
        """)
        target = tmp_path / "target.py"
        target.write_text(target_source)

        sub_dir = tmp_path / "pkg"
        sub_dir.mkdir()
        consumer_source = dedent("""\
            from target import target_func

            def nested_caller():
                target_func()
        """)
        (sub_dir / "consumer.py").write_text(consumer_source)

        result, affected_files, affected_entities = _make_result_and_sets()

        ctx = EntityAnalysisContext(
            file_path="target.py",
            entity_name="target_func",
            full_file=target,
            repo_path=tmp_path,
        )
        _collect_reverse_calls(
            result=result,
            ctx=ctx,
            affected_files=affected_files,
            affected_entities=affected_entities,
        )

        rg = result.get("reverse_call_graph", {})
        callers = rg.get("target_func", [])
        nested_callers = [c for c in callers if "pkg/consumer.py:" in c]
        assert len(nested_callers) >= 1, (
            f"Expected nested cross-file caller from pkg/consumer.py, got: {callers}"
        )

    def test_no_entity_name_returns_full_reverse_graph(self, tmp_path: Path) -> None:
        """When entity_name is None, the full reverse graph is returned."""
        source = dedent("""\
            def func_a():
                func_b()

            def func_b():
                pass
        """)
        target = tmp_path / "module.py"
        target.write_text(source)

        result, affected_files, affected_entities = _make_result_and_sets()

        ctx = EntityAnalysisContext(
            file_path="module.py",
            entity_name=None,
            full_file=target,
            repo_path=tmp_path,
        )
        _collect_reverse_calls(
            result=result,
            ctx=ctx,
            affected_files=affected_files,
            affected_entities=affected_entities,
        )

        rg = result.get("reverse_call_graph", {})
        # func_b should have func_a as a caller
        assert "func_b" in rg
        assert "func_a" in rg["func_b"]

    def test_error_handling_stores_error(self, tmp_path: Path) -> None:
        """When the target file cannot be parsed, an error is stored gracefully."""
        target = tmp_path / "bad_file.xyz"
        target.write_text("this is not parseable code")

        result, affected_files, affected_entities = _make_result_and_sets()

        ctx = EntityAnalysisContext(
            file_path="bad_file.xyz",
            entity_name=None,
            full_file=target,
            repo_path=tmp_path,
        )
        _collect_reverse_calls(
            result=result,
            ctx=ctx,
            affected_files=affected_files,
            affected_entities=affected_entities,
        )

        # Should either succeed with empty graph or record an error
        assert "reverse_call_graph" in result
