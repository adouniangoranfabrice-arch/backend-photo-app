from datetime import datetime, timezone

from pydantic import BaseModel, Field

class EventModel(BaseModel):
    photographer_id: str

    name: str = Field(
        ...,
        min_length=2,
        max_length=200
    )

    description: str | None = None

    event_type: str = Field(
        ...,
        max_length=50
    )

    event_date: datetime | None = None

    location: str | None = Field(
        default=None,
        max_length=255
    )

    cover_photo: str | None = None

    public_token: str

    is_public: bool = True

    public_url: str

    status: str = "ACTIVE"

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )