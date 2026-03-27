import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_NAME: str = os.getenv("DB_NAME", "eventsnap")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "defaultsecret")

    @classmethod
    def get_database_url(cls):
        return f"postgresql+asyncpg://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}/{cls.DB_NAME}"
