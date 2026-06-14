import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.enums import MembershipStatus
from app.models.invite import TenantInvite
from app.models.membership import TenantMembership
from app.models.user import User
from app.schemas.invite import InviteCreate, InviteCreated, InviteRead

settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _build_invite_url(token: str) -> str:
    # Points at the SPA accept page, which signs the user in if needed and
    # then POSTs /api/v1/invites/{token}/accept.
    return f"{settings.frontend_base_url}/invites/{token}/accept"


async def create_invite(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    inviter: User,
    payload: InviteCreate,
) -> InviteCreated:
    existing_member = await session.execute(
        select(TenantMembership)
        .join(User, TenantMembership.user_id == User.id)
        .where(TenantMembership.tenant_id == tenant_id, User.email == payload.email)
    )
    if existing_member.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this tenant",
        )

    pending = await session.execute(
        select(TenantInvite).where(
            TenantInvite.tenant_id == tenant_id,
            TenantInvite.email == payload.email,
            TenantInvite.accepted_at.is_(None),
        )
    )
    if pending.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pending invite already exists for this email",
        )

    raw_token = secrets.token_urlsafe(32)
    invite = TenantInvite(
        tenant_id=tenant_id,
        email=payload.email.lower(),
        role=payload.role,
        token_hash=_hash_token(raw_token),
        invited_by_user_id=inviter.id,
        expires_at=datetime.now(UTC)
        + timedelta(hours=settings.invite_token_lifetime_hours),
    )
    session.add(invite)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invite could not be created",
        ) from exc
    await session.refresh(invite)

    invite_read = InviteRead.model_validate(invite)
    return InviteCreated(invite=invite_read, invite_url=_build_invite_url(raw_token))


async def list_pending_invites(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[InviteRead]:
    result = await session.execute(
        select(TenantInvite)
        .where(
            TenantInvite.tenant_id == tenant_id,
            TenantInvite.accepted_at.is_(None),
        )
        .order_by(TenantInvite.created_at.desc())
    )
    return [InviteRead.model_validate(inv) for inv in result.scalars().all()]


async def revoke_invite(
    session: AsyncSession, tenant_id: uuid.UUID, invite_id: uuid.UUID
) -> None:
    invite = await session.get(TenantInvite, invite_id)
    if invite is None or invite.tenant_id != tenant_id or not invite.is_pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )
    await session.delete(invite)
    await session.commit()


async def accept_invite(
    session: AsyncSession, user: User, raw_token: str
) -> TenantMembership:
    token_hash = _hash_token(raw_token)
    result = await session.execute(
        select(TenantInvite).where(TenantInvite.token_hash == token_hash)
    )
    invite = result.scalar_one_or_none()
    if invite is None or not invite.is_pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite token"
        )
    if invite.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="Invite has expired"
        )
    if invite.email.lower() != user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite email does not match authenticated user",
        )

    existing = await session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == invite.tenant_id,
            TenantMembership.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already a member of this tenant",
        )

    membership = TenantMembership(
        tenant_id=invite.tenant_id,
        user_id=user.id,
        role=invite.role,
        status=MembershipStatus.active,
    )
    invite.accepted_at = datetime.now(UTC)
    session.add(membership)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not accept invite",
        ) from exc
    await session.refresh(membership)
    return membership
