from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import config
from src.models.user import User
from src.repositories.user_repository import UserRepository
from src.s3.client import S3Client, S3Error
from src.s3.keys import user_avatar_key
from src.users.schemas import AvatarUploadUrlRequest, UserUpdateRequest


class UserProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def update_profile(self, user: User, data: UserUpdateRequest) -> User:
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return user

        user = await self._users.update(user, **update_data)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def create_avatar_upload_url(
        self,
        user: User,
        data: AvatarUploadUrlRequest,
        s3: S3Client,
    ) -> tuple[str, str]:
        s3_key = user_avatar_key(user.id, data.content_type)
        try:
            upload_url = await s3.generate_presigned_upload_url(
                s3_key,
                data.content_type,
            )
            return upload_url, s3_key
        except S3Error as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            )

    async def complete_avatar_upload(
        self,
        user: User,
        s3_key: str,
        s3: S3Client,
    ) -> User:
        if not await s3.object_exists(s3_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Object not found in S3. Upload the file first.",
            )

        user = await self._users.update(user, avatar_s3_key=s3_key)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    @staticmethod
    def upload_ttl_seconds() -> int:
        return config.S3_PRESIGN_UPLOAD_TTL
