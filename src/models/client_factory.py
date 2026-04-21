"""
MITS LLM Client Factory

Unified factory for creating LLM clients with different backends:
- Ollama (default, easy setup)
- ExLlamaV2 (best MoE support, expert-level offloading)
- llama.cpp server (advanced control)

Usage:
    from src.models.client_factory import create_client, Backend

    # Auto-select best available backend
    client = create_client()

    # Force specific backend
    client = create_client(backend=Backend.EXLLAMA)
"""

from enum import Enum
from typing import Optional, Dict, Any, Union
import structlog

from src.config import settings

logger = structlog.get_logger()


class Backend(Enum):
    """Available inference backends."""
    OLLAMA = "ollama"
    EXLLAMA = "exllamav2"
    LLAMACPP = "llama.cpp"
    AUTO = "auto"


def create_client(
    backend: Backend = Backend.AUTO,
    model_path: Optional[str] = None,
    **kwargs
) -> Union['LLMClient', 'ExLlamaClient']:
    """
    Create LLM client with specified backend.

    Args:
        backend: Backend to use (AUTO, OLLAMA, EXLLAMA, LLAMACPP)
        model_path: Path to model (required for EXLLAMA)
        **kwargs: Backend-specific arguments

    Returns:
        Configured LLM client

    Examples:
        # Auto-select (prefers Ollama if available)
        client = create_client()

        # Force ExLlamaV2 for MoE optimization
        client = create_client(
            backend=Backend.EXLLAMA,
            model_path="/models/glm-4",
            gpu_split=[8.0],
            expert_cache_size=8
        )
    """
    # Get backend from settings if AUTO
    if backend == Backend.AUTO:
        backend_str = getattr(settings, 'MODEL_BACKEND', 'ollama').lower()
        backend = Backend(backend_str) if backend_str in [b.value for b in Backend] else Backend.OLLAMA

    logger.info("creating_llm_client", backend=backend.value)

    if backend == Backend.EXLLAMA:
        return _create_exllama_client(model_path, **kwargs)
    elif backend == Backend.LLAMACPP:
        return _create_llamacpp_client(model_path, **kwargs)
    else:
        return _create_ollama_client(**kwargs)


def _create_ollama_client(**kwargs) -> 'LLMClient':
    """Create Ollama client."""
    from src.models.llm_client import LLMClient

    return LLMClient(
        model=kwargs.get('model') or settings.MODEL_NAME,
        host=kwargs.get('host') or settings.OLLAMA_HOST,
        temperature=kwargs.get('temperature'),
        max_tokens=kwargs.get('max_tokens'),
    )


def _create_exllama_client(model_path: Optional[str], **kwargs) -> 'ExLlamaClient':
    """Create ExLlamaV2 client."""
    from src.models.exllama_client import ExLlamaClient, check_exllama_available

    if not check_exllama_available():
        raise ImportError(
            "ExLlamaV2 is not installed.\n"
            "Install with: pip install exllamav2\n"
            "Falling back to Ollama is recommended if ExLlamaV2 fails."
        )

    if not model_path:
        model_path = getattr(settings, 'EXLLAMA_MODEL_PATH', None)
        if not model_path:
            raise ValueError(
                "model_path is required for ExLlamaV2 backend.\n"
                "Set EXLLAMA_MODEL_PATH in .env or pass model_path argument."
            )

    # Get GPU configuration
    gpu_layers = getattr(settings, 'GPU_LAYERS', 25)
    vram_estimate = gpu_layers * 0.25  # Rough estimate

    return ExLlamaClient(
        model_path=model_path,
        gpu_split=kwargs.get('gpu_split') or [vram_estimate],
        max_seq_len=kwargs.get('max_seq_len') or getattr(settings, 'CONTEXT_LENGTH', 4096),
        expert_cache_size=kwargs.get('expert_cache_size', 8),
        flash_attention=kwargs.get('flash_attention', True),
    )


def _create_llamacpp_client(model_path: Optional[str], **kwargs) -> 'LLMClient':
    """Create llama.cpp server client (uses OpenAI-compatible API)."""
    # llama.cpp server exposes OpenAI-compatible API
    # We can use a simple HTTP client or the openai library

    from src.models.llm_client import LLMClient

    # llama.cpp server typically runs on port 8080
    host = kwargs.get('host') or getattr(settings, 'LLAMACPP_HOST', 'http://localhost:8080')

    logger.warning(
        "llamacpp_backend_experimental",
        host=host,
        note="llama.cpp server must be running separately"
    )

    # For now, we create an Ollama-like client that talks to llama.cpp server
    # This is a simplified implementation
    return LLMClient(
        model=kwargs.get('model', 'local'),
        host=host,
    )


def get_available_backends() -> Dict[str, bool]:
    """Check which backends are available."""
    available = {
        Backend.OLLAMA.value: False,
        Backend.EXLLAMA.value: False,
        Backend.LLAMACPP.value: False,
    }

    # Check Ollama
    try:
        import ollama
        client = ollama.Client(host=settings.OLLAMA_HOST)
        client.list()
        available[Backend.OLLAMA.value] = True
    except:
        pass

    # Check ExLlamaV2
    try:
        from src.models.exllama_client import check_exllama_available
        available[Backend.EXLLAMA.value] = check_exllama_available()
    except:
        pass

    # Check llama.cpp (just check if requests is available)
    try:
        import requests
        available[Backend.LLAMACPP.value] = True  # Server availability checked separately
    except:
        pass

    return available


def get_backend_info() -> Dict[str, Any]:
    """Get information about available backends and recommendations."""
    available = get_available_backends()

    info = {
        "available_backends": available,
        "recommended": None,
        "current": getattr(settings, 'MODEL_BACKEND', 'ollama'),
    }

    # Recommendation logic
    if available[Backend.EXLLAMA.value]:
        info["recommended"] = Backend.EXLLAMA.value
        info["recommendation_reason"] = "Best MoE support with expert-level offloading"
    elif available[Backend.OLLAMA.value]:
        info["recommended"] = Backend.OLLAMA.value
        info["recommendation_reason"] = "Easy setup, good general performance"
    else:
        info["recommended"] = Backend.LLAMACPP.value
        info["recommendation_reason"] = "Fallback option with advanced control"

    return info


# Convenience function for quick setup
def auto_setup_client(**kwargs):
    """
    Automatically set up the best available client.

    Tries backends in order: ExLlamaV2 -> Ollama -> llama.cpp
    """
    backends_to_try = [Backend.EXLLAMA, Backend.OLLAMA, Backend.LLAMACPP]
    available = get_available_backends()

    for backend in backends_to_try:
        if available.get(backend.value):
            try:
                return create_client(backend=backend, **kwargs)
            except Exception as e:
                logger.warning(f"Failed to create {backend.value} client: {e}")
                continue

    raise RuntimeError("No LLM backend available. Install Ollama or ExLlamaV2.")
