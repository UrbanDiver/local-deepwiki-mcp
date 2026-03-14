"""Tests for wiki quality improvements.

Covers content deduplication, cross-link code-block splitting,
table row protection, term validation, and architecture prompt content.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

# NOTE: wiki.files must be imported before crosslinks to avoid a circular
# import (crosslinks -> wiki.utils -> wiki/__init__ -> wiki.generator -> crosslinks).
from local_deepwiki.generators.wiki.files import (
    _DUPLICATE_SECTION_PATTERNS,
    _build_llm_prompt,
    _strip_enrichment_duplicates,
)
from local_deepwiki.generators.crosslinks import CrossLinker, EntityRegistry
from local_deepwiki.generators.wiki.term_validator import apply_term_corrections
from local_deepwiki.models import ChunkType


# ---------------------------------------------------------------------------
# Phase 1: Content Deduplication (_strip_enrichment_duplicates)
# ---------------------------------------------------------------------------


class TestStripEnrichmentDuplicates:
    """Tests for _strip_enrichment_duplicates in files.py."""

    def test_strips_classes_section_keeps_integration(self) -> None:
        content = (
            "## File Overview\n\nSome overview.\n\n"
            "## Classes\n\nClass A does X.\nClass B does Y.\n\n"
            "## Integration\n\nThis file integrates with Z."
        )
        result = _strip_enrichment_duplicates(content)
        assert "## Classes" not in result
        assert "Class A does X" not in result
        assert "## Integration" in result
        assert "This file integrates with Z" in result

    def test_strips_functions_section(self) -> None:
        content = (
            "## Overview\n\nOverview text.\n\n"
            "## Functions\n\n### foo()\n\nDoes something.\n\n"
            "## Design Notes\n\nSome notes."
        )
        result = _strip_enrichment_duplicates(content)
        assert "## Functions" not in result
        assert "foo()" not in result
        assert "## Design Notes" in result

    def test_strips_usage_examples_section(self) -> None:
        content = (
            "## Overview\n\nText.\n\n"
            "## Usage Examples\n\n```python\nfoo()\n```\n\n"
            "## Other\n\nMore text."
        )
        result = _strip_enrichment_duplicates(content)
        assert "## Usage Examples" not in result
        assert "## Other" in result

    def test_strips_usage_example_singular(self) -> None:
        content = (
            "## Overview\n\nText.\n\n"
            "## Usage Example\n\nSome example code.\n\n"
            "## Notes\n\nKeep this."
        )
        result = _strip_enrichment_duplicates(content)
        assert "## Usage Example" not in result
        assert "## Notes" in result

    def test_no_duplicate_sections_returns_unchanged(self) -> None:
        content = (
            "## File Overview\n\nThis file does X.\n\n"
            "## Key Concepts\n\nConcept A.\n\n"
            "## Design Notes\n\nTrade-off analysis."
        )
        result = _strip_enrichment_duplicates(content)
        assert result == content

    def test_strips_class_diagram_with_mermaid(self) -> None:
        content = (
            "## Overview\n\nText.\n\n"
            "## Class Diagram\n\n```mermaid\nclassDiagram\n"
            "    class Foo {\n        +bar()\n    }\n```\n\n"
            "## Integration\n\nKeep this."
        )
        result = _strip_enrichment_duplicates(content)
        assert "## Class Diagram" not in result
        assert "classDiagram" not in result
        assert "## Integration" in result

    def test_strips_api_reference_section(self) -> None:
        content = (
            "## Overview\n\nText.\n\n"
            "## API Reference\n\n### foo(x: int) -> str\n\nDoes something.\n\n"
            "## Notes\n\nKeep."
        )
        result = _strip_enrichment_duplicates(content)
        assert "## API Reference" not in result
        assert "foo(x: int)" not in result
        assert "## Notes" in result

    def test_strips_multiple_duplicate_sections(self) -> None:
        content = (
            "## Overview\n\nIntro.\n\n"
            "## Classes\n\nClass list.\n\n"
            "## Functions\n\nFunction list.\n\n"
            "## Usage Examples\n\nExample code.\n\n"
            "## API Reference\n\nAPI details.\n\n"
            "## Design Notes\n\nKeep this section."
        )
        result = _strip_enrichment_duplicates(content)
        assert "## Classes" not in result
        assert "## Functions" not in result
        assert "## Usage Examples" not in result
        assert "## API Reference" not in result
        assert "## Design Notes" in result
        assert "Keep this section." in result


# ---------------------------------------------------------------------------
# Phase 2: Cross-link improvements
# ---------------------------------------------------------------------------


class TestSplitByCodeBlocks:
    """Tests for CrossLinker._split_by_code_blocks."""

    def test_no_code_blocks_returns_single_non_code_part(self) -> None:
        content = "Hello world\nsome text\nmore text"
        parts = CrossLinker._split_by_code_blocks(content)
        assert len(parts) == 1
        text, is_code = parts[0]
        assert is_code is False
        assert "Hello world" in text

    def test_normal_fenced_code_block_splits_correctly(self) -> None:
        content = "Before code\n```python\nprint('hi')\n```\nAfter code"
        parts = CrossLinker._split_by_code_blocks(content)
        # Should be: non-code, code, non-code
        assert len(parts) == 3
        assert parts[0][1] is False  # before
        assert parts[1][1] is True  # code block
        assert parts[2][1] is False  # after
        assert "Before code" in parts[0][0]
        assert "print('hi')" in parts[1][0]
        assert "After code" in parts[2][0]

    def test_inline_triple_backticks_inside_code_block(self) -> None:
        """Inline ``` inside a code block (e.g., f-string) should NOT close the block."""
        content = (
            "Before\n"
            "```python\n"
            'tree_output = f"```\\n{tree}\\n```"\n'
            "print(tree_output)\n"
            "```\n"
            "After"
        )
        parts = CrossLinker._split_by_code_blocks(content)
        # The inline ``` is not at indent<=3 with nothing after the ``` on its line
        # (it has content after it), so it should NOT close the code block.
        # Result: non-code, code, non-code
        assert len(parts) == 3
        assert parts[0][1] is False
        assert parts[1][1] is True
        assert parts[2][1] is False
        # The code block should contain the f-string with inline backticks
        assert 'f"```' in parts[1][0]
        assert "After" in parts[2][0]

    def test_tilde_fenced_blocks(self) -> None:
        content = "Before\n~~~\ncode here\n~~~\nAfter"
        parts = CrossLinker._split_by_code_blocks(content)
        assert len(parts) == 3
        assert parts[0][1] is False
        assert parts[1][1] is True
        assert parts[2][1] is False
        assert "code here" in parts[1][0]

    def test_empty_content(self) -> None:
        parts = CrossLinker._split_by_code_blocks("")
        assert len(parts) == 1
        assert parts[0] == ("", False)


