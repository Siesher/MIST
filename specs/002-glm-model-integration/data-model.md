# Data Model: GLM Model Integration

**Date**: 2026-01-30
**Branch**: `002-glm-model-integration`

## Entities

### ModelConfiguration

Represents a model setup with all inference parameters.

```python
@dataclass
class ModelConfiguration:
    """Configuration for an LLM model."""

    # Identity
    name: str                          # e.g., "glm-4.7-flash-reap"
    display_name: str                  # e.g., "GLM-4.7-Flash-REAP (23B)"

    # Model source
    backend: Literal["ollama", "llama.cpp"]
    ollama_model: Optional[str]        # e.g., "glm-4.7-flash"
    gguf_repo: Optional[str]           # e.g., "unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF"
    gguf_file: Optional[str]           # e.g., "Q4_K_M"

    # Hardware allocation
    gpu_layers: int                    # Layers to load on GPU
    cpu_moe_layers: int                # MoE expert layers on CPU
    context_length: int                # Max context tokens

    # Memory estimates
    estimated_vram_gb: float
    estimated_ram_gb: float

    # Sampling parameters
    temperature: float = 0.2
    top_p: float = 0.9
    top_k: int = 2
    repetition_penalty: float = 1.0

    # KV cache quantization
    kv_cache_k_type: str = "q8_0"
    kv_cache_v_type: str = "q4_0"

    # Feature flags
    supports_thinking: bool = True
    supports_streaming: bool = True
    is_moe: bool = True
```

**Validation Rules**:
- `gpu_layers` must be >= 0 and <= total model layers
- `context_length` must be <= model's max context (202K for GLM-4.7)
- `temperature` must be between 0.0 and 2.0
- `repetition_penalty` should be 1.0-1.05 for GLM (higher causes issues)
- If `backend == "llama.cpp"`, `gguf_repo` and `gguf_file` are required

---

### InferenceMetrics

Tracks performance metrics per model session.

```python
@dataclass
class InferenceMetrics:
    """Performance metrics for model inference."""

    model_name: str
    session_id: str
    timestamp: datetime

    # Latency metrics
    time_to_first_token_ms: float      # TTFT
    tokens_per_second: float           # Generation speed
    total_generation_time_ms: float

    # Resource usage
    vram_used_mb: float
    ram_used_mb: float
    gpu_utilization_percent: float

    # Quality indicators
    input_tokens: int
    output_tokens: int
    context_length_used: int

    # Errors
    had_error: bool = False
    error_message: Optional[str] = None
```

**State Transitions**:
```
[Request Received] → [Model Loading] → [Generating] → [Complete/Error]
```

---

### ModelPreset

Predefined configurations for different use cases.

```python
MODEL_PRESETS = {
    # Primary recommendation
    "glm-4.7-flash-reap": ModelConfiguration(
        name="glm-4.7-flash-reap",
        display_name="GLM-4.7-Flash-REAP (23B) - Recommended",
        backend="ollama",
        ollama_model="glm-4.7-flash",
        gguf_repo="unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF",
        gguf_file="Q4_K_M",
        gpu_layers=25,
        cpu_moe_layers=22,
        context_length=4096,
        estimated_vram_gb=7.2,
        estimated_ram_gb=8.0,
        temperature=0.2,
        is_moe=True,
    ),

    # Fallback
    "deepseek-r1-8b": ModelConfiguration(
        name="deepseek-r1-8b",
        display_name="DeepSeek-R1-Distill-8B (Fallback)",
        backend="ollama",
        ollama_model="deepseek-r1:8b",
        gpu_layers=99,  # Full GPU
        cpu_moe_layers=0,
        context_length=4096,
        estimated_vram_gb=6.5,
        estimated_ram_gb=2.0,
        temperature=0.3,
        is_moe=False,
    ),

    # High quality (slower)
    "glm-4.7-flash-reap-q6": ModelConfiguration(
        name="glm-4.7-flash-reap-q6",
        display_name="GLM-4.7-Flash-REAP Q6_K (Higher Quality)",
        backend="ollama",
        ollama_model="glm-4.7-flash:q6_K",
        gguf_repo="unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF",
        gguf_file="Q6_K",
        gpu_layers=20,
        cpu_moe_layers=27,
        context_length=4096,
        estimated_vram_gb=7.5,
        estimated_ram_gb=14.0,
        temperature=0.2,
        is_moe=True,
    ),
}
```

---

## Relationships

```
ModelConfiguration ──1:N── InferenceMetrics
        │
        └── Stored in: Settings (active model)
        └── Stored in: MODEL_PRESETS (available options)

InferenceMetrics ──N:1── TutoringSession
        │
        └── Aggregated for performance monitoring
```

---

## Configuration File Schema

**Location**: `.env` or `config.yaml`

```yaml
# Model Selection
MODEL_PRIMARY: "glm-4.7-flash-reap"
MODEL_FALLBACK: "deepseek-r1-8b"

# Hardware Configuration
GPU_LAYERS: 25
CPU_MOE_LAYERS: 22
CONTEXT_LENGTH: 4096

# Sampling Parameters
TEMPERATURE: 0.2
TOP_P: 0.9
TOP_K: 2
REPETITION_PENALTY: 1.0

# KV Cache
KV_CACHE_K_TYPE: "q8_0"
KV_CACHE_V_TYPE: "q4_0"

# Backend
MODEL_BACKEND: "ollama"  # or "llama.cpp"
OLLAMA_HOST: "http://localhost:11434"
LLAMA_CPP_PATH: "/path/to/llama-server"

# Performance Logging
LOG_INFERENCE_METRICS: true
METRICS_DB_PATH: "./data/metrics.db"
```

---

## Index/Query Patterns

### Get Active Model Configuration
```python
def get_active_model() -> ModelConfiguration:
    """Get currently configured model."""
    preset_name = settings.MODEL_PRIMARY
    return MODEL_PRESETS.get(preset_name, MODEL_PRESETS["deepseek-r1-8b"])
```

### Get Models for Hardware Constraint
```python
def get_compatible_models(max_vram_gb: float, max_ram_gb: float) -> List[ModelConfiguration]:
    """Filter models that fit hardware constraints."""
    return [
        config for config in MODEL_PRESETS.values()
        if config.estimated_vram_gb <= max_vram_gb
        and config.estimated_ram_gb <= max_ram_gb
    ]
```

### Log Inference Metrics
```python
def log_metrics(metrics: InferenceMetrics) -> None:
    """Persist metrics for monitoring."""
    # SQLite or file-based storage
    pass
```

### Get Average Performance
```python
def get_model_performance(model_name: str, hours: int = 24) -> Dict[str, float]:
    """Get average performance metrics for a model."""
    # Returns: {"avg_ttft_ms": 2500, "avg_tps": 10.5, "error_rate": 0.02}
    pass
```
