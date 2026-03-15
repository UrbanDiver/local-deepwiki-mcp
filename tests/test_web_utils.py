"""Tests for local_deepwiki.web.utils."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from local_deepwiki.web.utils import (
    WebProviders,
    create_providers,
    create_query_service,
)


@pytest.fixture()
def _mock_providers(tmp_path: Path):
    """Patch provider factories so create_providers() works without real backends."""
    mock_config = MagicMock()
    mock_config.get_vector_db_path.return_value = tmp_path / "vectordb"
    mock_config.get_wiki_path.return_value = tmp_path / ".deepwiki"
    mock_config.embedding = MagicMock()
    mock_config.llm = MagicMock()
    mock_config.llm.model_copy.return_value = MagicMock()
    mock_config.llm_cache = MagicMock()
    mock_config.wiki.chat_llm_provider = "default"

    mock_embedding = MagicMock()
    mock_vs = MagicMock()
    mock_llm = MagicMock()

    with (
        patch("local_deepwiki.config.get_config", return_value=mock_config),
        patch(
            "local_deepwiki.providers.embeddings.get_embedding_provider",
            return_value=mock_embedding,
        ),
        patch("local_deepwiki.core.vectorstore.VectorStore", return_value=mock_vs),
        patch(
            "local_deepwiki.providers.llm.get_cached_llm_provider",
            return_value=mock_llm,
        ),
    ):
        yield {
            "config": mock_config,
            "embedding": mock_embedding,
            "vector_store": mock_vs,
            "llm": mock_llm,
        }


class TestWebProviders:
    """Tests for the WebProviders named tuple."""

    def test_namedtuple_fields(self) -> None:
        assert WebProviders._fields == ("vector_store", "llm", "config")

    def test_access_by_name(self) -> None:
        vs, llm, cfg = MagicMock(), MagicMock(), MagicMock()
        providers = WebProviders(vs, llm, cfg)
        assert providers.vector_store is vs
        assert providers.llm is llm
        assert providers.config is cfg

    def test_unpacking(self) -> None:
        vs, llm, cfg = MagicMock(), MagicMock(), MagicMock()
        v, l, c = WebProviders(vs, llm, cfg)
        assert v is vs
        assert l is llm
        assert c is cfg


class TestCreateProviders:
    """Tests for create_providers()."""

    @pytest.mark.usefixtures("_mock_providers")
    def test_returns_web_providers(self, _mock_providers, tmp_path: Path) -> None:
        result = create_providers(tmp_path)
        assert isinstance(result, WebProviders)
        assert result.vector_store is _mock_providers["vector_store"]
        assert result.llm is _mock_providers["llm"]
        assert result.config is _mock_providers["config"]

    @pytest.mark.usefixtures("_mock_providers")
    def test_default_provider_no_model_copy(
        self, _mock_providers, tmp_path: Path
    ) -> None:
        """When chat_llm_provider is 'default', llm config is used as-is."""
        _mock_providers["config"].wiki.chat_llm_provider = "default"
        create_providers(tmp_path)
        _mock_providers["config"].llm.model_copy.assert_not_called()

    @pytest.mark.usefixtures("_mock_providers")
    def test_chat_provider_override(self, _mock_providers, tmp_path: Path) -> None:
        """When chat_llm_provider is not 'default', llm_config is overridden."""
        _mock_providers["config"].wiki.chat_llm_provider = "anthropic"
        create_providers(tmp_path)
        _mock_providers["config"].llm.model_copy.assert_called_once_with(
            update={"provider": "anthropic"}
        )


class TestCreateQueryService:
    """Tests for create_query_service()."""

    @pytest.mark.usefixtures("_mock_providers")
    def test_delegates_to_create_providers(
        self, _mock_providers, tmp_path: Path
    ) -> None:
        with patch(
            "local_deepwiki.services.query_service.QueryService"
        ) as mock_qs_class:
            result = create_query_service(tmp_path)
            mock_qs_class.assert_called_once_with(
                _mock_providers["vector_store"],
                _mock_providers["llm"],
                _mock_providers["config"],
            )
            assert result is mock_qs_class.return_value
