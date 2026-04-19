from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.schemas import UserResponse
from src.db.db_depends import get_async_session
from src.models.user import User
from src.s3.client import S3Client, get_s3_client
from src.users.schemas import (
    AvatarCompleteRequest,
    AvatarUploadUrlRequest,
    AvatarUploadUrlResponse,
    UserUpdateRequest,
)
from src.users.service import UserProfileService

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UserUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    service = UserProfileService(session)
    updated = await service.update_profile(user, body)
    return UserResponse.model_validate(updated)


@router.post("/me/avatar/upload-url", response_model=AvatarUploadUrlResponse)
async def create_avatar_upload_url(
    body: AvatarUploadUrlRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    s3: S3Client = Depends(get_s3_client),
) -> AvatarUploadUrlResponse:
    service = UserProfileService(session)
    upload_url, s3_key = await service.create_avatar_upload_url(user, body, s3)
    return AvatarUploadUrlResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=service.upload_ttl_seconds(),
    )


@router.post("/me/avatar/complete", response_model=UserResponse)
async def complete_avatar_upload(
    body: AvatarCompleteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    s3: S3Client = Depends(get_s3_client),
) -> UserResponse:
    service = UserProfileService(session)
    updated = await service.complete_avatar_upload(user, body.s3_key, s3)
    return UserResponse.model_validate(updated)
