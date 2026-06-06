import uuid

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.db import SQLAlchemyUserDatabase

from app.auth.database import get_user_db
from app.config import get_settings
from app.models.user import User

settings = get_settings()


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    async def create(
        self,
        user_create,
        safe: bool = False,
        request: Request | None = None,
    ) -> User:
        user = await super().create(user_create, safe=safe, request=request)
        if getattr(user_create, "name", None):
            await self.user_db.update(user, {"name": user_create.name})
        return user

    async def on_after_register(self, user: User, request: Request | None = None):
        pass


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


from fastapi_users.authentication import (  # noqa: E402
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)


def get_jwt_strategy() -> JWTStrategy[models.UP, models.ID]:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)

bearer_transport = BearerTransport(tokenUrl="api/v1/auth/login")

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
