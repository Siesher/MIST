"""
Resource profiles for MITS deployment.

Three profiles scale the system to different hardware:
- lite: 16 GB RAM, CPU-only, mid-budget machine
- standard: 32 GB RAM, mid-range GPU (6-12 GB VRAM)
- max: 64+ GB RAM, high-end GPU (24+ GB) or cloud API

Each profile selects LLM quantization, context length, and feature flags
to match available resources.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ProfileName(str, Enum):
    """Named resource profiles."""

    LITE = "lite"  # 16 GB RAM, CPU only
    STANDARD = "standard"  # 32 GB RAM, mid GPU
    MAX = "max"  # 64+ GB RAM, high GPU or cloud


# ─────────────────────────────────────────────────────────────────────
# Profile Configuration
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResourceProfile:
    """Full configuration for a deployment profile.

    Attributes:
        name: Profile identifier.
        min_ram_gb: Minimum RAM required (total system).
        min_vram_gb: Minimum VRAM (0 = CPU only).
        llm_quantization: Recommended GGUF quant (Q4_K_M, Q5_K_M, FP16).
        llm_context_tokens: Max context length.
        llm_gpu_layers: GPU offload layers (-1 = all, 0 = CPU only).

        # Feature flags — each heavy feature checks these
        enable_rubert_affect: Load RuBERT emotion detector.
        enable_dkt: Use deep knowledge tracing beyond BKT.
        enable_llm_verifier: Use LLM to validate graph proposals.
        enable_source_extractor: Enable document → graph ingestion.
        enable_batch_inference: Batch multiple LLM calls.
        enable_speculative_decoding: Use draft model for acceleration.

        # Tunable limits
        max_tool_rounds: Max tool-calling rounds in one turn.
        max_concurrent_sessions: How many students at once.
        navigator_max_frontier: Max frontier results per query.
    """

    name: ProfileName
    min_ram_gb: int
    min_vram_gb: int = 0

    # LLM settings
    llm_quantization: str = "Q4_K_M"
    llm_context_tokens: int = 4096
    llm_gpu_layers: int = 0

    # Feature flags
    enable_rubert_affect: bool = False
    enable_dkt: bool = False
    enable_llm_verifier: bool = False
    enable_source_extractor: bool = True  # works but may be slow
    enable_batch_inference: bool = False
    enable_speculative_decoding: bool = False
    enable_tom_agent: bool = False  # ToM-Tutor feature 017
    tom_prompt_style: str = "short"  # "short" for lite, "full" for standard/max

    # Tunable limits
    max_tool_rounds: int = 3
    max_concurrent_sessions: int = 1
    navigator_max_frontier: int = 5
    tom_output_cap: int = 150  # max output tokens for ToM inference

    # Description for UX
    description: str = ""


# ─────────────────────────────────────────────────────────────────────
# Registered Profiles
# ─────────────────────────────────────────────────────────────────────


PROFILES: Dict[ProfileName, ResourceProfile] = {
    ProfileName.LITE: ResourceProfile(
        name=ProfileName.LITE,
        min_ram_gb=15,  # 16 GB sticker ≈ 15 GB reported after OS overhead
        min_vram_gb=0,
        llm_quantization="Q4_K_M",
        llm_context_tokens=4096,
        llm_gpu_layers=0,
        enable_rubert_affect=False,
        enable_dkt=False,
        enable_llm_verifier=False,
        enable_source_extractor=True,
        enable_batch_inference=False,
        enable_speculative_decoding=False,
        enable_tom_agent=False,  # disabled by default on lite (opt-in after latency check)
        tom_prompt_style="short",
        max_tool_rounds=2,
        max_concurrent_sessions=1,
        navigator_max_frontier=5,
        tom_output_cap=120,  # very tight to hit latency budget on CPU
        description=(
            "Minimum viable setup for a 16 GB RAM laptop without GPU. "
            "Full Knowledge Forge + Living KG functionality. "
            "LLM runs on CPU via Q4_K_M quantization (~12 tok/s). "
            "Rule-based affect detection only. RuBERT and DKT disabled. "
            "ToM agent opt-in (latency check required)."
        ),
    ),
    ProfileName.STANDARD: ResourceProfile(
        name=ProfileName.STANDARD,
        min_ram_gb=30,  # 32 GB sticker ≈ 31 GB reported
        min_vram_gb=6,
        llm_quantization="Q5_K_M",
        llm_context_tokens=8192,
        llm_gpu_layers=-1,  # all layers on GPU
        enable_rubert_affect=True,
        enable_dkt=True,
        enable_llm_verifier=True,
        enable_source_extractor=True,
        enable_batch_inference=True,
        enable_speculative_decoding=False,
        enable_tom_agent=True,
        tom_prompt_style="full",
        max_tool_rounds=3,
        max_concurrent_sessions=3,
        navigator_max_frontier=10,
        tom_output_cap=400,
        description=(
            "Recommended setup for a 32 GB RAM machine with 6-12 GB VRAM. "
            "Full feature set including RuBERT affect detection, DKT, "
            "LLM verification of graph proposals, and ToM-Tutor. ~35 tok/s."
        ),
    ),
    ProfileName.MAX: ResourceProfile(
        name=ProfileName.MAX,
        min_ram_gb=60,  # 64 GB sticker ≈ 63 GB reported
        min_vram_gb=24,
        llm_quantization="FP16",
        llm_context_tokens=32768,
        llm_gpu_layers=-1,
        enable_rubert_affect=True,
        enable_dkt=True,
        enable_llm_verifier=True,
        enable_source_extractor=True,
        enable_batch_inference=True,
        enable_speculative_decoding=True,
        enable_tom_agent=True,
        tom_prompt_style="full",
        max_tool_rounds=5,
        max_concurrent_sessions=16,
        navigator_max_frontier=20,
        tom_output_cap=500,
        description=(
            "Full-capability setup for 64+ GB RAM and high-end GPU "
            "(RTX 4090 / A100 / cloud Cerebras). All features enabled, "
            "32K context, batch inference, speculative decoding, ToM-Tutor. ~80+ tok/s."
        ),
    ),
}


# ─────────────────────────────────────────────────────────────────────
# Active Profile Selection
# ─────────────────────────────────────────────────────────────────────

_active_profile: Optional[ResourceProfile] = None


def get_active_profile() -> ResourceProfile:
    """Get the currently active resource profile.

    Priority: explicit set_active_profile() > MITS_PROFILE env var > auto-detect > LITE.
    """
    global _active_profile
    if _active_profile is not None:
        return _active_profile

    # Env var
    env_name = os.environ.get("MITS_PROFILE", "").lower().strip()
    if env_name in [p.value for p in ProfileName]:
        _active_profile = PROFILES[ProfileName(env_name)]
        logger.info(f"Active profile (from env): {_active_profile.name.value}")
        return _active_profile

    # Auto-detect from hardware
    detected = detect_recommended_profile()
    _active_profile = PROFILES[detected]
    logger.info(f"Active profile (auto-detected): {_active_profile.name.value}")
    return _active_profile


def set_active_profile(name: ProfileName) -> ResourceProfile:
    """Explicitly set the active profile."""
    global _active_profile
    _active_profile = PROFILES[name]
    logger.info(f"Active profile set to: {name.value}")
    return _active_profile


def reset_active_profile() -> None:
    """Clear cached active profile (for testing)."""
    global _active_profile
    _active_profile = None


# ─────────────────────────────────────────────────────────────────────
# Hardware Detection
# ─────────────────────────────────────────────────────────────────────


def detect_hardware() -> Dict[str, float]:
    """Detect available RAM and VRAM.

    Returns:
        Dict with 'ram_gb' and 'vram_gb' (0 if no GPU).
    """
    info: Dict[str, float] = {"ram_gb": 0.0, "vram_gb": 0.0}

    # RAM via psutil
    try:
        import psutil

        info["ram_gb"] = psutil.virtual_memory().total / (1024**3)
    except ImportError:
        logger.warning("psutil not available — cannot detect RAM")

    # VRAM via torch.cuda (optional)
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            info["vram_gb"] = props.total_memory / (1024**3)
    except (ImportError, RuntimeError):
        pass  # No GPU or torch not installed — vram stays 0

    return info


def detect_recommended_profile() -> ProfileName:
    """Pick the best-fitting profile for current hardware.

    Returns:
        Largest profile whose min requirements are satisfied.
    """
    hw = detect_hardware()
    ram = hw["ram_gb"]
    vram = hw["vram_gb"]

    # Iterate from highest to lowest, pick first that fits
    for name in (ProfileName.MAX, ProfileName.STANDARD, ProfileName.LITE):
        p = PROFILES[name]
        if ram >= p.min_ram_gb and vram >= p.min_vram_gb:
            return name

    # Fallback if even LITE requirements aren't met
    logger.warning(f"Hardware below lite profile: RAM={ram:.1f} GB, VRAM={vram:.1f} GB")
    return ProfileName.LITE


# ─────────────────────────────────────────────────────────────────────
# Feature Flag Helpers (convenience)
# ─────────────────────────────────────────────────────────────────────


def feature_enabled(feature: str) -> bool:
    """Check if a named feature is enabled in the active profile.

    Args:
        feature: Attribute name like 'enable_rubert_affect'.

    Returns:
        True if enabled in the active profile.
    """
    profile = get_active_profile()
    return bool(getattr(profile, feature, False))
