"""
Merge LoRA adapter from HuggingFace into base model and create Ollama model.

Downloads base Qwen3-4B-Instruct + GSPO adapter, merges LoRA weights,
saves merged safetensors, then creates Ollama model via CLI.

Requirements:
    pip install transformers peft accelerate torch

Usage:
    python training/scripts/merge_and_create_ollama.py

    # Custom adapter repo:
    python training/scripts/merge_and_create_ollama.py \
        --adapter-repo Siesher/mits-qwen3-4b-gspo \
        --ollama-name mits-tutor
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def _hf_download_with_retry(fn, *args, max_retries=5, **kwargs):
    """Retry HuggingFace downloads on 429 rate limit errors."""
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 30 * (attempt + 1)
                print(
                    f"      Rate limited (429), waiting {wait}s... (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
            else:
                raise


def merge_adapter(
    base_model: str,
    adapter_repo: str,
    output_dir: str,
    low_memory: bool = True,
) -> str:
    """Download base model + LoRA adapter, merge, save as safetensors.

    Args:
        base_model: HuggingFace model ID for the base model.
        adapter_repo: HuggingFace repo ID for the LoRA adapter.
        output_dir: Directory to save merged safetensors.
        low_memory: If True, use low_cpu_mem_usage to reduce peak RAM (~50% less).
    """
    import gc

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"\n[1/4] Downloading base model: {base_model}")
    print("      (first run downloads ~18 GB, cached afterwards)")
    if low_memory:
        print("      Low-memory mode: loading with reduced peak RAM usage")

    tokenizer = _hf_download_with_retry(
        AutoTokenizer.from_pretrained,
        base_model,
        trust_remote_code=True,
    )

    model = _hf_download_with_retry(
        AutoModelForCausalLM.from_pretrained,
        base_model,
        dtype=torch.float16,
        device_map="cpu",
        low_cpu_mem_usage=True,
        trust_remote_code=True,
    )

    print(f"\n[2/4] Loading LoRA adapter: {adapter_repo}")
    model = _hf_download_with_retry(
        PeftModel.from_pretrained,
        model,
        adapter_repo,
        low_cpu_mem_usage=True,
    )

    print("\n[3/4] Merging LoRA weights into base model...")
    model = model.merge_and_unload()
    gc.collect()

    print(f"\n[4/4] Saving merged model to {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir, max_shard_size="4GB")
    tokenizer.save_pretrained(output_dir)

    del model
    gc.collect()

    size_gb = sum(f.stat().st_size for f in Path(output_dir).rglob("*") if f.is_file()) / (1024**3)
    print(f"      Saved ({size_gb:.1f} GB)")

    return output_dir


def create_ollama_model(
    merged_dir: str,
    modelfile_path: str,
    ollama_name: str,
    quantize: str = "q8_0",
):
    """Create Ollama model from merged safetensors using Modelfile."""
    print(f"\n[4/4] Creating Ollama model '{ollama_name}' (quantize={quantize})")

    # Verify ollama is installed
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
        )
        print(f"      Ollama version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("ERROR: ollama not found. Install from https://ollama.com")
        sys.exit(1)

    cmd = ["ollama", "create", ollama_name, "-f", modelfile_path]
    if quantize:
        cmd.extend(["--quantize", quantize])

    print(f"      Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"\n  Model '{ollama_name}' created!")
    print(f"  Run:  ollama run {ollama_name}")


def main():
    parser = argparse.ArgumentParser(description="Merge LoRA adapter and create Ollama model")
    parser.add_argument("--base-model", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--adapter-repo", default="Siesher/mits-qwen3-9b-gspo")
    parser.add_argument("--merged-dir", default="training/merged_gspo_9b")
    parser.add_argument("--modelfile", default="training/Modelfile")
    parser.add_argument("--ollama-name", default="mits-tutor-9b")
    parser.add_argument(
        "--quantize", default="q8_0", help="Quantization: q8_0, q4_k_m, q5_k_m, or empty for none"
    )
    parser.add_argument(
        "--merge-only", action="store_true", help="Only merge, don't create Ollama model"
    )
    args = parser.parse_args()

    merged_dir = merge_adapter(
        base_model=args.base_model,
        adapter_repo=args.adapter_repo,
        output_dir=args.merged_dir,
    )

    if not args.merge_only:
        create_ollama_model(
            merged_dir=merged_dir,
            modelfile_path=args.modelfile,
            ollama_name=args.ollama_name,
            quantize=args.quantize,
        )


if __name__ == "__main__":
    main()
