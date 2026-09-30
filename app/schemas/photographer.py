from datetime import datetime

from pydantic import BaseModel, Field


class PhotographerCreate(BaseModel):
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


class PhotographerUpdate(BaseModel):
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


class PhotographerResponse(BaseModel):
    id: str
    user_id: str
    business_name: str | None
    bio: str | None
    profile_photo: str | None
    city: str | None
    phone: str | None
    website: str | None
    is_verified: bool
    created_at: datetime
    updated_at: datetime