import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Role


class PermissionDefinitionRead(BaseModel):
    key: str
    label: str
    description: str
    group: str


class RolePermissionsRead(BaseModel):
    role: Role
    permissions: list[str]


class RolePermissionsUpdate(BaseModel):
    permissions: list[str]


class TenantMembershipRead(BaseModel):
    """The calling user's role + effective permissions in a tenant."""

    tenant_id: uuid.UUID
    role: Role
    permissions: list[str]


class TenantWithMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    role: Role
    permissions: list[str]
