from sqlalchemy.engine import URL, make_url
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    DATABASE_URL: str | None = None
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "eventsnap"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_PRE_PING: bool = True
    SECRET_KEY: str

    # S3 / object storage configuration
    # Any S3-compatible provider works (AWS, MinIO, Yandex Cloud, etc.)
    S3_BUCKET_NAME: str = "eventsnap"
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str | None = None  # None = use AWS default
    S3_ACCESS_KEY_ID: str
    S3_SECRET_ACCESS_KEY: str
    # Base URL for building public object URLs returned to clients.
    # Example: "https://cdn.eventsnap.app" or "https://<bucket>.s3.<region>.amazonaws.com"
    S3_BASE_URL: str
    # Lifetime of presigned upload URLs in seconds (default: 15 minutes)
    S3_PRESIGN_UPLOAD_TTL: int = 900
    # Lifetime of presigned download URLs in seconds (default: 1 hour)
    S3_PRESIGN_DOWNLOAD_TTL: int = 3600

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 30
    REFRESH_TOKEN_TTL_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self._normalize_database_url(self.DATABASE_URL)

        url = URL.create(
            "postgresql+asyncpg",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        )
        return url.render_as_string(hide_password=False)

    def get_safe_database_url(self) -> str:
        return make_url(self.get_database_url()).render_as_string(hide_password=True)

    @staticmethod
    def _normalize_database_url(database_url: str) -> str:
        normalized = database_url.strip()
        if normalized.startswith("postgres://"):
            normalized = "postgresql://" + normalized.removeprefix("postgres://")

        url = make_url(normalized)
        if url.drivername == "postgresql" or url.drivername.startswith("postgresql+"):
            url = url.set(drivername="postgresql+asyncpg")
        return url.render_as_string(hide_password=False)


config = Config()
