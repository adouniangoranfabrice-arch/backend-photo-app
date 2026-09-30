from datetime import datetime

from pydantic import BaseModel


class PhotoResponse(BaseModel):

    id: str

    event_id: str

    photographer_id: str

    file_url: str

    thumbnail_url: str | None = None

    public_id: str | None = None

    original_name: str | None = None

    file_size: int | None = None

    mime_type: str | None = None

    width: int | None = None

    height: int | None = None

    format: str | None = None

    status: str

    created_at: datetime