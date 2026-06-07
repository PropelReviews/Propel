from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://propel:propel@localhost:5432/propel"
    jwt_secret: str = "change-me"
    jwt_lifetime_seconds: int = 3600

    # Server-side signup gate (independent of the frontend feature flag).
    auth_registration_enabled: bool = False
    auth_rate_limit_max_requests: int = 10
    auth_rate_limit_window_seconds: int = 60

    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_callback_base_url: str = "http://localhost:8000"

    invite_token_lifetime_hours: int = 72

    # Comma-separated list of origins allowed to call the API from a browser.
    # The SPA dev server runs on :5173; add deployed origins per environment.
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Self:
        if self.app_env.lower() in {"production", "prod", "beta"}:
            insecure_secrets = {"", "change-me", "test-secret"}
            if self.jwt_secret in insecure_secrets or len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET must be a random string of at least 32 characters in "
                    f"{self.app_env} environments."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
