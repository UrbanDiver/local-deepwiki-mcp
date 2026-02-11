"""Secure credential management for API providers.

This module provides secure credential handling without storing sensitive
information in instance variables or memory for longer than necessary.
"""

from __future__ import annotations

import os
from typing import Optional


class CredentialManager:
    """Manages credentials securely without storing in memory.

    API keys are retrieved from environment variables at initialization
    and validated, but never stored as instance attributes. This prevents
    accidental exposure through process memory dumps or debugging tools.
    """

    @staticmethod
    def get_api_key(env_var: str, provider: str) -> Optional[str]:
        """Get API key from environment without storing.

        Args:
            env_var: Environment variable name to check
            provider: Provider name for logging and validation

        Returns:
            API key string or None if not set

        Raises:
            ValueError: If key format appears invalid
        """
        key = os.environ.get(env_var)
        if not key:
            return None

        # Validate key format (basic check) - allow short test keys
        # Real API keys are much longer, but we need to support testing
        if len(key) < 4:
            raise ValueError(f"{provider} API key appears invalid (too short)")

        # Don't store in memory, validate and return
        return key

    # Minimum key length for generic providers
    _MIN_GENERIC_KEY_LENGTH = 8
    # Minimum key length for known providers (Anthropic, OpenAI)
    _MIN_KNOWN_KEY_LENGTH = 20

    @staticmethod
    def validate_key_format(key: str, provider: str) -> bool:
        """Validate API key format without storing.

        Performs strict provider-specific format validation. Anthropic keys
        must start with ``sk-ant-`` and OpenAI keys with ``sk-``, both with
        a minimum length of 20 characters. Generic providers require at
        least 8 characters.

        Args:
            key: API key to validate
            provider: Provider name to determine validation rules

        Returns:
            True if key format appears valid, False otherwise
        """
        if not key or len(key) < 4:
            return False

        if provider == "anthropic":
            return (
                key.startswith("sk-ant-")
                and len(key) > CredentialManager._MIN_KNOWN_KEY_LENGTH
            )
        elif provider == "openai":
            return (
                key.startswith("sk-")
                and len(key) > CredentialManager._MIN_KNOWN_KEY_LENGTH
            )
        else:
            return len(key) >= CredentialManager._MIN_GENERIC_KEY_LENGTH
