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
    # Set when an ingestion run failed because install/auth is broken.
    auth_error: str | None = None
    # Latest ingestion_run for this connection (any outcome).
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ConnectionStatusUpdate(BaseModel):
    # Admins may pause or revoke; reactivation is allowed for paused accounts.
    status: ConnectionStatus


class GitHubInstallURL(BaseModel):
    install_url: str


class LinearAuthorizeURL(BaseModel):
    authorization_url: str


class LinearConnectionStatus(BaseModel):
    connected: bool
    workspace_name: str | None = None
    # Underlying connected_accounts.status when a row exists (active/paused/revoked).
    status: str | None = None
    # Human-readable reason when ingestion paused the connection after an auth failure.
    auth_error: str | None = None
    # Latest Linear ingestion_run outcome for this tenant connection.
    last_sync_status: str | None = None
    last_sync_error: str | None = None


class InstallationSyncResult(BaseModel):
    created: int
    updated: int
    revoked: int
