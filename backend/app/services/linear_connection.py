"""Linear OAuth connection provisioning for ingestion.

A workspace admin starts the connect flow (gated by ``connections:manage``); we
round-trip them through Linear's OAuth using a signed ``state`` that binds the
exchange to (tenant, user) — the same HMAC pattern as the GitHub App install
state in ``connections``. On the callback we exchange the code, read the Linear
workspace, and upsert a ``connected_accounts`` row with the access/refresh
tokens encrypted at rest (``auth_type='oauth'``).
"""

from __future__ import annotations

import base64
import hmac
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.linear import oauth as linear_oauth
from app.models.connected_account import ConnectedAccount
from app.models.enums import AuthType, ConnectionStatus, IntegrationProvider, Role
from app.models.membership import TenantMembership
from app.services import role_permissions as role_permission_service
from app.services import token_crypto
from app.services.connections import clear_auth_failure

logger = logging.getLogger("propel.connections")

settings = get_settings()

_STATE_TTL_SECONDS = 600
_PURPOSE = "linear"
_CALLBACK_PATH = "/api/v1/connections/linear/callback"
_MANAGE_PERMISSION = "connections:manage"
# Refresh the access token when it expires within this window, so an ingestion
# run never starts with a token that lapses mid-pull.
_REFRESH_LEEWAY = timedelta(minutes=5)


def _redirect_uri() -> str:
    return f"{settings.oauth_callback_base_url}{_CALLBACK_PATH}"


# --------------------------------------------------------------------------- #
# Signed connect state (binds the OAuth round-trip to tenant + user)
# --------------------------------------------------------------------------- #
def _sign(payload: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), payload.encode(), sha256).hexdigest()


