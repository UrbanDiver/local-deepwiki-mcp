"""Comprehensive tests for CredentialManager to achieve 95%+ coverage.

Tests cover:
- get_api_key: Environment variable retrieval, missing keys, key validation
- validate_key_format: Provider-specific validation (anthropic, openai, generic)
- Test key handling: Short test keys, various test key patterns
- Edge cases: Empty strings, None values, boundary conditions
"""

import os
from unittest.mock import patch

import pytest

from local_deepwiki.providers.credentials import CredentialManager


class TestGetApiKey:
    """Tests for CredentialManager.get_api_key method."""

    def test_get_api_key_returns_key_from_environment(self):
        """Test that get_api_key returns the key from environment variable."""
        with patch.dict(os.environ, {"TEST_API_KEY": "valid-api-key-12345"}):
            result = CredentialManager.get_api_key("TEST_API_KEY", "test-provider")
            assert result == "valid-api-key-12345"

    def test_get_api_key_returns_none_when_not_set(self):
        """Test that get_api_key returns None when env var is not set."""
        # Ensure the env var is not set
        env_copy = os.environ.copy()
        env_copy.pop("NONEXISTENT_API_KEY", None)
        with patch.dict(os.environ, env_copy, clear=True):
            result = CredentialManager.get_api_key("NONEXISTENT_API_KEY", "test-provider")
            assert result is None

    def test_get_api_key_returns_none_for_empty_string(self):
        """Test that get_api_key returns None for empty string."""
        with patch.dict(os.environ, {"EMPTY_API_KEY": ""}):
            result = CredentialManager.get_api_key("EMPTY_API_KEY", "test-provider")
            assert result is None

    def test_get_api_key_raises_for_too_short_key(self):
        """Test that get_api_key raises ValueError for keys shorter than 4 chars."""
        with patch.dict(os.environ, {"SHORT_API_KEY": "abc"}):
            with pytest.raises(ValueError) as exc_info:
                CredentialManager.get_api_key("SHORT_API_KEY", "my-provider")

            assert "my-provider" in str(exc_info.value)
            assert "too short" in str(exc_info.value)

    def test_get_api_key_accepts_exactly_4_char_key(self):
        """Test that get_api_key accepts keys with exactly 4 characters."""
        with patch.dict(os.environ, {"FOUR_CHAR_KEY": "abcd"}):
            result = CredentialManager.get_api_key("FOUR_CHAR_KEY", "test-provider")
            assert result == "abcd"

    def test_get_api_key_accepts_long_key(self):
        """Test that get_api_key accepts long keys."""
        long_key = "sk-ant-" + "a" * 100
        with patch.dict(os.environ, {"LONG_API_KEY": long_key}):
            result = CredentialManager.get_api_key("LONG_API_KEY", "anthropic")
            assert result == long_key

    def test_get_api_key_raises_for_single_char_key(self):
        """Test that get_api_key raises ValueError for single character key."""
        with patch.dict(os.environ, {"SINGLE_CHAR_KEY": "x"}):
            with pytest.raises(ValueError) as exc_info:
                CredentialManager.get_api_key("SINGLE_CHAR_KEY", "provider")

            assert "invalid" in str(exc_info.value).lower()
            assert "too short" in str(exc_info.value)

    def test_get_api_key_raises_for_two_char_key(self):
        """Test that get_api_key raises ValueError for two character key."""
        with patch.dict(os.environ, {"TWO_CHAR_KEY": "xy"}):
            with pytest.raises(ValueError) as exc_info:
                CredentialManager.get_api_key("TWO_CHAR_KEY", "provider")

            assert "too short" in str(exc_info.value)

    def test_get_api_key_raises_for_three_char_key(self):
        """Test that get_api_key raises ValueError for three character key."""
        with patch.dict(os.environ, {"THREE_CHAR_KEY": "xyz"}):
            with pytest.raises(ValueError) as exc_info:
                CredentialManager.get_api_key("THREE_CHAR_KEY", "test")

            assert "too short" in str(exc_info.value)

    def test_get_api_key_provider_name_in_error_message(self):
        """Test that provider name appears in error message."""
        with patch.dict(os.environ, {"BAD_KEY": "ab"}):
            with pytest.raises(ValueError) as exc_info:
                CredentialManager.get_api_key("BAD_KEY", "custom-provider-name")

            assert "custom-provider-name" in str(exc_info.value)


