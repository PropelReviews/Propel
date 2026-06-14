"""Zitadel OIDC client (Auth Code + PKCE)."""

import json
import logging
import urllib.request
from collections.abc import Callable
from urllib.parse import urlparse

from authlib.integrations.starlette_client import OAuth

from app.config import Settings, get_settings

logger = logging.getLogger("propel.auth.oidc")

oauth = OAuth()

_BROWSER_ENDPOINTS = (
    "authorization_endpoint",
    "end_session_endpoint",
    "device_authorization_endpoint",
)
_SERVER_ENDPOINTS = (
    "token_endpoint",
    "jwks_uri",
    "userinfo_endpoint",
    "introspection_endpoint",
    "revocation_endpoint",
)


def _fetch_server_metadata(settings: Settings) -> dict:
    """Load OIDC metadata from the internal issuer."""
    metadata_url = settings.zitadel_oidc_metadata_url
    with urllib.request.urlopen(
        urllib.request.Request(
            metadata_url,
            headers={"Host": settings.zitadel_host_header},
        ),
        timeout=10,
    ) as response:
        return json.load(response)


def normalize_server_metadata(metadata: dict, settings: Settings) -> dict:
    """Rewrite Zitadel discovery URLs for browser vs server-side callers."""
    public_base = settings.zitadel_issuer.rstrip("/")
    internal_base = settings.zitadel_internal_issuer_url
    raw_issuer = str(metadata.get("issuer", public_base)).rstrip("/")

    def rewrite(url: str, base: str) -> str:
        if url.startswith(raw_issuer):
            return base + url[len(raw_issuer) :]
        if internal_base != public_base and url.startswith(internal_base):
            return public_base + url[len(internal_base) :]
        return url

    normalized = dict(metadata)
    for key in _BROWSER_ENDPOINTS:
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = rewrite(value, public_base)
    for key in _SERVER_ENDPOINTS:
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = rewrite(value, internal_base)
    normalized["issuer"] = public_base
    return normalized


def _zitadel_compliance_fix(
    host_header: str, internal_base: str
) -> Callable[[object], None]:
    """Ensure server-side token/JWKS calls reach Zitadel with the public Host."""
    internal_host = urlparse(internal_base).netloc

    def fix(session: object) -> None:
        original_request = session.request

        async def request_with_host(method, url, **kwargs):
            headers = dict(kwargs.get("headers") or {})
            if internal_host and internal_host in str(url) and "Host" not in headers:
                headers["Host"] = host_header
                kwargs["headers"] = headers
            return await original_request(method, url, **kwargs)

        session.request = request_with_host

    return fix


def register_oidc_client(settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    if not cfg.zitadel_oidc_enabled:
        return
    try:
        server_metadata = normalize_server_metadata(_fetch_server_metadata(cfg), cfg)
    except Exception:
        logger.exception(
            "Failed to load Zitadel OIDC metadata from %s",
            cfg.zitadel_oidc_metadata_url,
        )
        raise

    oauth.register(
        name="zitadel",
        overwrite=True,
        client_id=cfg.zitadel_client_id,
        client_secret=cfg.zitadel_client_secret,
        compliance_fix=_zitadel_compliance_fix(
            cfg.zitadel_host_header,
            cfg.zitadel_internal_issuer_url,
        ),
        client_kwargs={
            "scope": cfg.zitadel_oidc_scopes,
            "token_endpoint_auth_method": "client_secret_basic",
        },
        **server_metadata,
    )


register_oidc_client()
