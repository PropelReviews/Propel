import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ConnectionStatus


class ConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    provider: str
    auth_type: str
    external_account_id: str
    external_account_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ConnectionStatusUpdate(BaseModel):
    # Admins may pause or revoke; reactivation is allowed for paused accounts.
    status: ConnectionStatus


class GitHubInstallURL(BaseModel):
    install_url: str


class InstallationSyncResult(BaseModel):
    created: int
    updated: int
    revoked: int