class TestValidateKeyFormat:
    """Tests for CredentialManager.validate_key_format method."""

    # ----- Test Key Handling -----

    def test_validate_key_format_accepts_test_key_literal(self):
        """Test that 'test-key' is accepted as valid."""
        result = CredentialManager.validate_key_format("test-key", "anthropic")
        assert result is True

    def test_validate_key_format_accepts_test_literal(self):
        """Test that 'test' is accepted as valid."""
        result = CredentialManager.validate_key_format("test", "openai")
        assert result is True

    def test_validate_key_format_accepts_custom_key_literal(self):
        """Test that 'custom-key' is accepted as valid."""
        result = CredentialManager.validate_key_format("custom-key", "anthropic")
        assert result is True

    def test_validate_key_format_accepts_test_prefix(self):
        """Test that keys starting with 'test-' are accepted."""
        result = CredentialManager.validate_key_format("test-abc123", "openai")
        assert result is True

    def test_validate_key_format_accepts_test_hyphen_only(self):
        """Test that 'test-' prefix with any suffix is accepted."""
        result = CredentialManager.validate_key_format("test-", "generic")
        assert result is True

    def test_validate_key_format_test_key_for_any_provider(self):
        """Test that test keys work for any provider."""
        providers = ["anthropic", "openai", "other", "unknown", ""]
        for provider in providers:
            assert CredentialManager.validate_key_format("test-key", provider) is True
            assert CredentialManager.validate_key_format("test", provider) is True
            assert CredentialManager.validate_key_format("custom-key", provider) is True
            assert CredentialManager.validate_key_format("test-xyz", provider) is True

    # ----- Anthropic Provider Validation -----

    def test_validate_key_format_anthropic_valid_key(self):
        """Test valid Anthropic API key format."""
        # Valid Anthropic keys start with 'sk-ant-' and are >20 chars
        valid_key = "sk-ant-" + "a" * 30  # 37 chars total
        result = CredentialManager.validate_key_format(valid_key, "anthropic")
        assert result is True

    def test_validate_key_format_anthropic_short_but_valid_prefix(self):
        """Test Anthropic key with valid prefix but short length still passes (>=4 chars)."""
        # 'sk-ant-x' is 8 chars but only 1 char after prefix (not >20 total)
        # However, the fallback len(key) >= 4 applies
        short_key = "sk-ant-x"  # 8 chars
        result = CredentialManager.validate_key_format(short_key, "anthropic")
        # This passes because len("sk-ant-x") >= 4, even though it's not >20
        assert result is True

    def test_validate_key_format_anthropic_invalid_prefix(self):
        """Test Anthropic key with wrong prefix but valid length."""
        # Wrong prefix, but >=4 chars
        wrong_prefix = "sk-xyz-" + "a" * 30
        result = CredentialManager.validate_key_format(wrong_prefix, "anthropic")
        # Falls back to len(key) >= 4, which is True
        assert result is True

    def test_validate_key_format_anthropic_too_short(self):
        """Test Anthropic key that is too short."""
        # Less than 4 chars, not a test key
        result = CredentialManager.validate_key_format("abc", "anthropic")
        assert result is False

    def test_validate_key_format_anthropic_exactly_4_chars(self):
        """Test Anthropic key with exactly 4 chars (boundary)."""
        result = CredentialManager.validate_key_format("abcd", "anthropic")
        assert result is True

    def test_validate_key_format_anthropic_proper_key_21_chars(self):
        """Test Anthropic key with proper prefix and >20 chars."""
        # 'sk-ant-' is 7 chars, need >20 total, so need >=14 more
        key = "sk-ant-" + "x" * 14  # 21 chars total
        result = CredentialManager.validate_key_format(key, "anthropic")
        assert result is True

    def test_validate_key_format_anthropic_exactly_20_chars(self):
        """Test Anthropic key with proper prefix but exactly 20 chars (boundary)."""
        # 'sk-ant-' is 7 chars, need 13 more for 20 total
        key = "sk-ant-" + "x" * 13  # 20 chars total
        result = CredentialManager.validate_key_format(key, "anthropic")
        # Not >20, but len >= 4, so falls back to True
        assert result is True

    # ----- OpenAI Provider Validation -----

    def test_validate_key_format_openai_valid_key(self):
        """Test valid OpenAI API key format."""
        # Valid OpenAI keys start with 'sk-' and are >20 chars
        valid_key = "sk-" + "a" * 30  # 33 chars total
        result = CredentialManager.validate_key_format(valid_key, "openai")
        assert result is True

    def test_validate_key_format_openai_short_but_valid_prefix(self):
        """Test OpenAI key with valid prefix but short length still passes."""
        short_key = "sk-xyz"  # 6 chars, not >20
        result = CredentialManager.validate_key_format(short_key, "openai")
        # Falls back to len(key) >= 4
        assert result is True

    def test_validate_key_format_openai_invalid_prefix(self):
        """Test OpenAI key with wrong prefix but valid length."""
        wrong_prefix = "pk-" + "a" * 30
        result = CredentialManager.validate_key_format(wrong_prefix, "openai")
        # Falls back to len(key) >= 4
        assert result is True

    def test_validate_key_format_openai_too_short(self):
        """Test OpenAI key that is too short."""
        result = CredentialManager.validate_key_format("xyz", "openai")
        assert result is False

    def test_validate_key_format_openai_exactly_4_chars(self):
        """Test OpenAI key with exactly 4 chars (boundary)."""
        result = CredentialManager.validate_key_format("sk-x", "openai")
        assert result is True

    def test_validate_key_format_openai_proper_key_21_chars(self):
        """Test OpenAI key with proper prefix and >20 chars."""
        # 'sk-' is 3 chars, need >20 total, so need >=18 more
        key = "sk-" + "x" * 18  # 21 chars total
        result = CredentialManager.validate_key_format(key, "openai")
        assert result is True

    def test_validate_key_format_openai_exactly_20_chars(self):
        """Test OpenAI key with proper prefix but exactly 20 chars."""
        # 'sk-' is 3 chars, need 17 more for 20 total
        key = "sk-" + "x" * 17  # 20 chars total
        result = CredentialManager.validate_key_format(key, "openai")
        # Not >20, but len >= 4
        assert result is True

    # ----- Generic/Other Provider Validation -----

    def test_validate_key_format_generic_valid_key(self):
        """Test valid key for generic/unknown provider."""
        result = CredentialManager.validate_key_format("valid-key-1234", "other")
        assert result is True

    def test_validate_key_format_generic_too_short(self):
        """Test key that is too short for generic provider."""
        result = CredentialManager.validate_key_format("abc", "unknown")
        assert result is False

    def test_validate_key_format_generic_exactly_4_chars(self):
        """Test generic key with exactly 4 chars."""
        result = CredentialManager.validate_key_format("abcd", "random")
        assert result is True

    def test_validate_key_format_empty_provider_name(self):
        """Test with empty provider name (falls to generic validation)."""
        result = CredentialManager.validate_key_format("valid-key", "")
        assert result is True

    def test_validate_key_format_none_like_provider_name(self):
        """Test with unusual provider names."""
        result = CredentialManager.validate_key_format("valid-key", "none")
        assert result is True

    # ----- Edge Cases -----

    def test_validate_key_format_empty_key(self):
        """Test empty key string."""
        result = CredentialManager.validate_key_format("", "anthropic")
        assert result is False

    def test_validate_key_format_single_char_key(self):
        """Test single character key."""
        result = CredentialManager.validate_key_format("a", "openai")
        assert result is False

    def test_validate_key_format_two_char_key(self):
        """Test two character key."""
        result = CredentialManager.validate_key_format("ab", "generic")
        assert result is False

    def test_validate_key_format_three_char_key(self):
        """Test three character key."""
        result = CredentialManager.validate_key_format("abc", "other")
        assert result is False

    def test_validate_key_format_whitespace_only(self):
        """Test key with only whitespace."""
        # 4 spaces is >= 4 chars, so it passes length check
        result = CredentialManager.validate_key_format("    ", "anthropic")
        assert result is True  # Length check passes, no content validation

    def test_validate_key_format_key_with_special_chars(self):
        """Test key with special characters."""
        result = CredentialManager.validate_key_format("key!@#$%^&*()", "openai")
        assert result is True  # Length is sufficient

    def test_validate_key_format_very_long_key(self):
        """Test very long key."""
        long_key = "x" * 10000
        result = CredentialManager.validate_key_format(long_key, "anthropic")
        assert result is True

    def test_validate_key_format_key_with_newlines(self):
        """Test key with newlines."""
        result = CredentialManager.validate_key_format("key\nwith\nnewlines", "openai")
        assert result is True  # Length is sufficient

    def test_validate_key_format_unicode_key(self):
        """Test key with unicode characters."""
        result = CredentialManager.validate_key_format("key-" + "\u00e9" * 10, "generic")
        assert result is True

    def test_validate_key_format_sk_ant_exactly_prefix(self):
        """Test 'sk-ant-' alone (7 chars, not >20)."""
        result = CredentialManager.validate_key_format("sk-ant-", "anthropic")
        # 7 chars >= 4, so passes fallback
        assert result is True

    def test_validate_key_format_sk_alone(self):
        """Test 'sk-' alone for OpenAI (3 chars, not >= 4)."""
        result = CredentialManager.validate_key_format("sk-", "openai")
        assert result is False  # 3 chars < 4

    def test_validate_key_format_case_sensitivity_prefix(self):
        """Test that prefix matching is case-sensitive."""
        # 'SK-ANT-' is not 'sk-ant-'
        upper_key = "SK-ANT-" + "x" * 30
        result = CredentialManager.validate_key_format(upper_key, "anthropic")
        # Falls back to len(key) >= 4
        assert result is True

    def test_validate_key_format_case_sensitivity_provider(self):
        """Test provider name matching is case-sensitive."""
        # 'ANTHROPIC' is not 'anthropic'
        result = CredentialManager.validate_key_format("sk-ant-" + "x" * 30, "ANTHROPIC")
        # Provider 'ANTHROPIC' doesn't match 'anthropic', falls to generic
        assert result is True

    def test_validate_key_format_provider_with_whitespace(self):
        """Test provider name with whitespace (doesn't match any specific)."""
        result = CredentialManager.validate_key_format("valid-key-1234", " anthropic ")
        # Doesn't match 'anthropic' exactly, falls to generic
        assert result is True


