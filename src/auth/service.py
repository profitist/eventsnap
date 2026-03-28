from uuid import UUID

import jwt as pyjwt
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import create_token_pair, decode_token
from src.auth.passwords import hash_password, verify_password
from src.auth.schemas import AuthResponse, RegisterRequest, TokenPair, UserResponse
from src.repositories.user_repository import UserPasswordCredentialRepository, UserRepository


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._credentials = UserPasswordCredentialRepository(session)

    async def register(self, data: RegisterRequest) -> AuthResponse:
        email = data.email.lower().strip()

        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = await self._users.create(
            email=email,
            display_name=data.display_name,
        )
        pwd_hash = hash_password(data.password)
        await self._credentials.upsert_hash(user.id, pwd_hash)
        await self._session.commit()

        tokens = create_token_pair(user.id)
        return AuthResponse(
            user=UserResponse.model_validate(user),
            tokens=TokenPair(**tokens),
        )

    async def login(self, email: str, password: str) -> AuthResponse:
        email = email.lower().strip()

        user = await self._users.get_by_email(email)
        if user is None:
            # Constant-time: run bcrypt even on missing user to prevent timing attacks
            verify_password(password, "$2b$12$" + "x" * 53)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        credential = await self._credentials.get_by_user_id(user.id)
        if credential is None or not verify_password(password, credential.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        tokens = create_token_pair(user.id)
        return AuthResponse(
            user=UserResponse.model_validate(user),
            tokens=TokenPair(**tokens),
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except pyjwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user = await self._users.get_active_by_id(UUID(payload["sub"]))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        tokens = create_token_pair(user.id)
        return TokenPair(**tokens)
