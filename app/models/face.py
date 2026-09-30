from datetime import datetime, timezone

from pydantic import BaseModel, Field


class FaceModel(BaseModel):
    photo_id: str
    event_id: str
    photographer_id: str

    person_id: str | None = None

    x: float
    y: float
    width: float
    height: float

    confidence: float = Field(
        ge=0,
        le=1
    )

    embedding: list[float] | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )