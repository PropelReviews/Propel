"""OIDC session helpers and current-user dependency."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_async_session
from app.models.user import User

SESSION_USER_ID_KEY = "user_id"


def get_session_secret() -> str:
    settings = get_settings()
    if (
        settings.app_env.lower() in {"production", "prod", "beta"}
        and len(settings.session_secret) < 32
    ):
        raise RuntimeError("SESSION_SECRET must be at least 32 characters")
    return settings.session_secret


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> User:
    raw_id = request.session.get(SESSION_USER_ID_KEY)
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        user_id = uuid.UUID(str(raw_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        ) from exc

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


current_active_user = get_current_user


def establish_session(request: Request, user: User) -> None:
    request.session[SESSION_USER_ID_KEY] = str(user.id)


def clear_session(request: Request) -> None:
    request.session.clear()
