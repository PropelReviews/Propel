import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list["TenantMembership"]] = relationship(  # noqa: F821
        "TenantMembership", back_populates="tenant", lazy="selectin"
    )
    invites: Mapped[list["TenantInvite"]] = relationship(  # noqa: F821
        "TenantInvite", back_populates="tenant", lazy="selectin"
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
