from functools import lru_cache
from typing import Self
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Secret values written by Terraform/bootstrap that mean "not yet provisioned";
# treated as unset by the app.
PLACEHOLDER_SECRET_VALUES = frozenset(
    {"", "pending-bootstrap", "pending-sync", "None", "null", "<PAT>"}
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://propel:propel@localhost:5432/propel"

    # Signed cookie for the BFF session (httpOnly, server-side user id).
    session_secret: str = "change-me"
    session_cookie_name: str = "propel_session"
    session_max_age_seconds: int = 86400

    # Zitadel OIDC (identity provider). When disabled (e.g. unit tests), use
    # POST /api/v1/auth/test/login instead.
    zitadel_issuer: str = "http://localhost:8080"
    # Server-side OIDC discovery/token calls (defaults to public issuer).
    zitadel_internal_issuer: str = ""
    zitadel_client_id: str = ""
    zitadel_client_secret: str = ""
    # HMAC key for Zitadel Actions V2 webhooks (GitHub IdP mapping on Login V2).
    zitadel_actions_signing_key: str = ""
    # Default Zitadel org for org-scoped OIDC claims (local bootstrap writes this).
    zitadel_org_id: str = ""

    auth_rate_limit_max_requests: int = 10
    auth_rate_limit_window_seconds: int = 60

    # PostHog server-side SDK. POSTHOG_TOKEN (project key) + POSTHOG_HOST are shared
    # with tracing; the personal API key enables fast local flag evaluation (no
    # per-request network call).
    posthog_token: str = ""
    posthog_host: str = "https://us.i.posthog.com"
    posthog_personal_api_key: str = ""

    # Base URL of the API itself — where OIDC providers send the callback.
    oauth_callback_base_url: str = "http://localhost:8000"
    # Base URL of the browser SPA.
    frontend_base_url: str = "http://localhost:5173"

    # GitHub App used for data ingestion. The private key signs the short-lived
    # app JWT that is exchanged for per-installation tokens; the webhook secret
    # verifies install events.
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_webhook_secret: str = ""
    github_app_slug: str = ""

    # The same GitHub App's user-authorization (OAuth) credentials, used to
    # "Connect with GitHub" on the profile page (tool linking, not login).
    github_app_client_id: str = ""
    github_app_client_secret: str = ""

    @property
    def github_oauth_client_id(self) -> str:
        return self.github_app_client_id

    @property
    def github_oauth_client_secret(self) -> str:
        return self.github_app_client_secret

    @property
    def github_oauth_enabled(self) -> bool:
        return bool(self.github_oauth_client_id and self.github_oauth_client_secret)

    # Linear OAuth app (data connection).
    oauth_linear_client_id: str = ""
    oauth_linear_client_secret: str = ""

    @property
    def linear_oauth_enabled(self) -> bool:
        return bool(self.oauth_linear_client_id and self.oauth_linear_client_secret)

    token_encryption_key: str = ""

    ingestion_backfill_days: int = 90

    invite_token_lifetime_hours: int = 72

    cors_allowed_origins: str = (
        "http://localhost:5173,http://localhost:5174,http://localhost:3000"
    )

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

    @property
    def zitadel_oidc_enabled(self) -> bool:
        return bool(self.zitadel_client_id and self.zitadel_client_secret)

    @property
    def zitadel_actions_signing_key_effective(self) -> str:
        key = self.zitadel_actions_signing_key.strip()
        if key in PLACEHOLDER_SECRET_VALUES:
            return ""
        return key

    @property
    def zitadel_host_header(self) -> str:
        return urlparse(self.zitadel_issuer).hostname or "localhost"

    @property
    def zitadel_internal_issuer_url(self) -> str:
        return (self.zitadel_internal_issuer or self.zitadel_issuer).rstrip("/")

    @property
    def zitadel_oidc_metadata_url(self) -> str:
        return f"{self.zitadel_internal_issuer_url}/.well-known/openid-configuration"

    @property
    def zitadel_oidc_scopes(self) -> str:
        scopes = ["openid", "email", "profile"]
        if self.zitadel_org_id:
            scopes.append(f"urn:zitadel:iam:org:id:{self.zitadel_org_id}")
        return " ".join(scopes)

    @property
    def is_test_env(self) -> bool:
        return self.app_env.lower() == "test"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Self:
        if self.app_env.lower() in {"production", "prod", "beta"}:
            insecure_secrets = {"", "change-me", "test-secret"}
            if self.session_secret in insecure_secrets or len(self.session_secret) < 32:
                raise ValueError(
                    "SESSION_SECRET must be a random string of at least "
                    f"32 characters in {self.app_env} environments."
                )
            if not self.zitadel_oidc_enabled:
                raise ValueError(
                    "ZITADEL_CLIENT_ID and ZITADEL_CLIENT_SECRET are required in "
                    f"{self.app_env} environments."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
