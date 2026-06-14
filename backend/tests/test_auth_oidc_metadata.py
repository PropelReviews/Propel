"""OIDC metadata normalization for Zitadel compose/dev."""

from app.auth.oidc import normalize_server_metadata
from app.config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql://propel:propel@localhost:5432/propel",
        "session_secret": "test-secret-that-is-long-enough-for-validation",
        "app_env": "test",
    }
    base.update(overrides)
    return Settings(**base)


def test_settings_builds_org_scopes_when_org_id_set():
    settings = _settings(
        zitadel_org_id="377425894588809220",
    )
    assert (
        settings.zitadel_oidc_scopes
        == "openid email profile urn:zitadel:iam:org:id:377425894588809220"
    )


def test_settings_omits_org_scopes_without_org_id():
    settings = _settings()
    assert settings.zitadel_oidc_scopes == "openid email profile"


def test_normalize_server_metadata_rewrites_browser_and_server_urls():
    settings = _settings(
        zitadel_issuer="http://localhost:8080",
        zitadel_internal_issuer="http://zitadel:8080",
    )
    metadata = {
        "issuer": "http://localhost",
        "authorization_endpoint": "http://localhost/oauth/v2/authorize",
        "token_endpoint": "http://localhost/oauth/v2/token",
        "jwks_uri": "http://localhost/oauth/v2/keys",
        "end_session_endpoint": "http://localhost/oidc/v1/end_session",
    }

    normalized = normalize_server_metadata(metadata, settings)

    assert normalized["issuer"] == "http://localhost:8080"
    assert (
        normalized["authorization_endpoint"]
        == "http://localhost:8080/oauth/v2/authorize"
    )
    assert normalized["end_session_endpoint"] == (
        "http://localhost:8080/oidc/v1/end_session"
    )
    assert normalized["token_endpoint"] == "http://zitadel:8080/oauth/v2/token"
    assert normalized["jwks_uri"] == "http://zitadel:8080/oauth/v2/keys"
