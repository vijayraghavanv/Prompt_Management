# app/core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application settings
    APP_ENV: str = "development"
    LOG_LEVEL: str = "DEBUG"
    LOG_PATH: str = "app/logs/app.log"

    # Database settings
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "promptdb"

    # Security settings
    FERNET_KEY: str

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


# Export settings instance
settings = get_settings()