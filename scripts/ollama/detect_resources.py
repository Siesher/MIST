#!/usr/bin/env python3
"""
Detect system resources and recommend a MITS profile.

Usage:
    python scripts/detect_resources.py
    python scripts/detect_resources.py --set lite       # force lite profile
    python scripts/detect_resources.py --list           # show all profiles
"""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.resource_profiles import (  # noqa: E402
    PROFILES,
    ProfileName,
    detect_hardware,
    detect_recommended_profile,
)


def print_profile(p) -> None:
    """Pretty-print a profile."""
    print(
        f"  {p.name.value.upper():>8s} | "
        f"RAM >= {p.min_ram_gb:>2d} GB | "
        f"VRAM >= {p.min_vram_gb:>2d} GB | "
        f"{p.llm_quantization:>7s} | "
        f"ctx {p.llm_context_tokens:>5d}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="MITS resource detector")
    parser.add_argument("--list", action="store_true", help="List all profiles")
    parser.add_argument("--verbose", action="store_true", help="Show full profile")
    args = parser.parse_args()

    print("=" * 70)
    print("MITS Resource Detector")
    print("=" * 70)

    # Current hardware
    hw = detect_hardware()
    print("\nDetected hardware:")
    print(f"  RAM:  {hw['ram_gb']:5.1f} GB")
    print(f"  VRAM: {hw['vram_gb']:5.1f} GB" + (" (GPU)" if hw["vram_gb"] > 0 else " (no GPU)"))

    # Recommended profile
    recommended = detect_recommended_profile()
    p = PROFILES[recommended]
    print(f"\nRecommended profile: {recommended.value.upper()}")
    print(f"  {p.description}")

    # All profiles
    if args.list:
        print("\nAvailable profiles:")
        print("  " + "-" * 66)
        print("  NAME     | MIN RAM  | MIN VRAM | QUANT   | CTX")
        print("  " + "-" * 66)
        for name in (ProfileName.LITE, ProfileName.STANDARD, ProfileName.MAX):
            print_profile(PROFILES[name])
        print("")

    # Full details
    if args.verbose:
        print("\nFull profile configuration:")
        for k, v in asdict(p).items():
            print(f"  {k:>35s}: {v}")
        print("")

    # Usage hint
    print("To override: export MITS_PROFILE=lite|standard|max")
    print(f"Current env: MITS_PROFILE={__import__('os').environ.get('MITS_PROFILE', '(unset)')}")


if __name__ == "__main__":
    main()