class TestTableRowProtection:
    """Test that entity names inside markdown table rows are NOT linked."""

    def _make_linker_components(
        self,
    ) -> tuple[
        dict[str, tuple[str, str]], re.Pattern[str], re.Pattern[str], re.Pattern[str]
    ]:
        """Build linkable dict and regex patterns for a test entity."""
        linkable: dict[str, tuple[str, str]] = {
            "WikiGenerator": ("WikiGenerator", "../files/wiki/generator.md"),
        }
        sorted_names = sorted(linkable.keys(), key=len, reverse=True)
        alternation = "|".join(re.escape(n) for n in sorted_names)
        backtick_re = re.compile(
            rf"`(?:(?:[a-zA-Z_][a-zA-Z0-9_]*\.)+)?({alternation})`"
        )
        bold_re = re.compile(rf"\*\*({alternation})\*\*")
        plain_re = re.compile(rf"\b({alternation})\b")
        return linkable, backtick_re, bold_re, plain_re

    def test_entity_in_table_row_not_linked(self) -> None:
        linkable, backtick_re, bold_re, plain_re = self._make_linker_components()
        text = "| WikiGenerator | Generates wiki pages |"
        result = CrossLinker._add_links_to_text(
            text, linkable, backtick_re, bold_re, plain_re
        )
        # Table row should be protected — no link should be added
        assert "[WikiGenerator]" not in result
        assert "| WikiGenerator |" in result

    def test_entity_outside_table_is_linked(self) -> None:
        linkable, backtick_re, bold_re, plain_re = self._make_linker_components()
        text = "The WikiGenerator handles documentation."
        result = CrossLinker._add_links_to_text(
            text, linkable, backtick_re, bold_re, plain_re
        )
        assert "[WikiGenerator]" in result
        assert "../files/wiki/generator.md" in result


