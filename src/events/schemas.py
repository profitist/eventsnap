from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class EventCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    venue_name: str | None = Field(default=None, max_length=255)
    venue_address: str | None = Field(default=None, max_length=512)
    latitude: float | None = None
    longitude: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def coords_both_or_neither(self) -> "EventCreateRequest":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or neither")
        return self

    @model_validator(mode="after")
    def ends_after_starts(self) -> "EventCreateRequest":
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class EventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, pattern="^(draft|active|finished|archived)$")
    venue_name: str | None = Field(default=None, max_length=255)
    venue_address: str | None = Field(default=None, max_length=512)
    latitude: float | None = None
    longitude: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def coords_both_or_neither(self) -> "EventUpdateRequest":
        lat_set = "latitude" in self.model_fields_set
        lon_set = "longitude" in self.model_fields_set
        if lat_set != lon_set:
            raise ValueError("Provide both latitude and longitude, or neither")
        return self

    @model_validator(mode="after")
    def ends_after_starts(self) -> "EventUpdateRequest":
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class EventResponse(BaseModel):
    id: UUID
    organizer_id: UUID | None
    title: str
    description: str | None
    status: str
    cover_s3_key: str | None
    venue_name: str | None
    venue_address: str | None
    latitude: float | None
    longitude: float | None
    starts_at: datetime | None
    ends_at: datetime | None
    qr_token: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int


class EventJoinLinkResponse(BaseModel):
    event_id: UUID
    qr_token: str
    join_path: str


class EventJoinRequest(BaseModel):
    qr_token: str = Field(min_length=8, max_length=128)


class EventJoinResponse(BaseModel):
    event: EventResponse
    already_joined: bool


class EventParticipantResponse(BaseModel):
    user_id: UUID
    display_name: str
    avatar_s3_key: str | None = None
    role: str
    joined_at: datetime


class EventParticipantListResponse(BaseModel):
    items: list[EventParticipantResponse]
    total: int


class GalleryResponse(BaseModel):
    id: UUID
    event_id: UUID
    title: str | None
    description: str | None
    moderation_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GalleryUpdateRequest(BaseModel):
    moderation_enabled: bool | None = None


class CoverUploadUrlRequest(BaseModel):
    content_type: str = Field(min_length=3, max_length=100, pattern=r"^image/")


class CoverUploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in: int


class CoverCompleteRequest(BaseModel):
    s3_key: str = Field(min_length=1, max_length=512)
