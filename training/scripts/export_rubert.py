#!/usr/bin/env python3
"""
Export fine-tuned RuBERT affect model for production use.

Saves the model in a format compatible with src/models/affective_ml_detector.py.
Optionally converts to ONNX for faster CPU inference.

Usage:
    python training/scripts/export_rubert.py \
        --checkpoint data/models/rubert_affect \
        --output data/models/rubert_affect_prod

    # With ONNX export
    python training/scripts/export_rubert.py \
        --checkpoint data/models/rubert_affect \
        --output data/models/rubert_affect_prod \
        --onnx
"""

import argparse
import json
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def export_pytorch(checkpoint_dir: Path, output_dir: Path):
    """Export PyTorch model for production."""
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    logger.info(f"Loading model from {checkpoint_dir}")
    tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(checkpoint_dir))

    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Copy metadata if exists
    metadata_src = checkpoint_dir / "metadata.json"
    if metadata_src.exists():
        shutil.copy2(metadata_src, output_dir / "metadata.json")

    logger.info(f"PyTorch model exported to {output_dir}")

    # Print model info
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"  Parameters: {total_params:,}")
    logger.info(f"  Labels: {model.config.id2label}")


def export_onnx(checkpoint_dir: Path, output_dir: Path, max_length: int = 128):
    """Export to ONNX for faster CPU inference."""
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    logger.info("Exporting to ONNX...")
    tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(checkpoint_dir))
    model.eval()

    # Dummy input
    dummy = tokenizer(
        "тестовое сообщение",
        return_tensors="pt",
        padding="max_length",
        max_length=max_length,
        truncation=True,
    )

    onnx_path = output_dir / "model.onnx"
    output_dir.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        (dummy["input_ids"], dummy["attention_mask"]),
        str(onnx_path),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "logits": {0: "batch"},
        },
        opset_version=14,
    )

    # Save tokenizer alongside ONNX
    tokenizer.save_pretrained(str(output_dir))

    logger.info(f"ONNX model exported to {onnx_path}")
    logger.info(f"  File size: {onnx_path.stat().st_size / 1024 / 1024:.1f} MB")


def main():
    parser = argparse.ArgumentParser(description="Export RuBERT affect model")
    parser.add_argument("--checkpoint", type=str,
                        default="data/models/rubert_affect",
                        help="Path to fine-tuned model checkpoint")
    parser.add_argument("--output", type=str,
                        default="data/models/rubert_affect_prod",
                        help="Output directory for production model")
    parser.add_argument("--onnx", action="store_true",
                        help="Also export to ONNX format")
    parser.add_argument("--max-length", type=int, default=128,
                        help="Max sequence length for ONNX export")
    args = parser.parse_args()

    checkpoint_dir = Path(args.checkpoint)
    output_dir = Path(args.output)

    if not checkpoint_dir.exists():
        logger.error(f"Checkpoint not found: {checkpoint_dir}")
        return 1

    export_pytorch(checkpoint_dir, output_dir)

    if args.onnx:
        export_onnx(checkpoint_dir, output_dir / "onnx", args.max_length)

    logger.info("Export complete!")
    return 0


if __name__ == "__main__":
    exit(main())
