"""Backend configuration."""

from pydantic_settings import BaseSettings
from pydantic import Field


class BackendSettings(BaseSettings):
    """FastAPI backend settings."""

    OLLAMA_HOST: str = "http://localhost:11434"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000"

    # Inherited from MITS core
    MODEL_NAME: str = "glm-reap-23b"
    MAX_HINTS: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


backend_settings = BackendSettings()
