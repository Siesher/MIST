"""Recover full GSPO training metrics from loguru log file.

Parses the loguru log on Google Drive to extract per-step metrics
(correctness, format, socratic) that were lost from trainer_state.json.

Usage (Colab cell):
    %run training/scripts/recover_metrics_from_log.py \
        --log-file /content/drive/MyDrive/MITS/checkpoints/gspo_qwen3.5_9b_v2/gspo_training.log \
        --output-csv /content/drive/MyDrive/MITS/checkpoints/gspo_qwen3.5_9b_v2/metrics/training_metrics_full.csv

Or as a standalone module:
    from training.scripts.recover_metrics_from_log import parse_loguru_log, build_metrics_df
"""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ─── Regex patterns for loguru log lines ────────────────────────

# Main step line: "10:27:14 | INFO     | step=5 | loss=-0.0475 | reward=0.473±0.309 | lr=2.67e-07 | grad_norm=0.003"
STEP_PATTERN = re.compile(
    r"step=(?P<step>\d+)\s*\|\s*"
    r"loss=(?P<loss>[-\d.e+]+)\s*\|\s*"
    r"reward=(?P<reward_mean>[-\d.e+]+)±(?P<reward_std>[-\d.e+]+)\s*\|\s*"
    r"lr=(?P<learning_rate>[-\d.e+]+)\s*\|\s*"
    r"grad_norm=(?P<grad_norm>[-\d.e+]+)"
)

# Reward detail lines: "rewards/_base_format_fn/mean: 0.7719"
REWARD_DETAIL_PATTERN = re.compile(
    r"rewards/(?P<reward_name>[a-z_]+)/(?P<stat>mean|std):\s*(?P<value>[-\d.e+]+)"
)

# Stage markers: "STAGE 1:" or "STAGE 2:"
STAGE_MARKER_PATTERN = re.compile(r"STAGE\s+(?P<stage>\d+)")

# Completion length: "completion_length/mean: 1234.5"
COMPLETION_LENGTH_PATTERN = re.compile(r"completion_length/mean:\s*(?P<value>[-\d.e+]+)")


def _map_reward_name(raw_name: str) -> str | None:
    """Map raw reward function name to clean column prefix."""
    if "correctness" in raw_name:
        return "correctness"
    elif "format" in raw_name:
        return "format"
    elif "socratic" in raw_name:
        return "socratic"
    return None


def parse_loguru_log(log_path: str | Path) -> list[dict[str, Any]]:
    """Parse loguru log file and extract per-step training metrics.

    Args:
        log_path: Path to the loguru log file.

    Returns:
        List of dicts, one per training step, with all available metrics.
    """
    log_path = Path(log_path)
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    logger.info(f"Read {len(lines)} lines from {log_path}")

    records: list[dict[str, Any]] = []
    current_record: dict[str, Any] | None = None
    current_stage = "stage1"
    stage_step_counts: dict[str, int] = {}

    for line in lines:
        # Strip ANSI escape codes (loguru file sink may include them)
        clean_line = re.sub(r"\x1b\[[0-9;]*m", "", line)

        # Detect stage transitions
        stage_match = STAGE_MARKER_PATTERN.search(clean_line)
        if stage_match:
            new_stage = f"stage{stage_match.group('stage')}"
            if new_stage != current_stage:
                current_stage = new_stage
                logger.info(f"  Detected transition to {current_stage}")

        # Match main step line
        step_match = STEP_PATTERN.search(clean_line)
        if step_match:
            # Save previous record if exists
            if current_record is not None:
                records.append(current_record)

            step_num = int(step_match.group("step"))

            # Detect stage boundary: if step resets to small number after large
            if current_stage in stage_step_counts:
                last_step = stage_step_counts[current_stage]
                if step_num < last_step - 10:
                    # Step number decreased significantly — likely new stage
                    stage_idx = int(current_stage[-1]) + 1
                    current_stage = f"stage{stage_idx}"
                    logger.info(
                        f"  Step reset detected ({last_step} -> {step_num}), now {current_stage}"
                    )
            stage_step_counts[current_stage] = step_num

            current_record = {
                "stage": current_stage,
                "step": step_num,
                "loss": float(step_match.group("loss")),
                "reward_mean": float(step_match.group("reward_mean")),
                "reward_std": float(step_match.group("reward_std")),
                "learning_rate": float(step_match.group("learning_rate")),
                "grad_norm": float(step_match.group("grad_norm")),
            }
            continue

        # Match reward detail lines (must follow a step line)
        if current_record is not None:
            reward_match = REWARD_DETAIL_PATTERN.search(clean_line)
            if reward_match:
                reward_name = _map_reward_name(reward_match.group("reward_name"))
                if reward_name:
                    stat = reward_match.group("stat")
                    value = float(reward_match.group("value"))
                    current_record[f"{reward_name}_{stat}"] = value
                continue

            # Match completion length
            cl_match = COMPLETION_LENGTH_PATTERN.search(clean_line)
            if cl_match:
                current_record["completion_length_mean"] = float(cl_match.group("value"))
                continue

    # Don't forget last record
    if current_record is not None:
        records.append(current_record)

    logger.info(f"  Parsed {len(records)} step records")

    # Report per-stage counts
    stage_counts = {}
    for r in records:
        stage_counts[r["stage"]] = stage_counts.get(r["stage"], 0) + 1
    for stage, count in sorted(stage_counts.items()):
        logger.info(f"  {stage}: {count} steps")

    return records


