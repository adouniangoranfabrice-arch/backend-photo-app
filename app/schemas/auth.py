from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timezone
from app.models.users import UserRole


class RegisterRequest(BaseModel):
    firstname: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    lastname: str = Field(
        ...,
        min_length=2,
        max_length=100
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8
    )

    business_name: str | None = Field(
            default=None,
            max_length=150
        )
    
    bio: str | None = None

    
    
    city: str | None = Field(
            default=None,
            max_length=100
        )
    
    phone: str | None = Field(
            default=None,
            max_length=30
        )
    
    website: str | None = None

class UserResponse(BaseModel):
    id: str
    firstname: str
    lastname: str
    email: EmailStr
    phone: str | None = None
    role: UserRole
    business_name: str | None
    bio: str | None
    profile_photo: str | None
    city: str | None
    phone: str | None
    website: str | None
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

class LoginRequest(BaseModel):
    email: EmailStr

    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str