#!/usr/bin/env python3
"""
Download and preprocess ASSISTments 2009-2010 skill-builder dataset for DKT training.

Pipeline:
    1. Download dataset from public mirror
    2. Remove scaffolding problems
    3. Map skills to integer IDs
    4. Create interaction sequences per student
    5. Pad/truncate to fixed length
    6. Split into train/val/test

Output:
    data/training/assistments_train.pt
    data/training/assistments_val.pt
    data/training/assistments_test.pt
    data/training/assistments_skill_map.json

Usage:
    python training/scripts/prepare_assistments.py
    python training/scripts/prepare_assistments.py --max-seq-len 200 --min-interactions 5
"""

import json
import argparse
import logging
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Try importing optional deps
try:
    import torch
except ImportError:
    logger.error("PyTorch required: pip install torch")
    exit(1)

try:
    import pandas as pd
except ImportError:
    logger.error("Pandas required: pip install pandas")
    exit(1)


DATASET_URL = "https://ndownloader.figshare.com/files/44732737"
FALLBACK_INFO = """
If automatic download fails, manually download from:
  https://figshare.com/articles/dataset/skill_builder_data_csv/25309000

Place the CSV in: data/training/assistments_raw.csv
"""


def download_dataset(output_path: Path) -> Path:
    """Download ASSISTments dataset."""
    csv_path = output_path / "assistments_raw.csv"

    if csv_path.exists():
        logger.info(f"Dataset already exists: {csv_path}")
        return csv_path

    output_path.mkdir(parents=True, exist_ok=True)

    try:
        import urllib.request
        logger.info("Downloading ASSISTments dataset...")
        urllib.request.urlretrieve(DATASET_URL, csv_path)
        logger.info(f"Downloaded to {csv_path}")
    except Exception as e:
        logger.warning(f"Download failed: {e}")
        logger.info(FALLBACK_INFO)
        raise

    return csv_path


def load_and_clean(csv_path: Path) -> pd.DataFrame:
    """Load and clean the dataset."""
    logger.info(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path, encoding="latin1", low_memory=False)
    logger.info(f"Raw records: {len(df)}")

    # Required columns
    required = ["user_id", "skill_name", "correct"]
    for col in required:
        if col not in df.columns:
            # Try alternative column names
            if col == "skill_name" and "skill_id" in df.columns:
                df["skill_name"] = df["skill_id"].astype(str)
            else:
                raise ValueError(f"Missing column: {col}")

    # Remove rows with missing skill or correctness
    df = df.dropna(subset=["skill_name", "correct"])

    # Remove scaffolding problems (original != 1)
    if "original" in df.columns:
        before = len(df)
        df = df[df["original"] == 1]
        logger.info(f"Removed scaffolding: {before} -> {len(df)}")

    # Ensure correct is binary
    df["correct"] = df["correct"].astype(int).clip(0, 1)

    # Sort by user and order
    if "order_id" in df.columns:
        df = df.sort_values(["user_id", "order_id"])
    else:
        df = df.sort_values("user_id")

    logger.info(f"Cleaned records: {len(df)}")
    logger.info(f"Students: {df['user_id'].nunique()}")
    logger.info(f"Skills: {df['skill_name'].nunique()}")

    return df


def create_skill_map(df: pd.DataFrame) -> Dict[str, int]:
    """Map skill names to integer IDs."""
    skills = sorted(df["skill_name"].unique())
    skill_map = {name: idx for idx, name in enumerate(skills)}
    logger.info(f"Skill map: {len(skill_map)} skills")
    return skill_map


def create_sequences(
    df: pd.DataFrame,
    skill_map: Dict[str, int],
    max_seq_len: int = 200,
    min_interactions: int = 5,
) -> List[Tuple[List[int], List[int]]]:
    """Create interaction sequences per student."""
    sequences = []

    for user_id, group in df.groupby("user_id"):
        if len(group) < min_interactions:
            continue

        skill_ids = [skill_map[s] for s in group["skill_name"]]
        corrects = group["correct"].tolist()

        # Truncate if needed
        if len(skill_ids) > max_seq_len:
            skill_ids = skill_ids[:max_seq_len]
            corrects = corrects[:max_seq_len]

        sequences.append((skill_ids, corrects))

    logger.info(f"Created {len(sequences)} sequences (min {min_interactions} interactions)")
    return sequences


def pad_sequences(
    sequences: List[Tuple[List[int], List[int]]],
    max_len: int = 200,
    pad_value: int = -1,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Pad sequences to fixed length and create tensors."""
    n = len(sequences)
    skills_tensor = torch.full((n, max_len), pad_value, dtype=torch.long)
    correct_tensor = torch.full((n, max_len), pad_value, dtype=torch.long)
    lengths = torch.zeros(n, dtype=torch.long)

    for i, (skill_ids, corrects) in enumerate(sequences):
        seq_len = min(len(skill_ids), max_len)
        skills_tensor[i, :seq_len] = torch.tensor(skill_ids[:seq_len])
        correct_tensor[i, :seq_len] = torch.tensor(corrects[:seq_len])
        lengths[i] = seq_len

    return skills_tensor, correct_tensor, lengths


def split_data(
    skills: torch.Tensor,
    corrects: torch.Tensor,
    lengths: torch.Tensor,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> dict:
    """Split into train/val/test."""
    n = len(skills)
    rng = np.random.RandomState(seed)
    indices = rng.permutation(n)

    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    splits = {}
    for name, idx in [
        ("train", indices[:train_end]),
        ("val", indices[train_end:val_end]),
        ("test", indices[val_end:]),
    ]:
        splits[name] = {
            "skills": skills[idx],
            "corrects": corrects[idx],
            "lengths": lengths[idx],
        }
        logger.info(f"  {name}: {len(idx)} sequences")

    return splits


def main():
    parser = argparse.ArgumentParser(description="Prepare ASSISTments for DKT")
    parser.add_argument("--data-dir", type=str, default="data/training")
    parser.add_argument("--max-seq-len", type=int, default=200)
    parser.add_argument("--min-interactions", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    # Download
    csv_path = download_dataset(data_dir)

    # Load and clean
    df = load_and_clean(csv_path)

    # Create skill map
    skill_map = create_skill_map(df)

    # Save skill map
    skill_map_path = data_dir / "assistments_skill_map.json"
    with open(skill_map_path, "w") as f:
        json.dump(skill_map, f, indent=2)
    logger.info(f"Skill map saved: {skill_map_path}")

    # Create sequences
    sequences = create_sequences(df, skill_map, args.max_seq_len, args.min_interactions)

    # Pad and tensorize
    skills, corrects, lengths = pad_sequences(sequences, args.max_seq_len)

    # Split
    splits = split_data(skills, corrects, lengths, seed=args.seed)

    # Save
    for name, data in splits.items():
        path = data_dir / f"assistments_{name}.pt"
        torch.save(data, path)
        logger.info(f"Saved {name}: {path}")

    logger.info(f"\nDone! num_skills={len(skill_map)}, total_sequences={len(sequences)}")


if __name__ == "__main__":
    main()