def build_metrics_df(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert parsed records to a clean DataFrame.

    Args:
        records: List of dicts from parse_loguru_log().

    Returns:
        DataFrame with standardized columns, sorted by stage and step.
    """
    df = pd.DataFrame(records)

    # Ensure standard column order
    expected_cols = [
        "stage",
        "step",
        "loss",
        "reward_mean",
        "reward_std",
        "correctness_mean",
        "correctness_std",
        "format_mean",
        "format_std",
        "socratic_mean",
        "socratic_std",
        "learning_rate",
        "grad_norm",
        "completion_length_mean",
    ]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    df = df[expected_cols].sort_values(["stage", "step"]).reset_index(drop=True)

    # Report completeness
    for stage in df["stage"].unique():
        sdf = df[df["stage"] == stage]
        n_total = len(sdf)
        n_format = sdf["format_mean"].notna().sum()
        n_socratic = sdf["socratic_mean"].notna().sum()
        logger.info(
            f"  {stage}: {n_total} rows, "
            f"format={n_format}/{n_total}, "
            f"socratic={n_socratic}/{n_total}"
        )

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover GSPO metrics from loguru log")
    parser.add_argument(
        "--log-file",
        required=True,
        help="Path to gspo_training.log on Google Drive",
    )
    parser.add_argument(
        "--output-csv",
        required=True,
        help="Path to write the full metrics CSV",
    )
    parser.add_argument(
        "--merge-with",
        default=None,
        help="Optional: existing CSV to merge with (fills NaN values)",
    )
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    # Parse log
    records = parse_loguru_log(args.log_file)
    df = build_metrics_df(records)

    # Optionally merge with existing CSV
    if args.merge_with and Path(args.merge_with).exists():
        existing = pd.read_csv(args.merge_with)
        logger.info(f"Merging with existing CSV: {len(existing)} rows from {args.merge_with}")

        # Use log-parsed data as primary, fill gaps from existing
        merged = df.set_index(["stage", "step"])
        existing_idx = existing.set_index(["stage", "step"])

        # For columns present in both, prefer log-parsed (more complete)
        for col in merged.columns:
            if col in existing_idx.columns:
                merged[col] = merged[col].fillna(existing_idx[col])

        # Add any columns only in existing
        for col in existing_idx.columns:
            if col not in merged.columns:
                merged[col] = existing_idx[col]

        df = merged.reset_index().sort_values(["stage", "step"]).reset_index(drop=True)
        logger.info(f"Merged result: {len(df)} rows")

    # Save
    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"Saved full metrics: {output_path} ({len(df)} rows)")

    # Print summary
    print("\n" + "=" * 70)
    print("RECOVERED METRICS SUMMARY")
    print("=" * 70)
    for stage in df["stage"].unique():
        sdf = df[df["stage"] == stage]
        print(f"\n[{stage.upper()}]")
        print(f"  Steps: {sdf['step'].min()} → {sdf['step'].max()} ({len(sdf)} rows)")
        print(
            f"  Loss: {sdf['loss'].mean():.4f} avg ({sdf['loss'].min():.4f} min, {sdf['loss'].max():.4f} max)"
        )
        if sdf["correctness_mean"].notna().any():
            print(f"  Correctness: {sdf['correctness_mean'].mean():.3f} avg")
        if sdf["format_mean"].notna().any():
            print(f"  Format: {sdf['format_mean'].mean():.3f} avg")
        if sdf["socratic_mean"].notna().any():
            print(f"  Socratic: {sdf['socratic_mean'].mean():.3f} avg")
        print(f"  Reward: {sdf['reward_mean'].mean():.3f} avg")
    print("=" * 70)


if __name__ == "__main__":
    main()
