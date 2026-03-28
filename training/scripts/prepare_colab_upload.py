"""
Prepare files for Google Colab upload.

Creates a staging directory with the exact Drive structure needed
to run the MITS training pipeline (GSPO -> KTO -> DPO).

Usage:
    python scripts/prepare_colab_upload.py [--output PATH]

After running, upload the contents of the staging folder to Google Drive root (MyDrive/).
"""
import argparse
import os
import shutil
import sys

# Files to stage: (local_path, drive_relative_path)
FILES = [
    # Python scripts -> MyDrive/training/scripts/
    ("training/scripts/stem_rewards.py",      "training/scripts/stem_rewards.py"),
    ("training/scripts/verify_answers.py",    "training/scripts/verify_answers.py"),
    ("training/scripts/sort_curriculum.py",    "training/scripts/sort_curriculum.py"),
    ("training/scripts/evaluate_stage.py",     "training/scripts/evaluate_stage.py"),
    ("training/scripts/__init__.py",           "training/scripts/__init__.py"),

    # Training data -> MyDrive/training/data/
    ("training/data/rl_combined.jsonl",        "training/data/rl_combined.jsonl"),
    ("training/data/rl_combined.stats.json",   "training/data/rl_combined.stats.json"),
    ("training/data/eval_benchmark.jsonl",     "training/data/eval_benchmark.jsonl"),
    ("training/data/preference_pairs.jsonl",   "training/data/preference_pairs.jsonl"),

    # Dialog data -> MyDrive/data/training/
    ("data/training/dialogs.jsonl",            "data/training/dialogs.jsonl"),

    # Notebooks -> MyDrive/notebooks/ (for reference, run from Colab)
    ("notebooks/grpo_qwen3.5_9b.ipynb",       "notebooks/grpo_qwen3.5_9b.ipynb"),
    ("notebooks/kto_qwen3.5_9b.ipynb",        "notebooks/kto_qwen3.5_9b.ipynb"),
    ("notebooks/dpo_polish_qwen3.5_9b.ipynb",  "notebooks/dpo_polish_qwen3.5_9b.ipynb"),
]

# Empty directories to create
DIRS = [
    "MITS/checkpoints/gspo_qwen3.5_9b",
    "MITS/checkpoints/kto_qwen3.5_9b",
    "MITS/checkpoints/dpo_qwen3.5_9b",
    "MITS/evaluation/reports",
    "MITS/training/data",
]


def main():
    parser = argparse.ArgumentParser(description="Prepare files for Colab upload")
    parser.add_argument(
        "--output", default="colab_upload",
        help="Staging directory (default: colab_upload/)",
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    staging = os.path.join(project_root, args.output)

    # Clean previous staging
    if os.path.exists(staging):
        shutil.rmtree(staging)

    print(f"Staging directory: {staging}")
    print(f"Project root: {project_root}")
    print()

    # Create empty directories
    for d in DIRS:
        path = os.path.join(staging, d)
        os.makedirs(path, exist_ok=True)

    # Copy files
    total_size = 0
    copied = 0
    missing = []

    for local_rel, drive_rel in FILES:
        src = os.path.join(project_root, local_rel)
        dst = os.path.join(staging, drive_rel)

        if not os.path.exists(src):
            missing.append(local_rel)
            print(f"  MISSING: {local_rel}")
            continue

        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        size = os.path.getsize(src)
        total_size += size
        copied += 1
        size_str = f"{size / 1024 / 1024:.1f} MB" if size > 1024 * 1024 else f"{size / 1024:.0f} KB"
        print(f"  {drive_rel} ({size_str})")

    # Also symlink eval_benchmark to MITS/training/data/ (notebooks look there too)
    eval_src = os.path.join(staging, "training/data/eval_benchmark.jsonl")
    eval_dst = os.path.join(staging, "MITS/training/data/eval_benchmark.jsonl")
    if os.path.exists(eval_src) and not os.path.exists(eval_dst):
        shutil.copy2(eval_src, eval_dst)
        print(f"  MITS/training/data/eval_benchmark.jsonl (copy)")

    print()
    print(f"{'=' * 50}")
    print(f"Copied: {copied}/{len(FILES)} files ({total_size / 1024 / 1024:.1f} MB)")
    if missing:
        print(f"Missing: {len(missing)} files:")
        for m in missing:
            print(f"  - {m}")
    print()
    print("Upload instructions:")
    print(f"  1. Open Google Drive (drive.google.com)")
    print(f"  2. Upload the CONTENTS of '{args.output}/' to 'My Drive' root")
    print(f"     - training/ folder -> My Drive/training/")
    print(f"     - data/ folder -> My Drive/data/")
    print(f"     - notebooks/ folder -> My Drive/notebooks/")
    print(f"     - MITS/ folder -> My Drive/MITS/")
    print(f"  3. Open notebooks in Colab: GSPO -> KTO -> DPO")
    print()
    print("Directory structure on Drive:")
    for root, dirs, files in os.walk(staging):
        level = root.replace(staging, "").count(os.sep)
        indent = "  " * level
        basename = os.path.basename(root) or args.output
        print(f"{indent}{basename}/")
        subindent = "  " * (level + 1)
        for f in sorted(files):
            size = os.path.getsize(os.path.join(root, f))
            size_str = f"{size / 1024 / 1024:.1f}M" if size > 1024 * 1024 else f"{size / 1024:.0f}K"
            print(f"{subindent}{f} ({size_str})")


if __name__ == "__main__":
    main()