# ---------------------------------------------------------------------------
# Phase 3: Term Validation (apply_term_corrections)
# ---------------------------------------------------------------------------


class TestApplyTermCorrections:
    """Tests for apply_term_corrections in term_validator.py."""

    def test_model_communication_protocol_corrected(self) -> None:
        content = "This project uses the Model Communication Protocol."
        result = apply_term_corrections(content)
        assert "Model Context Protocol" in result
        assert "Model Communication Protocol" not in result

    def test_model_completion_protocol_corrected(self) -> None:
        content = "Built on the Model Completion Protocol standard."
        result = apply_term_corrections(content)
        assert "Model Context Protocol" in result
        assert "Model Completion Protocol" not in result

    def test_treesitter_corrected_outside_code_block(self) -> None:
        content = "The parser uses TreeSitter grammars."
        result = apply_term_corrections(content)
        assert "tree-sitter" in result
        assert "TreeSitter" not in result

    def test_treesitter_not_corrected_inside_code_block(self) -> None:
        content = "Some text.\n```python\nparser = TreeSitter()\n```\nMore text."
        result = apply_term_corrections(content)
        # Inside the code block, TreeSitter should remain unchanged
        assert "TreeSitter()" in result

    def test_lancedb_corrected(self) -> None:
        content = "Data is stored in LanceDb."
        result = apply_term_corrections(content)
        assert "LanceDB" in result
        assert "LanceDb" not in result

    def test_fastmcp_corrected(self) -> None:
        content = "Built with FastMcp framework."
        result = apply_term_corrections(content)
        assert "FastMCP" in result
        assert "FastMcp" not in result

    def test_no_corrections_needed_returns_unchanged(self) -> None:
        content = "This is correct text with Model Context Protocol and tree-sitter."
        result = apply_term_corrections(content)
        assert result == content

    def test_multiple_corrections_in_one_content(self) -> None:
        content = (
            "The Model Communication Protocol server uses TreeSitter "
            "for parsing and LanceDb for storage. FastMcp provides the framework."
        )
        result = apply_term_corrections(content)
        assert "Model Context Protocol" in result
        assert "tree-sitter" in result
        assert "LanceDB" in result
        assert "FastMCP" in result
        # Originals should all be gone
        assert "Model Communication Protocol" not in result
        assert "TreeSitter" not in result
        assert "LanceDb" not in result
        assert "FastMcp" not in result


# ---------------------------------------------------------------------------
# Phase 4: Architecture Prompt Content Verification
# ---------------------------------------------------------------------------


class TestFilesPromptContent:
    """Verify that _build_llm_prompt in files.py contains key quality phrases."""

    def test_prompt_mentions_key_concepts(self) -> None:
        source = inspect.getsource(_build_llm_prompt)
        assert "Key Concepts" in source

    def test_prompt_mentions_design_notes(self) -> None:
        source = inspect.getsource(_build_llm_prompt)
        assert "Design Notes" in source

    def test_prompt_contains_do_not_include_instruction(self) -> None:
        source = inspect.getsource(_build_llm_prompt)
        assert "Do NOT include these sections" in source

    def test_prompt_mentions_why(self) -> None:
        source = inspect.getsource(_build_llm_prompt)
        assert "WHY" in source


class TestArchitecturePromptContent:
    """Verify that generate_architecture_page in pages.py contains quality phrases."""

    def _get_source(self) -> str:
        from local_deepwiki.generators.wiki.pages import generate_architecture_page

        return inspect.getsource(generate_architecture_page)

    def test_prompt_mentions_why_multiple_times(self) -> None:
        source = self._get_source()
        # Should appear at least twice (WHY in component descriptions + design decisions)
        assert source.count("WHY") >= 2

    def test_prompt_mentions_trade_offs(self) -> None:
        source = self._get_source()
        assert "trade-off" in source.lower() or "trade-offs" in source.lower()

    def test_prompt_mentions_design_decisions_and_trade_offs(self) -> None:
        source = self._get_source()
        assert "Design Decisions and Trade-offs" in source

    def test_prompt_mentions_focus_on_why(self) -> None:
        source = self._get_source()
        assert "Focus on WHY" in source
