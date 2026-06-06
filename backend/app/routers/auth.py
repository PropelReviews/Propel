from fastapi import APIRouter, Depends

from app.auth.manager import auth_backend, current_active_user, fastapi_users
from app.auth.oauth import OAUTH_STATE_SECRET, github_oauth_client, google_oauth_client
from app.config import get_settings
from app.models.user import User
from app.schemas.user import UserCreate, UserMeRead, UserRead

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
            associate_by_email=True,
            is_verified_by_default=True,
        ),
        prefix="/google",
    )

if settings.oauth_github_client_id and settings.oauth_github_client_secret:
    router.include_router(
        fastapi_users.get_oauth_router(
            github_oauth_client,
            auth_backend,
            OAUTH_STATE_SECRET,
            redirect_url=f"{settings.oauth_callback_base_url}/api/v1/auth/github/callback",
            associate_by_email=True,
            is_verified_by_default=True,
        ),
        prefix="/github",
    )


@router.get("/me", response_model=UserMeRead)
async def me(user: User = Depends(current_active_user)):
    return UserMeRead.model_validate(user)
