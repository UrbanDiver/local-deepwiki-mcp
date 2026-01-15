"""Tests for MCP server input validation."""

import pytest

from local_deepwiki.handlers import (
    MAX_CONTEXT_CHUNKS,
    MAX_SEARCH_LIMIT,
    MIN_CONTEXT_CHUNKS,
    MIN_SEARCH_LIMIT,
    VALID_EMBEDDING_PROVIDERS,
    VALID_LANGUAGES,
    VALID_LLM_PROVIDERS,
    _validate_language,
    _validate_languages_list,
    _validate_non_empty_string,
    _validate_positive_int,
    _validate_provider,
)


class TestValidatePositiveInt:
    """Tests for _validate_positive_int function."""

    def test_returns_default_for_none(self):
        """Test that None returns the default value."""
        result = _validate_positive_int(None, "test", 1, 100, default=10)
        assert result == 10

    def test_returns_value_within_bounds(self):
        """Test that valid values are returned unchanged."""
        result = _validate_positive_int(50, "test", 1, 100, default=10)
        assert result == 50

    def test_clamps_to_minimum(self):
        """Test that values below minimum are clamped."""
        result = _validate_positive_int(0, "test", 1, 100, default=10)
        assert result == 1

    def test_clamps_to_maximum(self):
        """Test that values above maximum are clamped."""
        result = _validate_positive_int(200, "test", 1, 100, default=10)
        assert result == 100

    def test_raises_for_non_integer(self):
        """Test that non-integer raises ValueError."""
        with pytest.raises(ValueError, match="must be an integer"):
            _validate_positive_int("not_an_int", "test", 1, 100, default=10)

    def test_raises_for_float(self):
        """Test that float raises ValueError."""
        with pytest.raises(ValueError, match="must be an integer"):
            _validate_positive_int(3.14, "test", 1, 100, default=10)


class TestValidateNonEmptyString:
    """Tests for _validate_non_empty_string function."""

    def test_returns_valid_string(self):
        """Test that valid strings are returned."""
        result = _validate_non_empty_string("hello", "test")
        assert result == "hello"

    def test_returns_string_with_whitespace(self):
        """Test that strings with content are returned."""
        result = _validate_non_empty_string("  hello  ", "test")
        assert result == "  hello  "

    def test_raises_for_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_non_empty_string("", "test")

    def test_raises_for_whitespace_only(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_non_empty_string("   ", "test")

    def test_raises_for_non_string(self):
        """Test that non-string raises ValueError."""
        with pytest.raises(ValueError, match="must be a string"):
            _validate_non_empty_string(123, "test")

    def test_raises_for_list(self):
        """Test that list raises ValueError."""
        with pytest.raises(ValueError, match="must be a string"):
            _validate_non_empty_string(["a", "b"], "test")


class TestValidateLanguage:
    """Tests for _validate_language function."""

    def test_returns_none_for_none(self):
        """Test that None input returns None."""
        result = _validate_language(None)
        assert result is None

    def test_returns_valid_language(self):
        """Test that valid language is returned."""
        result = _validate_language("python")
        assert result == "python"

    def test_accepts_all_valid_languages(self):
        """Test all valid languages are accepted."""
        for lang in VALID_LANGUAGES:
            result = _validate_language(lang)
            assert result == lang

    def test_raises_for_invalid_language(self):
        """Test that invalid language raises ValueError."""
        with pytest.raises(ValueError, match="Invalid language"):
            _validate_language("invalid_language")

    def test_error_message_shows_valid_options(self):
        """Test that error message includes valid options."""
        with pytest.raises(ValueError) as exc_info:
            _validate_language("bad")
        assert "python" in str(exc_info.value)


class TestValidateLanguagesList:
    """Tests for _validate_languages_list function."""

    def test_returns_none_for_none(self):
        """Test that None input returns None."""
        result = _validate_languages_list(None)
        assert result is None

    def test_returns_valid_list(self):
        """Test that valid list is returned."""
        result = _validate_languages_list(["python", "javascript"])
        assert result == ["python", "javascript"]

    def test_returns_empty_list(self):
        """Test that empty list is returned."""
        result = _validate_languages_list([])
        assert result == []

    def test_raises_for_invalid_language_in_list(self):
        """Test that invalid language in list raises ValueError."""
        with pytest.raises(ValueError, match="Invalid languages"):
            _validate_languages_list(["python", "invalid"])

    def test_raises_for_multiple_invalid_languages(self):
        """Test that multiple invalid languages are listed."""
        with pytest.raises(ValueError) as exc_info:
            _validate_languages_list(["bad1", "bad2"])
        error_msg = str(exc_info.value)
        assert "bad1" in error_msg
        assert "bad2" in error_msg

    def test_raises_for_non_list(self):
        """Test that non-list raises ValueError."""
        with pytest.raises(ValueError, match="must be a list"):
            _validate_languages_list("python")


class TestValidateProvider:
    """Tests for _validate_provider function."""

    def test_returns_none_for_none(self):
        """Test that None input returns None."""
        result = _validate_provider(None, {"a", "b"}, "test")
        assert result is None

    def test_returns_valid_provider(self):
        """Test that valid provider is returned."""
        result = _validate_provider("a", {"a", "b"}, "test")
        assert result == "a"

    def test_accepts_all_valid_llm_providers(self):
        """Test all valid LLM providers are accepted."""
        for provider in VALID_LLM_PROVIDERS:
            result = _validate_provider(provider, VALID_LLM_PROVIDERS, "llm_provider")
            assert result == provider

    def test_accepts_all_valid_embedding_providers(self):
        """Test all valid embedding providers are accepted."""
        for provider in VALID_EMBEDDING_PROVIDERS:
            result = _validate_provider(
                provider, VALID_EMBEDDING_PROVIDERS, "embedding_provider"
            )
            assert result == provider

    def test_raises_for_invalid_provider(self):
        """Test that invalid provider raises ValueError."""
        with pytest.raises(ValueError, match="Invalid test_provider"):
            _validate_provider("invalid", {"a", "b"}, "test_provider")

    def test_error_message_shows_valid_options(self):
        """Test that error message includes valid options."""
        with pytest.raises(ValueError) as exc_info:
            _validate_provider("bad", {"x", "y"}, "test")
        error_msg = str(exc_info.value)
        assert "x" in error_msg or "y" in error_msg


class TestValidationConstants:
    """Tests for validation constants."""

    def test_context_bounds_are_reasonable(self):
        """Test that context chunk bounds make sense."""
        assert MIN_CONTEXT_CHUNKS >= 1
        assert MAX_CONTEXT_CHUNKS <= 100
        assert MIN_CONTEXT_CHUNKS < MAX_CONTEXT_CHUNKS

    def test_search_limit_bounds_are_reasonable(self):
        """Test that search limit bounds make sense."""
        assert MIN_SEARCH_LIMIT >= 1
        assert MAX_SEARCH_LIMIT <= 1000
        assert MIN_SEARCH_LIMIT < MAX_SEARCH_LIMIT

    def test_valid_languages_not_empty(self):
        """Test that there are valid languages."""
        assert len(VALID_LANGUAGES) > 0
        assert "python" in VALID_LANGUAGES

    def test_valid_llm_providers_not_empty(self):
        """Test that there are valid LLM providers."""
        assert len(VALID_LLM_PROVIDERS) > 0
        assert "ollama" in VALID_LLM_PROVIDERS

    def test_valid_embedding_providers_not_empty(self):
        """Test that there are valid embedding providers."""
        assert len(VALID_EMBEDDING_PROVIDERS) > 0
        assert "local" in VALID_EMBEDDING_PROVIDERS
