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


class MemberRoleUpdate(BaseModel):
    role: Role
