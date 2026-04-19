from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import config

DB_URL = config.get_database_url()

async_engine = create_async_engine(
    DB_URL,
    echo=config.DB_ECHO,
    pool_pre_ping=config.DB_POOL_PRE_PING,
    pool_size=config.DB_POOL_SIZE,
    max_overflow=config.DB_MAX_OVERFLOW,
)

async_session_maker = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
