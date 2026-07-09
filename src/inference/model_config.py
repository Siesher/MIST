"""
Model Configuration dataclass for MITS.

Defines the ModelConfiguration dataclass for representing
LLM model settings with hardware and sampling parameters.
"""

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class ModelConfiguration:
    """Configuration for an LLM model."""

    # Identity
    name: str
    display_name: str

    # Model source
    backend: Literal["ollama", "llama.cpp", "huggingface"] = "ollama"
    ollama_model: Optional[str] = None
    hf_model_path: Optional[str] = None
    hf_adapter_path: Optional[str] = None
    gguf_repo: Optional[str] = None
    gguf_file: Optional[str] = None

    # Hardware allocation
    gpu_layers: int = 25
    cpu_moe_layers: int = 0
    context_length: int = 4096

    # Memory estimates
    estimated_vram_gb: float = 0.0
    estimated_ram_gb: float = 0.0

    # Sampling parameters (GLM-optimized defaults)
    temperature: float = 0.2
    top_p: float = 0.9
    top_k: int = 2
    repetition_penalty: float = 1.0
    max_tokens: int = 2048

    # KV cache quantization (Ollama/llama.cpp)
    kv_cache_k_type: str = "q8_0"
    kv_cache_v_type: str = "q4_0"

    # TurboQuant KV cache compression (HuggingFace backend)
    turbo_quant_enabled: bool = False
    turbo_quant_key_bits: int = 3
    turbo_quant_value_bits: int = 3

    # Feature flags
    supports_thinking: bool = True
    supports_streaming: bool = True
    is_moe: bool = False

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.backend == "llama.cpp" and not (self.gguf_repo and self.gguf_file):
            raise ValueError("llama.cpp backend requires gguf_repo and gguf_file")
        if self.repetition_penalty > 1.05:
            raise ValueError("repetition_penalty > 1.05 causes issues with GLM models")
        if self.gpu_layers < 0:
            raise ValueError("gpu_layers must be >= 0")
        if self.context_length < 512:
            raise ValueError("context_length must be >= 512")

    def get_ollama_options(self) -> dict:
        """Get options dict for Ollama API."""
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repeat_penalty": self.repetition_penalty,
            "num_predict": self.max_tokens,
            "num_ctx": self.context_length,
            "num_gpu": self.gpu_layers,
        }


# Predefined model configurations
MODEL_CONFIGS = {
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
    "deepseek-r1-8b": ModelConfiguration(
        name="deepseek-r1-8b",
        display_name="DeepSeek-R1-Distill-8B (Fallback)",
        backend="ollama",
        ollama_model="deepseek-r1:8b",
        gpu_layers=99,
        cpu_moe_layers=0,
        context_length=4096,
        estimated_vram_gb=6.5,
        estimated_ram_gb=2.0,
        temperature=0.3,
        is_moe=False,
    ),
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
    "qwen3-8b": ModelConfiguration(
        name="qwen3-8b",
        display_name="Qwen3-8B-Instruct (Baseline)",
        backend="ollama",
        ollama_model="qwen3:8b",
        gpu_layers=99,
        context_length=32768,
        estimated_vram_gb=5.0,
        estimated_ram_gb=2.0,
        temperature=0.7,
        is_moe=False,
    ),
    # ── GSPO fine-tuned Qwen3.5-9B (primary tutor model) ──
    "mits-tutor-9b-think": ModelConfiguration(
        name="mits-tutor-9b-think",
        display_name="MITS Tutor 9B (GSPO fine-tuned, Q4_K_M)",
        backend="ollama",
        ollama_model="mits-tutor-9b-think",
        hf_model_path="Siesher/mits-qwen3-9b-gspo",
        gpu_layers=99,
        context_length=4096,
        estimated_vram_gb=5.5,
        estimated_ram_gb=2.0,
        temperature=1.0,
        top_p=0.95,
        top_k=20,
        repetition_penalty=1.0,
        is_moe=False,
        supports_thinking=True,
    ),
    # ── HuggingFace backend with TurboQuant KV cache compression ──
    # Siesher/mits-qwen3-9b-kto — это MERGED full model (safetensors), не LoRA.
    # Первый запуск скачает ~17 GB (один раз), потом использует HF cache.
    "qwen3.5-9b-turbo": ModelConfiguration(
        name="qwen3.5-9b-turbo",
        display_name="Qwen3.5-9B-KTO (merged) + TurboQuant (3-bit KV, 32K ctx)",
        backend="huggingface",
        hf_model_path="Siesher/mits-qwen3-9b-kto",  # merged KTO full model
        hf_adapter_path=None,
        gpu_layers=99,
        context_length=32768,
        estimated_vram_gb=8.0,
        estimated_ram_gb=2.0,
        temperature=1.0,
        top_p=0.95,
        top_k=20,
        repetition_penalty=1.0,
        is_moe=False,
        turbo_quant_enabled=True,
        turbo_quant_key_bits=3,
        turbo_quant_value_bits=3,
    ),
    "qwen3.5-9b-turbo-no-adapter": ModelConfiguration(
        name="qwen3.5-9b-turbo-no-adapter",
        display_name="Qwen3.5-9B base + TurboQuant (без fine-tune, для сравнения)",
        backend="huggingface",
        hf_model_path="Qwen/Qwen3.5-9B",
        hf_adapter_path=None,
        gpu_layers=99,
        context_length=32768,
        estimated_vram_gb=8.0,
        estimated_ram_gb=2.0,
        temperature=0.7,
        top_p=0.95,
        top_k=20,
        repetition_penalty=1.0,
        is_moe=False,
        turbo_quant_enabled=True,
        turbo_quant_key_bits=3,
        turbo_quant_value_bits=3,
    ),
    "qwen3.5-9b-turbo-2.5bit": ModelConfiguration(
        name="qwen3.5-9b-turbo-2.5bit",
        display_name="Qwen3.5-9B-KTO + TurboQuant 2-bit (64K ctx, макс.компрессия)",
        backend="huggingface",
        hf_model_path="Qwen/Qwen3.5-9B",
        hf_adapter_path="Siesher/mits-qwen3-9b-kto",
        gpu_layers=99,
        context_length=65536,
        estimated_vram_gb=7.5,
        estimated_ram_gb=2.0,
        temperature=1.0,
        top_p=0.95,
        top_k=20,
        repetition_penalty=1.0,
        is_moe=False,
        # TurboQuant 2-bit per paper Section 4.3:
        # 32 outlier channels at 3 bits + 96 regular at 2 bits → 2.25 effective
        turbo_quant_enabled=True,
        turbo_quant_key_bits=2,
        turbo_quant_value_bits=2,
    ),
}


def get_model_config(name: str) -> Optional[ModelConfiguration]:
    """Get model configuration by name."""
    return MODEL_CONFIGS.get(name)


def get_available_models() -> list[str]:
    """Get list of available model names."""
    return list(MODEL_CONFIGS.keys())


def get_models_for_vram(max_vram_gb: float) -> list[ModelConfiguration]:
    """Get models that fit within VRAM constraint."""
    return [config for config in MODEL_CONFIGS.values() if config.estimated_vram_gb <= max_vram_gb]
