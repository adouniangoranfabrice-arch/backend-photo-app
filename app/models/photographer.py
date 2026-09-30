from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PhotographerModel(BaseModel):
    user_id: str

    business_name: str | None = Field(
        default=None,
        max_length=150
    )

    bio: str | None = None

    profile_photo: str | None = None

    city: str | None = Field(
        default=None,
        max_length=100
    )

    phone: str | None = Field(
        default=None,
        max_length=30
    )

    website: str | None = None

    is_verified: bool = False

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )