from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from src.config import config


def create_token_pair(user_id: UUID) -> dict[str, str]:
    now = datetime.now(tz=timezone.utc)

    access_payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=config.ACCESS_TOKEN_TTL_MINUTES),
    }
    refresh_payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=config.REFRESH_TOKEN_TTL_DAYS),
    }

    access_token = jwt.encode(access_payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)

    return {"access_token": access_token, "refresh_token": refresh_token}


def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on any failure."""
    payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"Expected token type {expected_type!r}, got {payload.get('type')!r}"
        )
    return payload
