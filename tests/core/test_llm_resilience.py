"""
Tests for LLM client resilience — timeout and retry configuration.

Verifies that CoreSettings resilience fields propagate to OpenAI client
constructors without changing existing call signatures.
"""

import pytest
from unittest.mock import patch, MagicMock, call


class TestCoreSettingsDefaults:
    """Verify resilience settings have correct defaults."""

    def test_timeout_default(self):
        from alfred.config import CoreSettings

        settings = CoreSettings(openai_api_key="test-key")
        assert settings.openai_timeout == 60

    def test_max_retries_default(self):
        from alfred.config import CoreSettings

        settings = CoreSettings(openai_api_key="test-key")
        assert settings.openai_max_retries == 3

    def test_custom_timeout_from_env(self):
        from alfred.config import CoreSettings

        with patch.dict("os.environ", {"OPENAI_TIMEOUT": "30", "OPENAI_API_KEY": "k"}):
            settings = CoreSettings(openai_api_key="k")
            assert settings.openai_timeout == 30

    def test_custom_max_retries_from_env(self):
        from alfred.config import CoreSettings

        with patch.dict("os.environ", {"OPENAI_MAX_RETRIES": "5", "OPENAI_API_KEY": "k"}):
            settings = CoreSettings(openai_api_key="k")
            assert settings.openai_max_retries == 5


class TestClientConstruction:
    """Verify OpenAI clients receive timeout and max_retries from settings."""

    def test_sync_client_gets_timeout_and_retries(self):
        """get_client() passes timeout and max_retries to OpenAI()."""
        import alfred.llm.client as client_mod

        # Reset singleton
        client_mod._client = None

        with (
            patch.object(client_mod, "settings") as mock_settings,
            patch("alfred.llm.client.OpenAI") as MockOpenAI,
            patch("alfred.llm.client.instructor") as mock_instructor,
        ):
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_timeout = 45
            mock_settings.openai_max_retries = 4
            mock_instructor.from_openai.return_value = MagicMock()

            client_mod.get_client()

            MockOpenAI.assert_called_once_with(
                api_key="test-key",
                timeout=45,
                max_retries=4,
            )

        # Clean up singleton
        client_mod._client = None

    def test_async_client_gets_timeout_and_retries(self):
        """get_raw_async_client() passes timeout and max_retries to AsyncOpenAI()."""
        import alfred.llm.client as client_mod

        # Reset singleton
        client_mod._raw_async_client = None

        with (
            patch.object(client_mod, "settings") as mock_settings,
            patch("alfred.llm.client.AsyncOpenAI") as MockAsyncOpenAI,
        ):
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_timeout = 90
            mock_settings.openai_max_retries = 5

            client_mod.get_raw_async_client()

            MockAsyncOpenAI.assert_called_once_with(
                api_key="test-key",
                timeout=90,
                max_retries=5,
            )

        # Clean up singleton
        client_mod._raw_async_client = None

    def test_singleton_reuses_client(self):
        """Second call to get_client() returns same instance."""
        import alfred.llm.client as client_mod

        client_mod._client = None

        with (
            patch.object(client_mod, "settings") as mock_settings,
            patch("alfred.llm.client.OpenAI") as MockOpenAI,
            patch("alfred.llm.client.instructor") as mock_instructor,
        ):
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_timeout = 60
            mock_settings.openai_max_retries = 3
            mock_instructor.from_openai.return_value = MagicMock()

            first = client_mod.get_client()
            second = client_mod.get_client()

            assert first is second
            MockOpenAI.assert_called_once()  # Only constructed once

        client_mod._client = None

    def test_singleton_reset_rebuilds(self):
        """Resetting _client to None causes reconstruction."""
        import alfred.llm.client as client_mod

        client_mod._client = None

        with (
            patch.object(client_mod, "settings") as mock_settings,
            patch("alfred.llm.client.OpenAI") as MockOpenAI,
            patch("alfred.llm.client.instructor") as mock_instructor,
        ):
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_timeout = 60
            mock_settings.openai_max_retries = 3
            mock_instructor.from_openai.return_value = MagicMock()

            client_mod.get_client()
            client_mod._client = None  # Reset
            client_mod.get_client()

            assert MockOpenAI.call_count == 2  # Constructed twice

        client_mod._client = None