def build_connect_state(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    exp = int(time.time()) + _STATE_TTL_SECONDS
    payload = f"{_PURPOSE}:{tenant_id}:{user_id}:{exp}"
    raw = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_connect_state(state: str) -> tuple[uuid.UUID, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(state.encode()).decode()
        payload, signature = raw.rsplit(":", 1)
        purpose, tenant_str, user_str, exp_str = payload.split(":")
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning(
            "Invalid Linear connect state",
            extra={"event": "connection.linear", "error.message": "invalid_state"},
        )
        raise HTTPException(status_code=400, detail="Invalid connect state") from exc

    if purpose != _PURPOSE or not hmac.compare_digest(signature, _sign(payload)):
        logger.warning(
            "Linear connect state signature mismatch",
            extra={"event": "connection.linear", "error.message": "signature_mismatch"},
        )
        raise HTTPException(status_code=400, detail="Connect state signature mismatch")
    if int(exp_str) < int(time.time()):
        logger.warning(
            "Linear connect state expired",
            extra={"event": "connection.linear", "error.message": "state_expired"},
        )
        raise HTTPException(status_code=400, detail="Connect state expired")
    return uuid.UUID(tenant_str), uuid.UUID(user_str)


def build_authorize_url(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    if not settings.linear_oauth_enabled:
        raise HTTPException(
            status_code=503, detail="Linear is not configured for this deployment"
        )
    state = build_connect_state(tenant_id, user_id)
    return linear_oauth.build_authorize_url(_redirect_uri(), state)


# --------------------------------------------------------------------------- #
# Callback: exchange code + upsert the connection
# --------------------------------------------------------------------------- #
async def _require_manage_permission(
    session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    membership = await session.scalar(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=403, detail="You are not a member of this workspace"
        )
    role = Role(membership.role)
    permissions = await role_permission_service.get_effective_permissions(
        session, tenant_id, role
    )
    if _MANAGE_PERMISSION not in permissions:
        logger.warning(
            "User without connections:manage attempted Linear connect",
            extra={
                "event": "connection.linear",
                "tenant.id": str(tenant_id),
                "user.id": str(user_id),
                "error.message": "not_permitted",
            },
        )
        raise HTTPException(
            status_code=403, detail="You cannot manage connections for this workspace"
        )


async def bind_linear_oauth(
    session: AsyncSession,
    code: str,
    state: str,
) -> ConnectedAccount:
    # The signed state (not a bearer header) carries the initiating user, so the
    # callback is reachable as a top-level browser navigation — same model as
    # the GitHub account-link callback.
    tenant_id, user_id = verify_connect_state(state)
    await _require_manage_permission(session, tenant_id, user_id)

    token = await linear_oauth.exchange_code(code, _redirect_uri())
    workspace_id, workspace_name = await linear_oauth.fetch_workspace(
        token.access_token
    )

    existing = await session.scalar(
        select(ConnectedAccount).where(
            ConnectedAccount.tenant_id == tenant_id,
            ConnectedAccount.provider == IntegrationProvider.linear.value,
            ConnectedAccount.external_account_id == workspace_id,
        )
    )
    access_encrypted = token_crypto.encrypt_token(token.access_token)
    refresh_encrypted = (
        token_crypto.encrypt_token(token.refresh_token) if token.refresh_token else None
    )

    if existing is None:
        account = ConnectedAccount(
            tenant_id=tenant_id,
            connected_by_user_id=user_id,
            provider=IntegrationProvider.linear.value,
            auth_type=AuthType.oauth.value,
            external_account_id=workspace_id,
            external_account_name=workspace_name,
            access_token_encrypted=access_encrypted,
            refresh_token_encrypted=refresh_encrypted,
            token_expires_at=token.expires_at,
            scopes=token.scopes,
            status=ConnectionStatus.active.value,
        )
        session.add(account)
        clear_auth_failure(account)
    else:
        account = existing
        account.connected_by_user_id = user_id
        account.external_account_name = workspace_name
        account.access_token_encrypted = access_encrypted
        account.refresh_token_encrypted = refresh_encrypted
        account.token_expires_at = token.expires_at
        account.scopes = token.scopes
        account.status = ConnectionStatus.active.value
        clear_auth_failure(account)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        logger.error(
            "Linear connection binding failed",
            extra={
                "event": "connection.linear",
                "tenant.id": str(tenant_id),
                "linear.workspace_id": workspace_id,
                "error.message": "integrity_error",
            },
        )
        raise HTTPException(
            status_code=409, detail="Connection could not be created"
        ) from exc
    await session.refresh(account)
    logger.info(
        "Linear connection bound",
        extra={
            "event": "connection.linear",
            "tenant.id": str(tenant_id),
            "connected_account.id": str(account.id),
            "linear.workspace_id": workspace_id,
        },
    )
    return account


# --------------------------------------------------------------------------- #
# Read helpers
# --------------------------------------------------------------------------- #
async def get_active_linear_account(
    session: AsyncSession, tenant_id: uuid.UUID
) -> ConnectedAccount | None:
    """The active Linear connection for a tenant, or None."""
    return await session.scalar(
        select(ConnectedAccount).where(
            ConnectedAccount.tenant_id == tenant_id,
            ConnectedAccount.provider == IntegrationProvider.linear.value,
            ConnectedAccount.status == ConnectionStatus.active.value,
        )
    )


async def get_linear_account(
    session: AsyncSession, tenant_id: uuid.UUID
) -> ConnectedAccount | None:
    """Latest Linear connection for a tenant (any status), or None.

    Prefer an active row so reconnect stays healthy; otherwise surface
    paused/revoked state for the workspace Integrations UI.
    """
    active = await get_active_linear_account(session, tenant_id)
    if active is not None:
        return active
    return await session.scalar(
        select(ConnectedAccount)
        .where(
            ConnectedAccount.tenant_id == tenant_id,
            ConnectedAccount.provider == IntegrationProvider.linear.value,
        )
        .order_by(ConnectedAccount.updated_at.desc())
        .limit(1)
    )


# --------------------------------------------------------------------------- #
# Token access (decrypt + refresh) for ingestion runs
# --------------------------------------------------------------------------- #
def _is_expiring(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    return datetime.now(UTC) >= expires_at - _REFRESH_LEEWAY


async def get_access_token(session: AsyncSession, account: ConnectedAccount) -> str:
    """Return a valid Linear access token, refreshing and persisting if needed.

    Raises ``LinearOAuthError`` / ``TokenEncryptionError`` if the stored token
    can't be decrypted or refreshed; the orchestrator treats that as a run
    failure (the connection needs reconnecting).
    """
    if not account.access_token_encrypted:
        raise linear_oauth.LinearOAuthError(
            "Linear connection has no stored access token"
        )

    if account.refresh_token_encrypted and _is_expiring(account.token_expires_at):
        refresh_token = token_crypto.decrypt_token(account.refresh_token_encrypted)
        token = await linear_oauth.refresh_access_token(refresh_token)
        account.access_token_encrypted = token_crypto.encrypt_token(token.access_token)
        if token.refresh_token:
            account.refresh_token_encrypted = token_crypto.encrypt_token(
                token.refresh_token
            )
        account.token_expires_at = token.expires_at
        if token.scopes:
            account.scopes = token.scopes
        await session.commit()
        await session.refresh(account)
        logger.info(
            "Refreshed Linear access token",
            extra={
                "event": "connection.linear",
                "connected_account.id": str(account.id),
            },
        )
        return token.access_token

    return token_crypto.decrypt_token(account.access_token_encrypted)
