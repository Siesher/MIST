"""Build GSPO Q4_K_M GGUF локально для honest eval.

Pipeline:
  1. Load base Qwen3.5-9B fp16 from HF cache (CPU)
  2. Apply GSPO LoRA adapter (Siesher/mits-qwen3-9b-gspo)
  3. merge_and_unload() → standalone fp16 model
  4. save_pretrained → HF format на диск
  5. convert_hf_to_gguf.py → mits-gspo.f16.gguf (subprocess)
  6. llama-quantize → mits-gspo.q4km.gguf (subprocess)

Memory budget на 32GB RAM:
  - Base fp16 weights: ~18 GB
  - LoRA adapter: ~0.16 GB
  - Merge buffer: ~4-6 GB transient
  - Total peak: ~24-26 GB (tight но workable)

Time estimate (Ryzen 9 9950X, no GPU):
  - Load base: ~2-4 min (CPU SSD bandwidth-bound)
  - Apply LoRA + merge: ~5-15 min (per-layer matmul)
  - Save merged HF: ~3-5 min (write 18 GB)
  - convert_hf_to_gguf: ~5 min
  - quantize Q4_K_M: ~3 min
  Total: ~20-30 min

Usage:
  uv run python scripts/build_gspo_gguf.py
"""
from __future__ import annotations

import io
import os
import sys
import subprocess
import time
from pathlib import Path

# Force UTF-8 stdout — Windows default cp1251 cannot encode Russian Cyrillic + arrows.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
MODELS_DIR = ROOT / "training/models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

LLAMA_BIN = ROOT / "tools/llama.cpp/bin"
LLAMA_CONVERT = ROOT / "tools/llama.cpp/convert_hf_to_gguf.py"
LLAMA_QUANTIZE = LLAMA_BIN / "llama-quantize.exe"

BASE_HF = "Qwen/Qwen3.5-9B"
# Direct local path — avoids PEFT trying to re-download adapter_model.bin (HF auth fail).
GSPO_ADAPTER = r"C:\Users\Maksim\.cache\huggingface\hub\models--Siesher--mits-qwen3-9b-gspo\snapshots\9cdfadb759652c179aeae9d3773e837b2687e3e9"

MERGED_DIR = MODELS_DIR / "mits-gspo-merged-hf"
OUT_F16 = MODELS_DIR / "mits-gspo.f16.gguf"
OUT_Q4 = MODELS_DIR / "mits-gspo.q4km.gguf"


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def step_merge() -> None:
    """Step 1-4: load base + LoRA, merge, save HF."""
    if MERGED_DIR.exists() and (MERGED_DIR / "config.json").exists():
        log(f"SKIP merge — {MERGED_DIR.name} already exists")
        return

    log("Importing torch + transformers + peft...")
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer
    from peft import PeftModel

    log(f"Loading base {BASE_HF} в fp16 (low_cpu_mem_usage)...")
    t0 = time.time()
    base = AutoModelForImageTextToText.from_pretrained(
        BASE_HF,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    log(f"  Base loaded in {time.time() - t0:.1f}s")

    log(f"Loading tokenizer...")
    tok = AutoTokenizer.from_pretrained(BASE_HF)

    log(f"Applying GSPO LoRA from {GSPO_ADAPTER}...")
    t0 = time.time()
    peft_model = PeftModel.from_pretrained(base, GSPO_ADAPTER)
    log(f"  LoRA applied in {time.time() - t0:.1f}s")

    log(f"Merging adapter (merge_and_unload)...")
    t0 = time.time()
    merged = peft_model.merge_and_unload()
    log(f"  Merged in {time.time() - t0:.1f}s")

    log(f"Saving merged model к {MERGED_DIR}...")
    t0 = time.time()
    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(MERGED_DIR, safe_serialization=True, max_shard_size="5GB")
    tok.save_pretrained(MERGED_DIR)
    log(f"  Saved in {time.time() - t0:.1f}s")

    # Free memory before subprocess
    del merged, peft_model, base, tok
    import gc
    gc.collect()
    log(f"Memory freed; merged saved at {MERGED_DIR}")


def step_convert() -> None:
    """Step 5: convert merged HF → GGUF f16 via subprocess."""
    if OUT_F16.exists():
        sz = OUT_F16.stat().st_size / (1024**3)
        log(f"SKIP convert — {OUT_F16.name} exists ({sz:.2f} GB)")
        return

    log(f"Running convert_hf_to_gguf.py → {OUT_F16.name}")
    cmd = [
        sys.executable,
        str(LLAMA_CONVERT),
        str(MERGED_DIR),
        "--outfile", str(OUT_F16),
        "--outtype", "f16",
    ]
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    elapsed = time.time() - t0
    if result.returncode != 0:
        log(f"FAILED ({elapsed:.1f}s):")
        log(f"STDOUT tail:\n{result.stdout[-2000:]}")
        log(f"STDERR tail:\n{result.stderr[-2000:]}")
        sys.exit(1)
    sz = OUT_F16.stat().st_size / (1024**3)
    log(f"  Converted in {elapsed:.1f}s — {OUT_F16.name} {sz:.2f} GB")


def step_quantize() -> None:
    """Step 6: quantize f16 → Q4_K_M via llama-quantize."""
    if OUT_Q4.exists():
        sz = OUT_Q4.stat().st_size / (1024**3)
        log(f"SKIP quantize — {OUT_Q4.name} exists ({sz:.2f} GB)")
        return

    log(f"Running llama-quantize → {OUT_Q4.name}")
    cmd = [str(LLAMA_QUANTIZE), str(OUT_F16), str(OUT_Q4), "Q4_K_M"]
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    elapsed = time.time() - t0
    if result.returncode != 0:
        log(f"FAILED ({elapsed:.1f}s):")
        log(f"STDOUT tail:\n{result.stdout[-2000:]}")
        log(f"STDERR tail:\n{result.stderr[-2000:]}")
        sys.exit(1)
    sz = OUT_Q4.stat().st_size / (1024**3)
    log(f"  Quantized in {elapsed:.1f}s — {OUT_Q4.name} {sz:.2f} GB")


def main() -> None:
    log("=== GSPO GGUF build pipeline ===")
    log(f"Output: {OUT_Q4}")
    log("")

    step_merge()
    step_convert()
    step_quantize()

    log("")
    log("=== ALL STAGES COMPLETE ===")
    log(f"Final Q4_K_M: {OUT_Q4} ({OUT_Q4.stat().st_size / (1024**3):.2f} GB)")
    log("Next: register в Ollama via Modelfile (см. training/Modelfile.eval-gspo)")


if __name__ == "__main__":
    main()
