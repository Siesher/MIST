"""V-STaR within-task pairing (A+B): trajectories -> DPO preference pairs.

A — correctness-mixed (0<n_correct<4); B — completeness в all-correct (4/4).
Без PRM (composite-этап добавит prm/pedagogy scores позже).

Usage: uv run python scripts/build_vstar_pairs.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent
TRAJ = ROOT / "training/data/vstar_trajectories_hard.jsonl"
OUT = ROOT / "training/data/vstar_dpo_pairs.jsonl"


def make_completion(traj: dict) -> str:
    """Полный completion: <think>{thinking}</think>\\n{content}."""
    thinking = traj.get("thinking", "").strip()
    content = traj.get("content", "").strip()
    return f"<think>{thinking}</think>\n{content}"


def has_content(traj: dict) -> bool:
    return len(traj.get("content", "").strip()) > 0


def build_pair_record(row: dict, chosen: dict, rejected: dict, strategy: str) -> dict:
    return {
        "pair_id": f"{row['subset_idx']}__{chosen['sample_idx']}__{rejected['sample_idx']}",
        "prompt": [{"role": "user", "content": row["prompt"]}],
        "chosen": make_completion(chosen),
        "rejected": make_completion(rejected),
        "domain": row.get("domain", "?"),
        "difficulty": row.get("difficulty", "hard"),
        "strategy": strategy,
        "scores_chosen": {
            "correctness": float(chosen["correct"]),
            "completeness": float(has_content(chosen)),
        },
        "scores_rejected": {
            "correctness": float(rejected["correct"]),
            "completeness": float(has_content(rejected)),
        },
    }
