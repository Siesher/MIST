#!/usr/bin/env python3
"""
MITS LoRA Adapter Merge Script

Merges LoRA adapter weights into base model for faster inference.
The merged model can be used directly or converted to GGUF for Ollama.

Usage:
    python training/scripts/merge_adapter.py \
        --base-model Qwen/Qwen2.5-7B-Instruct \
        --adapter ./outputs/mits-tutor-qlora \
        --output ./models/mits-tutor-merged
"""

import argparse
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)
logger = structlog.get_logger()


def merge_adapter(
    base_model_path: str,
    adapter_path: str,
    output_path: str,
    dtype: str = "bfloat16"
):
    """
    Merge LoRA adapter into base model.

    Args:
        base_model_path: HuggingFace model ID or path
        adapter_path: Path to LoRA adapter
        output_path: Path to save merged model
        dtype: Output dtype (float16, bfloat16, float32)
    """
    logger.info(
        "starting_merge",
        base=base_model_path,
        adapter=adapter_path,
        output=output_path
    )

    # Load base model (in full precision for merging)
    logger.info("loading_base_model")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=getattr(torch, dtype),
        device_map="auto",
        trust_remote_code=True
    )

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_path,
        trust_remote_code=True
    )

    # Load and merge LoRA adapter
    logger.info("loading_adapter")
    model = PeftModel.from_pretrained(base_model, adapter_path)

    logger.info("merging_weights")
    model = model.merge_and_unload()

    # Save merged model
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("saving_merged_model", path=str(output_path))
    model.save_pretrained(output_path, safe_serialization=True)
    tokenizer.save_pretrained(output_path)

    # Save merge info
    info = {
        "base_model": base_model_path,
        "adapter": adapter_path,
        "dtype": dtype,
        "merged": True
    }

    import json
    with open(output_path / "merge_info.json", "w") as f:
        json.dump(info, f, indent=2)

    logger.info("merge_complete", output=str(output_path))

    # Print next steps
    print("\n" + "="*60)
    print("Merge complete!")
    print(f"Merged model saved to: {output_path}")
    print("="*60)
    print("\nNext steps:")
    print(f"1. Test the model:")
    print(f"   python -c \"from transformers import pipeline; p = pipeline('text-generation', '{output_path}'); print(p('Hello'))\"")
    print(f"\n2. Convert to GGUF for Ollama (optional):")
    print(f"   python llama.cpp/convert_hf_to_gguf.py {output_path} --outfile model.gguf")
    print(f"\n3. Use in MITS:")
    print(f"   Set HF_MODEL_PATH={output_path} in .env")
    print(f"   Set MODEL_BACKEND=huggingface in .env")


def parse_args():
    parser = argparse.ArgumentParser(description="Merge LoRA adapter into base model")

    parser.add_argument(
        '--base-model',
        type=str,
        default='Qwen/Qwen2.5-7B-Instruct',
        help='Base model HuggingFace ID or path'
    )
    parser.add_argument(
        '--adapter',
        type=str,
        required=True,
        help='Path to LoRA adapter directory'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./models/mits-tutor-merged',
        help='Output path for merged model'
    )
    parser.add_argument(
        '--dtype',
        type=str,
        choices=['float16', 'bfloat16', 'float32'],
        default='bfloat16',
        help='Output dtype'
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    merge_adapter(
        base_model_path=args.base_model,
        adapter_path=args.adapter,
        output_path=args.output,
        dtype=args.dtype
    )
