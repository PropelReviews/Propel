import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.manager import current_active_user
from app.config import get_settings
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.connection import (
    ConnectionRead,
    ConnectionStatusUpdate,
    GitHubInstallURL,
    InstallationSyncResult,
)
from app.services import connections as connection_service

logger = logging.getLogger("propel.connections")

router = APIRouter(prefix="/api/v1", tags=["connections"])
settings = get_settings()


@router.get(
    "/tenants/{tenant_id}/connections",
    response_model=list[ConnectionRead],
)
async def list_connections(
    ctx=Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    accounts = await connection_service.list_connections(session, ctx.tenant.id)
    return [ConnectionRead.model_validate(a) for a in accounts]


@router.get(
    "/tenants/{tenant_id}/connections/github/install",
    response_model=GitHubInstallURL,
)
async def github_install_url(
    ctx=Depends(require_admin),
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
    ctx=Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    account = await connection_service.update_connection_status(
        session, ctx.tenant.id, connection_id, payload
    )
    return ConnectionRead.model_validate(account)


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
