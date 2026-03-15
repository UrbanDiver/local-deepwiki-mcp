"""Tests for core.query_utils — shared query condensation and term expansion.

Tests cover:
- Filler word stripping from conversational queries
- Technical term preservation
- Fallback behavior when condensation removes everything
- Short-query padding with anchor terms
- Project term expansion for known domain vocabulary
"""

from __future__ import annotations

import pytest

from local_deepwiki.core.query_utils import condense_query, expand_project_terms


# ── condense_query ──────────────────────────────────────────────────


class TestCondenseQuery:
    def test_strips_filler_words(self):
        """Conversational filler like 'tell', 'everything', 'about' should be removed."""
        result = condense_query("tell me everything about how the rag works")
        lowered = result.lower()
        assert "tell" not in lowered.split()
        assert "everything" not in lowered.split()
        assert "rag" in lowered

    def test_preserves_technical_terms(self):
        """Pure technical queries should pass through unchanged."""
        query = "VectorStore search hybrid"
        result = condense_query(query)
        # All meaningful terms must survive
        for term in ("vectorstore", "search", "hybrid"):
            assert term in result.lower()

    def test_returns_original_when_nothing_left(self):
        """If every word is filler, return the original query (non-empty)."""
        query = "how does it work"
        result = condense_query(query)
        assert len(result) > 0

    def test_short_condensed_gets_padding(self):
        """Very short condensed queries get padding terms for embedding signal."""
        # 'rag' is the only non-filler word — condensed to 1 word, should
        # be padded with anchor terms to give the embedding model signal.
        result = condense_query("tell me about rag")
        words = result.lower().split()
        assert "rag" in words
        assert len(words) >= 3  # rag + at least 2 padding terms

    def test_no_change_when_condensation_insignificant(self):
        """If condensation barely shortens the query, return the original."""
        query = "VectorStore search hybrid retrieval pipeline"
        result = condense_query(query)
        # All words are technical, so condensation should be <=10% shorter
        # and the function should return the original
        assert result == query

    def test_empty_string(self):
        """Empty input should return empty output without error."""
        result = condense_query("")
        assert result == ""

    def test_single_filler_word(self):
        """A single filler word should still return something non-empty."""
        result = condense_query("how")
        assert len(result) > 0


# ── expand_project_terms ────────────────────────────────────────────


class TestExpandProjectTerms:
    def test_expands_handler(self):
        """'handler' should expand to include handler-specific search terms."""
        result = expand_project_terms("handler architecture")
        lowered = result.lower()
        assert "handler" in lowered
        assert "architecture" in lowered
        # Should include at least one expansion term
        assert "handle_" in lowered or "tool_handlers" in lowered

    def test_expands_provider(self):
        """'provider' should expand to include provider-specific search terms."""
        result = expand_project_terms("LLM provider setup")
        lowered = result.lower()
        assert "provider" in lowered
        # Should include at least one expansion term
        assert "llmprovider" in lowered or "get_llm_provider" in lowered

    def test_no_expansion_for_unknown(self):
        """Unknown terms should not be modified — original query preserved."""
        query = "random unknown term"
        result = expand_project_terms(query)
        # Original words must all be present
        for word in query.split():
            assert word.lower() in result.lower()

    def test_expands_indexer(self):
        """'indexer' should expand to include indexing-specific terms."""
        result = expand_project_terms("indexer pipeline")
        lowered = result.lower()
        assert "indexer" in lowered
        assert "index_repository" in lowered or "handle_index" in lowered

    def test_multiple_expansions(self):
        """Multiple recognized terms should all get expanded."""
        result = expand_project_terms("handler provider")
        lowered = result.lower()
        # Both handler and provider expansions should appear
        has_handler_expansion = "handle_" in lowered or "tool_handlers" in lowered
        has_provider_expansion = (
            "llmprovider" in lowered or "get_llm_provider" in lowered
        )
        assert has_handler_expansion
        assert has_provider_expansion

    def test_empty_string(self):
        """Empty input should return empty output."""
        result = expand_project_terms("")
        assert result == ""