class TestCredentialManagerStaticBehavior:
    """Tests verifying CredentialManager's static method behavior."""

    def test_credential_manager_methods_are_static(self):
        """Test that both methods are static and don't require instance."""
        # These should not require instantiation
        assert callable(CredentialManager.get_api_key)
        assert callable(CredentialManager.validate_key_format)

    def test_credential_manager_can_be_called_without_instance(self):
        """Test methods can be called directly on class."""
        with patch.dict(os.environ, {"TEST_KEY": "valid-key"}):
            result = CredentialManager.get_api_key("TEST_KEY", "provider")
            assert result == "valid-key"

        result = CredentialManager.validate_key_format("test-key", "provider")
        assert result is True

    def test_credential_manager_instance_can_call_static_methods(self):
        """Test that instance can also call static methods (Python behavior)."""
        manager = CredentialManager()
        result = manager.validate_key_format("test-key", "provider")
        assert result is True


class TestIntegrationScenarios:
    """Integration-style tests combining get_api_key and validate_key_format."""

    def test_full_anthropic_flow_valid(self):
        """Test full Anthropic credential flow with valid key."""
        valid_key = "sk-ant-api3xxxxxxxxxxxxxxxxxxxx"  # >20 chars
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": valid_key}):
            key = CredentialManager.get_api_key("ANTHROPIC_API_KEY", "anthropic")
            assert key == valid_key
            assert CredentialManager.validate_key_format(key, "anthropic") is True

    def test_full_openai_flow_valid(self):
        """Test full OpenAI credential flow with valid key."""
        valid_key = "sk-proj-xxxxxxxxxxxxxxxxxxxx"  # >20 chars
        with patch.dict(os.environ, {"OPENAI_API_KEY": valid_key}):
            key = CredentialManager.get_api_key("OPENAI_API_KEY", "openai")
            assert key == valid_key
            assert CredentialManager.validate_key_format(key, "openai") is True

    def test_full_flow_with_test_key(self):
        """Test full flow with test key for both providers."""
        with patch.dict(os.environ, {"API_KEY": "test-key"}):
            key = CredentialManager.get_api_key("API_KEY", "anthropic")
            assert key == "test-key"
            assert CredentialManager.validate_key_format(key, "anthropic") is True
            assert CredentialManager.validate_key_format(key, "openai") is True
            assert CredentialManager.validate_key_format(key, "generic") is True

    def test_missing_key_flow(self):
        """Test flow when key is missing."""
        env_copy = os.environ.copy()
        env_copy.pop("MISSING_KEY", None)
        with patch.dict(os.environ, env_copy, clear=True):
            key = CredentialManager.get_api_key("MISSING_KEY", "provider")
            assert key is None
            # Can't validate None, this simulates the provider check
            # In real usage, provider would raise error for None key

    def test_invalid_key_flow(self):
        """Test flow with invalid short key."""
        with patch.dict(os.environ, {"BAD_KEY": "xy"}):
            with pytest.raises(ValueError) as exc_info:
                CredentialManager.get_api_key("BAD_KEY", "provider")
            assert "too short" in str(exc_info.value)
