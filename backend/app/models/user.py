import uuid
from datetime import datetime

from fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Login OAuth only (Google/GitHub identity). Tool API tokens belong in the
# future connected_accounts table — see docs/backend/data-model.md.


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    __tablename__ = "oauth_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount", lazy="selectin", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["TenantMembership"]] = relationship(  # noqa: F821
        "TenantMembership", back_populates="user", lazy="selectin"
    )
