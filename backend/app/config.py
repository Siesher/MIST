"""Backend configuration."""

from pydantic import model_validator
from pydantic_settings import BaseSettings

JWT_SECRET_PLACEHOLDER = "change-me-in-production"


class BackendSettings(BaseSettings):
    """FastAPI backend settings."""

    OLLAMA_HOST: str = "http://localhost:11434"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://192.168.8.167:3000"

    # LLM backend selection: "ollama" | "llamacpp" (llama-server / llama-swap)
    LLM_BACKEND: str = "llamacpp"
    LLM_BASE_URL: str = "http://127.0.0.1:8090/v1"  # llama-swap direct (mits-eval-* models)
    LLM_MODEL: str = "mits-tutor"  # llama-swap config: 64K ctx + TurboQuant turbo3
    # Внешние OpenAI-совместимые провайдеры (OpenRouter/DeepSeek/OpenAI/vLLM-хосты):
    # выставьте LLM_BASE_URL на их /v1, LLM_MODEL на их id, LLM_API_KEY на ключ.
    # Пусто (по умолчанию) = локальный llama-server без авторизации (open-source self-host).
    LLM_API_KEY: str = ""
    # `chat_template_kwargs` (enable_thinking) — расширение llama.cpp/vLLM, НЕ стандарт
    # OpenAI: часть облачных провайдеров отвергает его 400-й. False для таких провайдеров.
    LLM_SEND_TEMPLATE_KWARGS: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./backend/data/mits.db"

    # JWT
    JWT_SECRET_KEY: str = JWT_SECRET_PLACEHOLDER
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Model selection
    MODEL_NAME: str = "mits-tutor-9b-fast"
    MODEL_FINETUNED: str = "mits-tutor-9b-fast"  # KTO + Fast profile (num_predict=1024, short think)
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

    # Public-instance hardening
    REQUIRE_AUTH: bool = False  # True: LLM-пути требуют логина (публичный деплой)
    ANON_LLM_LIMIT: int = 60  # анонимных LLM-вызовов с одного IP за окно
    ANON_LLM_WINDOW: float = 3600.0  # секунд

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

    @model_validator(mode="after")
    def _require_prod_jwt_secret(self) -> "BackendSettings":
        """Fail-fast: запрет дефолтного JWT-секрета вне DEBUG-режима."""
        if not self.DEBUG and self.JWT_SECRET_KEY == JWT_SECRET_PLACEHOLDER:
            raise RuntimeError(
                "JWT_SECRET_KEY всё ещё содержит dev-заглушку при DEBUG=false. "
                'Сгенерируйте секрет (например, `python -c "import secrets; print(secrets.token_urlsafe(64))"`) '
                "и задайте его через переменную окружения или .env."
            )
        return self


backend_settings = BackendSettings()
