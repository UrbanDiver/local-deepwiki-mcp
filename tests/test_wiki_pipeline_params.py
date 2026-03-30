"""Tests for WikiPipelineParams frozen dataclass."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from conftest import make_wiki_ctx
from local_deepwiki.generators.wiki.pipeline_params import WikiPipelineParams


class TestWikiPipelineParamsConstruction:
    """Test construction and field access on WikiPipelineParams."""

    def _make_params(self, **overrides):
        """Build a WikiPipelineParams with sensible defaults."""
        ctx = overrides.pop("ctx", make_wiki_ctx())
        write_callback = overrides.pop("write_callback", AsyncMock())
        progress_callback = overrides.pop("progress_callback", None)
        all_source_files = overrides.pop("all_source_files", None)
        return WikiPipelineParams(
            ctx=ctx,
            write_callback=write_callback,
            progress_callback=progress_callback,
            all_source_files=all_source_files,
        )

    def test_creates_with_required_fields(self):
        params = self._make_params()
        assert params.ctx is not None
        assert params.write_callback is not None

    def test_progress_callback_defaults_to_none(self):
        params = self._make_params()
        assert params.progress_callback is None

    def test_all_source_files_defaults_to_none(self):
        params = self._make_params()
        assert params.all_source_files is None

    def test_fields_are_accessible(self):
        ctx = make_wiki_ctx(repo_path=Path("/tmp/repo"))
        write_cb = AsyncMock()

        def progress_cb(msg, current, total):
            pass

        source_files = ["src/main.py", "src/utils.py"]

        params = WikiPipelineParams(
            ctx=ctx,
            write_callback=write_cb,
            progress_callback=progress_cb,
            all_source_files=source_files,
        )

        assert params.ctx is ctx
        assert params.write_callback is write_cb
        assert params.progress_callback is progress_cb
        assert params.all_source_files == ["src/main.py", "src/utils.py"]

    def test_context_fields_accessible_through_ctx(self):
        """Verify that pipeline context fields are reachable via params.ctx."""
        repo_path = Path("/tmp/test-repo")
        wiki_path = Path("/tmp/wiki")
        llm = AsyncMock()
        vs = AsyncMock()
        status_mgr = MagicMock()

        ctx = make_wiki_ctx(
            repo_path=repo_path,
            wiki_path=wiki_path,
            llm=llm,
            vector_store=vs,
            status_manager=status_mgr,
        )
        params = self._make_params(ctx=ctx)

        assert params.ctx.repo_path == repo_path
        assert params.ctx.wiki_path == wiki_path
        assert params.ctx.llm is llm
        assert params.ctx.vector_store is vs
        assert params.ctx.status_manager is status_mgr


class TestWikiPipelineParamsImmutability:
    """Verify that WikiPipelineParams is truly frozen."""

    def _make_params(self):
        return WikiPipelineParams(
            ctx=make_wiki_ctx(),
            write_callback=AsyncMock(),
        )

    def test_cannot_set_ctx(self):
        params = self._make_params()
        try:
            params.ctx = make_wiki_ctx()  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass

    def test_cannot_set_write_callback(self):
        params = self._make_params()
        try:
            params.write_callback = AsyncMock()  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass

    def test_cannot_set_progress_callback(self):
        params = self._make_params()
        try:
            params.progress_callback = MagicMock()  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass

    def test_cannot_set_all_source_files(self):
        params = self._make_params()
        try:
            params.all_source_files = ["x.py"]  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass


class TestWikiPipelineParamsUsesSlots:
    """Confirm slots are used for memory efficiency."""

    def test_has_slots(self):
        assert hasattr(WikiPipelineParams, "__slots__")

    def test_no_dict(self):
        params = WikiPipelineParams(
            ctx=make_wiki_ctx(),
            write_callback=AsyncMock(),
        )
        assert not hasattr(params, "__dict__")


class TestWikiPipelineParamsEquality:
    """Frozen dataclasses support structural equality by default."""

    def test_equal_instances(self):
        ctx = make_wiki_ctx()
        write_cb = AsyncMock()
        a = WikiPipelineParams(ctx=ctx, write_callback=write_cb)
        b = WikiPipelineParams(ctx=ctx, write_callback=write_cb)
        assert a == b

    def test_different_callbacks_not_equal(self):
        ctx = make_wiki_ctx()
        a = WikiPipelineParams(ctx=ctx, write_callback=AsyncMock())
        b = WikiPipelineParams(ctx=ctx, write_callback=AsyncMock())
        assert a != b
