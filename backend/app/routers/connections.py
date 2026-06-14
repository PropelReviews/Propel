import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_tenant_context, require_permission
from app.auth.session import current_active_user
from app.config import get_settings
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.connection import (
    ConnectionRead,
    ConnectionStatusUpdate,
    GitHubInstallURL,
    InstallationSyncResult,
    LinearAuthorizeURL,
    LinearConnectionStatus,
)
from app.services import connections as connection_service
from app.services import linear_connection as linear_connection_service

logger = logging.getLogger("propel.connections")

router = APIRouter(prefix="/api/v1", tags=["connections"])
settings = get_settings()


@router.get(
    "/tenants/{tenant_id}/connections",
    response_model=list[ConnectionRead],
)
async def list_connections(
    ctx=Depends(require_permission("connections:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    accounts = await connection_service.list_connections(session, ctx.tenant.id)
    return [ConnectionRead.model_validate(a) for a in accounts]


@router.get(
    "/tenants/{tenant_id}/connections/github/install",
    response_model=GitHubInstallURL,
)
async def github_install_url(
    ctx=Depends(require_permission("connections:manage")),
    user: User = Depends(current_active_user),
):
    url = connection_service.build_github_install_url(ctx.tenant.id, user.id)
    return GitHubInstallURL(install_url=url)


@router.patch(
    "/tenants/{tenant_id}/connections/{connection_id}",
    response_model=ConnectionRead,
)
async def update_connection(
    connection_id: uuid.UUID,
    payload: ConnectionStatusUpdate,
    ctx=Depends(require_permission("connections:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    account = await connection_service.update_connection_status(
        session, ctx.tenant.id, connection_id, payload
    )
    return ConnectionRead.model_validate(account)


@router.get(
    "/tenants/{tenant_id}/connections/linear",
    response_model=LinearConnectionStatus,
)
async def linear_connection_status(
    ctx=Depends(get_tenant_context),
    session: AsyncSession = Depends(get_async_session),
):
    """Whether this tenant has an active Linear connection (visible to members)."""
    account = await linear_connection_service.get_active_linear_account(
        session, ctx.tenant.id
    )
    return LinearConnectionStatus(
        connected=account is not None,
        workspace_name=account.external_account_name if account else None,
    )


@router.get(
    "/tenants/{tenant_id}/connections/linear/authorize",
    response_model=LinearAuthorizeURL,
)
async def linear_authorize_url(
    ctx=Depends(require_permission("connections:manage")),
    user: User = Depends(current_active_user),
):
    """Authorization URL to connect a Linear workspace to this tenant.

    The SPA redirects the browser here; Linear returns to the backend callback,
    which exchanges the code and binds the connection.
    """
    url = linear_connection_service.build_authorize_url(ctx.tenant.id, user.id)
    return LinearAuthorizeURL(authorization_url=url)


@router.get("/connections/linear/callback")
async def linear_callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_async_session),
):
    """Linear redirects here after authorization with code + signed state.

    The signed state (not a bearer header) carries the initiating user, so this
    endpoint is reachable as a top-level browser navigation. On success or
    failure we bounce back to the SPA workspace settings page.
    """
    redirect_base = f"{settings.frontend_base_url}/settings/workspace"
    try:
        await linear_connection_service.bind_linear_oauth(session, code, state)
    except Exception:  # noqa: BLE001 — surface failure to the SPA, don't 500 the redirect
        logger.exception("Linear connection failed")
        return RedirectResponse(url=f"{redirect_base}?linear=error", status_code=303)
    return RedirectResponse(url=f"{redirect_base}?linear=connected", status_code=303)


@router.get("/connections/github/app", response_model=GitHubInstallURL)
async def github_public_install_url(
    user: User = Depends(current_active_user),
):
    """Public GitHub App install URL for onboarding (no tenant required).

    Installing the app is all an org needs: discovery auto-provisions the
    tenant + connection and imports the member roster with roles.
    """
    if not settings.github_app_slug:
        raise HTTPException(
            status_code=503, detail="GitHub App is not configured for this deployment"
        )
    return GitHubInstallURL(
        install_url=(
            f"https://github.com/apps/{settings.github_app_slug}/installations/new"
        )
    )


@router.post("/connections/github/sync", response_model=InstallationSyncResult)
async def sync_github_installations(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Reconcile connections with GitHub installations on demand.

    Lets onboarding pick up a fresh install immediately ("I've installed it")
    instead of waiting for the webhook or the hourly schedule. Idempotent.
    """
    summary = await connection_service.sync_installations_from_github(session)
    return InstallationSyncResult(**summary)


@router.get("/connections/github/setup")
async def github_setup_callback(
    installation_id: str,
    state: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """GitHub redirects here after install with installation_id + signed state."""
    await connection_service.bind_github_installation(
        session, user.id, installation_id, state
    )
    # Bounce the admin back to the SPA connections view (the SPA is a separate
    # origin from the API, so use the frontend base URL, not the callback host).
    return RedirectResponse(
        url=f"{settings.frontend_base_url}/connections?github=connected",
        status_code=303,
    )


@router.post("/webhooks/github", status_code=202)
async def github_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not connection_service.verify_webhook_signature(body, signature):
        logger.warning(
            "Rejected GitHub webhook: invalid signature",
            extra={"event": "connection.webhook", "error.message": "invalid_signature"},
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = request.headers.get("X-GitHub-Event", "")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if event == "installation":
        await connection_service.process_installation_webhook(session, payload)
    return {"status": "accepted"}
