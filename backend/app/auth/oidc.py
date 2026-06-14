"""Zitadel OIDC client (Auth Code + PKCE)."""

from authlib.integrations.starlette_client import OAuth

from app.config import get_settings

oauth = OAuth()

_settings = get_settings()


def register_oidc_client() -> None:
    if not _settings.zitadel_oidc_enabled:
        return
    oauth.register(
        name="zitadel",
        client_id=_settings.zitadel_client_id,
        client_secret=_settings.zitadel_client_secret,
        server_metadata_url=_settings.zitadel_oidc_metadata_url,
        client_kwargs={
            "scope": (
                "openid email profile urn:zitadel:iam:org:id: urn:zitadel:iam:org:name:"
            ),
            "token_endpoint_auth_method": "client_secret_basic",
        },
    )


register_oidc_client()
