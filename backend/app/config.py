"""Backend configuration."""

from pydantic_settings import BaseSettings
from pydantic import Field


class BackendSettings(BaseSettings):
    """FastAPI backend settings."""

    OLLAMA_HOST: str = "http://localhost:11434"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./backend/data/mits.db"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Model selection
    MODEL_NAME: str = "glm-reap-23b"
    MODEL_FINETUNED: str = ""  # e.g. "mits-tutor-qwen3-4b"; empty = use MODEL_NAME
    USE_FINETUNED: bool = False  # Set True to use fine-tuned model
    AUTO_SELECT_MODEL: bool = True  # Auto-detect hardware and pick best model
    SHOW_THINKING: bool = False  # Show <think> blocks in debug mode
    MAX_HINTS: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


backend_settings = BackendSettings()
