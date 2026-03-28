from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from src.auth.service import AuthService
from src.db.db_depends import get_async_session
from src.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_async_session),
) -> AuthResponse:
    service = AuthService(session)
    return await service.register(body)


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
) -> AuthResponse:
    service = AuthService(session)
    return await service.login(body.email, body.password)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TokenPair:
    service = AuthService(session)
    return await service.refresh(body.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
