"""
Hardware Auto-Detection Service

Detects available RAM, VRAM, and Ollama models to automatically
select the best model for the current hardware.

Selection logic:
- VRAM >= 4GB or RAM >= 16GB: Qwen3-4B (best quality)
- VRAM >= 2GB or RAM >= 8GB:  Qwen3-1.7B (lightweight)
- Otherwise:                   GLM fallback or API

Usage:
    from backend.app.services.hardware_detector import detect_hardware, select_model

    hw = detect_hardware()
    model = select_model(hw)
"""

import os
import logging
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class HardwareInfo:
    """Detected hardware capabilities."""
    total_ram_gb: float = 0.0
    available_ram_gb: float = 0.0
    gpu_name: Optional[str] = None
    gpu_vram_gb: float = 0.0
    gpu_available: bool = False
    ollama_models: List[str] = None
    ollama_running: bool = False

    def __post_init__(self):
        if self.ollama_models is None:
            self.ollama_models = []


# Known MITS models in preference order
MITS_MODELS = [
    {
        "name": "mits-tutor-qwen3-4b",
        "min_ram_gb": 16,
        "min_vram_gb": 4,
        "ram_usage_gb": 4.5,
        "vram_usage_gb": 3.5,
        "quality": "high",
        "description": "Qwen3-4B fine-tuned STEM tutor",
    },
    {
        "name": "mits-tutor-qwen3-1.7b",
        "min_ram_gb": 8,
        "min_vram_gb": 2,
        "ram_usage_gb": 3.0,
        "vram_usage_gb": 2.0,
        "quality": "medium",
        "description": "Qwen3-1.7B lightweight STEM tutor",
    },
    {
        "name": "glm-reap-23b",
        "min_ram_gb": 16,
        "min_vram_gb": 8,
        "ram_usage_gb": 13.0,
        "vram_usage_gb": 8.0,
        "quality": "high",
        "description": "GLM-4.7-Flash ReAP pruned (existing)",
    },
]


def detect_hardware(ollama_host: str = "http://localhost:11434") -> HardwareInfo:
    """Detect available hardware capabilities."""
    hw = HardwareInfo()

    # RAM detection via psutil
    try:
        import psutil
        mem = psutil.virtual_memory()
        hw.total_ram_gb = round(mem.total / (1024 ** 3), 1)
        hw.available_ram_gb = round(mem.available / (1024 ** 3), 1)
    except ImportError:
        logger.debug("psutil not available, trying OS-level detection")
        try:
            if os.name == 'nt':
                import ctypes
                kernel32 = ctypes.windll.kernel32
                c_ulong = ctypes.c_ulonglong
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong),
                        ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', c_ulong),
                        ('ullAvailPhys', c_ulong),
                        ('ullTotalPageFile', c_ulong),
                        ('ullAvailPageFile', c_ulong),
                        ('ullTotalVirtual', c_ulong),
                        ('ullAvailVirtual', c_ulong),
                        ('ullAvailExtendedVirtual', c_ulong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(stat)
                kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                hw.total_ram_gb = round(stat.ullTotalPhys / (1024 ** 3), 1)
                hw.available_ram_gb = round(stat.ullAvailPhys / (1024 ** 3), 1)
        except Exception as e:
            logger.warning(f"RAM detection failed: {e}")

    # GPU detection via torch.cuda
    try:
        import torch
        if torch.cuda.is_available():
            hw.gpu_available = True
            hw.gpu_name = torch.cuda.get_device_name(0)
            total_vram = torch.cuda.get_device_properties(0).total_mem
            hw.gpu_vram_gb = round(total_vram / (1024 ** 3), 1)
    except ImportError:
        logger.debug("torch not available, skipping GPU detection")

    # Ollama model detection
    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=5)
        if resp.status_code == 200:
            hw.ollama_running = True
            models = resp.json().get("models", [])
            hw.ollama_models = [m["name"] for m in models]
    except Exception:
        hw.ollama_running = False

    logger.info(
        f"Hardware: RAM={hw.total_ram_gb}GB (avail={hw.available_ram_gb}GB), "
        f"GPU={'%s %.1fGB' % (hw.gpu_name, hw.gpu_vram_gb) if hw.gpu_available else 'none'}, "
        f"Ollama={'running' if hw.ollama_running else 'not running'} "
        f"({len(hw.ollama_models)} models)"
    )

    return hw


