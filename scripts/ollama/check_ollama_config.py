#!/usr/bin/env python3
"""
Check Ollama Configuration for MITS.

Feature 010: Verify Ollama setup for optimal performance.

Checks:
- Ollama version and status
- Available models
- Flash Attention support
- GPU configuration
- Recommended settings
"""

import os
import sys

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def print_header(text: str) -> None:
    """Print a header."""
    print(f"\n{'='*60}")
    print(f" {text}")
    print('='*60)


def print_status(name: str, status: bool, details: str = "") -> None:
    """Print status line."""
    icon = "✓" if status else "✗"
    color_code = "\033[92m" if status else "\033[91m"
    reset = "\033[0m"
    print(f"  {color_code}{icon}{reset} {name}: {details}")


def check_ollama_running() -> tuple:
    """Check if Ollama is running."""
    if not HAS_REQUESTS:
        return False, "requests library not installed"

    try:
        response = requests.get("http://localhost:11434/api/version", timeout=5)
        if response.status_code == 200:
            version = response.json().get("version", "unknown")
            return True, f"v{version}"
        return False, f"HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Connection refused - Ollama not running?"
    except Exception as e:
        return False, str(e)


def get_available_models() -> list:
    """Get list of available models."""
    if not HAS_REQUESTS:
        return []

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return [m.get("name", "") for m in models]
        return []
    except Exception:
        return []


def check_gpu_support() -> tuple:
    """Check GPU support."""
    # Check for CUDA
    cuda_available = False
    cuda_version = None

    try:
        import torch
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            cuda_version = torch.version.cuda
    except ImportError:
        pass

    # Check environment variables
    cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "not set")

    return cuda_available, cuda_version, cuda_visible


def check_flash_attention_env() -> dict:
    """Check Flash Attention environment setup."""
    env_vars = {
        "OLLAMA_FLASH_ATTENTION": os.environ.get("OLLAMA_FLASH_ATTENTION"),
        "OLLAMA_NUM_GPU": os.environ.get("OLLAMA_NUM_GPU"),
        "OLLAMA_GPU_LAYERS": os.environ.get("OLLAMA_GPU_LAYERS"),
    }
    return env_vars


def check_model_config(model_name: str) -> dict:
    """Get model configuration from Ollama."""
    if not HAS_REQUESTS:
        return {}

    try:
        response = requests.post(
            "http://localhost:11434/api/show",
            json={"name": model_name},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception:
        return {}


def get_recommendations() -> list:
    """Generate optimization recommendations."""
    recommendations = []

    # Check Flash Attention
    flash_env = os.environ.get("OLLAMA_FLASH_ATTENTION")
    if flash_env != "1":
        recommendations.append(
            "Enable Flash Attention for faster inference:\n"
            "  set OLLAMA_FLASH_ATTENTION=1 (Windows)\n"
            "  export OLLAMA_FLASH_ATTENTION=1 (Linux/Mac)"
        )

    # Check GPU layers
    gpu_layers = os.environ.get("OLLAMA_GPU_LAYERS")
    if not gpu_layers:
        recommendations.append(
            "Set GPU layers for partial offload (8GB VRAM):\n"
            "  set OLLAMA_GPU_LAYERS=25 (Windows)\n"
            "  export OLLAMA_GPU_LAYERS=25 (Linux/Mac)"
        )

    # Check context size
    recommendations.append(
        "Optimal Ollama model parameters for MITS:\n"
        "  num_ctx: 4096\n"
        "  num_batch: 512\n"
        "  num_thread: 4 (CPU cores for inference)"
    )

    return recommendations


def main():
    print_header("MITS Ollama Configuration Check")

    # 1. Check Ollama status
    print("\n[1] Ollama Server Status")
    running, version = check_ollama_running()
    print_status("Ollama running", running, version)

    if not running:
        print("\n⚠️  Ollama is not running. Please start it with:")
        print("   ollama serve")
        return 1

    # 2. Available models
    print("\n[2] Available Models")
    models = get_available_models()
    if models:
        print(f"  Found {len(models)} model(s):")
        for model in models:
            print(f"    • {model}")
    else:
        print("  No models found. Install with:")
        print("    ollama pull glm-4.7-flash")

    # 3. GPU Support
    print("\n[3] GPU Support")
    cuda_available, cuda_version, cuda_visible = check_gpu_support()
    print_status("CUDA available", cuda_available, f"v{cuda_version}" if cuda_version else "not detected")
    print(f"    CUDA_VISIBLE_DEVICES: {cuda_visible}")

    # 4. Flash Attention Environment
    print("\n[4] Flash Attention Configuration")
    env_vars = check_flash_attention_env()
    for var, value in env_vars.items():
        status = value is not None
        print_status(var, status, value or "not set")

    # 5. Model Configuration (if glm-4.7-flash available)
    target_model = "glm-4.7-flash"
    if target_model in models:
        print(f"\n[5] Model Configuration: {target_model}")
        config = check_model_config(target_model)
        if config:
            params = config.get("parameters", "")
            print(f"  Parameters: {params[:200]}..." if len(params) > 200 else f"  Parameters: {params}")

    # 6. Recommendations
    print("\n[6] Optimization Recommendations")
    recommendations = get_recommendations()
    for i, rec in enumerate(recommendations, 1):
        print(f"\n  {i}. {rec}")

    # 7. Optimal configuration snippet
    print_header("Recommended .env Settings")
    print("""
# Ollama Performance Settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_FLASH_ATTENTION=1
OLLAMA_GPU_LAYERS=25
OLLAMA_NUM_PARALLEL=1

# MITS Performance Settings (config.py)
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_BATCH=512
CACHE_SIMILARITY_THRESHOLD=0.90
COMPRESSION_TOKEN_THRESHOLD=4000
RESOURCE_MONITOR_ENABLED=true
VRAM_ALERT_THRESHOLD_MB=7000
""")

    print_header("Check Complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
