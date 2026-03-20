from typing import Generator

from .database import async_session_maker


def get_async_session() -> Generator:
    with async_session_maker() as session:
        yield session
