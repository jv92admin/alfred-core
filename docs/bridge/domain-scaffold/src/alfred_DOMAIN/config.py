"""Domain-specific settings.

Extends CoreSettings to add domain-specific environment variables.
Uses a dual .env pattern: domain-specific vars first, shared vars as fallback.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DomainSettings(BaseSettings):
    model_config = SettingsConfigDict(
        # TODO: create your .env file with these variables
        # First file = domain-specific, second = shared (e.g., OpenAI key)
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # TODO: add your environment variables
    supabase_url: str = ""
    supabase_anon_key: str = ""


settings = DomainSettings()
