from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ActivityLogModel(BaseModel):
    user_id: str | None = None
    photographer_id: str | None = None

    user_role: str | None = None

    action: str
    resource: str | None = None
    resource_id: str | None = None

    description: str | None = None
    target: str | None = None

    ip_address: str | None = None
    user_agent: str | None = None

    metadata: dict = Field(default_factory=dict)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )