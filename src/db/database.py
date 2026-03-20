from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from src.config import Config


DB_URL = Config.get_database_url()

async_engine = create_async_engine(DB_URL, echo=True)

async_session_maker = sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
