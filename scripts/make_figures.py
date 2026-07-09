"""Генерация графиков ВКР из реальных данных (matplotlib).

Usage: uv run --with matplotlib python scripts/make_figures.py
Выход: figures/fig_*.png
"""

from __future__ import annotations

import io
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
FIGURES = ROOT / "figures"
TRAJ = ROOT / "training/data/vstar_trajectories_hard.jsonl"

plt.rcParams.update({"font.size": 11, "font.family": "DejaVu Sans", "figure.dpi": 150})

DOMAINS = ["Математика", "Физика", "Химия", "Биология", "Информатика"]
BASELINE = [79.1, 74.4, 46.7, 28.6, 46.5]
# per-stage per-domain (Base, GSPO, KTO, DPO) — из главы 4.3
PER_STAGE = {
    "Математика": [79.1, 87.2, 87.5, 88.2],
    "Физика": [74.4, 82.1, 82.7, 84.3],
    "Химия": [46.7, 55.2, 56.4, 58.4],
    "Биология": [28.6, 37.2, 40.5, 43.0],
    "Информатика": [46.5, 55.8, 56.9, 58.6],
}
STAGES = ["Base", "GSPO", "KTO", "DPO"]
VSTAR_YIELD = {"Математика": 31, "Информатика": 14, "Физика": 11, "Биология": 7, "Химия": 2}


def fig_baseline() -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(DOMAINS, BASELINE, color="#5B8FF9")
    ax.axhline(55.1, ls="--", color="#888", label="macro-среднее 55,1%")
    ax.set_ylabel("Точность, %")
    ax.set_title("Базовая точность Qwen3.5-9B по STEM-доменам")
    ax.set_ylim(0, 100)
    for b, v in zip(bars, BASELINE):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v}", ha="center", fontsize=10)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_baseline_domains.png", bbox_inches="tight")
    plt.close(fig)


def fig_per_stage() -> None:
    import numpy as np

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(DOMAINS))
    w = 0.2
    colors = ["#BfBfBf", "#5B8FF9", "#5AD8A6", "#F6BD16"]
    for i, st in enumerate(STAGES):
        vals = [PER_STAGE[d][i] for d in DOMAINS]
        ax.bar(x + (i - 1.5) * w, vals, w, label=st, color=colors[i])
    ax.set_xticks(x)
    ax.set_xticklabels(DOMAINS, rotation=15)
    ax.set_ylabel("Точность, %")
    ax.set_title("Точность по стадиям обучения и доменам (Base → GSPO → KTO → DPO)")
    ax.set_ylim(0, 100)
    ax.legend(ncol=4)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_per_stage.png", bbox_inches="tight")
    plt.close(fig)


def fig_ncorrect_hist() -> None:
    rows = [json.loads(line) for line in TRAJ.open(encoding="utf-8") if line.strip()]
    nc = Counter(r["n_correct"] for r in rows)
    keys = [0, 1, 2, 3, 4]
    vals = [nc.get(k, 0) for k in keys]
    colors = ["#E8684A", "#F6BD16", "#F6BD16", "#F6BD16", "#5AD8A6"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar([f"{k}/4" for k in keys], vals, color=colors)
    ax.set_ylabel("Число задач")
    ax.set_xlabel("Корректных траекторий из N=4")
    ax.set_title(f"Распределение n_correct (V-STaR, {len(rows)} hard-задач): бимодальное")
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v + 3,
            f"{v}\n({v / len(rows) * 100:.0f}%)",
            ha="center",
            fontsize=9,
        )
    ax.text(
        0.5,
        0.92,
        "крайние 0/4 и 4/4 — не usable; mixed (1-3/4) → DPO-пары",
        transform=ax.transAxes,
        ha="center",
        fontsize=9,
        color="#666",
    )
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_ncorrect_hist.png", bbox_inches="tight")
    plt.close(fig)


def fig_vstar_yield() -> None:
    doms = list(VSTAR_YIELD.keys())
    vals = [VSTAR_YIELD[d] for d in doms]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(doms, vals, color="#945FB9")
    ax.set_ylabel("Usable пар (correctness-mixed)")
    ax.set_title("Выход within-task пар по доменам (V-STaR hard, всего 65 + 19 completeness)")
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.5, str(v), ha="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_vstar_yield.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    fig_baseline()
    fig_per_stage()
    fig_ncorrect_hist()
    fig_vstar_yield()
    print(
        "[ok] сгенерированы: fig_baseline_domains, fig_per_stage, fig_ncorrect_hist, fig_vstar_yield"
    )


if __name__ == "__main__":
    main()
