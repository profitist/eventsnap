from pydantic import BaseModel, Field


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=150)


class AvatarUploadUrlRequest(BaseModel):
    content_type: str = Field(min_length=3, max_length=100, pattern=r"^image/")


class AvatarUploadUrlResponse(BaseModel):
    upload_url: str
    s3_key: str
    expires_in: int


class AvatarCompleteRequest(BaseModel):
    s3_key: str = Field(min_length=1, max_length=512)
