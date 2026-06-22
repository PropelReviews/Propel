"""Sign in / sign up with GitHub for the browser SPA.

fastapi-users ships an OAuth login router, but its callback returns the JWT as
a JSON body via the bearer transport — unusable from a top-level browser
navigation. This module implements the same login/registration find-or-create
(delegating to the user manager's `oauth_callback`, which also claims pending
org identities) but finishes with a redirect back to the SPA, handing the
freshly minted JWT to the frontend in the URL fragment.

The OAuth `state` is a signed, short-lived token tagged with a `login` purpose
so it cannot be swapped with the account-link state in `github_link`.
"""

from __future__ import annotations

import base64
import hmac
import logging
import time
from hashlib import sha256

from fastapi import HTTPException, status

from app.auth.oauth import github_oauth_client
from app.config import get_settings

logger = logging.getLogger("propel.auth")

settings = get_settings()

_STATE_TTL_SECONDS = 600
_LOGIN_CALLBACK_PATH = "/api/v1/auth/github/login/callback"
_PURPOSE = "login"


def _redirect_uri() -> str:
    return f"{settings.oauth_callback_base_url}{_LOGIN_CALLBACK_PATH}"


def _sign(payload: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), payload.encode(), sha256).hexdigest()


def build_login_state() -> str:
    exp = int(time.time()) + _STATE_TTL_SECONDS
    payload = f"{_PURPOSE}:{exp}"
    raw = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_login_state(state: str) -> None:
    try:
        raw = base64.urlsafe_b64decode(state.encode()).decode()
        payload, signature = raw.rsplit(":", 1)
        purpose, exp_str = payload.split(":")
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning(
            "Invalid GitHub login state",
            extra={"event": "auth.github_login", "error.message": "invalid_state"},
        )
        raise HTTPException(status_code=400, detail="Invalid login state") from exc

    if purpose != _PURPOSE or not hmac.compare_digest(signature, _sign(payload)):
        logger.warning(
            "GitHub login state signature mismatch",
            extra={"event": "auth.github_login", "error.message": "signature_mismatch"},
        )
        raise HTTPException(status_code=400, detail="Login state signature mismatch")
    if int(exp_str) < int(time.time()):
        logger.warning(
            "GitHub login state expired",
            extra={"event": "auth.github_login", "error.message": "state_expired"},
        )
        raise HTTPException(status_code=400, detail="Login state expired")


async def build_authorize_url() -> str:
    if not settings.github_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub sign-in is not configured",
        )
    state = build_login_state()
    return await github_oauth_client.get_authorization_url(_redirect_uri(), state=state)


async def exchange_code(code: str) -> tuple[str, str, str | None]:
    """Trade the OAuth code for (access_token, github_id, email)."""
    token = await github_oauth_client.get_access_token(code, _redirect_uri())
    access_token = token["access_token"]
    account_id, account_email = await github_oauth_client.get_id_email(access_token)
    return access_token, str(account_id), account_email
