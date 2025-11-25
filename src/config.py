"""
MITS Configuration Module

Central configuration management using Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # ─────────────────────────────────────────────────────────────
    # LLM Settings
    # ─────────────────────────────────────────────────────────────
    OLLAMA_HOST: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL"
    )
    MODEL_NAME: str = Field(
        default="qwen3:30b-a3b",
        description="Model to use for tutoring"
    )
    TEMPERATURE: float = Field(
        default=0.7,
        ge=0.0, le=2.0,
        description="LLM temperature for generation"
    )
    MAX_TOKENS: int = Field(
        default=2048,
        description="Maximum tokens in response"
    )
    
    # ─────────────────────────────────────────────────────────────
    # Tutoring Settings
    # ─────────────────────────────────────────────────────────────
    MAX_HINTS: int = Field(
        default=3,
        description="Maximum hints before revealing answer"
    )
    MAX_ATTEMPTS_BEFORE_TELLING: int = Field(
        default=5,
        description="Max wrong attempts before telling answer"
    )
    THINKING_MODE: bool = Field(
        default=True,
        description="Enable Qwen3 thinking mode (/think)"
    )
    
    # ─────────────────────────────────────────────────────────────
    # Knowledge Tracing
    # ─────────────────────────────────────────────────────────────
    INITIAL_MASTERY: float = Field(
        default=0.3,
        description="Initial skill mastery level"
    )
    LEARN_RATE: float = Field(
        default=0.1,
        description="Learning rate for knowledge update"
    )
    FORGET_RATE: float = Field(
        default=0.02,
        description="Forgetting rate for unused skills"
    )
    SLIP_RATE: float = Field(
        default=0.05,
        description="Probability of slip (know but fail)"
    )
    GUESS_RATE: float = Field(
        default=0.1,
        description="Probability of guess (don't know but succeed)"
    )
    
    # ─────────────────────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────────────────────
    DB_PATH: Path = Field(
        default=Path("./data/mits.db"),
        description="SQLite database path"
    )
    VECTOR_DB_PATH: Path = Field(
        default=Path("./data/chromadb"),
        description="ChromaDB path for embeddings"
    )
    
    # ─────────────────────────────────────────────────────────────
    # Logging
    # ─────────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level"
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
