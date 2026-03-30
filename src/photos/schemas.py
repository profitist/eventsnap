from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PhotoUploadUrlRequest(BaseModel):
    filename: str | None = Field(default=None, max_length=255)
    content_type: str = Field(min_length=3, max_length=100, pattern=r"^image/")
    file_size_bytes: int | None = Field(default=None, gt=0)
    width_px: int | None = Field(default=None, gt=0)
    height_px: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def dimensions_both_or_neither(self) -> "PhotoUploadUrlRequest":
        width_set = self.width_px is not None
        height_set = self.height_px is not None
        if width_set != height_set:
            raise ValueError("Provide both width_px and height_px, or neither")
        return self


class PhotoUploadUrlResponse(BaseModel):
    photo_id: UUID
    upload_url: str
    s3_key: str
    expires_in: int
    moderation_status: str


class PhotoResponse(BaseModel):
    id: UUID
    gallery_id: UUID
    uploader_id: UUID | None
    original_s3_key: str
    original_url: str | None = None
    thumbnail_s3_key: str | None = None
    thumbnail_url: str | None = None
    original_filename: str | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    moderation_status: str
    moderation_comment: str | None = None
    moderated_at: datetime | None = None
    moderated_by_id: UUID | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PhotoListResponse(BaseModel):
    items: list[PhotoResponse]
    total: int


class PendingCountResponse(BaseModel):
    total: int


class PhotoApproveRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=512)


class PhotoRejectRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=512)
