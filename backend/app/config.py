from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GA_", env_file=".env", extra="ignore")

    app_name: str = "Intelligent Grammar and Writing Assistant"
    lt_url: str = "https://api.languagetool.org/v2/check"
    lt_language: str = "en-US"
    lt_timeout_seconds: float = 12.0
    lt_requests_per_minute: int = 18
    lt_cache_seconds: int = 3600
    lt_enabled: bool = True
    lt_offsets_utf16: bool = True
    max_text_chars: int = 60000
    chunk_chars: int = 15000
    max_suggestions: int = 4
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",")]
        return [origin for origin in origins if origin]


@lru_cache
def get_settings() -> Settings:
    return Settings()
