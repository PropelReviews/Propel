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

    # Server-side signup gate. When PostHog is configured the `auth_registration_flag`
    # feature flag is the source of truth (fail closed if it can't be evaluated);
    # otherwise (local/dev/test, no PostHog) this setting governs.
    auth_registration_enabled: bool = False
    auth_registration_flag: str = "auth-registration-enabled"
    auth_rate_limit_max_requests: int = 10
    auth_rate_limit_window_seconds: int = 60

    # PostHog server-side SDK. POSTHOG_TOKEN (project key) + POSTHOG_HOST are shared
    # with tracing; the personal API key enables fast local flag evaluation (no
    # per-request network call).
    posthog_token: str = ""
    posthog_host: str = "https://us.i.posthog.com"
    posthog_personal_api_key: str = ""

    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    # Base URL of the API itself — where providers send the OAuth callback (the
    # backend). Used to build OAuth `redirect_uri`s, e.g.
    # {oauth_callback_base_url}/api/v1/auth/github/login/callback.
    oauth_callback_base_url: str = "http://localhost:8000"
    # Base URL of the browser SPA. The API and SPA are separate origins in
    # deployment (api.<zone> vs app.<zone>), so OAuth callbacks finish by
    # redirecting the browser here (e.g. {frontend_base_url}/auth/github/callback).
    # Defaults to the local Vite dev server.
    frontend_base_url: str = "http://localhost:5173"

    # GitHub App used for data ingestion. The private key signs the short-lived
    # app JWT that is exchanged for per-installation tokens; the webhook secret
    # verifies install events.
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_webhook_secret: str = ""
    github_app_slug: str = ""

    # The same GitHub App's user-authorization (OAuth) credentials, used to
    # "Sign in / Connect with GitHub". These are the App's **Client ID** (e.g.
    # `Iv1...`) and a generated **client secret** — distinct from
    # `github_app_id` (numeric, app JWT) and `github_app_private_key`. When set,
    # they take precedence over the standalone `oauth_github_*` app below, so a
    # single GitHub App covers both ingestion and login.
    github_app_client_id: str = ""
    github_app_client_secret: str = ""

    @property
    def github_oauth_client_id(self) -> str:
        """Effective GitHub login client id (App reused, else standalone app)."""
        return self.github_app_client_id or self.oauth_github_client_id

    @property
    def github_oauth_client_secret(self) -> str:
        return self.github_app_client_secret or self.oauth_github_client_secret

    @property
    def github_oauth_enabled(self) -> bool:
        return bool(self.github_oauth_client_id and self.github_oauth_client_secret)

    # Fernet key for encrypting OAuth tool tokens (future providers). GitHub App
    # installs mint tokens per run and do not use this.
    token_encryption_key: str = ""

    # First-run backfill window for repo resources (Copilot is capped by GitHub).
    ingestion_backfill_days: int = 90

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
