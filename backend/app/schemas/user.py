import uuid
from datetime import datetime

from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Role


class UserRead(schemas.BaseUser[uuid.UUID]):
    name: str | None = None
    created_at: datetime | None = None


class UserCreate(schemas.BaseUserCreate):
    name: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    name: str | None = None


class UserMeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime | None = None
