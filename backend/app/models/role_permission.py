import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import Role


class TenantRolePermission(Base):
    """A permission grant for a role within a tenant.

    Presence of a row means the role holds the permission; absence means it
    doesn't. Defaults are seeded on tenant creation (see services/tenants.py).
    """

    __tablename__ = "tenant_role_permissions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "role", "permission", name="uq_tenant_role_permission"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="role", create_type=False), nullable=False
    )
    permission: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
