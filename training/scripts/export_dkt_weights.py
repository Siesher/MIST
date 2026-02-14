#!/usr/bin/env python3
"""
Export trained DKT weights compatible with src/models/dkt_model.py.

Loads the checkpoint from training and saves in the format expected
by the production DKTModel class.

Usage:
    python training/scripts/export_dkt_weights.py \
        --checkpoint data/models/dkt_pretrained.pt \
        --output data/models/dkt_pretrained.pt
"""

import argparse
import json
from pathlib import Path

import torch


def export_weights(checkpoint_path: Path, output_path: Path):
    """Export DKT weights to production format."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    # Extract model config
    config = {
        "num_skills": checkpoint.get("num_skills", 123),
        "hidden_size": checkpoint.get("hidden_size", 64),
        "num_layers": checkpoint.get("num_layers", 1),
        "embed_size": checkpoint.get("embed_size", 32),
        "val_auc": checkpoint.get("val_auc", 0.0),
        "epoch": checkpoint.get("epoch", 0),
    }

    # Save in production format
    output_path.parent.mkdir(parents=True, exist_ok=True)
    production_checkpoint = {
        "model_state_dict": checkpoint["model_state_dict"],
        "config": config,
    }
    torch.save(production_checkpoint, output_path)

    print(f"Exported DKT weights:")
    print(f"  Source: {checkpoint_path}")
    print(f"  Output: {output_path}")
    print(f"  Config: {json.dumps(config, indent=2)}")
    print(f"  State dict keys: {list(checkpoint['model_state_dict'].keys())}")


def main():
    parser = argparse.ArgumentParser(description="Export DKT weights")
    parser.add_argument("--checkpoint", type=str,
                        default="data/models/dkt_pretrained.pt")
    parser.add_argument("--output", type=str,
                        default="data/models/dkt_pretrained.pt")
    args = parser.parse_args()

    export_weights(Path(args.checkpoint), Path(args.output))


if __name__ == "__main__":
    main()
