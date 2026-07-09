"""V-STaR within-task pairing (A+B): trajectories -> DPO preference pairs.

A — correctness-mixed (0<n_correct<4); B — completeness в all-correct (4/4).
Без PRM (composite-этап добавит prm/pedagogy scores позже).

Usage: uv run python scripts/build_vstar_pairs.py
"""

from __future__ import annotations

import io
import json
import sys
from collections import Counter
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
            "correctness": float(bool(chosen["correct"])),
            "completeness": float(has_content(chosen)),
        },
        "scores_rejected": {
            "correctness": float(bool(rejected["correct"])),
            "completeness": float(has_content(rejected)),
        },
    }


def _chosen_key(t: dict) -> tuple:
    # приоритет: есть content -> early_boxed -> меньший sample_idx
    return (not has_content(t), t.get("done_reason") != "early_boxed", t["sample_idx"])


def _rejected_key(t: dict) -> tuple:
    # приоритет: есть content (честный контраст) -> меньший sample_idx
    return (not has_content(t), t["sample_idx"])


def select_pair_A(row: dict) -> tuple[dict, dict]:
    """correctness-mixed: chosen=лучшая correct, rejected=лучшая incorrect."""
    trs = row["trajectories"]
    correct = [t for t in trs if t["correct"]]
    incorrect = [t for t in trs if not t["correct"]]
    chosen = min(correct, key=_chosen_key)
    rejected = min(incorrect, key=_rejected_key)
    return chosen, rejected


def select_pair_B(row: dict) -> tuple[dict, dict] | None:
    """completeness в 4/4: chosen=correct+content, rejected=correct+обрезка. None если нет смеси."""
    trs = row["trajectories"]
    with_c = [t for t in trs if has_content(t)]
    without_c = [t for t in trs if not has_content(t)]
    if not with_c or not without_c:
        return None
    chosen = min(with_c, key=lambda t: t["sample_idx"])
    rejected = min(without_c, key=lambda t: t["sample_idx"])
    return chosen, rejected


def build_all_pairs(rows: list[dict]) -> list[dict]:
    pairs = []
    for row in rows:
        nc = row["n_correct"]
        if 0 < nc < 4:
            ch, rj = select_pair_A(row)
            pairs.append(build_pair_record(row, ch, rj, "A"))
        elif nc == 4:
            res = select_pair_B(row)
            if res is not None:
                ch, rj = res
                pairs.append(build_pair_record(row, ch, rj, "B"))
    return pairs


def main() -> None:
    rows = [json.loads(line) for line in TRAJ.open(encoding="utf-8") if line.strip()]
    pairs = build_all_pairs(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    strat = Counter(p["strategy"] for p in pairs)
    dom = Counter(p["domain"] for p in pairs)
    print(f"[ok] {len(pairs)} пар -> {OUT}")
    print(f"  strategy: {dict(strat)}")
    print(f"  domain: {dict(dom)}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
