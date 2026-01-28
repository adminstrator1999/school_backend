"""Application settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    APP_NAME: str = "School Accounting"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/school_accounting"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 3  # 3 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
