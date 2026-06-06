import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class WaitlistCreate(BaseModel):
    email: EmailStr


class WaitlistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime
