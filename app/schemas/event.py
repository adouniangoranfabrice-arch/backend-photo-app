# from datetime import datetime

# from pydantic import BaseModel, Field


# class EventCreate(BaseModel):
#     name: str = Field(
#         ...,
#         min_length=2,
#         max_length=200
#     )

#     description: str | None = None

#     event_type: str = Field(
#         ...,
#         max_length=50
#     )

#     event_date: datetime | None = None

#     location: str | None = Field(
#         default=None,
#         max_length=255
#     )

#     cover_photo: str | None = None

#     is_public: bool = True


# class EventUpdate(BaseModel):
#     name: str | None = Field(
#         default=None,
#         min_length=2,
#         max_length=200
#     )

#     description: str | None = None

#     event_type: str | None = Field(
#         default=None,
#         max_length=50
#     )

#     event_date: datetime | None = None

#     location: str | None = Field(
#         default=None,
#         max_length=255
#     )

#     cover_photo: str | None = None

#     is_public: bool | None = None

#     status: str | None = None


# class EventResponse(BaseModel):
#     id: str
#     photographer_id: str
#     name: str
#     description: str | None
#     event_type: str
#     event_date: datetime | None
#     location: str | None
#     cover_photo: str | None
#     public_token: str
#     is_public: bool
#     status: str
#     created_at: datetime
#     updated_at: datetime

from datetime import datetime

from pydantic import BaseModel, Field


class EventCreate(BaseModel):

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

    is_public: bool = True


class EventUpdate(BaseModel):

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=200
    )

    description: str | None = None

    event_type: str | None = Field(
        default=None,
        max_length=50
    )

    event_date: datetime | None = None

    location: str | None = Field(
        default=None,
        max_length=255
    )

    is_public: bool | None = None

    status: str | None = None


class EventResponse(BaseModel):

    id: str

    photographer_id: str

    name: str

    description: str | None

    event_type: str

    event_date: datetime | None

    location: str | None

    cover_photo: str | None

    public_token: str

    public_url: str

    is_public: bool

    status: str

    created_at: datetime

    updated_at: datetime