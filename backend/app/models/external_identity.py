import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import IntegrationProvider

# Bridge between an external provider identity (today: a GitHub org member) and a
# Propel user. Populated by ingestion (github_identity service) from the org
# roster + user profiles; `propel_user_id` is filled in when we can confidently
# link or auto-provision. This is identity linkage, not user-record merging.


class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "external_user_id",
            name="uq_external_identity_user",
        ),
        UniqueConstraint(
            "tenant_id",
            "provider",
            "external_login",
            name="uq_external_identity_login",
        ),
        # One external identity per Propel user per tenant/provider.
        Index(
            "uq_external_identity_propel_user",
            "tenant_id",
            "provider",
            "propel_user_id",
            unique=True,
            postgresql_where=text("propel_user_id IS NOT NULL"),
        ),
        Index("ix_external_identities_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    connected_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_accounts.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=IntegrationProvider.github.value
    )
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_login: Mapped[str] = mapped_column(String(255), nullable=False)
    external_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    external_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_org_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    propel_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    link_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # `metadata` is reserved on the declarative Base, so the attribute is `meta`.
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    linked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
