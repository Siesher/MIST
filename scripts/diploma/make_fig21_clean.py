"""Рис. 2.1 — radical redesign: 2 linear rows + ONE elbow connector.

Overlap-free by construction:
    * Каждый ряд — одна горизонтальная цепочка, боксы на одной y-координате.
    * Все стрелки между боксами одного ряда — ровно горизонтальные.
    * Между рядами — ровно ОДИН прямоугольный elbow из Tutor → SessionAnalyzer.
    * Knowledge Forge — последний бокс в асинхронном ряду (GraphEvolver пишет в него).
    * Подпись стрелки размещается строго в пустом промежутке между рядами.
    * Текст о чтениях — в сноске под асинхронным рядом (не арроу на картинке).

Output: figures/diploma/courseware_fig_2_architecture.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

FIG_PATH = Path("C:/Work/MITS/figures/diploma/courseware_fig_2_architecture.png")
FIG_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Palette ───────────────────────────────────────────────────────────
C_SYNC_BAND = "#EEF4FC"
C_ASYNC_BAND = "#F0F6EC"
C_SYNC_BOX = "#C7DDF2"
C_ASYNC_BOX = "#CFE3C3"
C_IO = "#E8E8E8"
C_STORAGE = "#FAE6A1"
EDGE = "#1F1F1F"
A_SYNC = "#1F4E8C"
A_CONNECTOR = "#7A3F88"
A_ASYNC = "#386F31"


def _box(ax, x, y, w, h, title, subtitle="", bg=C_SYNC_BOX, title_size=13, subtitle_size=10):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.10",
            linewidth=1.3,
            edgecolor=EDGE,
            facecolor=bg,
            zorder=3,
        )
    )
    if subtitle:
        ax.text(
            x + w / 2,
            y + h * 0.65,
            title,
            ha="center",
            va="center",
            fontsize=title_size,
            fontweight="bold",
            zorder=4,
        )
        ax.text(
            x + w / 2,
            y + h * 0.28,
            subtitle,
            ha="center",
            va="center",
            fontsize=subtitle_size,
            color="#555",
            zorder=4,
        )
    else:
        ax.text(
            x + w / 2,
            y + h / 2,
            title,
            ha="center",
            va="center",
            fontsize=title_size,
            fontweight="bold",
            zorder=4,
        )


def _h_arrow(ax, x1, x2, y, color=A_SYNC, lw=1.7):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y),
            (x2, y),
            arrowstyle="-|>",
            mutation_scale=16,
            linewidth=lw,
            color=color,
            zorder=5,
        )
    )


def build() -> None:
    # Compact figure — 11x5 inches so fonts stay legible after docx 6.3" insertion
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 7)
    ax.axis("off")

    # ── Title ──────────────────────────────────────────────────
    ax.text(
        7,
        6.75,
        "Архитектура подсистемы персонализированной навигации",
        ha="center",
        fontsize=14,
        fontweight="bold",
    )
    ax.text(
        7,
        6.45,
        "MITS · функции 016 Knowledge Forge + 017 ToM-Tutor + 018 PathSlime",
        ha="center",
        fontsize=10,
        color="#555",
        style="italic",
    )

    # ── Band 1: Sync ───────────────────────────────────────────
    ax.add_patch(
        FancyBboxPatch(
            (0.3, 4.2),
            13.4,
            1.9,
            boxstyle="round,pad=0.02,rounding_size=0.10",
            linewidth=0.6,
            edgecolor="#BBB",
            facecolor=C_SYNC_BAND,
            alpha=0.55,
            zorder=0,
        )
    )
    ax.text(
        0.5,
        6.02,
        "Синхронный поток (один ход диалога)",
        ha="left",
        va="top",
        fontsize=10,
        color="#555",
        style="italic",
        zorder=1,
    )

    # Sync row — 6 evenly spaced boxes at y=4.55, h=1.2
    sync_y, sync_h = 4.55, 1.2
    sync_w = 1.85
    gap = 0.25
    total_w = 6 * sync_w + 5 * gap
    x0 = (14 - total_w) / 2

    sync_boxes = [
        ("Сообщение", "обучающегося", C_IO),
        ("Navigator", "Dijkstra", C_SYNC_BOX),
        ("PathSlime", "k ∈ {2, 3, 5}", C_SYNC_BOX),
        ("ToM Agent", "belief state", C_SYNC_BOX),
        ("Tutor +\nVerifier", "LLM · SymPy", C_SYNC_BOX),
        ("Ответ", "тьютора", C_IO),
    ]

    centers_sync_x = []
    for i, (title, sub, bg) in enumerate(sync_boxes):
        x = x0 + i * (sync_w + gap)
        _box(ax, x, sync_y, sync_w, sync_h, title, sub, bg=bg, title_size=11.5, subtitle_size=8.5)
        centers_sync_x.append(x + sync_w / 2)

    # Horizontal arrows between sync boxes
    arrow_y = sync_y + sync_h / 2
    for i in range(len(sync_boxes) - 1):
        x1 = x0 + i * (sync_w + gap) + sync_w
        x2 = x0 + (i + 1) * (sync_w + gap)
        _h_arrow(ax, x1, x2, arrow_y, color=A_SYNC)

    # ── Band 2: Async ──────────────────────────────────────────
    ax.add_patch(
        FancyBboxPatch(
            (0.3, 0.4),
            13.4,
            1.9,
            boxstyle="round,pad=0.02,rounding_size=0.10",
            linewidth=0.6,
            edgecolor="#BBB",
            facecolor=C_ASYNC_BAND,
            alpha=0.55,
            zorder=0,
        )
    )
    ax.text(
        0.5,
        2.22,
        "Асинхронный поток (Living Knowledge Graph)",
        ha="left",
        va="top",
        fontsize=10,
        color="#555",
        style="italic",
        zorder=1,
    )

    # Async row — 4 boxes: SessAnal, Queue, Evolver, Forge
    async_y, async_h = 0.7, 1.25
    async_widths = [2.5, 2.3, 2.3, 2.9]  # Forge is slightly wider
    async_gap = 0.3
    total_async = sum(async_widths) + 3 * async_gap
    x0a = (14 - total_async) / 2

    async_boxes = [
        ("SessionAnalyzer", "SessionTrace →\nProposal[]", C_ASYNC_BOX),
        ("ProposalQueue", "merge by key\n+ confidence", C_ASYNC_BOX),
        ("GraphEvolver", "rule + LLM\nverify", C_ASYNC_BOX),
        ("Knowledge Forge", "forge.json · 83 узла", C_STORAGE),
    ]

    async_x_positions = []
    running_x = x0a
    for i, (title, sub, bg) in enumerate(async_boxes):
        w = async_widths[i]
        _box(
            ax, running_x, async_y, w, async_h, title, sub, bg=bg, title_size=11, subtitle_size=8.5
        )
        async_x_positions.append((running_x, w))
        running_x += w + async_gap

    # Horizontal arrows in async row
    arrow_y_a = async_y + async_h / 2
    for i in range(len(async_boxes) - 1):
        x1 = async_x_positions[i][0] + async_x_positions[i][1]
        x2 = async_x_positions[i + 1][0]
        _h_arrow(ax, x1, x2, arrow_y_a, color=A_ASYNC)

    # ── Connector: Tutor → SessionAnalyzer (ONE elbow) ─────────
    tutor_cx = centers_sync_x[4]
    sa_cx = async_x_positions[0][0] + async_x_positions[0][1] / 2

    # Route elbow HIGH (close to sync band) so legend can occupy the exact middle.
    y_elbow = 3.85
    # Vertical 1
    ax.plot([tutor_cx, tutor_cx], [sync_y, y_elbow], color=A_CONNECTOR, linewidth=1.7, zorder=5)
    # Horizontal
    ax.plot([tutor_cx, sa_cx], [y_elbow, y_elbow], color=A_CONNECTOR, linewidth=1.7, zorder=5)
    # Vertical 2 (with arrowhead)
    ax.add_patch(
        FancyArrowPatch(
            (sa_cx, y_elbow),
            (sa_cx, async_y + async_h),
            arrowstyle="-|>",
            mutation_scale=16,
            linewidth=1.7,
            color=A_CONNECTOR,
            zorder=5,
        )
    )

    # Label for connector — right above the elbow horizontal segment
    label_x = (tutor_cx + sa_cx) / 2
    ax.text(
        label_x,
        y_elbow + 0.12,
        "SessionTrace (после хода)",
        ha="center",
        va="bottom",
        fontsize=9.5,
        color=A_CONNECTOR,
        style="italic",
        fontweight="bold",
    )

    # ── Footer note (reads from Forge) ─────────────────────────
    ax.text(
        7,
        0.15,
        "Все агенты синхронного потока читают Knowledge Forge через navigator API "
        "(explore, find_path, diagnose_gap)",
        ha="center",
        fontsize=9,
        color="#666",
        style="italic",
    )

    # ── Legend — строго в середине между двумя band'ами ───────
    # Mid-gap y coordinate: (band_sync_bottom 4.2 + band_async_top 2.3) / 2 = 3.25
    # Positioned HORIZONTALLY centered via data coordinates converted to axes fraction.
    legend_handles = [
        mpatches.Patch(color=A_SYNC, label="Синхронный поток"),
        mpatches.Patch(color=A_CONNECTOR, label="Передача трассы"),
        mpatches.Patch(color=A_ASYNC, label="Асинхронный поток"),
    ]
    # Convert data coords (7, 3.0) -> axes fraction (xlim 0..14 so x_ax=0.5; ylim 0..7 so y_ax≈0.43)
    ax.legend(
        handles=legend_handles,
        loc="center",
        bbox_to_anchor=(7 / 14, 3.0 / 7),
        bbox_transform=ax.transAxes,
        ncol=3,
        frameon=True,
        fontsize=9.5,
        framealpha=0.96,
        edgecolor="#BBB",
        facecolor="white",
    )

    fig.savefig(FIG_PATH, bbox_inches="tight", dpi=220)
    plt.close(fig)


def replace_in_docx() -> None:
    """Replace Рис. 2.1 picture in Курсовом проекте with the freshly built PNG."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.shared import Inches, Pt

    doc_path = Path("C:/Work/MITS/docs/Курсовой_проект_Сухацкий_2026.docx")
    doc = Document(str(doc_path))

    cap_idx = None
    for i, p in enumerate(doc.paragraphs):
        if "Рисунок 2.1" in p.text and "Агентная архитектура" in p.text:
            cap_idx = i
            break
    if cap_idx is None:
        print("  ! Рис. 2.1 caption not found — skipping replacement")
        return

    pic_para = doc.paragraphs[cap_idx - 1]
    print(f"  found Рис. 2.1 at caption[{cap_idx}], picture[{cap_idx - 1}]")

    old_p = pic_para._p
    parent = old_p.getparent()
    idx = list(parent).index(old_p)
    new_p_xml = OxmlElement("w:p")
    parent.insert(idx, new_p_xml)
    parent.remove(old_p)

    from docx.text.paragraph import Paragraph as _P

    new_para = _P(new_p_xml, pic_para._parent)
    new_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = new_para.add_run()
    run.add_picture(str(FIG_PATH), width=Inches(6.3))
    new_para.paragraph_format.space_before = Pt(6)
    new_para.paragraph_format.space_after = Pt(3)

    doc.save(str(doc_path))
    print(f"  ✓ replaced in {doc_path.name}")


if __name__ == "__main__":
    build()
    print(f"✓ Saved PNG: {FIG_PATH}")
    print(f"  size:  {FIG_PATH.stat().st_size // 1024} KB")
    print("\n=== Replacing in Курсовом проекте ===")
    replace_in_docx()
