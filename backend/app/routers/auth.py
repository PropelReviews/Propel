import logging

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.manager import (
    auth_backend,
    current_active_user,
    fastapi_users,
    get_jwt_strategy,
    get_user_manager,
)
from app.auth.oauth import github_oauth_client, google_oauth_client
from app.config import get_settings
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.user import (
    GitHubConnection,
    GitHubLinkURL,
    UserCreate,
    UserMeRead,
    UserRead,
)
from app.services import github_link, github_login

logger = logging.getLogger("propel.auth")
settings = get_settings()
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="",
)
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="",
)

if settings.oauth_google_client_id and settings.oauth_google_client_secret:
    router.include_router(
        fastapi_users.get_oauth_router(
            google_oauth_client,
            auth_backend,
            settings.jwt_secret,
            redirect_url=f"{settings.oauth_callback_base_url}/api/v1/auth/google/callback",
            # Disabled until email verification prevents account
            # pre-registration attacks.
            associate_by_email=False,
            is_verified_by_default=True,
        ),
        prefix="/google",
    )

if settings.oauth_github_client_id and settings.oauth_github_client_secret:
    router.include_router(
        fastapi_users.get_oauth_router(
            github_oauth_client,
            auth_backend,
            settings.jwt_secret,
            redirect_url=f"{settings.oauth_callback_base_url}/api/v1/auth/github/callback",
            associate_by_email=False,
            is_verified_by_default=True,
        ),
        prefix="/github",
    )


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
        is_verified=user.is_verified,
        created_at=user.created_at,
        github=github,
    )


@router.get("/github/login/authorize", response_model=GitHubLinkURL)
async def github_login_authorize():
    """Return the GitHub authorization URL to sign in / sign up with GitHub."""
    url = await github_login.build_authorize_url()
    return GitHubLinkURL(authorization_url=url)


@router.get("/github/login/callback")
async def github_login_callback(
    code: str,
    state: str,
    user_manager=Depends(get_user_manager),
    strategy=Depends(get_jwt_strategy),
):
    """GitHub redirects here after the user authorizes sign-in.

    Finds or creates the Propel user for this GitHub identity, mints a session
    JWT, and bounces back to the SPA OAuth handler with the token in the URL
    fragment (fragments are never sent to a server). On failure we redirect with
    an `error` marker instead.
    """
    handler = f"{settings.oauth_callback_base_url}/auth/github/callback"
    try:
        github_login.verify_login_state(state)
        access_token, account_id, account_email = await github_login.exchange_code(code)
        user = await user_manager.oauth_callback(
            "github",
            access_token,
            account_id,
            account_email or "",
            associate_by_email=False,
            is_verified_by_default=True,
        )
        if not user.is_active:
            return RedirectResponse(
                url=f"{handler}#error=account_inactive", status_code=303
            )
        token = await strategy.write_token(user)
    except Exception:  # noqa: BLE001 — report failure to the SPA, don't 500 the redirect
        logger.exception("GitHub login failed")
        return RedirectResponse(
            url=f"{handler}#error=github_login_failed", status_code=303
        )
    return RedirectResponse(url=f"{handler}#access_token={token}", status_code=303)


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
    """GitHub redirects here after the user authorizes the link.

    The state token (not a bearer header) carries the initiating user, so this
    endpoint is reachable as a top-level browser navigation. On success we bounce
    back to the SPA profile page.
    """
    redirect_base = f"{settings.oauth_callback_base_url}/profile"
    try:
        await github_link.complete_link(session, code, state)
    except Exception:  # noqa: BLE001 — surface failure to the SPA, don't 500 the redirect
        logger.exception("GitHub account link failed")
        return RedirectResponse(url=f"{redirect_base}?github=error", status_code=303)
    return RedirectResponse(url=f"{redirect_base}?github=connected", status_code=303)
