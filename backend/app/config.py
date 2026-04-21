"""Backend configuration."""

from pydantic_settings import BaseSettings


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
    MODEL_NAME: str = "mits-tutor-9b-fast"
    MODEL_FINETUNED: str = (
        "mits-tutor-9b-fast"  # KTO + Fast profile (num_predict=1024, short think)
    )
    MODEL_FALLBACK: str = "mits-tutor-9b-think"  # Original KTO profile for quality comparison
    USE_FINETUNED: bool = True  # Set True to use fine-tuned model
    AUTO_SELECT_MODEL: bool = True  # Auto-detect hardware and pick best model
    SHOW_THINKING: bool = False  # Show <think> blocks in debug mode
    MAX_HINTS: int = 3

    # Experimental: HuggingFace backend with TurboQuant KV compression
    # Enables 32K+ context on 8GB VRAM (vs 4K on Ollama)
    USE_HF_BACKEND: bool = False  # Set True to use src/inference/turbo_quant.py path
    HF_MODEL_CONFIG: str = "qwen3.5-9b-turbo"  # Key from MODEL_CONFIGS in model_config.py
    HF_CONTEXT_LENGTH: int = 32768  # Override for turbo backend

    # Speculative Decoding (arXiv 2302.01318)
    # Uses a small draft model to propose tokens, main model verifies batch.
    # 1.5-3x speedup on predictable sequences (math, code). No quality loss.
    SPECULATIVE_DECODING: bool = False
    SPECULATIVE_DRAFT_MODEL: str = "qwen2.5:0.5b"
    SPECULATIVE_NUM_DRAFT: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


backend_settings = BackendSettings()
