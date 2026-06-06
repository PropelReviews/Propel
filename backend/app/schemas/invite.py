import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import Role


class InviteCreate(BaseModel):
    email: EmailStr
    role: Role


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: Role
    expires_at: datetime
    created_at: datetime
    invited_by_user_id: uuid.UUID | None


class InviteCreated(BaseModel):
    invite: InviteRead
    invite_url: str


class InviteAcceptRead(BaseModel):
    tenant_id: uuid.UUID
    role: Role
