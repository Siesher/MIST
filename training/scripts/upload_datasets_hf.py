#!/usr/bin/env python3
"""
Upload MITS training datasets to Hugging Face Hub.

Uploads three configs to Siesher/mits-stem-training-data:
  - sft:         combined_stem_balanced.jsonl (40K SFT examples)
  - preference:  preference_pairs.jsonl (12K SimPO pairs)
  - gspo:        gspo_problems.jsonl (15K GSPO problems)

Usage:
    python training/scripts/upload_datasets_hf.py
    python training/scripts/upload_datasets_hf.py --private
"""

import argparse
import json
import sys
from pathlib import Path

from datasets import Dataset, DatasetDict, Features, Value, Sequence


HF_REPO = "Siesher/mits-stem-training-data"

DATASET_CONFIGS = {
    "sft": {
        "path": "training/data/combined_stem_balanced.jsonl",
        "description": "SFT training data: 40K balanced STEM examples with <think> reasoning",
    },
    "preference": {
        "path": "training/data/preference_pairs.jsonl",
        "description": "SimPO preference pairs: Socratic (chosen) vs Direct (rejected) responses",
    },
    "gspo": {
        "path": "training/data/gspo_problems.jsonl",
        "description": "GSPO/RL training problems with ground truth answers",
    },
}


def load_jsonl(path: str) -> list:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def upload_all(private: bool = False):
    from datasets import Dataset
    from collections import Counter

    for config_name, config in DATASET_CONFIGS.items():
        path = config["path"]
        if not Path(path).exists():
            print(f"SKIP: {path} not found")
            continue

        records = load_jsonl(path)
        print(f"\n{'='*60}")
        print(f"Config: {config_name}")
        print(f"  File: {path}")
        print(f"  Records: {len(records)}")
        print(f"  Description: {config['description']}")

        # Show domain distribution
        domains = Counter(r.get("domain", "?") for r in records)
        for d, c in sorted(domains.items()):
            print(f"    {d}: {c}")

        # Convert prompt field for preference pairs (list of dicts → string)
        if config_name == "preference":
            for r in records:
                if isinstance(r.get("prompt"), list):
                    # Convert messages list to plain text instruction
                    r["prompt"] = r["prompt"][0]["content"] if r["prompt"] else ""

        # Create HF Dataset
        ds = Dataset.from_list(records)

        # Split 95/5 train/test
        split = ds.train_test_split(test_size=0.05, seed=42)
        print(f"  Train: {len(split['train'])}, Test: {len(split['test'])}")

        # Push
        print(f"  Pushing to {HF_REPO} (config={config_name})...")
        split.push_to_hub(
            HF_REPO,
            config_name=config_name,
            private=private,
        )
        print(f"  Done!")

    print(f"\nAll datasets uploaded to: https://huggingface.co/datasets/{HF_REPO}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private", action="store_true", help="Make dataset private")
    args = parser.parse_args()

    upload_all(private=args.private)
    return 0


if __name__ == "__main__":
    sys.exit(main())
