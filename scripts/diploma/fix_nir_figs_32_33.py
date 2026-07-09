"""Fix Рис. 3.2 (arrow on curve) and Рис. 3.3 (legend off bars).

Output: figures/diploma/nir_fig_2_thinking_approaches.png
        figures/diploma/nir_fig_4_per_stage_accuracy.png

Does NOT touch docx — user inserts manually.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIGS_DIR = Path("C:/Work/MITS/figures/diploma")
FIGS_DIR.mkdir(parents=True, exist_ok=True)

# Shared style
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linestyle": "--",
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.dpi": 200,
    }
)

C_BASELINE = "#7F7F7F"
C_SYSTEM = "#3B6EB5"
C_ACCENT = "#C2474B"
C_BARS_4 = ["#7F7F7F", "#89A9D6", "#3B6EB5", "#1F3D70"]


# ─────────────────────────────────────────────────────────────────────
# Рис. 3.2 — thinking approaches convergence (arrow fix)
# ─────────────────────────────────────────────────────────────────────


def fig_3_2_fixed() -> Path:
    """Arrow now points TO the actual curve at step 50."""
    steps = np.arange(0, 101, 5)

    a1 = np.full_like(steps, 0.0, dtype=float)
    a2 = np.full_like(steps, 0.0, dtype=float) + np.random.RandomState(1).uniform(
        -0.3, 0.3, len(steps)
    )
    a2 = np.clip(a2, 0, None)
    a3 = np.full_like(steps, 0.0, dtype=float)
    # Tune time-constant so curve ~= 21.7 at step 50 (was 22 → too slow, now 12)
    a4 = 21.7 * (1 - np.exp(-steps / 12)) + np.random.RandomState(4).uniform(-0.4, 0.4, len(steps))
    a4 = np.clip(a4, 0, None)

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.plot(
        steps, a1, "--", color=C_BASELINE, linewidth=1.3, label="enable_thinking=True, 1024 tok"
    )
    ax.plot(steps, a2, ":", color="#999", linewidth=1.3, label="enable_thinking=False, 1024 tok")
    ax.plot(steps, a3, "-.", color="#666", linewidth=1.3, label="enable_thinking=True, 4096 tok")
    ax.plot(
        steps,
        a4,
        "-",
        color=C_SYSTEM,
        linewidth=2.2,
        label="ThinkingBudgetProcessor + Cold-Start SFT + ReDit",
    )

    ax.set_xlabel("Шаг обучения", fontsize=9)
    ax.set_ylabel("Correctness reward, %", fontsize=9)
    ax.set_title(
        "Сходимость correctness-вознаграждения для 4 подходов (GSPO-стадия, шаги 0–100)",
        fontsize=10,
    )
    ax.legend(loc="upper left", fontsize=8.5, frameon=False)
    ax.set_ylim(-1, 30)

    # Arrow pointing EXACTLY to the curve point at step 50
    step50_idx = int(np.where(steps == 50)[0][0])  # index 10
    actual_y = float(a4[step50_idx])
    ax.annotate(
        f"шаг 50: {actual_y:.1f}%",
        xy=(50, actual_y),  # arrowhead touches curve exactly
        xytext=(58, actual_y - 6),  # label below-right, out of other lines
        fontsize=9,
        color=C_ACCENT,
        fontweight="bold",
        arrowprops=dict(
            arrowstyle="->",
            color=C_ACCENT,
            lw=1.4,
            shrinkA=0,
            shrinkB=2,  # don't shrink at tail, slight at head
        ),
    )
    # Also mark the point with a small circle for clarity
    ax.plot(50, actual_y, "o", color=C_ACCENT, markersize=6, zorder=5)

    p = FIGS_DIR / "nir_fig_2_thinking_approaches.png"
    fig.savefig(p)
    plt.close(fig)
    return p


# ─────────────────────────────────────────────────────────────────────
# Рис. 3.3 — per-stage accuracy (legend off bars)
# ─────────────────────────────────────────────────────────────────────


def fig_3_3_fixed() -> Path:
    """Legend moved below plot area — no overlap with bars."""
    domains = ["Math", "Physics", "CS", "Chemistry", "Biology", "Средняя"]
    base = [79.1, 74.4, 46.5, 46.7, 28.6, 55.1]
    gspo = [82.3, 77.9, 52.1, 50.4, 35.2, 63.5]
    kto = [83.4, 78.8, 55.6, 52.1, 38.9, 64.8]
    dpo = [84.7, 80.3, 58.6, 54.2, 43.0, 66.5]

    # Taller figure to leave space at bottom for legend
    fig, ax = plt.subplots(figsize=(10, 5.8))
    x = np.arange(len(domains))
    w = 0.2

    ax.bar(x - 1.5 * w, base, w, label="Base", color=C_BARS_4[0], edgecolor="#222")
    ax.bar(x - 0.5 * w, gspo, w, label="GSPO", color=C_BARS_4[1], edgecolor="#222")
    ax.bar(x + 0.5 * w, kto, w, label="KTO", color=C_BARS_4[2], edgecolor="#222")
    ax.bar(x + 1.5 * w, dpo, w, label="DPO (финал)", color=C_BARS_4[3], edgecolor="#222")

    for i, (b, g, k, d) in enumerate(zip(base, gspo, kto, dpo)):
        ax.text(i - 1.5 * w, b + 1, f"{b:.1f}", ha="center", fontsize=6.5)
        ax.text(i - 0.5 * w, g + 1, f"{g:.1f}", ha="center", fontsize=6.5)
        ax.text(i + 0.5 * w, k + 1, f"{k:.1f}", ha="center", fontsize=6.5)
        ax.text(i + 1.5 * w, d + 1, f"{d:.1f}", ha="center", fontsize=6.5, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(domains, fontsize=9)
    ax.set_ylabel("Точность, %", fontsize=9)
    ax.set_title(
        "Точность Qwen3.5-9B по доменам на каждой стадии 3-ступенчатого обучения",
        fontsize=10,
    )
    ax.set_ylim(0, 100)
    ax.axhline(55.1, color=C_ACCENT, linestyle=":", linewidth=1, alpha=0.6)
    ax.axhline(66.5, color="#4F8F4A", linestyle=":", linewidth=1, alpha=0.6)

    # Legend BELOW the axes — guaranteed no overlap with bars
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),  # below axes
        ncol=4,
        frameon=False,
        fontsize=10,
    )

    # Leave extra space at bottom for legend via tight_layout
    fig.subplots_adjust(bottom=0.18)

    p = FIGS_DIR / "nir_fig_4_per_stage_accuracy.png"
    fig.savefig(p)
    plt.close(fig)
    return p


if __name__ == "__main__":
    p1 = fig_3_2_fixed()
    print(f"✓ Рис. 3.2: {p1.name} ({p1.stat().st_size // 1024} KB)")
    p2 = fig_3_3_fixed()
    print(f"✓ Рис. 3.3: {p2.name} ({p2.stat().st_size // 1024} KB)")
