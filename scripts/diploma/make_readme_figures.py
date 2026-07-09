"""Generate 2 README figures: feature_timeline.png and domain_heatmap.png.

Style matches existing figures/diploma/* (DejaVu Sans, print-friendly palette)
while leaning a bit darker to echo README cyberpunk banner.

Output: figures/readme/feature_timeline.png, figures/readme/domain_heatmap.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

FIGS_DIR = Path(__file__).resolve().parents[2] / "figures" / "readme"
FIGS_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.dpi": 200,
        "axes.facecolor": "#FDFDFE",
    }
)

# Palette — lilac/indigo to match README banner
C_016 = "#818CF8"  # indigo
C_017 = "#A78BFA"  # violet
C_018 = "#C4B5FD"  # lilac
C_ACCENT = "#5B21B6"


def feature_timeline() -> Path:
    """Horizontal timeline: 016 Knowledge Forge -> 017 ToM-Tutor -> 018 PathSlime."""
    fig, ax = plt.subplots(figsize=(11, 2.8))
    ax.set_xlim(0, 12)
    ax.set_ylim(-1.5, 2.2)
    ax.axis("off")

    features = [
        (1.0, C_016, "016 Knowledge Forge", "Living KG\n83 nodes x 88 edges", "мар 2026"),
        (5.0, C_017, "017 ToM-Tutor", "Mental Model\n70%↕95% root-hit", "апр 2026"),
        (9.0, C_018, "018 PathSlime", "Lévy-Gaussian SMA\nk diverse paths", "апр 2026"),
    ]

    for x, color, title, subtitle, date in features:
        ax.add_patch(
            FancyBboxPatch(
                (x - 1.25, -0.7),
                2.5,
                1.4,
                boxstyle="round,pad=0.02,rounding_size=0.18",
                linewidth=1.6,
                edgecolor=C_ACCENT,
                facecolor=color,
                alpha=0.85,
            )
        )
        ax.text(x, 0.5, title, ha="center", va="center", fontsize=11, fontweight="bold", color="white")
        ax.text(x, -0.1, subtitle, ha="center", va="center", fontsize=8.5, color="white", style="italic")
        ax.text(x, -1.15, date, ha="center", va="center", fontsize=8.5, color=C_ACCENT)

    for x_start, x_end in [(2.25, 3.75), (6.25, 7.75)]:
        ax.annotate(
            "",
            xy=(x_end, 0),
            xytext=(x_start, 0),
            arrowprops=dict(arrowstyle="->", color=C_ACCENT, lw=2.0),
        )

    ax.set_title("Feature Timeline — 2026 diploma iteration", fontsize=12, pad=12, color=C_ACCENT)
    out = FIGS_DIR / "feature_timeline.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def domain_heatmap() -> Path:
    """Heatmap domain x stage accuracy, honest — KTO/DPO as NaN/dash."""
    domains = ["Math", "Physics", "Chemistry", "Biology", "CS"]
    stages = ["Base\n(n=143)", "GSPO\n(n=141)", "KTO", "DPO"]

    # Real numbers from evaluation/reports/compare_base_vs_gspo_20260331_115146.json
    data = np.array(
        [
            [1.000, 0.826, np.nan, np.nan],  # Math
            [0.967, 0.900, np.nan, np.nan],  # Physics
            [0.900, 0.966, np.nan, np.nan],  # Chemistry
            [0.800, 0.800, np.nan, np.nan],  # Biology
            [0.862, 0.897, np.nan, np.nan],  # CS
        ]
    )

    fig, ax = plt.subplots(figsize=(8, 4.8))

    cmap = plt.get_cmap("Purples")
    cmap.set_bad(color="#EEEEEE")
    masked = np.ma.masked_invalid(data)
    im = ax.imshow(masked, cmap=cmap, aspect="auto", vmin=0.5, vmax=1.0)

    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels(stages, fontsize=10)
    ax.set_yticks(range(len(domains)))
    ax.set_yticklabels(domains, fontsize=10)

    for i in range(len(domains)):
        for j in range(len(stages)):
            val = data[i, j]
            if np.isnan(val):
                ax.text(j, i, "—", ha="center", va="center", fontsize=13, color="#666")
            else:
                color = "white" if val > 0.85 else "#222"
                ax.text(
                    j,
                    i,
                    f"{val * 100:.1f}%",
                    ha="center",
                    va="center",
                    fontsize=10.5,
                    color=color,
                    fontweight="bold",
                )

    cbar = plt.colorbar(im, ax=ax, fraction=0.035, pad=0.04)
    cbar.set_label("Accuracy", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    ax.set_title(
        "Per-domain accuracy x training stage (n=143/141 for Base/GSPO; KTO & DPO pending)",
        fontsize=11,
        pad=12,
        color=C_ACCENT,
    )
    ax.set_xlabel("Training stage", fontsize=10)

    out = FIGS_DIR / "domain_heatmap.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def main() -> None:
    p1 = feature_timeline()
    print(f"feature_timeline: {p1.name} ({p1.stat().st_size // 1024} KB)")
    p2 = domain_heatmap()
    print(f"domain_heatmap:   {p2.name} ({p2.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
