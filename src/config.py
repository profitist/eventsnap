from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "localhost"
    DB_NAME: str = "eventsnap"
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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def get_database_url(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}/{self.DB_NAME}"


config = Config()