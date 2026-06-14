import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.oidc import oauth
from app.auth.reconcile import get_or_create_test_user, reconcile_user_from_claims
from app.auth.session import (
    clear_session,
    current_active_user,
    establish_session,
)
from app.config import get_settings
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.user import GitHubConnection, GitHubLinkURL, UserMeRead
from app.services import github_identity, github_link

logger = logging.getLogger("propel.auth")
settings = get_settings()
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _callback_url(request: Request) -> str:
    return str(request.url_for("oidc_callback"))


def _post_login_redirect(request: Request) -> str:
    return request.session.pop("post_login_redirect", settings.frontend_base_url)


@router.get("/login")
async def login(request: Request):
    """Start OIDC Auth Code + PKCE flow (redirect to Zitadel hosted login)."""
    if not settings.zitadel_oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC_NOT_CONFIGURED",
        )
    redirect_uri = _callback_url(request)
    return await oauth.zitadel.authorize_redirect(
        request,
        redirect_uri,
        code_challenge_method="S256",
    )


@router.get("/callback", name="oidc_callback")
async def oidc_callback(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """OIDC callback — exchange code, reconcile user, set session cookie."""
    if not settings.zitadel_oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC_NOT_CONFIGURED",
        )
    try:
        token = await oauth.zitadel.authorize_access_token(request)
        userinfo = token.get("userinfo") or await oauth.zitadel.parse_id_token(
            request, token
        )
    except Exception:
        logger.exception("OIDC callback failed")
        return RedirectResponse(
            url=f"{settings.frontend_base_url}/signin?error=oidc_failed",
            status_code=303,
        )

    sub = userinfo.get("sub")
    email = userinfo.get("email")
    if not sub or not email:
        return RedirectResponse(
            url=f"{settings.frontend_base_url}/signin?error=missing_claims",
            status_code=303,
        )

    user = await reconcile_user_from_claims(
        session,
        sub=sub,
        email=email,
        email_verified=bool(userinfo.get("email_verified")),
        org_id=userinfo.get("urn:zitadel:iam:org:id"),
        org_name=userinfo.get("urn:zitadel:iam:org:name"),
        name=userinfo.get("name") or userinfo.get("preferred_username"),
    )
    establish_session(request, user)
    return RedirectResponse(url=_post_login_redirect(request), status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """Clear the BFF session and redirect through Zitadel end-session."""
    clear_session(request)
    if not settings.zitadel_oidc_enabled:
        return RedirectResponse(url=settings.frontend_base_url, status_code=303)

    params = urlencode(
        {
            "post_logout_redirect_uri": settings.frontend_base_url,
            "client_id": settings.zitadel_client_id,
        }
    )
    end_session = f"{settings.zitadel_issuer.rstrip('/')}/oidc/v1/end_session?{params}"
    return RedirectResponse(url=end_session, status_code=303)


@router.get("/me", response_model=UserMeRead)
async def me(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    account = await github_link.get_github_account(session, user.id)
    github = GitHubConnection()
    if account is not None:
        github = GitHubConnection(
            connected=True,
            account_id=account.account_id,
            account_email=account.account_email or None,
            login=await github_link.get_linked_github_login(session, user.id),
        )
    return UserMeRead(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        email_verified=user.email_verified,
        created_at=user.created_at,
        github=github,
    )


@router.get("/github/link/authorize", response_model=GitHubLinkURL)
async def github_link_authorize(user: User = Depends(current_active_user)):
    """Return the GitHub authorization URL for the signed-in user to link."""
    url = await github_link.build_authorize_url(user.id)
    return GitHubLinkURL(authorization_url=url)


@router.get("/github/link/callback")
async def github_link_callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_async_session),
):
    """GitHub redirects here after the user authorizes the link."""
    redirect_base = f"{settings.frontend_base_url}/profile"
    try:
        await github_link.complete_link(session, code, state)
    except Exception:
        logger.exception("GitHub account link failed")
        return RedirectResponse(url=f"{redirect_base}?github=error", status_code=303)
    return RedirectResponse(url=f"{redirect_base}?github=connected", status_code=303)


@router.post("/test/login")
async def test_login(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    email: str = "test@example.com",
):
    """Test-only session bootstrap (APP_ENV=test)."""
    if not get_settings().is_test_env:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user = await get_or_create_test_user(session, email=email)
    await github_identity.link_email_identity(session, user.id, user.email)
    establish_session(request, user)
    return {"user_id": str(user.id), "email": user.email}
