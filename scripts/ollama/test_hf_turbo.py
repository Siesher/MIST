"""Standalone test for HuggingFace + TurboQuant backend.

Загружает Qwen3.5-9B base + KTO LoRA adapter с TurboQuant KV compression.
Замеряет VRAM, tok/s, сравнивает качество с Ollama.

ПЕРЕД ЗАПУСКОМ убей Ollama чтобы освободить VRAM:
    Get-Process ollama* | Stop-Process -Force

Usage:
    python scripts/test_hf_turbo.py
    python scripts/test_hf_turbo.py --config qwen3.5-9b-turbo-2.5bit
    python scripts/test_hf_turbo.py --no-adapter     # без KTO fine-tune
"""

from __future__ import annotations

import argparse
import gc
import logging
import sys
import time
from pathlib import Path

# Project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_hf_turbo")


TEST_PROMPTS = [
    ("Простая арифметика", "Сколько будет 2+2? Отвечай кратко."),
    ("Тригонометрия", "Выведи формулу для sin(2x). Кратко."),
    (
        "Сократический стиль",
        "Как подойти к интегралу ∫x·sin(x)dx? Не давай ответ, задай направляющий вопрос.",
    ),
]


def measure_vram_mb() -> float | None:
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        torch.cuda.synchronize()
        return torch.cuda.memory_allocated() / (1024**2)
    except Exception:
        return None


def free_memory() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="qwen3.5-9b-turbo")
    parser.add_argument(
        "--no-adapter", action="store_true", help="Use base model without KTO adapter"
    )
    parser.add_argument(
        "--no-turbo",
        action="store_true",
        help="Force-disable TurboQuant KV cache (use standard DynamicCache)",
    )
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()

    print("=" * 60)
    print(f" HF + TurboQuant Benchmark — config: {args.config}")
    print("=" * 60)

    # Baseline VRAM
    free_memory()
    vram_before = measure_vram_mb()
    if vram_before is None:
        print("\nERROR: torch.cuda.is_available() = False — fix CUDA before continuing")
        return 3
    print(f"\nBaseline VRAM (before model load): {vram_before:.1f} MiB")

    # Load model
    print(f"\nLoading model configuration '{args.config}'...")
    from src.inference.model_config import get_model_config
    from src.inference.turbo_quant import TurboQuantConfig
    from src.models.hf_client import HuggingFaceClient

    cfg = get_model_config(args.config)
    if cfg is None:
        print(f"ERROR: config '{args.config}' not found")
        return 2

    tq = None
    if cfg.turbo_quant_enabled and not args.no_turbo:
        tq = TurboQuantConfig(
            key_bits=cfg.turbo_quant_key_bits,
            value_bits=cfg.turbo_quant_value_bits,
        )
        print(f"  TurboQuant: K={tq.key_bits}b V={tq.value_bits}b")
    else:
        print("  TurboQuant: DISABLED (using standard DynamicCache)")

    adapter = None if args.no_adapter else cfg.hf_adapter_path
    print(f"  Base model: {cfg.hf_model_path}")
    print(f"  LoRA adapter: {adapter or '(none — base model)'}")
    print(f"  Context: {cfg.context_length} tokens")
    print()

    t_load_start = time.perf_counter()
    try:
        client = HuggingFaceClient(
            model_path=cfg.hf_model_path,
            adapter_path=adapter,
            quantize=True,  # 4-bit NF4 always on (fits on 8GB)
            turbo_quant_config=tq,
        )
    except Exception as e:
        print(f"\nFATAL: model load failed: {e}")
        import traceback

        traceback.print_exc()
        return 1
    t_load = time.perf_counter() - t_load_start

    vram_loaded = measure_vram_mb()
    print(f"\n✓ Model loaded in {t_load:.1f}s")
    if vram_loaded and vram_before is not None:
        print(f"  VRAM: {vram_loaded:.0f} MiB  (+{vram_loaded - vram_before:.0f} MiB for model)")

    # Generation benchmarks
    print("\n" + "-" * 60)
    print(" Generation benchmarks")
    print("-" * 60)

    results = []
    for label, prompt in TEST_PROMPTS:
        print(f"\n▸ {label}")
        print(f"  prompt: {prompt[:70]}")

        t_start = time.perf_counter()
        try:
            response = client.generate(
                prompt=prompt,
                system="Ты — репетитор. Отвечай кратко по-русски.",
                max_tokens=args.max_tokens,
                temperature=cfg.temperature,
                thinking=False,
            )
        except Exception as e:
            import traceback

            print(f"  ERROR: {type(e).__name__}: {e}")
            print("  --- traceback (last 20 frames) ---")
            traceback.print_exc(limit=20)
            print("  ---")
            continue
        t_gen = time.perf_counter() - t_start

        # Token count estimation via tokenizer
        out_tokens = len(client.tokenizer.encode(response))
        tok_per_sec = out_tokens / t_gen if t_gen > 0 else 0

        print(f"  response ({out_tokens} tok, {t_gen:.2f}s, {tok_per_sec:.1f} tok/s):")
        print(f"    {response[:200]}")

        results.append(
            {
                "label": label,
                "tokens": out_tokens,
                "time_s": t_gen,
                "tok_per_sec": tok_per_sec,
            }
        )

    # Summary
    print("\n" + "=" * 60)
    print(" Summary")
    print("=" * 60)
    if results:
        avg_tps = sum(r["tok_per_sec"] for r in results) / len(results)
        print(f"  Avg tok/s: {avg_tps:.1f}")
        print(f"  Load time: {t_load:.1f}s")
        if vram_loaded:
            print(f"  Peak VRAM: {vram_loaded:.0f} MiB ({vram_loaded / 1024:.2f} GiB)")
        print(f"  Config: {cfg.display_name}")

    print("\n✓ Done. Сравни с Ollama (mits-tutor-9b-fast): ~29 tok/s на 2080.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
