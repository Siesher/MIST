"""Regenerate Рис. 2.1 (agent architecture) and replace it in Курсовом проекте.

Previous diagram had: overlapping boxes, weird arrow endpoints, tiny labels,
misaligned dashed lines. New version uses a proper layered layout with
FancyBboxPatch + FancyArrowPatch.

Run:
    python -X utf8 scripts/redo_fig21_architecture.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO = Path("C:/Work/MITS")
COURSEWORK = REPO / "docs/Курсовой_проект_Сухацкий_2026.docx"
FIG_PATH = REPO / "figures/diploma/courseware_fig_2_architecture.png"


# Colour palette — muted, print-friendly
COLOR_INPUT = "#E8EEF7"
COLOR_NAV = "#D0E1F2"  # Navigation layer (Navigator, PathSlime)
COLOR_COG = "#FCE8D0"  # Cognitive layer (ToM)
COLOR_EVO = "#DDEBD5"  # Graph evolution layer (Analyzer, Evolver)
COLOR_STORE = "#FFF4C4"  # Knowledge Forge storage
COLOR_OUTPUT = "#EADDE8"
EDGE_COLOR = "#333333"
ARROW_BLUE = "#2B5C9E"
ARROW_GREEN = "#4A8F3F"
ARROW_GRAY = "#888888"


def _box(ax, x, y, w, h, title, subtitle="", bg=COLOR_NAV, font_size=10):
    """Rounded rectangle with centered title + subtitle."""
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        linewidth=1.2,
        edgecolor=EDGE_COLOR,
        facecolor=bg,
    )
    ax.add_patch(box)
    if subtitle:
        ax.text(
            x + w / 2,
            y + h * 0.62,
            title,
            ha="center",
            va="center",
            fontsize=font_size,
            fontweight="bold",
        )
        ax.text(
            x + w / 2,
            y + h * 0.28,
            subtitle,
            ha="center",
            va="center",
            fontsize=font_size - 1.5,
            color="#555",
            style="italic",
        )
    else:
        ax.text(
            x + w / 2,
            y + h / 2,
            title,
            ha="center",
            va="center",
            fontsize=font_size,
            fontweight="bold",
        )


def _arrow(ax, x1, y1, x2, y2, color=ARROW_BLUE, style="-|>", linewidth=1.4, zorder=3):
    arr = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle=style,
        mutation_scale=14,
        linewidth=linewidth,
        color=color,
        zorder=zorder,
    )
    ax.add_patch(arr)


def build_figure() -> Path:
    fig, ax = plt.subplots(figsize=(10.5, 7.5))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis("off")

    # ── Layer backgrounds (subtle) ─────────────────────────────
    layers = [
        (0.3, 8.0, 13.4, 1.5, "Вход / Выход", "#F6F6F6"),
        (0.3, 5.8, 13.4, 1.8, "Уровень 1. Генерация траекторий", "#F1F6FB"),
        (0.3, 3.7, 13.4, 1.8, "Уровень 2. Модель ученика (ToM)", "#FBF3E9"),
        (0.3, 1.6, 13.4, 1.8, "Уровень 3. Эволюция графа знаний", "#F3F7F0"),
        (0.3, 0.1, 13.4, 1.2, "Хранилище", "#FAF5DC"),
    ]
    for x, y, w, h, label, bg in layers:
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.01,rounding_size=0.08",
                linewidth=0.7,
                edgecolor="#C5C5C5",
                facecolor=bg,
                alpha=0.55,
                zorder=0,
            )
        )
        ax.text(
            x + 0.15,
            y + h - 0.2,
            label,
            ha="left",
            va="top",
            fontsize=9,
            color="#666",
            style="italic",
        )

    # ── Input / Output ─────────────────────────────────────────
    _box(
        ax,
        0.6,
        8.25,
        2.6,
        1.0,
        "Сообщение\nобучающегося",
        "+ target concept",
        bg=COLOR_INPUT,
        font_size=10,
    )
    _box(
        ax,
        10.8,
        8.25,
        2.9,
        1.0,
        "Ответ тьютора",
        "Response + LearningPath × k",
        bg=COLOR_OUTPUT,
        font_size=10,
    )

    # ── Layer 1: Navigator + PathSlime ─────────────────────────
    _box(
        ax,
        1.0,
        6.0,
        3.2,
        1.4,
        "Navigator",
        "Dijkstra baseline\ncontracts/knowledge_forge.py",
        bg=COLOR_NAV,
    )
    _box(ax, 5.3, 6.0, 3.5, 1.4, "PathSlime", "Lévy + Gaussian SMA\nk ∈ {2, 3, 5}", bg=COLOR_NAV)
    _box(ax, 9.9, 6.0, 3.5, 1.4, "Tutor / Verifier", "LLM planner + SymPy", bg=COLOR_NAV)

    # ── Layer 2: Mental Model ──────────────────────────────────
    _box(
        ax,
        4.0,
        3.9,
        4.5,
        1.4,
        "MentalModelAgent (ToM)",
        "belief = ⟨gap_concepts,\nmisconceptions, confidence⟩",
        bg=COLOR_COG,
    )

    # ── Layer 3: Session analysis + evolution ──────────────────
    _box(ax, 1.6, 1.8, 3.2, 1.4, "SessionAnalyzer", "SessionTrace →\nGraphProposal[]", bg=COLOR_EVO)
    _box(ax, 6.0, 1.8, 3.1, 1.4, "ProposalQueue", "аккумулятор\nс верификацией", bg=COLOR_EVO)
    _box(
        ax, 10.2, 1.8, 3.0, 1.4, "GraphEvolver", "rule+LLM verify,\nidempotent merge", bg=COLOR_EVO
    )

    # ── Storage layer ──────────────────────────────────────────
    _box(
        ax,
        3.5,
        0.25,
        7.0,
        1.0,
        "Knowledge Forge",
        "forge.json — 83 узла, 88+ рёбер (6 типов узлов × 10 типов рёбер)",
        bg=COLOR_STORE,
    )

    # ── Arrows: Input → Navigator ──────────────────────────────
    _arrow(ax, 1.9, 8.25, 2.6, 7.4, color=ARROW_BLUE)
    # Navigator → PathSlime
    _arrow(ax, 4.2, 6.7, 5.3, 6.7, color=ARROW_BLUE)
    # PathSlime → Tutor
    _arrow(ax, 8.8, 6.7, 9.9, 6.7, color=ARROW_BLUE)
    # Tutor → Output
    _arrow(ax, 12.2, 7.4, 12.2, 8.25, color=ARROW_BLUE)

    # Input → ToM (direct history feed)
    _arrow(ax, 2.0, 8.25, 5.0, 5.3, color=ARROW_GRAY, style="->")

    # ToM → Tutor (belief feeds tutor)
    _arrow(ax, 8.2, 4.6, 10.5, 6.0, color=ARROW_BLUE)

    # Tutor → SessionAnalyzer (async after turn)
    _arrow(ax, 11.0, 6.0, 4.0, 2.8, color=ARROW_GRAY, style="->", linewidth=1.0)
    ax.text(7.5, 3.8, "async: после хода", fontsize=8, color="#888", style="italic", rotation=-10)

    # SessionAnalyzer → ProposalQueue → GraphEvolver
    _arrow(ax, 4.8, 2.5, 6.0, 2.5, color=ARROW_GREEN)
    _arrow(ax, 9.1, 2.5, 10.2, 2.5, color=ARROW_GREEN)

    # Navigator / PathSlime / ToM → Knowledge Forge (reads)
    for x_start in (2.5, 7.0, 6.3):
        _arrow(
            ax,
            x_start,
            6.0 if x_start != 6.3 else 3.9,
            x_start + 0.2,
            1.3,
            color=ARROW_GRAY,
            style="->",
            linewidth=0.9,
        )
    # GraphEvolver → Knowledge Forge (writes)
    _arrow(ax, 11.5, 1.8, 10.0, 1.3, color=ARROW_GREEN)

    # Knowledge Forge → Navigator/PathSlime/ToM (read-back)
    _arrow(ax, 4.8, 1.25, 3.0, 6.0, color=ARROW_GRAY, style="->", linewidth=0.9)

    # ── Legend ────────────────────────────────────────────────
    legend_patches = [
        mpatches.Patch(color=ARROW_BLUE, label="синхронный поток хода"),
        mpatches.Patch(color=ARROW_GREEN, label="обновление графа"),
        mpatches.Patch(color=ARROW_GRAY, label="асинхронные / чтения"),
    ]
    ax.legend(
        handles=legend_patches,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
        ncol=3,
        frameon=False,
        fontsize=9,
    )

    # Title
    ax.text(
        7,
        9.7,
        "Агентная архитектура подсистемы персонализированной навигации",
        ha="center",
        fontsize=12,
        fontweight="bold",
    )
    ax.text(
        7,
        9.35,
        "MITS · функции 016 Knowledge Forge + 017 ToM-Tutor + 018 PathSlime",
        ha="center",
        fontsize=10,
        color="#555",
        style="italic",
    )

    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, bbox_inches="tight", dpi=200)
    plt.close(fig)
    return FIG_PATH


# ─────────────────────────────────────────────────────────────────────
# Replace picture in docx
# ─────────────────────────────────────────────────────────────────────


def replace_figure_in_docx(image_path: Path) -> None:
    print(f"Opening {COURSEWORK}")
    doc = Document(str(COURSEWORK))

    # Find the caption "Рисунок 2.1 — Агентная архитектура..."
    cap_idx = None
    for i, p in enumerate(doc.paragraphs):
        if "Рисунок 2.1" in p.text and "Агентная архитектура" in p.text:
            cap_idx = i
            break
    if cap_idx is None:
        print("  ! caption not found — inserting fresh would need anchor logic")
        return

    # Picture lives in the paragraph BEFORE caption
    pic_para = doc.paragraphs[cap_idx - 1]
    print(f"  found caption at [{cap_idx}], picture at [{cap_idx - 1}]")

    # Clear all runs in picture paragraph then add new picture
    # (simpler: remove old paragraph, create new one in its place)
    old_p = pic_para._p
    parent = old_p.getparent()
    parent_index = list(parent).index(old_p)

    # Build new paragraph with image
    from docx.text.paragraph import Paragraph

    new_p_xml = OxmlElement("w:p")
    parent.insert(parent_index, new_p_xml)
    parent.remove(old_p)

    new_para = Paragraph(new_p_xml, pic_para._parent)
    new_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = new_para.add_run()
    run.add_picture(str(image_path), width=Inches(6.3))
    new_para.paragraph_format.space_before = Pt(6)
    new_para.paragraph_format.space_after = Pt(3)

    doc.save(str(COURSEWORK))
    print(f"  saved: {COURSEWORK}")


def main() -> None:
    print("=== Regenerating Рис. 2.1 ===")
    p = build_figure()
    print(f"  saved: {p} ({p.stat().st_size // 1024} KB)")

    print("\n=== Replacing in Курсовом проекте ===")
    replace_figure_in_docx(p)

    print("\n✓ DONE. Open the docx — Рис. 2.1 now shows layered architecture.")


if __name__ == "__main__":
    main()
