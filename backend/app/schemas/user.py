import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class GitHubConnection(BaseModel):
    connected: bool = False
    account_id: str | None = None
    account_email: str | None = None
    login: str | None = None


class GitHubLinkURL(BaseModel):
    authorization_url: str


class UserMeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None
    is_active: bool
    email_verified: bool
    created_at: datetime | None = None
    github: GitHubConnection = GitHubConnection()
