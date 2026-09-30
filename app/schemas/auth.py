from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timezone


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

class UserResponse(BaseModel):
    id: str
    firstname: str
    lastname: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

class LoginRequest(BaseModel):
    email: EmailStr

    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"