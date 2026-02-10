"""Comprehensive tests for CredentialManager to achieve 95%+ coverage.

Tests cover:
- get_api_key: Environment variable retrieval, missing keys, key validation
- validate_key_format: Provider-specific validation (anthropic, openai, generic)
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
        env_copy = os.environ.copy()
        env_copy.pop("NONEXISTENT_API_KEY", None)
        with patch.dict(os.environ, env_copy, clear=True):
            result = CredentialManager.get_api_key(
                "NONEXISTENT_API_KEY", "test-provider"
            )
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
    """Tests for CredentialManager.validate_key_format method.

    Strict provider-specific validation:
    - Anthropic: must start with 'sk-ant-' AND len > 20
    - OpenAI: must start with 'sk-' AND len > 20
    - Generic: must have len >= 8
    """

    # ----- Anthropic Provider Validation -----

    def test_validate_key_format_anthropic_valid_key(self):
        """Test valid Anthropic API key format."""
        valid_key = "sk-ant-" + "a" * 30  # 37 chars total
        result = CredentialManager.validate_key_format(valid_key, "anthropic")
        assert result is True

    def test_validate_key_format_anthropic_short_with_valid_prefix(self):
        """Test Anthropic key with valid prefix but too short (not >20)."""
        short_key = "sk-ant-x"  # 8 chars, not >20
        result = CredentialManager.validate_key_format(short_key, "anthropic")
        assert result is False

    def test_validate_key_format_anthropic_invalid_prefix(self):
        """Test Anthropic key with wrong prefix fails even with valid length."""
        wrong_prefix = "sk-xyz-" + "a" * 30
        result = CredentialManager.validate_key_format(wrong_prefix, "anthropic")
        assert result is False

    def test_validate_key_format_anthropic_too_short(self):
        """Test Anthropic key that is too short (<4 chars)."""
        result = CredentialManager.validate_key_format("abc", "anthropic")
        assert result is False

    def test_validate_key_format_anthropic_4_chars_no_prefix(self):
        """Test Anthropic key with 4 chars but wrong prefix fails."""
        result = CredentialManager.validate_key_format("abcd", "anthropic")
        assert result is False

    def test_validate_key_format_anthropic_proper_key_21_chars(self):
        """Test Anthropic key with proper prefix and >20 chars."""
        key = "sk-ant-" + "x" * 14  # 21 chars total
        result = CredentialManager.validate_key_format(key, "anthropic")
        assert result is True

    def test_validate_key_format_anthropic_exactly_20_chars(self):
        """Test Anthropic key with proper prefix but exactly 20 chars (boundary, not >20)."""
        key = "sk-ant-" + "x" * 13  # 20 chars total
        result = CredentialManager.validate_key_format(key, "anthropic")
        assert result is False

    # ----- OpenAI Provider Validation -----

    def test_validate_key_format_openai_valid_key(self):
        """Test valid OpenAI API key format."""
        valid_key = "sk-" + "a" * 30  # 33 chars total
        result = CredentialManager.validate_key_format(valid_key, "openai")
        assert result is True

    def test_validate_key_format_openai_short_with_valid_prefix(self):
        """Test OpenAI key with valid prefix but too short (not >20)."""
        short_key = "sk-xyz"  # 6 chars, not >20
        result = CredentialManager.validate_key_format(short_key, "openai")
        assert result is False

    def test_validate_key_format_openai_invalid_prefix(self):
        """Test OpenAI key with wrong prefix fails even with valid length."""
        wrong_prefix = "pk-" + "a" * 30
        result = CredentialManager.validate_key_format(wrong_prefix, "openai")
        assert result is False

    def test_validate_key_format_openai_too_short(self):
        """Test OpenAI key that is too short (<4 chars)."""
        result = CredentialManager.validate_key_format("xyz", "openai")
        assert result is False

    def test_validate_key_format_openai_4_chars_with_prefix(self):
        """Test OpenAI key 'sk-x' (4 chars, valid prefix but not >20)."""
        result = CredentialManager.validate_key_format("sk-x", "openai")
        assert result is False

    def test_validate_key_format_openai_proper_key_21_chars(self):
        """Test OpenAI key with proper prefix and >20 chars."""
        key = "sk-" + "x" * 18  # 21 chars total
        result = CredentialManager.validate_key_format(key, "openai")
        assert result is True

    def test_validate_key_format_openai_exactly_20_chars(self):
        """Test OpenAI key with proper prefix but exactly 20 chars (boundary, not >20)."""
        key = "sk-" + "x" * 17  # 20 chars total
        result = CredentialManager.validate_key_format(key, "openai")
        assert result is False

    # ----- Generic/Other Provider Validation -----

    def test_validate_key_format_generic_valid_key(self):
        """Test valid key for generic/unknown provider (>=8 chars)."""
        result = CredentialManager.validate_key_format("valid-key-1234", "other")
        assert result is True

    def test_validate_key_format_generic_too_short(self):
        """Test key that is too short for generic provider (<8 chars)."""
        result = CredentialManager.validate_key_format("abc", "unknown")
        assert result is False

    def test_validate_key_format_generic_exactly_8_chars(self):
        """Test generic key with exactly 8 chars (boundary)."""
        result = CredentialManager.validate_key_format("abcdefgh", "random")
        assert result is True

    def test_validate_key_format_generic_7_chars(self):
        """Test generic key with 7 chars (just below minimum)."""
        result = CredentialManager.validate_key_format("abcdefg", "random")
        assert result is False

    def test_validate_key_format_generic_4_chars(self):
        """Test generic key with 4 chars (below min 8)."""
        result = CredentialManager.validate_key_format("abcd", "random")
        assert result is False

    def test_validate_key_format_empty_provider_name(self):
        """Test with empty provider name (falls to generic validation)."""
        result = CredentialManager.validate_key_format("valid-key-longkey", "")
        assert result is True

    def test_validate_key_format_none_like_provider_name(self):
        """Test with unusual provider names (generic path)."""
        result = CredentialManager.validate_key_format("valid-key-longkey", "none")
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
        """Test key with only whitespace (4 spaces, passes len check but not format)."""
        # 4 spaces >= 4 but not >= 8, and doesn't start with sk-ant- or sk-
        result = CredentialManager.validate_key_format("    ", "anthropic")
        assert result is False  # No sk-ant- prefix

    def test_validate_key_format_whitespace_generic(self):
        """Test key with whitespace for generic provider (needs >=8)."""
        result = CredentialManager.validate_key_format("        ", "generic")
        assert result is True  # 8 spaces >= 8

    def test_validate_key_format_key_with_special_chars(self):
        """Test key with special characters for generic (>=8 chars)."""
        result = CredentialManager.validate_key_format("key!@#$%^&*()", "generic")
        assert result is True  # 13 chars >= 8

    def test_validate_key_format_special_chars_openai(self):
        """Test key with special characters for openai (wrong prefix)."""
        result = CredentialManager.validate_key_format("key!@#$%^&*()", "openai")
        assert result is False  # Doesn't start with sk-

    def test_validate_key_format_very_long_key_generic(self):
        """Test very long key for generic provider."""
        long_key = "x" * 10000
        result = CredentialManager.validate_key_format(long_key, "generic")
        assert result is True

    def test_validate_key_format_very_long_key_anthropic_no_prefix(self):
        """Test very long key for anthropic without correct prefix."""
        long_key = "x" * 10000
        result = CredentialManager.validate_key_format(long_key, "anthropic")
        assert result is False  # No sk-ant- prefix

    def test_validate_key_format_key_with_newlines_generic(self):
        """Test key with newlines for generic (>=8 chars)."""
        result = CredentialManager.validate_key_format("key\nwith\nnewlines", "generic")
        assert result is True  # 17 chars >= 8

    def test_validate_key_format_unicode_key(self):
        """Test key with unicode characters for generic."""
        result = CredentialManager.validate_key_format(
            "key-" + "\u00e9" * 10, "generic"
        )
        assert result is True  # 14 chars >= 8

    def test_validate_key_format_sk_ant_exactly_prefix(self):
        """Test 'sk-ant-' alone (7 chars, not >20)."""
        result = CredentialManager.validate_key_format("sk-ant-", "anthropic")
        assert result is False  # Only 7 chars, not >20

    def test_validate_key_format_sk_alone(self):
        """Test 'sk-' alone for OpenAI (3 chars, <4)."""
        result = CredentialManager.validate_key_format("sk-", "openai")
        assert result is False  # 3 chars < 4

    def test_validate_key_format_case_sensitivity_prefix(self):
        """Test that prefix matching is case-sensitive."""
        upper_key = "SK-ANT-" + "x" * 30
        result = CredentialManager.validate_key_format(upper_key, "anthropic")
        assert result is False  # 'SK-ANT-' != 'sk-ant-'

    def test_validate_key_format_case_sensitivity_provider(self):
        """Test provider name matching is case-sensitive."""
        key = "sk-ant-" + "x" * 30  # Valid anthropic key
        result = CredentialManager.validate_key_format(key, "ANTHROPIC")
        # Provider 'ANTHROPIC' doesn't match 'anthropic', falls to generic
        # 37 chars >= 8 for generic
        assert result is True

    def test_validate_key_format_provider_with_whitespace(self):
        """Test provider name with whitespace (doesn't match any specific)."""
        result = CredentialManager.validate_key_format(
            "valid-key-1234567", " anthropic "
        )
        # Doesn't match 'anthropic' exactly, falls to generic: 17 chars >= 8
        assert result is True

    # ----- Test keys are NOT special-cased -----

    def test_validate_key_format_test_key_not_special_cased_anthropic(self):
        """Test that 'test-key' is NOT special-cased for anthropic."""
        result = CredentialManager.validate_key_format("test-key", "anthropic")
        assert result is False  # No sk-ant- prefix, not >20

    def test_validate_key_format_test_key_not_special_cased_openai(self):
        """Test that 'test-key' is NOT special-cased for openai."""
        result = CredentialManager.validate_key_format("test-key", "openai")
        assert result is False  # No sk- prefix or too short

    def test_validate_key_format_test_key_for_generic(self):
        """Test that 'test-key' uses generic validation."""
        result = CredentialManager.validate_key_format("test-key", "generic")
        assert result is True  # 8 chars >= 8

    def test_validate_key_format_test_literal(self):
        """Test that 'test' is not special-cased (4 chars, too short for all)."""
        assert CredentialManager.validate_key_format("test", "anthropic") is False
        assert CredentialManager.validate_key_format("test", "openai") is False
        assert (
            CredentialManager.validate_key_format("test", "generic") is False
        )  # 4 < 8

    def test_validate_key_format_test_prefix_generic(self):
        """Test keys starting with 'test-' use normal validation."""
        # 'test-abc123' is 11 chars >= 8, so passes generic
        assert CredentialManager.validate_key_format("test-abc123", "generic") is True
        # But fails anthropic (no sk-ant- prefix)
        assert (
            CredentialManager.validate_key_format("test-abc123", "anthropic") is False
        )
        # And fails openai (no sk- prefix)
        assert CredentialManager.validate_key_format("test-abc123", "openai") is False

    # ----- Constants -----

    def test_min_generic_key_length_constant(self):
        """Test that the generic minimum key length constant is accessible."""
        assert CredentialManager._MIN_GENERIC_KEY_LENGTH == 8

    def test_min_known_key_length_constant(self):
        """Test that the known provider minimum key length constant is accessible."""
        assert CredentialManager._MIN_KNOWN_KEY_LENGTH == 20


class TestCredentialManagerStaticBehavior:
    """Tests verifying CredentialManager's static method behavior."""

    def test_credential_manager_methods_are_static(self):
        """Test that both methods are static and don't require instance."""
        assert callable(CredentialManager.get_api_key)
        assert callable(CredentialManager.validate_key_format)

    def test_credential_manager_can_be_called_without_instance(self):
        """Test methods can be called directly on class."""
        with patch.dict(os.environ, {"TEST_KEY": "valid-key-longkey"}):
            result = CredentialManager.get_api_key("TEST_KEY", "provider")
            assert result == "valid-key-longkey"

        # 'valid-key-longkey' is 17 chars >= 8 for generic
        result = CredentialManager.validate_key_format("valid-key-longkey", "provider")
        assert result is True

    def test_credential_manager_instance_can_call_static_methods(self):
        """Test that instance can also call static methods (Python behavior)."""
        manager = CredentialManager()
        # 'test-key-long' is 13 chars >= 8 for generic
        result = manager.validate_key_format("test-key-long", "provider")
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

    def test_full_flow_with_test_key_fails_format(self):
        """Test that 'test-key' passes get_api_key but fails format validation."""
        with patch.dict(os.environ, {"API_KEY": "test-key"}):
            key = CredentialManager.get_api_key("API_KEY", "anthropic")
            assert key == "test-key"
            # test-key is 8 chars, passes generic but fails provider-specific
            assert CredentialManager.validate_key_format(key, "anthropic") is False
            assert CredentialManager.validate_key_format(key, "openai") is False
            assert (
                CredentialManager.validate_key_format(key, "generic") is True
            )  # 8 >= 8

    def test_missing_key_flow(self):
        """Test flow when key is missing."""
        env_copy = os.environ.copy()
        env_copy.pop("MISSING_KEY", None)
        with patch.dict(os.environ, env_copy, clear=True):
            key = CredentialManager.get_api_key("MISSING_KEY", "provider")
            assert key is None

    def test_invalid_key_flow(self):
        """Test flow with invalid short key."""
        with patch.dict(os.environ, {"BAD_KEY": "xy"}):
            with pytest.raises(ValueError) as exc_info:
                CredentialManager.get_api_key("BAD_KEY", "provider")
            assert "too short" in str(exc_info.value)
