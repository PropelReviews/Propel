"""Self-service GitHub account linking for the signed-in Propel user.

This is the user-facing counterpart to the org-driven linking in
`github_identity`. A logged-in user clicks "Connect with GitHub" on their
profile; we round-trip them through GitHub's login OAuth app using a signed
`state` (HMAC of user_id + expiry, same pattern as the GitHub App install
state in `connections`), record the resulting `oauth_accounts` row, and then
let `github_identity.link_oauth_identity` claim any pending org identities
whose GitHub user id matches — closing the loop for members whose GitHub
email is private or differs from their Propel email.
"""

from __future__ import annotations

import base64
import hmac
import logging
import time
import uuid
from hashlib import sha256

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.oauth import github_oauth_client
from app.config import get_settings
from app.models.enums import IntegrationProvider
from app.models.external_identity import ExternalIdentity
from app.models.user import OAuthAccount, User
from app.services import github_identity

logger = logging.getLogger("propel.auth")

settings = get_settings()

_GITHUB = IntegrationProvider.github.value
_STATE_TTL_SECONDS = 600
_LINK_CALLBACK_PATH = "/api/v1/auth/github/link/callback"


def _redirect_uri() -> str:
    return f"{settings.oauth_callback_base_url}{_LINK_CALLBACK_PATH}"


# --------------------------------------------------------------------------- #
# Signed link state (binds the OAuth round-trip to the initiating user)
# --------------------------------------------------------------------------- #
def _sign(payload: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), payload.encode(), sha256).hexdigest()


def build_link_state(user_id: uuid.UUID) -> str:
    exp = int(time.time()) + _STATE_TTL_SECONDS
    payload = f"{user_id}:{exp}"
    raw = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_link_state(state: str) -> uuid.UUID:
    try:
        raw = base64.urlsafe_b64decode(state.encode()).decode()
        payload, signature = raw.rsplit(":", 1)
        user_str, exp_str = payload.split(":")
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning(
            "Invalid GitHub link state",
            extra={"event": "auth.github_link", "error.message": "invalid_state"},
        )
        raise HTTPException(status_code=400, detail="Invalid link state") from exc

    if not hmac.compare_digest(signature, _sign(payload)):
        logger.warning(
            "GitHub link state signature mismatch",
            extra={"event": "auth.github_link", "error.message": "signature_mismatch"},
        )
        raise HTTPException(status_code=400, detail="Link state signature mismatch")
    if int(exp_str) < int(time.time()):
        logger.warning(
            "GitHub link state expired",
            extra={"event": "auth.github_link", "error.message": "state_expired"},
        )
        raise HTTPException(status_code=400, detail="Link state expired")
    return uuid.UUID(user_str)


# --------------------------------------------------------------------------- #
# Authorize
# --------------------------------------------------------------------------- #
async def build_authorize_url(user_id: uuid.UUID) -> str:
    if not (settings.oauth_github_client_id and settings.oauth_github_client_secret):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub sign-in is not configured",
        )
    state = build_link_state(user_id)
    return await github_oauth_client.get_authorization_url(
        _redirect_uri(), state=state
    )


# --------------------------------------------------------------------------- #
# Callback: associate the GitHub identity with the user
# --------------------------------------------------------------------------- #
async def complete_link(session: AsyncSession, code: str, state: str) -> User:
    """Exchange the OAuth code, attach the GitHub identity, then claim org links."""
    user_id = verify_link_state(state)
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    token = await github_oauth_client.get_access_token(code, _redirect_uri())
    access_token = token["access_token"]
    account_id, account_email = await github_oauth_client.get_id_email(access_token)
    account_id = str(account_id)

    await _attach_oauth_account(session, user, account_id, account_email, access_token)
    await session.commit()

    # Claim any pending org identities (across tenants) that match this GitHub
    # user id — this is what links the user into their org's Propel tenant.
    await github_identity.link_oauth_identity(session, user.id, account_id)

    logger.info(
        "GitHub account linked to Propel user",
        extra={
            "event": "auth.github_link",
            "user.id": str(user.id),
            "github.account_id": account_id,
        },
    )
    return user


async def _attach_oauth_account(
    session: AsyncSession,
    user: User,
    account_id: str,
    account_email: str | None,
    access_token: str,
) -> None:
    owner_id = await session.scalar(
        select(OAuthAccount.user_id).where(
            OAuthAccount.oauth_name == _GITHUB,
            OAuthAccount.account_id == account_id,
        )
    )
    if owner_id is not None and owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This GitHub account is already linked to another Propel user",
        )

    existing = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user.id,
            OAuthAccount.oauth_name == _GITHUB,
        )
    )
    if existing is None:
        session.add(
            OAuthAccount(
                user_id=user.id,
                oauth_name=_GITHUB,
                access_token=access_token,
                account_id=account_id,
                account_email=account_email or "",
            )
        )
    else:
        existing.account_id = account_id
        existing.access_token = access_token
        if account_email:
            existing.account_email = account_email


# --------------------------------------------------------------------------- #
# Read helpers for the profile UI
# --------------------------------------------------------------------------- #
async def get_github_account(
    session: AsyncSession, user_id: uuid.UUID
) -> OAuthAccount | None:
    return await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user_id,
            OAuthAccount.oauth_name == _GITHUB,
        )
    )


async def get_linked_github_login(
    session: AsyncSession, user_id: uuid.UUID
) -> str | None:
    """The GitHub @login for this user, sourced from any linked org identity."""
    return await session.scalar(
        select(ExternalIdentity.external_login)
        .where(
            ExternalIdentity.provider == _GITHUB,
            ExternalIdentity.propel_user_id == user_id,
            ExternalIdentity.external_login.is_not(None),
        )
        .order_by(ExternalIdentity.linked_at.desc())
        .limit(1)
    )