def select_model(
    hw: HardwareInfo,
    prefer_finetuned: bool = True,
) -> Dict[str, Any]:
    """Select the best model for detected hardware.

    Returns dict with:
        name: Ollama model name
        reason: Why this model was selected
        available: Whether the model is already in Ollama
        quality: "high", "medium", or "fallback"
    """
    for model in MITS_MODELS:
        # Skip non-fine-tuned if preferring fine-tuned
        if prefer_finetuned and model["name"] == "glm-reap-23b":
            continue

        fits_ram = hw.available_ram_gb >= model["ram_usage_gb"]
        fits_vram = (
            hw.gpu_available and hw.gpu_vram_gb >= model["vram_usage_gb"]
        ) if hw.gpu_available else False

        # Can run on CPU if enough RAM, or on GPU if enough VRAM
        can_run = fits_ram or fits_vram
        if not can_run:
            continue

        is_available = model["name"] in hw.ollama_models

        reason_parts = []
        if fits_vram:
            reason_parts.append(f"GPU {hw.gpu_name} ({hw.gpu_vram_gb}GB VRAM)")
        elif fits_ram:
            reason_parts.append(f"CPU mode ({hw.available_ram_gb}GB available RAM)")

        return {
            "name": model["name"],
            "description": model["description"],
            "quality": model["quality"],
            "available": is_available,
            "needs_pull": not is_available,
            "reason": f"Selected: {model['description']} — " + ", ".join(reason_parts),
            "estimated_ram_gb": model["ram_usage_gb"],
            "estimated_vram_gb": model["vram_usage_gb"] if fits_vram else 0,
        }

    # Fallback: try GLM if available
    for model in MITS_MODELS:
        if model["name"] in hw.ollama_models:
            return {
                "name": model["name"],
                "description": model["description"],
                "quality": model["quality"],
                "available": True,
                "needs_pull": False,
                "reason": f"Fallback: using already-downloaded {model['name']}",
                "estimated_ram_gb": model["ram_usage_gb"],
                "estimated_vram_gb": 0,
            }

    return {
        "name": "glm-reap-23b",
        "description": "GLM fallback (may need manual pull)",
        "quality": "fallback",
        "available": False,
        "needs_pull": True,
        "reason": "No suitable model found for hardware. Pull glm-reap-23b manually.",
        "estimated_ram_gb": 13.0,
        "estimated_vram_gb": 0,
    }


def get_vram_profile(
    model_name: str,
    ollama_host: str = "http://localhost:11434",
) -> Dict[str, Any]:
    """Profile actual VRAM usage of a running model.

    Constitution IV requires total inference VRAM < 6GB.
    """
    profile = {"model": model_name, "vram_gb": None, "compliant": None}

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()

            # Run a test inference to measure peak VRAM
            resp = requests.post(
                f"{ollama_host}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "Реши уравнение 2x + 5 = 15",
                    "stream": False,
                    "options": {"num_predict": 256},
                },
                timeout=120,
            )

            peak_vram = torch.cuda.max_memory_allocated() / (1024 ** 3)
            profile["vram_gb"] = round(peak_vram, 2)
            profile["compliant"] = peak_vram < 6.0
            profile["limit_gb"] = 6.0
    except Exception as e:
        profile["error"] = str(e)

    return profile


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    hw = detect_hardware()
    print("\n--- Hardware Info ---")
    print(f"RAM: {hw.total_ram_gb} GB (available: {hw.available_ram_gb} GB)")
    if hw.gpu_available:
        print(f"GPU: {hw.gpu_name} ({hw.gpu_vram_gb} GB VRAM)")
    else:
        print("GPU: not available")
    print(f"Ollama: {'running' if hw.ollama_running else 'not running'}")
    if hw.ollama_models:
        print(f"Models: {', '.join(hw.ollama_models)}")

    selection = select_model(hw)
    print("\n--- Model Selection ---")
    print(json.dumps(selection, indent=2, ensure_ascii=False))
