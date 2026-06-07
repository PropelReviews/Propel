"""connected_accounts provisioning for ingestion.

GitHub App installs are bound to a tenant via a signed `state` round-trip: the
install URL carries an HMAC of (tenant_id, user_id, expiry); GitHub redirects
back to the setup callback with that state plus the installation_id, which we
verify before creating the connected_accounts row. The webhook then keeps the
row's status and metadata in sync with GitHub (suspend, revoke, repo changes).
"""

from __future__ import annotations

import base64
import hmac
import logging
import time
import uuid
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.github import app_auth
from app.models.connected_account import ConnectedAccount
from app.models.enums import AuthType, ConnectionStatus, IntegrationProvider, Role
from app.models.membership import TenantMembership
from app.schemas.connection import ConnectionStatusUpdate

logger = logging.getLogger("propel.connections")

settings = get_settings()

_STATE_TTL_SECONDS = 600
_GITHUB_INSTALL_URL = "https://github.com/apps/{slug}/installations/new?state={state}"


# --------------------------------------------------------------------------- #
# Signed install state
# --------------------------------------------------------------------------- #
def _sign(payload: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), payload.encode(), sha256).hexdigest()


def build_install_state(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    exp = int(time.time()) + _STATE_TTL_SECONDS
    payload = f"{tenant_id}:{user_id}:{exp}"
    raw = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_install_state(state: str) -> tuple[uuid.UUID, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(state.encode()).decode()
        payload, signature = raw.rsplit(":", 1)
        tenant_str, user_str, exp_str = payload.split(":")
    except (ValueError, UnicodeDecodeError) as exc:
        logger.warning(
            "Invalid GitHub install state",
            extra={"event": "connection.install", "error.message": "invalid_state"},
        )
        raise HTTPException(status_code=400, detail="Invalid install state") from exc

    if not hmac.compare_digest(signature, _sign(payload)):
        logger.warning(
            "GitHub install state signature mismatch",
            extra={
                "event": "connection.install",
                "error.message": "signature_mismatch",
            },
        )
        raise HTTPException(status_code=400, detail="Install state signature mismatch")
    if int(exp_str) < int(time.time()):
        logger.warning(
            "GitHub install state expired",
            extra={"event": "connection.install", "error.message": "state_expired"},
        )
        raise HTTPException(status_code=400, detail="Install state expired")
    return uuid.UUID(tenant_str), uuid.UUID(user_str)


def build_github_install_url(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    if not settings.github_app_slug:
        raise HTTPException(
            status_code=503, detail="GitHub App is not configured (GITHUB_APP_SLUG)"
        )
    state = build_install_state(tenant_id, user_id)
    return _GITHUB_INSTALL_URL.format(slug=settings.github_app_slug, state=state)


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
async def list_connections(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[ConnectedAccount]:
    result = await session.execute(
        select(ConnectedAccount)
        .where(ConnectedAccount.tenant_id == tenant_id)
        .order_by(ConnectedAccount.created_at.desc())
    )
    return list(result.scalars().all())


async def update_connection_status(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    payload: ConnectionStatusUpdate,
) -> ConnectedAccount:
    account = await session.get(ConnectedAccount, connection_id)
    if account is None or account.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Connection not found")
    account.status = payload.status.value
    await session.commit()
    await session.refresh(account)
    return account


# --------------------------------------------------------------------------- #
# Setup callback (tenant binding)
# --------------------------------------------------------------------------- #
async def bind_github_installation(
    session: AsyncSession,
    user_id: uuid.UUID,
    installation_id: str,
    state: str,
) -> ConnectedAccount:
    tenant_id, state_user_id = verify_install_state(state)
    if state_user_id != user_id:
        logger.warning(
            "GitHub install state user mismatch",
            extra={
                "event": "connection.install",
                "tenant.id": str(tenant_id),
                "error.message": "user_mismatch",
            },
        )
        raise HTTPException(
            status_code=403, detail="Install state does not match the current user"
        )

    membership = await session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    membership = membership.scalar_one_or_none()
    if membership is None or membership.role != Role.admin:
        logger.warning(
            "Non-admin attempted GitHub install binding",
            extra={
                "event": "connection.install",
                "tenant.id": str(tenant_id),
                "user.id": str(user_id),
                "error.message": "not_admin",
            },
        )
        raise HTTPException(
            status_code=403, detail="Only a tenant admin can connect GitHub"
        )

    account_name = await _fetch_installation_account_name(installation_id)

    existing = await session.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.tenant_id == tenant_id,
            ConnectedAccount.provider == IntegrationProvider.github.value,
            ConnectedAccount.external_account_id == installation_id,
        )
    )
    account = existing.scalar_one_or_none()
    if account is None:
        account = ConnectedAccount(
            tenant_id=tenant_id,
            connected_by_user_id=user_id,
            provider=IntegrationProvider.github.value,
            auth_type=AuthType.github_app_installation.value,
            external_account_id=installation_id,
            external_account_name=account_name,
            status=ConnectionStatus.active.value,
        )
        session.add(account)
    else:
        account.status = ConnectionStatus.active.value
        if account_name:
            account.external_account_name = account_name

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        logger.error(
            "GitHub connection binding failed",
            extra={
                "event": "connection.install",
                "tenant.id": str(tenant_id),
                "github.installation_id": installation_id,
                "error.message": "integrity_error",
            },
        )
        raise HTTPException(
            status_code=409, detail="Connection could not be created"
        ) from exc
    await session.refresh(account)
    logger.info(
        "GitHub connection bound",
        extra={
            "event": "connection.install",
            "tenant.id": str(tenant_id),
            "connected_account.id": str(account.id),
            "github.installation_id": installation_id,
        },
    )
    return account


async def _fetch_installation_account_name(installation_id: str) -> str | None:
    # Best effort: enriches the row with the org login. Never blocks binding.
    try:
        installation = await app_auth.get_installation(installation_id)
    except Exception:  # noqa: BLE001 — enrichment must not fail provisioning
        logger.warning(
            "Could not enrich GitHub installation with account name",
            extra={
                "event": "connection.install",
                "github.installation_id": installation_id,
            },
        )
        return None
    account = installation.get("account") or {}
    return account.get("login")


# --------------------------------------------------------------------------- #
# Webhook
# --------------------------------------------------------------------------- #
def verify_webhook_signature(body: bytes, signature_header: str | None) -> bool:
    if not settings.github_app_webhook_secret or not signature_header:
        return False
    expected = (
        "sha256="
        + hmac.new(
            settings.github_app_webhook_secret.encode(), body, sha256
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header)


async def process_installation_webhook(session: AsyncSession, payload: dict) -> None:
    """Keep an already-bound connection in sync with GitHub install events.

    Tenant binding happens in the setup callback (which carries our signed
    state); the webhook never sees the state, so it only updates existing rows.
    """
    action = payload.get("action")
    installation = payload.get("installation") or {}
    installation_id = str(installation.get("id") or "")
    if not installation_id:
        return

    result = await session.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.provider == IntegrationProvider.github.value,
            ConnectedAccount.external_account_id == installation_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        return

    previous_status = account.status
    if action in {"deleted", "revoked"}:
        account.status = ConnectionStatus.revoked.value
    elif action == "suspend":
        account.status = ConnectionStatus.paused.value
    elif action in {"created", "unsuspend", "new_permissions_accepted"}:
        account.status = ConnectionStatus.active.value
        github_account = installation.get("account") or {}
        if github_account.get("login"):
            account.external_account_name = github_account["login"]
        if installation.get("permissions"):
            account.scopes = installation["permissions"]
    else:
        return

    await session.commit()
    logger.info(
        "GitHub installation webhook processed",
        extra={
            "event": "connection.webhook",
            "github.webhook_action": action,
            "github.installation_id": installation_id,
            "connected_account.id": str(account.id),
            "tenant.id": str(account.tenant_id),
            "connection.status_before": previous_status,
            "connection.status_after": account.status,
        },
    )
