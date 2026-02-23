"""Tests for partial failure warning propagation in wiki generation."""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from local_deepwiki.generators.wiki.generator import WikiGenerator, _GenerationContext
from local_deepwiki.models import IndexStatus, WikiPage


def _make_index_status(repo_path: str = "/tmp/repo") -> IndexStatus:
    """Create a minimal IndexStatus for testing."""
    return IndexStatus(
        repo_path=repo_path,
        indexed_at=time.time(),
        total_files=1,
        total_chunks=1,
        languages={"python": 1},
        files=[],
    )


class TestGenerationContextWarnings:
    """Tests for _GenerationContext.warnings field."""

    def test_warnings_defaults_to_empty_list(self) -> None:
        """New _GenerationContext has an empty warnings list."""
        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=[],
            full_rebuild=False,
        )

        assert ctx.warnings == []
        assert isinstance(ctx.warnings, list)

    def test_warnings_can_be_appended(self) -> None:
        """Warnings can be appended to the context."""
        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=[],
            full_rebuild=False,
        )

        ctx.warnings.append("test warning")
        ctx.warnings.append("another warning")

        assert len(ctx.warnings) == 2
        assert ctx.warnings[0] == "test warning"


def _make_generator(tmp_path: Path) -> WikiGenerator:
    """Create a WikiGenerator with mocked internals for testing."""
    mock_vector_store = MagicMock()
    mock_vector_store.search = AsyncMock(return_value=[])
    mock_vector_store.embedding_provider = MagicMock()

    wiki_path = tmp_path / "wiki"
    wiki_path.mkdir(exist_ok=True)

    generator = WikiGenerator.__new__(WikiGenerator)
    generator.wiki_path = wiki_path
    generator.vector_store = mock_vector_store
    generator.status_manager = MagicMock()
    generator.status_manager.page_statuses = {}
    generator._write_page = AsyncMock()

    return generator


class TestDependencyGraphFailureWarning:
    """Tests that dependency graph failure is recorded in context warnings."""

    async def test_dependency_graph_failure_records_warning(
        self, tmp_path: Path
    ) -> None:
        """Failed dependency graph generation stores warning in ctx."""
        generator = _make_generator(tmp_path)

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=["src/test.py"],
            full_rebuild=True,
        )

        index_status = _make_index_status(str(tmp_path))

        with (
            patch(
                "local_deepwiki.generators.wiki.generator.generate_inheritance_page",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "local_deepwiki.generators.wiki.generator.generate_glossary_page",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "local_deepwiki.generators.wiki.generator.generate_coverage_page",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "local_deepwiki.generators.wiki.generator.generate_dependency_graph_page",
                new_callable=AsyncMock,
                side_effect=RuntimeError("graph computation failed"),
            ),
        ):
            await generator._generate_auxiliary_pages(ctx, index_status, None)

        # Dependency graph failure should be recorded
        dep_warnings = [w for w in ctx.warnings if "Dependency graph" in w]
        assert len(dep_warnings) == 1
        assert "graph computation failed" in dep_warnings[0]

    async def test_generation_completes_despite_dep_graph_failure(
        self, tmp_path: Path
    ) -> None:
        """Wiki generation continues even if dependency graph fails."""
        generator = _make_generator(tmp_path)

        ctx = _GenerationContext(
            pages=[],
            pages_generated=0,
            pages_skipped=0,
            all_source_files=["src/test.py"],
            full_rebuild=True,
        )

        index_status = _make_index_status(str(tmp_path))

        with (
            patch(
                "local_deepwiki.generators.wiki.generator.generate_inheritance_page",
                new_callable=AsyncMock,
                return_value="# Inheritance\n",
            ),
            patch(
                "local_deepwiki.generators.wiki.generator.generate_glossary_page",
                new_callable=AsyncMock,
                return_value="# Glossary\n",
            ),
            patch(
                "local_deepwiki.generators.wiki.generator.generate_coverage_page",
                new_callable=AsyncMock,
                return_value="# Coverage\n",
            ),
            patch(
                "local_deepwiki.generators.wiki.generator.generate_dependency_graph_page",
                new_callable=AsyncMock,
                side_effect=RuntimeError("graph computation failed"),
            ),
        ):
            # Should not raise
            await generator._generate_auxiliary_pages(ctx, index_status, None)

        # Pages from the successful generators should still be recorded
        assert ctx.pages_generated >= 3
        assert len(ctx.warnings) == 1


class TestProgressTrackerWarnings:
    """Tests that progress tracker persists generation warnings."""

    def test_finalize_writes_warnings_to_status(self, tmp_path: Path) -> None:
        """Warnings are written to generation_status.json via finalize."""
        from local_deepwiki.generators.progress_tracker import GenerationProgress

        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=0)

        warnings = [
            "Dependency graph generation failed: timeout",
            "Caller search failed for 'my_func': connection error",
        ]

        progress.finalize(success=True, warnings=warnings)

        status_path = tmp_path / "generation_status.json"
        assert status_path.exists()

        with open(status_path) as f:
            status = json.load(f)

        assert "generation_warnings" in status
        assert len(status["generation_warnings"]) == 2
        assert "timeout" in status["generation_warnings"][0]

    def test_finalize_omits_warnings_key_when_none(self, tmp_path: Path) -> None:
        """When no warnings, generation_warnings key is absent."""
        from local_deepwiki.generators.progress_tracker import GenerationProgress

        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=0)

        progress.finalize(success=True)

        status_path = tmp_path / "generation_status.json"
        with open(status_path) as f:
            status = json.load(f)

        assert "generation_warnings" not in status

    def test_finalize_omits_warnings_key_when_empty(self, tmp_path: Path) -> None:
        """When warnings list is empty, generation_warnings key is absent."""
        from local_deepwiki.generators.progress_tracker import GenerationProgress

        progress = GenerationProgress(wiki_path=tmp_path)
        progress.start_phase("test", total=0)

        progress.finalize(success=True, warnings=[])

        status_path = tmp_path / "generation_status.json"
        with open(status_path) as f:
            status = json.load(f)

        assert "generation_warnings" not in status
