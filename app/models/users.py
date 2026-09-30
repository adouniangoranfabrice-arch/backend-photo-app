from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    PHOTOGRAPHER = "PHOTOGRAPHER"
    USER = "USER"


class UserModel(BaseModel):
    firstname: str = Field(..., min_length=2, max_length=100)
    lastname: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password_hash: str
    phone: str | None = Field(default=None, max_length=30)
    role: UserRole = UserRole.PHOTOGRAPHER
    is_active: bool = True

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
