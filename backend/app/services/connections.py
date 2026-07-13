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
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.github import app_auth
from app.models.connected_account import ConnectedAccount
from app.models.enums import AuthType, ConnectionStatus, IntegrationProvider, Role
from app.models.ingestion_run import IngestionRun
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.schemas.connection import ConnectionRead, ConnectionStatusUpdate
from app.services import github_identity
from app.services import role_permissions as role_permission_service

logger = logging.getLogger("propel.connections")

settings = get_settings()

_STATE_TTL_SECONDS = 600
_GITHUB_INSTALL_URL = "https://github.com/apps/{slug}/installations/new?state={state}"
_AUTH_META_KEY = "auth"
_SYNC_ERROR_CLEARED_AT_KEY = "sync_error_cleared_at"


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


def auth_error_message(account: ConnectedAccount) -> str | None:
    auth = (account.meta or {}).get(_AUTH_META_KEY)
    if not isinstance(auth, dict):
        return None
    message = auth.get("message")
    return str(message) if message else None


async def latest_sync_outcome(
    session: AsyncSession, account: ConnectedAccount
) -> tuple[str | None, str | None]:
    """Return ``(status, error)`` for the newest ingestion run on this account.

    Errors from before a reconnect (``meta.sync_error_cleared_at``) are ignored so
    the workspace UI does not keep showing a stale failure after the user fixes
    the connection.
    """
    run = await session.scalar(
        select(IngestionRun)
        .where(IngestionRun.connected_account_id == account.id)
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    if run is None:
        return None, None

    if run.status == "error" and _sync_error_is_stale(account, run.started_at):
        return None, None
    return run.status, run.error


def _sync_error_is_stale(
    account: ConnectedAccount, started_at: datetime | None
) -> bool:
    if started_at is None:
        return False
    cleared_raw = (account.meta or {}).get(_SYNC_ERROR_CLEARED_AT_KEY)
    if not isinstance(cleared_raw, str):
        return False
    try:
        cleared_at = datetime.fromisoformat(cleared_raw)
    except ValueError:
        return False
    started = (
        started_at if started_at.tzinfo is not None else started_at.replace(tzinfo=UTC)
    )
    if cleared_at.tzinfo is None:
        cleared_at = cleared_at.replace(tzinfo=UTC)
    return started <= cleared_at


async def to_connection_read(
    session: AsyncSession, account: ConnectedAccount
) -> ConnectionRead:
    last_status, last_error = await latest_sync_outcome(session, account)
    return ConnectionRead(
        id=account.id,
        tenant_id=account.tenant_id,
        provider=account.provider,
        auth_type=account.auth_type,
        external_account_id=account.external_account_id,
        external_account_name=account.external_account_name,
        status=account.status,
        auth_error=auth_error_message(account),
        last_sync_status=last_status,
        last_sync_error=last_error,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def clear_auth_failure(account: ConnectedAccount) -> None:
    """Clear auth / sync error markers after a successful reconnect.

    Drops ``meta.auth`` and stamps ``sync_error_cleared_at`` so stale failed
    ingestion runs no longer surface on the workspace Integrations cards.
    """
    meta = dict(account.meta or {})
    meta.pop(_AUTH_META_KEY, None)
    meta[_SYNC_ERROR_CLEARED_AT_KEY] = datetime.now(UTC).isoformat()
    account.meta = meta


def mark_auth_failure(
    account: ConnectedAccount,
    *,
    reason: str,
    message: str,
    status: ConnectionStatus = ConnectionStatus.paused,
) -> None:
    """Record that ingestion cannot authenticate this connection.

    Sets ``status`` so hourly jobs skip the account, and stores a short reason
    on ``meta.auth`` for the workspace Integrations UI.
    """
    meta = dict(account.meta or {})
    meta.pop(_SYNC_ERROR_CLEARED_AT_KEY, None)
    meta[_AUTH_META_KEY] = {
        "reason": reason,
        "message": message,
        "at": datetime.now(UTC).isoformat(),
    }
    account.status = status.value
    account.meta = meta


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
    if payload.status == ConnectionStatus.active:
        clear_auth_failure(account)
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
        clear_auth_failure(account)
    else:
        account.status = ConnectionStatus.active.value
        clear_auth_failure(account)
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
# Installation discovery (GitHub is the source of truth)
# --------------------------------------------------------------------------- #
async def _tenant_for_org_login(session: AsyncSession, login: str) -> Tenant:
    """Find or create the tenant for a GitHub org (slug = lowercased login)."""
    slug = login.lower()
    result = await session.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if tenant is not None:
        return tenant
    tenant = Tenant(name=login, slug=slug)
    session.add(tenant)
    await session.flush()
    session.add_all(role_permission_service.default_permission_rows(tenant.id))
    logger.info(
        "Auto-provisioned tenant for GitHub org",
        extra={
            "event": "connection.discover",
            "tenant.id": str(tenant.id),
            "github.org": login,
        },
    )
    return tenant


def _provision_account_for_installation(
    session: AsyncSession, tenant: Tenant, installation: dict
) -> ConnectedAccount:
    account = ConnectedAccount(
        tenant_id=tenant.id,
        provider=IntegrationProvider.github.value,
        auth_type=AuthType.github_app_installation.value,
        external_account_id=str(installation["id"]),
        external_account_name=(installation.get("account") or {}).get("login"),
        scopes=installation.get("permissions"),
        status=(
            ConnectionStatus.paused.value
            if installation.get("suspended_at")
            else ConnectionStatus.active.value
        ),
    )
    session.add(account)
    return account


async def sync_installations_from_github(session: AsyncSession) -> dict[str, int]:
    """Reconcile connected_accounts against the App's actual installations.

    Every org with the app installed gets an active connected_accounts row
    (auto-provisioning a tenant on first sight); rows whose installation no
    longer exists on GitHub are revoked. This makes installing the app the only
    step needed for an org to be ingested.
    """
    installations = await app_auth.list_installations()
    seen_ids: set[str] = set()
    created = updated = 0
    new_accounts: list[ConnectedAccount] = []

    for installation in installations:
        installation_id = str(installation.get("id") or "")
        login = (installation.get("account") or {}).get("login")
        if not installation_id or not login:
            continue
        seen_ids.add(installation_id)
        status = (
            ConnectionStatus.paused.value
            if installation.get("suspended_at")
            else ConnectionStatus.active.value
        )

        result = await session.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.provider == IntegrationProvider.github.value,
                ConnectedAccount.external_account_id == installation_id,
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            tenant = await _tenant_for_org_login(session, login)
            account = _provision_account_for_installation(session, tenant, installation)
            new_accounts.append(account)
            created += 1
            logger.info(
                "Auto-provisioned GitHub connection from installation",
                extra={
                    "event": "connection.discover",
                    "tenant.id": str(tenant.id),
                    "github.installation_id": installation_id,
                    "github.org": login,
                },
            )
        elif (
            account.status != status
            or account.external_account_name != login
            or account.scopes != installation.get("permissions")
            or (
                status == ConnectionStatus.active.value
                and auth_error_message(account) is not None
            )
        ):
            account.status = status
            account.external_account_name = login
            if installation.get("permissions"):
                account.scopes = installation["permissions"]
            if status == ConnectionStatus.active.value:
                clear_auth_failure(account)
            updated += 1

    # Installations gone from GitHub mean the app was uninstalled; revoke.
    revoke_query = select(ConnectedAccount).where(
        ConnectedAccount.provider == IntegrationProvider.github.value,
        ConnectedAccount.auth_type == AuthType.github_app_installation.value,
        ConnectedAccount.status != ConnectionStatus.revoked.value,
    )
    if seen_ids:
        revoke_query = revoke_query.where(
            ConnectedAccount.external_account_id.not_in(seen_ids)
        )
    revoked = 0
    for account in (await session.execute(revoke_query)).scalars():
        account.status = ConnectionStatus.revoked.value
        revoked += 1
        logger.info(
            "Revoked GitHub connection: installation no longer exists",
            extra={
                "event": "connection.discover",
                "connected_account.id": str(account.id),
                "github.installation_id": account.external_account_id,
            },
        )

    await session.commit()

    # Pre-import the member roster for orgs we just discovered so identities
    # and roles exist before anyone signs up (best effort — the hourly
    # ingestion run also reconciles).
    for account in new_accounts:
        try:
            await github_identity.import_roster_for_account(session, account)
        except Exception:  # noqa: BLE001 — enrichment must not fail discovery
            logger.exception(
                "GitHub roster import failed after discovery",
                extra={
                    "event": "connection.discover",
                    "connected_account.id": str(account.id),
                    "github.installation_id": account.external_account_id,
                },
            )

    summary = {"created": created, "updated": updated, "revoked": revoked}
    logger.info(
        "GitHub installation sync complete",
        extra={
            "event": "connection.discover",
            "github.installation_count": len(seen_ids),
            **{f"connection.{key}": value for key, value in summary.items()},
        },
    )
    return summary


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
    """Keep connected_accounts in sync with GitHub install events.

    A `created` event for an unknown installation auto-provisions a tenant and
    connection (same as the hourly installation sync); other events update the
    existing row's status.
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
        login = (installation.get("account") or {}).get("login")
        if action != "created" or not login:
            return
        tenant = await _tenant_for_org_login(session, login)
        account = _provision_account_for_installation(session, tenant, installation)
        await session.commit()
        logger.info(
            "Auto-provisioned GitHub connection from webhook",
            extra={
                "event": "connection.webhook",
                "github.webhook_action": action,
                "github.installation_id": installation_id,
                "tenant.id": str(tenant.id),
            },
        )
        try:
            await github_identity.import_roster_for_account(session, account)
        except Exception:  # noqa: BLE001 — enrichment must not fail the webhook
            logger.exception(
                "GitHub roster import failed after webhook install",
                extra={
                    "event": "connection.webhook",
                    "connected_account.id": str(account.id),
                    "github.installation_id": installation_id,
                },
            )
        return

    previous_status = account.status
    if action in {"deleted", "revoked"}:
        account.status = ConnectionStatus.revoked.value
    elif action == "suspend":
        account.status = ConnectionStatus.paused.value
    elif action in {"created", "unsuspend", "new_permissions_accepted"}:
        account.status = ConnectionStatus.active.value
        clear_auth_failure(account)
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
