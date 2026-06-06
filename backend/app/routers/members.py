import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_async_session
from app.schemas.membership import (
    GitHubIdentityLink,
    GitHubIdentityRead,
    MemberRead,
    MemberRoleUpdate,
)
from app.services import github_identity
from app.services import members as member_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/members", tags=["members"])

github_members_router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/github-members", tags=["github-members"]
)


@router.get("/", response_model=list[MemberRead])
async def list_members(
    ctx=Depends(require_permission("members:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return await member_service.list_members(session, ctx.tenant.id)


@router.patch("/{user_id}/role", response_model=MemberRead)
async def assign_role(
    user_id: uuid.UUID,
    payload: MemberRoleUpdate,
    ctx=Depends(require_permission("members:assign_role")),
    session: AsyncSession = Depends(get_async_session),
):
    return await member_service.assign_role(session, ctx.tenant.id, user_id, payload)


@router.delete("/{user_id}", status_code=204)
async def remove_member(
    user_id: uuid.UUID,
    ctx=Depends(require_permission("members:remove")),
    session: AsyncSession = Depends(get_async_session),
):
    await member_service.remove_member(session, ctx.tenant.id, user_id)


@github_members_router.get("/", response_model=list[GitHubIdentityRead])
async def list_github_members(
    ctx=Depends(require_permission("github_identities:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    return await github_identity.list_identities(session, ctx.tenant.id)


@github_members_router.patch("/{identity_id}/link", response_model=GitHubIdentityRead)
async def link_github_member(
    identity_id: uuid.UUID,
    payload: GitHubIdentityLink,
    ctx=Depends(require_permission("github_identities:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    return await github_identity.manual_link(
        session, ctx.tenant.id, identity_id, payload.user_id
    )


@github_members_router.delete("/{identity_id}/link", response_model=GitHubIdentityRead)
async def unlink_github_member(
    identity_id: uuid.UUID,
    ctx=Depends(require_permission("github_identities:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    return await github_identity.manual_unlink(session, ctx.tenant.id, identity_id)
