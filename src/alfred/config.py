"""
Alfred Core - Configuration and settings.

CoreSettings contains only what the orchestration engine needs.
Domain-specific settings live in domain packages (e.g., KitchenSettings, FPLSettings).
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    """
    Core settings shared by all domains.

    Contains only what the alfred orchestration engine needs.
    Domain-specific settings (Supabase, session, etc.) go in subclasses.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str

    # LangSmith (optional)
    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "alfred-v2"

    # Application
    alfred_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Prompt logging
    # ALFRED_LOG_PROMPTS=1 - log to local files (dev only)
    alfred_log_prompts: bool = False

    @property
    def is_development(self) -> bool:
        return self.alfred_env == "development"

    @property
    def is_production(self) -> bool:
        return self.alfred_env == "production"


@lru_cache
def get_core_settings() -> CoreSettings:
    """Get cached CoreSettings instance (no Supabase fields required)."""
    return CoreSettings()


class _CoreSettingsProxy:
    """Lazy proxy for CoreSettings — only needs OPENAI_API_KEY."""

    _instance: CoreSettings | None = None

    def __getattr__(self, name: str):
        if self._instance is None:
            self._instance = get_core_settings()
        return getattr(self._instance, name)


core_settings = _CoreSettingsProxy()
