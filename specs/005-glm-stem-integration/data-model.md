# Data Model: GLM-STEM Model Integration

**Feature**: 005-glm-stem-integration
**Date**: 2026-02-02

## Entities

### ModelConfiguration (Extended)

Расширение существующего `ModelConfig` в `model_manager.py`:

```
ModelConfig
├── name: str                    # "GLM-STEM-42exp (REAP-pruned)"
├── backend: ModelBackend        # OLLAMA
├── purpose: ModelPurpose        # TUTOR
├── ollama_model: str            # "glm-stem-42exp"
├── hf_model_path: str           # "Siesher/glm-stem-42exp-gguf"
├── estimated_vram_gb: float     # 5.5
├── estimated_ram_gb: float      # 6.0
├── max_tokens: int              # 2048
├── temperature: float           # 0.2
└── context_length: int          # 4096
```

### InstallationState

Состояние установки модели (runtime, не персистируется):

```
InstallationState
├── model_name: str              # "glm-stem-42exp"
├── gguf_variant: str            # "q4km" | "q8"
├── download_progress: float     # 0.0 - 1.0
├── download_path: Path          # ~/models/glm-stem-42exp-q4km.gguf
├── is_downloaded: bool
├── is_registered: bool          # в Ollama
└── error_message: Optional[str]
```

### TestResult

Результат тестирования модели:

```
TestResult
├── test_name: str               # "test_algebra_linear_equation"
├── category: str                # "algebra" | "calculus" | "programming" | "physics" | "russian"
├── prompt: str                  # "Solve: 2x + 5 = 13"
├── expected_contains: list[str] # ["4", "x = 4"]
├── actual_response: str
├── passed: bool
├── latency_ms: float
└── tokens_generated: int
```

## Relationships

```
ModelManager
    └── MODEL_PRESETS
            └── "glm-stem-42exp-tutor" → ModelConfig

Settings (config.py)
    ├── MODEL_NAME → "glm-stem-42exp"
    ├── MODEL_PRIMARY → "glm-stem-42exp"
    └── MODEL_FALLBACK → "glm-4.7-flash"

LLMClient
    └── model → "glm-stem-42exp" (from settings)
            └── _apply_model_defaults() → GLM-specific params
```

## State Transitions

### Installation Flow

```
NOT_INSTALLED
    ↓ [run install script]
DOWNLOADING
    ↓ [download complete]
DOWNLOADED
    ↓ [ollama create]
REGISTERED
    ↓ [verification test]
READY
```

### Model Selection Flow (Runtime)

```
START
    ↓
Check if glm-stem-42exp in ollama list
    ├── YES → Use glm-stem-42exp
    └── NO → Log warning → Use fallback (glm-4.7-flash)
```

## Validation Rules

| Field | Rule |
|-------|------|
| gguf_variant | Must be "q4km" or "q8" |
| download_path | Must have 20GB free space |
| temperature | Must be 0.2 for GLM models |
| repeat_penalty | Must be 1.0 for GLM (critical!) |
| context_length | Max 4096 for stable operation |

## File Artifacts

| Artifact | Location | Size |
|----------|----------|------|
| Q4_K_M GGUF | `~/models/glm-stem-42exp-q4km.gguf` | ~13GB |
| Q8_0 GGUF | `~/models/glm-stem-42exp-q8.gguf` | ~21GB |
| Modelfile | `~/models/Modelfile.glm-stem` | ~500B |
