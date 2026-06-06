import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import Role


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: EmailStr
    name: str | None
    role: Role
    created_at: datetime
    github_login: str | None = None
    github_link_status: str | None = None


class MemberRoleUpdate(BaseModel):
    role: Role


class GitHubIdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_user_id: str
    external_login: str
    external_email: str | None
    external_name: str | None
    github_org_role: str | None
    propel_user_id: uuid.UUID | None
    link_method: str | None
    status: str
    last_synced_at: datetime | None
    linked_at: datetime | None


class GitHubIdentityLink(BaseModel):
    user_id: uuid.UUID
