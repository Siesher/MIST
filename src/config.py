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
        default="glm-reap-23b",
        description="Primary model (REAP-pruned GLM-4.7, 23B total, 3B active, 25% lighter)"
    )
    MODEL_PRIMARY: str = Field(
        default="glm-reap-23b",
        description="Primary model - REAP-pruned, faster inference"
    )
    MODEL_FALLBACK: str = Field(
        default="glm-4.7-flash",
        description="Fallback model - original GLM-4.7-Flash (30B)"
    )

    # ─────────────────────────────────────────────────────────────
    # Sampling Parameters (optimized for GLM)
    # ─────────────────────────────────────────────────────────────
    TEMPERATURE: float = Field(
        default=0.7,
        ge=0.0, le=2.0,
        description="LLM temperature (0.7 for REAP model; <0.5 causes repetition loops)"
    )
    TOP_P: float = Field(
        default=0.95,
        ge=0.0, le=1.0,
        description="Top-p sampling (0.95 recommended for REAP)"
    )
    TOP_K: int = Field(
        default=0,
        ge=0,
        description="Top-k sampling (0=disabled, use min_p instead for REAP)"
    )
    MIN_P: float = Field(
        default=0.01,
        ge=0.0, le=1.0,
        description="Min-p sampling (filters low-probability tokens, key for REAP stability)"
    )
    REPETITION_PENALTY: float = Field(
        default=1.0,
        ge=1.0, le=1.05,
        description="Repetition penalty (MUST be 1.0 for REAP/GLM, higher causes loops)"
    )
    MAX_TOKENS: int = Field(
        default=2048,
        description="Maximum tokens in response"
    )

    # ─────────────────────────────────────────────────────────────
    # Hardware Configuration (for partial GPU/CPU offload)
    # ─────────────────────────────────────────────────────────────
    GPU_LAYERS: int = Field(
        default=28,
        ge=0,
        description="Layers on GPU. REAP: 28/47 blocks ≈ 7.2GB VRAM (RTX 2080 8GB, tested)"
    )
    CONTEXT_LENGTH: int = Field(
        default=8192,
        ge=512,
        description="Maximum context length in tokens"
    )
    KV_CACHE_K_TYPE: str = Field(
        default="q8_0",
        description="KV cache key quantization type"
    )
    KV_CACHE_V_TYPE: str = Field(
        default="q4_0",
        description="KV cache value quantization type"
    )
    FLASH_ATTENTION: bool = Field(
        default=True,
        description="Enable Flash Attention (RTX 2080+ Turing architecture)"
    )
    NUM_THREAD: int = Field(
        default=0,
        ge=0,
        description="CPU threads for inference (0=auto). Ryzen 9 9950x: 16 physical cores"
    )
    NUM_BATCH: int = Field(
        default=1024,
        ge=64,
        description="Batch size for prompt processing (larger = faster prompt eval)"
    )

    # ─────────────────────────────────────────────────────────────
    # Backend Selection
    # ─────────────────────────────────────────────────────────────
    MODEL_BACKEND: str = Field(
        default="ollama",
        description="Inference backend: ollama, exllamav2, llama.cpp"
    )

    # ─────────────────────────────────────────────────────────────
    # ExLlamaV2 Settings (for MoE optimization)
    # ─────────────────────────────────────────────────────────────
    EXLLAMA_MODEL_PATH: Optional[str] = Field(
        default=None,
        description="Path to model directory for ExLlamaV2"
    )
    EXLLAMA_GPU_SPLIT: Optional[str] = Field(
        default=None,
        description="GPU VRAM split in GB, comma-separated (e.g., '8.0' or '8.0,8.0')"
    )
    EXLLAMA_EXPERT_CACHE: int = Field(
        default=8,
        ge=1,
        description="Number of MoE experts to keep cached on GPU"
    )
    EXLLAMA_FLASH_ATTENTION: bool = Field(
        default=True,
        description="Enable Flash Attention 2 for faster inference"
    )

    # ─────────────────────────────────────────────────────────────
    # Performance Monitoring
    # ─────────────────────────────────────────────────────────────
    LOG_INFERENCE_METRICS: bool = Field(
        default=True,
        description="Log inference performance metrics"
    )
    METRICS_DB_PATH: Path = Field(
        default=Path("./data/metrics.db"),
        description="SQLite database for metrics"
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
        description="Enable thinking mode (<think> tags) for Nemotron/Qwen models"
    )

    # ─────────────────────────────────────────────────────────────
    # Model Backend (Ollama vs HuggingFace)
    # ─────────────────────────────────────────────────────────────
    MODEL_BACKEND: str = Field(
        default="ollama",
        description="Model backend: 'ollama' or 'huggingface'"
    )
    HF_MODEL_PATH: Optional[str] = Field(
        default=None,
        description="Path to HuggingFace model (for 'huggingface' backend)"
    )
    HF_ADAPTER_PATH: Optional[str] = Field(
        default=None,
        description="Path to LoRA adapter (optional)"
    )
    HF_QUANTIZE: bool = Field(
        default=True,
        description="Use 4-bit quantization for HuggingFace models"
    )

    # ─────────────────────────────────────────────────────────────
    # Knowledge Tracing (BKT + DKT)
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

    # DKT (Deep Knowledge Tracing) Settings
    DKT_ENABLED: bool = Field(
        default=True,
        description="Enable DKT model after threshold interactions"
    )
    DKT_THRESHOLD: int = Field(
        default=10,
        description="Number of interactions before switching from BKT to DKT"
    )
    DKT_HIDDEN_SIZE: int = Field(
        default=64,
        description="LSTM hidden layer size for DKT (keep small for 8GB VRAM)"
    )
    DKT_NUM_LAYERS: int = Field(
        default=1,
        description="Number of LSTM layers"
    )

    # Knowledge Decay (Ebbinghaus)
    KNOWLEDGE_DECAY_RATE: float = Field(
        default=0.05,
        description="Daily decay rate for unpracticed topics"
    )

    # ─────────────────────────────────────────────────────────────
    # Cognitive Load Estimation
    # ─────────────────────────────────────────────────────────────
    COGNITIVE_LOAD_ENABLED: bool = Field(
        default=True,
        description="Enable cognitive load estimation"
    )
    RESPONSE_TIME_WEIGHT: float = Field(
        default=0.4,
        description="Weight of response time in cognitive load estimation"
    )
    ERROR_PATTERN_WEIGHT: float = Field(
        default=0.3,
        description="Weight of error patterns in cognitive load estimation"
    )
    HINT_REQUEST_WEIGHT: float = Field(
        default=0.2,
        description="Weight of hint requests in cognitive load estimation"
    )
    TASK_COMPLEXITY_WEIGHT: float = Field(
        default=0.1,
        description="Weight of task complexity in cognitive load estimation"
    )
    COGNITIVE_OVERLOAD_THRESHOLD: float = Field(
        default=0.75,
        description="Score above which cognitive overload is detected"
    )

    # ─────────────────────────────────────────────────────────────
    # Memory System
    # ─────────────────────────────────────────────────────────────
    SESSION_MEMORY_MAX_TURNS: int = Field(
        default=20,
        description="Maximum conversation turns to keep in session memory"
    )
    STUDENT_MEMORY_DB_PATH: Path = Field(
        default=Path("./data/students.db"),
        description="SQLite database for student memory"
    )
    MEMORY_SYNC_INTERVAL: int = Field(
        default=5,
        description="Sync memory to disk every N interactions"
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

    # ─────────────────────────────────────────────────────────────
    # Extended Features: Streaming
    # ─────────────────────────────────────────────────────────────
    STREAMING_ENABLED: bool = Field(
        default=True,
        description="Enable streaming responses"
    )

    # ─────────────────────────────────────────────────────────────
    # Extended Features: REST API
    # ─────────────────────────────────────────────────────────────
    API_SECRET_KEY: str = Field(
        default="change-this-to-a-secure-secret-key-min-32-chars",
        description="Secret key for JWT token signing"
    )
    API_RATE_LIMIT: int = Field(
        default=60,
        description="API rate limit per minute"
    )
    API_TOKEN_EXPIRE_HOURS: int = Field(
        default=24,
        description="JWT token expiration in hours"
    )

    # ─────────────────────────────────────────────────────────────
    # Extended Features: Gamification
    # ─────────────────────────────────────────────────────────────
    GAMIFICATION_ENABLED: bool = Field(
        default=True,
        description="Enable gamification features"
    )
    XP_MULTIPLIER: float = Field(
        default=1.0,
        description="XP multiplier for events"
    )
    STREAK_FREEZE_COUNT: int = Field(
        default=3,
        description="Number of streak freezes available"
    )

    # ─────────────────────────────────────────────────────────────
    # Extended Features: Spaced Repetition
    # ─────────────────────────────────────────────────────────────
    SPACED_REPETITION_ENABLED: bool = Field(
        default=True,
        description="Enable spaced repetition system"
    )
    SM2_INITIAL_EASINESS: float = Field(
        default=2.5,
        description="SM-2 initial easiness factor"
    )
    SM2_MIN_EASINESS: float = Field(
        default=1.3,
        description="SM-2 minimum easiness factor"
    )

    # ─────────────────────────────────────────────────────────────
    # UI Settings (Claude-style interface)
    # ─────────────────────────────────────────────────────────────
    UI_DEFAULT_THEME: str = Field(
        default="dark",
        description="Default UI theme: 'dark' or 'light'"
    )
    UI_ANIMATION_ENABLED: bool = Field(
        default=True,
        description="Enable UI animations"
    )
    UI_SIDEBAR_COLLAPSED: bool = Field(
        default=False,
        description="Default sidebar collapsed state"
    )
    UI_SHOW_THINKING: bool = Field(
        default=True,
        description="Show model thinking process by default"
    )
    UI_CHAT_MAX_WIDTH: int = Field(
        default=800,
        description="Maximum chat container width in pixels"
    )

    # ─────────────────────────────────────────────────────────────
    # Groundbreaking Innovations (009)
    # ─────────────────────────────────────────────────────────────

    # Affective State Detection
    AFFECTIVE_DETECTION_ENABLED: bool = Field(
        default=True,
        description="Enable affective state detection from text"
    )
    AFFECTIVE_CONFIDENCE_THRESHOLD: float = Field(
        default=0.6,
        ge=0.0, le=1.0,
        description="Minimum confidence to act on detected affective state"
    )
    AFFECTIVE_WINDOW_SIZE: int = Field(
        default=5,
        ge=1,
        description="Number of recent messages to analyze for affective state"
    )
    AFFECT_DETECTOR_TYPE: str = Field(
        default="rules",
        description="Affect detector type: 'rules' (rule-based) or 'ml' (RuBERT)"
    )
    AFFECT_ML_MODEL_PATH: str = Field(
        default="data/models/rubert_affect",
        description="Path to fine-tuned RuBERT affect model"
    )

    # Generative Task Synthesis
    TASK_SYNTHESIS_ENABLED: bool = Field(
        default=True,
        description="Enable LLM + SymPy task generation"
    )
    TASK_SYNTHESIS_MAX_RETRIES: int = Field(
        default=3,
        ge=1,
        description="Maximum retries for task generation if verification fails"
    )
    TASK_SYNTHESIS_VERIFY_WITH_SYMPY: bool = Field(
        default=True,
        description="Verify generated tasks with SymPy"
    )

    # Counterfactual Explanations
    COUNTERFACTUAL_ENABLED: bool = Field(
        default=True,
        description="Enable counterfactual explanations for errors"
    )

    # Metacognitive Scaffolding
    METACOGNITIVE_ENABLED: bool = Field(
        default=True,
        description="Enable metacognitive scaffolding"
    )
    METACOGNITIVE_REFLECTION_THRESHOLD_MINUTES: int = Field(
        default=30,
        ge=5,
        description="Session duration before offering reflection"
    )

    # Learning Path Optimization
    LEARNING_PATH_ENABLED: bool = Field(
        default=True,
        description="Enable personalized learning path optimization"
    )
    LEARNING_PATH_MASTERY_THRESHOLD: float = Field(
        default=0.7,
        ge=0.0, le=1.0,
        description="Mastery level to consider skill 'learned'"
    )

    # Multi-Modal Math Input (Vision)
    VISION_ANALYZER_ENABLED: bool = Field(
        default=True,
        description="Enable vision-based math OCR"
    )
    VISION_MODEL: str = Field(
        default="qwen2.5-vl:7b",
        description="Ollama vision model for OCR (Qwen2.5-VL-7B recommended)"
    )
    VISION_CONFIDENCE_THRESHOLD: float = Field(
        default=0.7,
        ge=0.0, le=1.0,
        description="Minimum confidence for OCR results"
    )
    VISION_VRAM_LIMIT_GB: float = Field(
        default=3.0,
        ge=1.0,
        description="VRAM limit for vision model"
    )

    # ─────────────────────────────────────────────────────────────
    # Performance Optimization (010)
    # ─────────────────────────────────────────────────────────────

    # Semantic Cache Settings
    CACHE_SIMILARITY_THRESHOLD: float = Field(
        default=0.90,
        ge=0.5, le=1.0,
        description="Minimum cosine similarity for cache hit"
    )
    CACHE_MAX_SIZE: int = Field(
        default=1000,
        ge=100,
        description="Maximum cache entries before LRU eviction"
    )
    CACHE_TTL_HOURS: int = Field(
        default=24,
        ge=1,
        description="Cache entry TTL in hours"
    )

    # Context Compression Settings
    COMPRESSION_TOKEN_THRESHOLD: int = Field(
        default=4000,
        ge=1000,
        description="Token count threshold to trigger context compression"
    )
    COMPRESSION_RECENT_MESSAGES: int = Field(
        default=10,
        ge=3,
        description="Number of recent messages to keep in full"
    )
    COMPRESSION_MAX_KEY_EVENTS: int = Field(
        default=10,
        ge=3,
        description="Maximum key events to extract from older messages"
    )

    # Resource Monitoring Settings
    RESOURCE_MONITOR_ENABLED: bool = Field(
        default=True,
        description="Enable background resource monitoring"
    )
    RESOURCE_SAMPLE_INTERVAL_SEC: int = Field(
        default=30,
        ge=5,
        description="Resource sampling interval in seconds"
    )
    VRAM_ALERT_THRESHOLD_MB: int = Field(
        default=7000,
        ge=1000,
        description="VRAM usage threshold for alerts (MB)"
    )
    RAM_ALERT_THRESHOLD_MB: int = Field(
        default=14000,
        ge=1000,
        description="RAM usage threshold for alerts (MB)"
    )

    # Few-Shot Settings
    FEW_SHOT_ENABLED: bool = Field(
        default=True,
        description="Enable few-shot prompting"
    )
    FEW_SHOT_COUNT: int = Field(
        default=2,
        ge=1, le=5,
        description="Number of few-shot examples to include"
    )
    FEW_SHOT_MIN_SIMILARITY: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="Minimum similarity for few-shot example selection"
    )
    FEW_SHOT_PATH: Path = Field(
        default=Path("./data/few_shot"),
        description="Path to few-shot examples directory"
    )

    # Chain-of-Thought Settings
    COT_ENABLED: bool = Field(
        default=True,
        description="Enable Chain-of-Thought prompting"
    )
    COT_MIN_DIFFICULTY: str = Field(
        default="medium",
        description="Minimum difficulty level to use CoT (easy/medium/hard)"
    )

    # A/B Testing Settings
    AB_TESTING_ENABLED: bool = Field(
        default=True,
        description="Enable A/B testing framework"
    )

    # Batch Embedding Settings
    BATCH_EMBEDDING_SIZE: int = Field(
        default=16,
        ge=1, le=64,
        description="Batch size for embedding processing"
    )
    BATCH_EMBEDDING_TIMEOUT_MS: int = Field(
        default=50,
        ge=10,
        description="Timeout window for batch collection (ms)"
    )

    # Ollama Optimization Settings
    OLLAMA_NUM_CTX: int = Field(
        default=4096,
        ge=512,
        description="Ollama context window size"
    )
    OLLAMA_NUM_BATCH: int = Field(
        default=512,
        ge=64,
        description="Ollama batch size for prompt processing"
    )

    # Report Generation Settings
    REPORTS_PATH: Path = Field(
        default=Path("./data/reports"),
        description="Path for generated reports"
    )

    # Performance Targets
    TARGET_RESPONSE_TIME_MS: int = Field(
        default=2000,
        ge=500,
        description="Target response time in milliseconds"
    )
    TARGET_CACHE_HIT_RATE: float = Field(
        default=0.20,
        ge=0.0, le=1.0,
        description="Target cache hit rate"
    )
    TARGET_VRAM_MB: int = Field(
        default=7000,
        ge=1000,
        description="Target maximum VRAM usage (MB)"
    )

    # ─────────────────────────────────────────────────────────────
    # Extended Features: Caching
    # ─────────────────────────────────────────────────────────────
    EMBEDDING_CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable persistent embedding cache"
    )
    EMBEDDING_CACHE_MAX_SIZE: int = Field(
        default=100000,
        description="Maximum embeddings to cache"
    )
    EMBEDDING_CACHE_PATH: Path = Field(
        default=Path("./data/embeddings_cache"),
        description="Path for embedding cache storage"
    )
    RESPONSE_CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable response caching"
    )
    RESPONSE_CACHE_TTL_SECONDS: int = Field(
        default=3600,
        description="Response cache TTL in seconds"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Allow extra fields like CEREBRAS_API_KEY_*


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
