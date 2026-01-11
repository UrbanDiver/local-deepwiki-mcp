"""Tests for configuration."""

from pathlib import Path

import pytest

from local_deepwiki.config import Config, get_config, set_config


class TestConfig:
    """Test suite for Config."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()

        assert config.embedding.provider == "local"
        assert config.llm.provider == "ollama"
        assert "python" in config.parsing.languages
        assert config.chunking.max_chunk_tokens == 512

    def test_embedding_config(self):
        """Test embedding configuration."""
        config = Config()

        assert config.embedding.local.model == "all-MiniLM-L6-v2"
        assert config.embedding.openai.model == "text-embedding-3-small"

    def test_llm_config(self):
        """Test LLM configuration."""
        config = Config()

        assert config.llm.ollama.model == "qwen3-coder:30b"
        assert config.llm.ollama.base_url == "http://localhost:11434"
        assert config.llm.anthropic.model == "claude-sonnet-4-20250514"
        assert config.llm.openai.model == "gpt-4o"

    def test_parsing_config(self):
        """Test parsing configuration."""
        config = Config()

        assert "node_modules/**" in config.parsing.exclude_patterns
        assert config.parsing.max_file_size == 1048576

    def test_get_wiki_path(self, tmp_path):
        """Test wiki path generation."""
        config = Config()
        wiki_path = config.get_wiki_path(tmp_path)

        assert wiki_path == tmp_path / ".deepwiki"

    def test_get_vector_db_path(self, tmp_path):
        """Test vector database path generation."""
        config = Config()
        db_path = config.get_vector_db_path(tmp_path)

        assert db_path == tmp_path / ".deepwiki" / "vectors.lance"

    def test_global_config(self):
        """Test global config singleton."""
        config1 = get_config()
        config2 = get_config()

        # Should return the same instance
        assert config1 is config2

    def test_set_config(self):
        """Test setting global config."""
        new_config = Config()
        new_config.chunking.max_chunk_tokens = 1024

        set_config(new_config)
        retrieved = get_config()

        assert retrieved.chunking.max_chunk_tokens == 1024

        # Reset to default
        set_config(Config())
