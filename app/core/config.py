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

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
