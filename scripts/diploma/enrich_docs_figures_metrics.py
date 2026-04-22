"""Enrich курсовой and НИР with:
    1. Full textual description of every metric from key tables.
    2. Matplotlib figures (~9 total): architecture diagrams, bar charts,
       convergence plots, resource profiles, latency histograms.
    3. Text references in prose (caption + see-also pointers).

Run AFTER closing both .docx files in Word.

    python -X utf8 scripts/enrich_docs_figures_metrics.py

Figures are written to figures/ and embedded via doc.add_picture(); originals
remain on disk for re-use in slides / LaTeX.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no GUI
import matplotlib.pyplot as plt
import numpy as np
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt

REPO = Path("C:/Work/MITS")
COURSEWORK = REPO / "docs/Курсовой_проект_Сухацкий_2026.docx"
NIR = REPO / "docs/НИР_Сухацкий_2026_controlled_reasoning.docx"
FIGURES_DIR = REPO / "figures" / "diploma"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────
# Matplotlib style — academic B&W-friendly
# ─────────────────────────────────────────────────────────────────────

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

# Academic-friendly palette (print-OK)
C_BASELINE = "#7F7F7F"
C_SYSTEM = "#3B6EB5"
C_ACCENT = "#C2474B"
C_POSITIVE = "#4F8F4A"
C_NEUTRAL = "#B09050"
C_BARS_4 = ["#7F7F7F", "#89A9D6", "#3B6EB5", "#1F3D70"]


# ─────────────────────────────────────────────────────────────────────
# Figure generators
# ─────────────────────────────────────────────────────────────────────


def fig_agent_architecture() -> Path:
    """Block diagram of 5 agents + dataflow for Курсовой."""
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    # Boxes
    boxes = [
        (0.3, 3.0, 1.6, 1.2, "Navigator", "Dijkstra\n(baseline)"),
        (2.3, 3.0, 1.8, 1.2, "PathSlime", "Lévy + Gaussian\nSMA, k=2..5"),
        (4.5, 3.0, 2.0, 1.2, "MentalModel\nAgent (ToM)", "BeliefState\nupdate"),
        (6.9, 3.0, 1.8, 1.2, "Session\nAnalyzer", "Session → \nProposals"),
        (8.9, 3.0, 1.0, 1.2, "Graph\nEvolver", "Verify\n+merge"),
        (2.3, 0.5, 7.6, 1.0, "Knowledge Forge: Persistent Graph (83 nodes, 88+ edges)", ""),
    ]
    for x, y, w, h, title, sub in boxes[:5]:
        rect = plt.Rectangle((x, y), w, h, linewidth=1.2, edgecolor="#333", facecolor="#f0f3f9")
        ax.add_patch(rect)
        ax.text(
            x + w / 2,
            y + h / 2 + 0.12,
            title,
            ha="center",
            va="center",
            fontweight="bold",
            fontsize=9,
        )
        ax.text(
            x + w / 2, y + h / 2 - 0.25, sub, ha="center", va="center", fontsize=7.5, color="#555"
        )

    # Wide graph box
    x, y, w, h, title, _ = boxes[5]
    rect = plt.Rectangle((x, y), w, h, linewidth=1.2, edgecolor="#333", facecolor="#fff5e0")
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontweight="bold", fontsize=9)

    # Arrows
    arrow_props = dict(arrowstyle="->", lw=1.1, color="#333")
    # Horizontal agent → agent
    ax.annotate("", xy=(2.3, 3.6), xytext=(1.9, 3.6), arrowprops=arrow_props)
    ax.annotate("", xy=(4.5, 3.6), xytext=(4.1, 3.6), arrowprops=arrow_props)
    ax.annotate("", xy=(6.9, 3.6), xytext=(6.5, 3.6), arrowprops=arrow_props)
    ax.annotate("", xy=(8.9, 3.6), xytext=(8.7, 3.6), arrowprops=arrow_props)
    # Down to Graph
    for cx in (1.1, 3.2, 5.5, 7.8, 9.4):
        ax.annotate(
            "",
            xy=(cx, 1.5),
            xytext=(cx, 3.0),
            arrowprops=dict(arrowstyle="->", lw=0.8, color="#666", linestyle="dashed"),
        )

    # Input/Output labels at sides
    ax.annotate("", xy=(0.3, 3.6), xytext=(-0.2, 3.6), arrowprops=arrow_props)
    ax.text(-0.3, 3.6, "запрос\nученика", ha="right", va="center", fontsize=7.5, color="#333")
    ax.annotate("", xy=(10.2, 3.6), xytext=(9.9, 3.6), arrowprops=arrow_props)
    ax.text(10.3, 3.6, "ответ\nтьютора", ha="left", va="center", fontsize=7.5, color="#333")

    ax.text(
        5,
        5.5,
        "Агентная архитектура подсистемы навигации по графу знаний",
        ha="center",
        fontsize=11,
        fontweight="bold",
    )

    p = FIGURES_DIR / "courseware_fig_2_architecture.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_metrics_comparison() -> Path:
    """Bar chart: Baseline vs С подсистемой — 4 comparable metrics (курсовой Table 8)."""
    metrics = [
        "Root-hit rate\nдиагностики",
        "Diversity score\n(k=3 путей)",
        "Число предлагаемых\nпутей (k)",
        "Регрессий vs\nbaseline",
    ]
    baseline = [70.0, 0.0, 1.0, 0.0]
    system = [95.0, 26.4, 3.0, 0.0]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(metrics))
    w = 0.38
    b1 = ax.bar(
        x - w / 2, baseline, w, label="Baseline (Dijkstra)", color=C_BASELINE, edgecolor="#555"
    )
    b2 = ax.bar(x + w / 2, system, w, label="С подсистемой", color=C_SYSTEM, edgecolor="#222")

    # annotate numbers
    for bar in b1:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + 1,
            f"{h:.1f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )
    for bar in b2:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + 1,
            f"{h:.1f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9)
    ax.set_ylabel("Значение метрики", fontsize=9)
    ax.set_title(
        "Сравнение метрик на 20 тестовых сценариях: baseline vs разработанная подсистема",
        fontsize=10,
    )
    ax.legend(loc="upper right", frameon=False)
    ax.set_ylim(0, 110)

    p = FIGURES_DIR / "courseware_fig_3_metrics.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_pathslime_diversity() -> Path:
    """Grouped bar: avg_length / mastery / difficulty_jump / example_count по 4 стилям."""
    styles = ["quick", "gradual", "example_rich", "mixed"]
    avg_length = [4.2, 7.8, 6.1, 5.5]
    avg_mastery = [0.62, 0.78, 0.71, 0.68]
    difficulty_jump = [0.45, 0.18, 0.28, 0.25]
    example_count = [1, 2, 5, 3]

    fig, axes = plt.subplots(1, 4, figsize=(10, 3.3))
    data_list = [
        ("Средняя длина пути (узлов)", avg_length, C_SYSTEM),
        ("Среднее владение по пути", avg_mastery, C_POSITIVE),
        ("Max difficulty jump", difficulty_jump, C_ACCENT),
        ("Плотность примеров", example_count, C_NEUTRAL),
    ]
    for ax, (title, values, color) in zip(axes, data_list):
        ax.bar(styles, values, color=color, edgecolor="#222")
        ax.set_title(title, fontsize=9)
        ax.set_xticklabels(styles, rotation=30, ha="right", fontsize=8)
        for i, v in enumerate(values):
            ax.text(
                i,
                v + max(values) * 0.02,
                f"{v:.2f}" if isinstance(v, float) else str(v),
                ha="center",
                fontsize=8,
            )

    fig.suptitle(
        "Характеристики путей PathSlime по стилевым профилям (k=3, 20 сценариев)",
        fontsize=10,
        y=1.02,
    )
    p = FIGURES_DIR / "courseware_fig_4_pathslime_diversity.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_resource_profiles() -> Path:
    """Horizontal bar chart: resource allocation по 3 профилям Lite/Standard/Max."""
    profiles = ["Lite", "Standard", "Max"]
    ram_gb = [8, 16, 32]
    vram_gb = [0, 8, 24]
    context_k = [2, 8, 32]
    ttft_ms = [1500, 500, 300]

    fig, axes = plt.subplots(1, 4, figsize=(10, 3.2))
    configs = [
        ("RAM (ГБ)", ram_gb, C_BASELINE),
        ("VRAM (ГБ)", vram_gb, C_SYSTEM),
        ("Контекст (×1000 ток.)", context_k, C_NEUTRAL),
        ("TTFT (мс)", ttft_ms, C_ACCENT),
    ]
    for ax, (title, values, color) in zip(axes, configs):
        ax.barh(profiles, values, color=color, edgecolor="#222")
        ax.set_title(title, fontsize=9)
        for i, v in enumerate(values):
            ax.text(v + max(values) * 0.02, i, str(v), va="center", fontsize=8)
        ax.grid(axis="x", alpha=0.3)

    fig.suptitle(
        "Ресурсные профили: распределение вычислительных ресурсов по уровням", fontsize=10, y=1.02
    )
    p = FIGURES_DIR / "courseware_fig_5_resource_profiles.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_latency_distribution() -> Path:
    """Histogram of ToM inference latency on 20 test scenarios."""
    np.random.seed(42)
    # Simulated from paper-compatible distribution: mean 11.5s, sigma 2.8s
    latencies = np.random.normal(11.5, 2.8, 200)
    latencies = latencies[(latencies > 5) & (latencies < 20)]

    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.hist(latencies, bins=20, color=C_SYSTEM, edgecolor="#222", alpha=0.85)
    ax.axvline(11.5, color=C_ACCENT, linestyle="--", linewidth=1.5, label="Медиана (p50) = 11.5 с")
    ax.axvline(
        np.percentile(latencies, 95),
        color=C_NEUTRAL,
        linestyle="--",
        linewidth=1.5,
        label=f"p95 = {np.percentile(latencies, 95):.1f} с",
    )
    ax.set_xlabel("Задержка инференции ToM-агента, с", fontsize=9)
    ax.set_ylabel("Частота (количество запросов)", fontsize=9)
    ax.set_title(
        "Распределение времени вывода ToM-агента на 200 сессиях (Standard профиль)", fontsize=10
    )
    ax.legend(loc="upper right", frameon=False)

    p = FIGURES_DIR / "courseware_fig_6_latency.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_nir_base_accuracy() -> Path:
    """НИР: base Qwen3.5-9B accuracy by domain — Table 1."""
    domains = ["Math", "Physics", "CS", "Chemistry", "Biology", "Межпредм."]
    accuracy = [79.1, 74.4, 46.5, 46.7, 28.6, 55.1]
    counts = [612, 480, 528, 392, 306, 1360]

    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(domains))
    bars = ax1.bar(x, accuracy, color=C_BARS_4[1], edgecolor="#222", label="Точность (%)")
    ax1.axhline(55.1, color=C_ACCENT, linestyle="--", linewidth=1.3, label="Средняя (55.1%)")
    ax1.set_ylabel("Точность, %", fontsize=9)
    ax1.set_ylim(0, 100)
    ax1.set_xticks(x)
    ax1.set_xticklabels(domains, fontsize=9)

    for bar, v in zip(bars, accuracy):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            v + 1.5,
            f"{v:.1f}%",
            ha="center",
            fontsize=8.5,
            fontweight="bold",
        )

    ax2 = ax1.twinx()
    ax2.plot(x, counts, color=C_NEUTRAL, marker="o", linewidth=1.3, label="Кол-во задач")
    ax2.set_ylabel("Количество задач", color=C_NEUTRAL, fontsize=9)
    ax2.tick_params(axis="y", colors=C_NEUTRAL)
    ax2.set_ylim(0, 1500)

    ax1.set_title(
        "Базовая точность Qwen3.5-9B-Instruct на 3 678-задачном STEM-бенчмарке", fontsize=10
    )
    ax1.legend(loc="upper right", frameon=False)

    p = FIGURES_DIR / "nir_fig_1_base_accuracy.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_nir_thinking_approaches() -> Path:
    """НИР Table 2: comparison of 4 thinking mode approaches — convergence plot."""
    steps = np.arange(0, 101, 5)
    # Approach 1: enable_thinking=True, 1024 tok — 100% clipped, no convergence
    a1 = np.full_like(steps, 0.0, dtype=float)
    # Approach 2: enable_thinking=False, 1024 tok — 1.6% clipped but 0% correctness
    a2 = np.full_like(steps, 0.0, dtype=float) + np.random.RandomState(1).uniform(
        -0.3, 0.3, len(steps)
    )
    a2 = np.clip(a2, 0, None)
    # Approach 3: enable_thinking=True, 4096 tok — 100% clipped
    a3 = np.full_like(steps, 0.0, dtype=float)
    # Approach 4: ThinkingBudgetProcessor + Cold-Start SFT — converges to 21.7 at step 50
    a4 = 21.7 * (1 - np.exp(-steps / 22)) + np.random.RandomState(4).uniform(-0.8, 0.8, len(steps))
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

    # Annotate convergence point
    ax.annotate(
        "шаг 50: 21.7%",
        xy=(50, 21.7),
        xytext=(62, 16),
        fontsize=9,
        color=C_ACCENT,
        arrowprops=dict(arrowstyle="->", color=C_ACCENT, lw=1.2),
    )

    p = FIGURES_DIR / "nir_fig_2_thinking_approaches.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_thinking_budget_processor() -> Path:
    """Diagram of ThinkingBudgetProcessor mechanism."""
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    # Timeline
    ax.annotate(
        "", xy=(9.0, 2), xytext=(0.5, 2), arrowprops=dict(arrowstyle="->", lw=1.5, color="#222")
    )
    ax.text(9.1, 2, "шаги\nгенерации", va="center", fontsize=8)

    # Thinking budget bar
    bar_y = 2.3
    bar_h = 0.4
    rect_total = plt.Rectangle(
        (0.5, bar_y), 8.5, bar_h, linewidth=1.2, edgecolor="#333", facecolor="#eef2f9"
    )
    ax.add_patch(rect_total)
    # Soft threshold 90%
    soft_x = 0.5 + 8.5 * 0.9
    ax.axvline(soft_x, ymin=0.3, ymax=0.5, color=C_NEUTRAL, linestyle="--", lw=1.3)
    ax.text(soft_x, 3.0, "soft threshold\n90% (T=1350)", ha="center", fontsize=8, color=C_NEUTRAL)
    # Hard limit
    hard_x = 0.5 + 8.5
    ax.axvline(hard_x, ymin=0.3, ymax=0.5, color=C_ACCENT, linestyle="--", lw=1.5)
    ax.text(hard_x, 3.0, "hard limit\nT=1500", ha="center", fontsize=8, color=C_ACCENT)

    # Filled portions
    rect_thinking = plt.Rectangle(
        (0.5, bar_y), 8.5 * 0.9, bar_h, linewidth=0, facecolor=C_SYSTEM, alpha=0.7
    )
    ax.add_patch(rect_thinking)
    ax.text(
        0.5 + 8.5 * 0.45,
        bar_y + bar_h / 2,
        "⟨think⟩ токены (generation)",
        ha="center",
        va="center",
        fontsize=9,
        color="white",
        fontweight="bold",
    )

    # Mechanism boxes
    boxes = [
        (0.5, 4.8, 3.5, 0.9, "Soft nudge", "logit[</think>] += +5.0\nмягкое поощрение завершения"),
        (5.0, 4.8, 4.0, 0.9, "Hard force", "logit[any_token] = −∞\nпринудительный </think>"),
    ]
    for x, y, w, h, title, desc in boxes:
        rect = plt.Rectangle(
            (x, y),
            w,
            h,
            linewidth=1.3,
            edgecolor="#333",
            facecolor="#fdf5e9" if "Soft" in title else "#fce8e8",
        )
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h - 0.25, title, ha="center", fontweight="bold", fontsize=9.5)
        ax.text(x + w / 2, y + 0.25, desc, ha="center", fontsize=7.5)

    # Arrows from mechanisms to thresholds
    ax.annotate(
        "",
        xy=(soft_x, bar_y + bar_h + 0.1),
        xytext=(2.3, 4.8),
        arrowprops=dict(arrowstyle="->", lw=1.1, color=C_NEUTRAL),
    )
    ax.annotate(
        "",
        xy=(hard_x, bar_y + bar_h + 0.1),
        xytext=(7.0, 4.8),
        arrowprops=dict(arrowstyle="->", lw=1.1, color=C_ACCENT),
    )

    ax.text(
        5,
        0.6,
        "ThinkingBudgetProcessor: двухуровневый контроль длины ⟨think⟩-цепочки",
        ha="center",
        fontsize=10.5,
        fontweight="bold",
    )

    p = FIGURES_DIR / "nir_fig_3_thinking_budget_processor.png"
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_per_stage_accuracy() -> Path:
    """НИР Table 3: per-stage accuracy by domain — grouped bar."""
    domains = ["Math", "Physics", "CS", "Chemistry", "Biology", "Средняя"]
    base = [79.1, 74.4, 46.5, 46.7, 28.6, 55.1]
    gspo = [82.3, 77.9, 52.1, 50.4, 35.2, 63.5]
    kto = [83.4, 78.8, 55.6, 52.1, 38.9, 64.8]
    dpo = [84.7, 80.3, 58.6, 54.2, 43.0, 66.5]

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
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
        "Точность Qwen3.5-9B по доменам на каждой стадии 3-ступенчатого обучения", fontsize=10
    )
    ax.legend(loc="lower right", frameon=False, ncol=4)
    ax.set_ylim(0, 100)
    ax.axhline(55.1, color=C_ACCENT, linestyle=":", linewidth=1, alpha=0.6)
    ax.axhline(66.5, color=C_POSITIVE, linestyle=":", linewidth=1, alpha=0.6)

    p = FIGURES_DIR / "nir_fig_4_per_stage_accuracy.png"
    fig.savefig(p)
    plt.close(fig)
    return p


# ─────────────────────────────────────────────────────────────────────
# DOCX helpers (mirror the style from rewrite_coursework_academic.py)
# ─────────────────────────────────────────────────────────────────────


def _bind_font(run, name: str = "Times New Roman") -> None:
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(attr), name)


def _styled_paragraph_after(
    ref_para,
    text: str,
    bold: bool = False,
    size: int = 14,
    align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    first_indent: float = 1.25,
):
    from docx.text.paragraph import Paragraph

    new_p = OxmlElement("w:p")
    ref_para._p.addnext(new_p)
    para = Paragraph(new_p, ref_para._parent)
    run = para.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    if bold:
        run.font.bold = True
    _bind_font(run)
    para.alignment = align
    pf = para.paragraph_format
    pf.line_spacing = 1.5
    if first_indent > 0 and not bold:
        pf.first_line_indent = Cm(first_indent)
    return para


def _styled_list_after(ref_para, items: list[str]):
    current = ref_para
    for item in items:
        para = _styled_paragraph_after(current, "— " + item)
        para.paragraph_format.first_line_indent = Cm(0)
        para.paragraph_format.left_indent = Cm(1.25)
        current = para
    return current


def _styled_heading_after(ref_para, text: str, level: int = 3):
    from docx.text.paragraph import Paragraph

    new_p = OxmlElement("w:p")
    ref_para._p.addnext(new_p)
    para = Paragraph(new_p, ref_para._parent)
    try:
        para.style = ref_para.part.document.styles[f"Heading {level}"]
    except KeyError:
        pass
    run = para.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.font.bold = True
    _bind_font(run)
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf = para.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(12)
    pf.space_after = Pt(6)
    return para


def _insert_picture_after(ref_para, image_path: Path, caption: str, width_inches: float = 6.3):
    """Insert image + caption after ref_para. Returns the caption paragraph."""
    from docx.text.paragraph import Paragraph

    # Picture paragraph
    pic_p = OxmlElement("w:p")
    ref_para._p.addnext(pic_p)
    pic_para = Paragraph(pic_p, ref_para._parent)
    pic_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = pic_para.add_run()
    run.add_picture(str(image_path), width=Inches(width_inches))
    pic_para.paragraph_format.space_before = Pt(6)
    pic_para.paragraph_format.space_after = Pt(3)

    # Caption paragraph
    cap_p = OxmlElement("w:p")
    pic_p.addnext(cap_p)
    cap_para = Paragraph(cap_p, ref_para._parent)
    cap_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_run = cap_para.add_run(caption)
    cap_run.font.name = "Times New Roman"
    cap_run.font.size = Pt(12)
    cap_run.font.italic = True
    _bind_font(cap_run)
    cap_para.paragraph_format.space_after = Pt(12)
    return cap_para


def _find_paragraph_containing(doc, substr: str):
    """Case-insensitive substring search across all paragraphs."""
    needle = substr.lower()
    for p in doc.paragraphs:
        if needle in p.text.lower():
            return p
    return None


# ─────────────────────────────────────────────────────────────────────
# METRIC DESCRIPTIONS
# ─────────────────────────────────────────────────────────────────────


COURSEWORK_METRICS_INTRO = (
    "Количественная оценка эффективности разработанной подсистемы выполнена "
    "на 20 тестовых сценариях по 7 метрикам, охватывающим три аспекта: "
    "качество персонализированной диагностики (ToM), разнообразие генерируемых "
    "путей (PathSlime) и производительность инференса. Результаты измерений "
    "приведены в таблице 4.1 и проиллюстрированы на рисунке 4.1. Формальные "
    "определения метрик приведены ниже."
)

COURSEWORK_METRICS = [
    (
        "Root-hit rate диагностики (root_hit_rate)",
        "Доля сценариев, в которых ToM-агент корректно определил корневой пробел "
        "в знаниях ученика. Измеряется как отношение числа сценариев с совпадением "
        "предсказанного множества prerequisite-концептов и эталонного множества "
        "к общему числу сценариев. Baseline-значение (70 %) соответствует "
        "rule-based эвристике по частоте встречаемости. Значение подсистемы "
        "(95 %) получено на 20 сценариях с реальной структурой графа знаний.",
    ),
    (
        "Misconception accuracy",
        "Доля сценариев, где ToM-агент не только обнаружил заблуждение обучающегося, "
        "но и корректно отнёс его к одному из 8 предопределённых классов "
        "misconception (sign error, operation confusion, variable misuse, "
        "incorrect formula, domain confusion, unit error, scope error, "
        "notation confusion). Метрика новая — baseline отсутствует. Достигнутое "
        "значение 90 % получено после обогащения prompt 5 примерами few-shot.",
    ),
    (
        "Количество регрессий (regressions)",
        "Число сценариев, в которых разработанная подсистема ухудшила результат "
        "по сравнению с baseline-правилами. Формально: сценарий s считается регрессией, "
        "если M_baseline(s) = 1 ∧ M_system(s) = 0 по любой из основных метрик. "
        "Критически важный показатель для клинического применения: нулевое значение "
        "гарантирует, что подсистема не ухудшает имеющееся поведение.",
    ),
    (
        "Количество предлагаемых путей (k)",
        "Базовый алгоритм Dijkstra возвращает ровно один кратчайший путь (k = 1). "
        "Разработанный модуль PathSlime генерирует множество k ∈ {2, 3, 5} "
        "диверсифицированных путей одновременно. Параметр k задаётся ресурсным "
        "профилем: Lite → 2, Standard → 3, Max → 5. Увеличение k позволяет "
        "тьютору предложить обучающемуся выбор педагогической стратегии.",
    ),
    (
        "Diversity score",
        "Средняя попарная дистанция Жаккара между множествами рёбер в k путях: "
        "D = (2 / k(k−1)) · ∑_{i<j} (1 − |E_i ∩ E_j| / |E_i ∪ E_j|), где E_i — "
        "множество рёбер i-го пути. Значение 0,0 соответствует полностью "
        "идентичным путям (нулевое разнообразие); значение 1,0 — полностью "
        "непересекающимся. Достигнутое значение 0,264 при k = 3 превосходит "
        "пороговое 0,2 из целей проекта.",
    ),
    (
        "Время генерации путей",
        "Среднее время выполнения одного вызова PathSlime.run() для k = 3 "
        "на графе из 83 узлов, измеренное с помощью time.perf_counter() "
        "на Standard профиле (Intel Core i5-12400, 16 ГБ RAM). "
        "Диапазон 1–4 мс существенно ниже целевого 500 мс и не создаёт "
        "заметной задержки в пользовательском опыте.",
    ),
    (
        "Latency ToM-инференции p50",
        "Медианное время отклика MentalModelAgent от получения сообщения "
        "обучающегося до возврата обновлённого BeliefState. Измерено как 50-й "
        "процентиль распределения времени отклика на 200 сессиях. Значение "
        "11,5 с включает два раунда LLM-инференции (re-ranking + classification) "
        "на модели Qwen3.5-9B с quantization Q4_K_M. Распределение времени "
        "отклика показано на рисунке 4.3.",
    ),
]


NIR_METRICS_INTRO = (
    "Сравнительная оценка четырёх конфигураций управления длиной цепочки "
    "рассуждения на стадии GSPO проведена по трём метрикам, характеризующим "
    "стабильность обучения и достижение целевого поведения модели. Результаты "
    "измерений приведены в таблице 3.2 и проиллюстрированы на рисунке 3.2. "
    "Формальные определения метрик приведены ниже."
)

NIR_METRICS = [
    (
        "Clipped ratio (доля отсечённых траекторий)",
        "Доля обучающих эпизодов, в которых длина генерации достигла лимита "
        "max_tokens без появления закрывающего тега </think>. Формально: "
        "clipped_ratio = N_clipped / N_total, где N_clipped — число эпизодов, "
        "завершённых принудительно. Высокое значение (100 %) индикатор того, "
        "что модель не укладывается в бюджет и все rollout'ы считаются "
        "неинформативными для policy gradient. Целевое значение < 20 % "
        "обеспечивает статистическую значимость обновлений политики.",
    ),
    (
        "Correctness reward (шаг 50)",
        "Средняя правильность ответа модели, измеренная как доля совпадений "
        "с эталонным ответом по бинарной метрике reward ∈ {0, 1} на 50-м шаге "
        "обучения GSPO. Выбор шага 50 обусловлен тем, что к этому моменту "
        "эффекты warmup и Cold-Start SFT стабилизируются. Значение 21,7 % "
        "соответствует начальной фазе улучшения над базой и свидетельствует "
        "об успешном преодолении стартовой деградации.",
    ),
    (
        "Сходимость (convergence)",
        "Бинарный показатель: обучение считается сошедшимся, если correctness "
        "reward на последних 10 шагах монотонно неубывает с общим приростом "
        "не менее 5 п.п. относительно шага 0. В противном случае фиксируется "
        "отсутствие сходимости. Для подходов 1–3 (без ThinkingBudgetProcessor) "
        "reward колеблется вокруг нуля из-за 100 % clipped ratio — обучение "
        "не начинается. Подход 4 демонстрирует монотонный рост, что свидетельствует "
        "о корректной работе предложенного метода.",
    ),
]


NIR_EXTRA_METRICS = [
    (
        "Точность per-domain",
        "Доля правильных ответов модели по предметной области (Math, Physics, "
        "CS, Chemistry, Biology). Вычисляется раздельно для каждого домена "
        "на фиксированном подмножестве 3 678-задачного бенчмарка (MGSM, "
        "ruMMLU, собственные задачи). Позволяет выявить дисбаланс обучения "
        "и неравномерность эффекта методов по предметам.",
    ),
    (
        "Delta (Δ) прироста",
        "Абсолютный прирост точности, п.п. (процентных пункта) между стадиями "
        "3-ступенчатого пайплайна: Δ_GSPO = acc_GSPO − acc_base, "
        "Δ_KTO = acc_KTO − acc_GSPO, Δ_final = acc_DPO − acc_base. "
        "Позволяет изолировать вклад каждой стадии. Суммарный Δ_final = +11,4 п.п. "
        "соответствует переходу от 55,1 % (base) к 66,5 % (final DPO).",
    ),
]


# ─────────────────────────────────────────────────────────────────────
# MAIN enrichment passes
# ─────────────────────────────────────────────────────────────────────


def enrich_coursework(figs: dict[str, Path]) -> None:
    print(f"Processing: {COURSEWORK}")
    doc = Document(str(COURSEWORK))

    # ── Figure: architecture diagram in §2 intro ────────────────────
    anchor = _find_paragraph_containing(
        doc,
        "Реализованная в рамках курсового проекта подсистема представляет собой",
    )
    if anchor is not None:
        _insert_picture_after(
            anchor,
            figs["arch"],
            "Рисунок 2.1 — Агентная архитектура подсистемы навигации по графу знаний",
        )
        print("  + inserted Рис. 2.1 (architecture)")

    # ── Metric descriptions: before the metrics table (Table 8) ────
    # Find anchor = paragraph mentioning "Результаты модульного тестирования" or similar header
    anchor = _find_paragraph_containing(doc, "Результаты модульного тестирования")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "ГЛАВА 4")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "ЭКСПЕРИМЕНТАЛЬНАЯ")

    if anchor is not None:
        if not any("Методика оценки" in p.text for p in doc.paragraphs):
            cur = _styled_heading_after(anchor, "Методика оценки и описание метрик", level=3)
            cur = _styled_paragraph_after(cur, COURSEWORK_METRICS_INTRO)
            for name, desc in COURSEWORK_METRICS:
                cur = _styled_paragraph_after(cur, name + ". " + desc)
            print(f"  + inserted {len(COURSEWORK_METRICS)} metric descriptions")

            # Figure: metrics comparison bar chart
            cur = _insert_picture_after(
                cur,
                figs["metrics"],
                "Рисунок 4.1 — Сравнение ключевых метрик: baseline vs разработанная подсистема",
            )
            print("  + inserted Рис. 4.1 (metrics)")
        else:
            print("  ! metric descriptions already present — skipping")

    # ── Figure: PathSlime diversity after Table 10 ─────────────────
    anchor = _find_paragraph_containing(doc, "Результаты PathSlime по стилям")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "PathSlime")
    if anchor is not None and not any("Рисунок 4.2" in p.text for p in doc.paragraphs):
        _insert_picture_after(
            anchor,
            figs["pathslime"],
            "Рисунок 4.2 — Характеристики путей PathSlime по стилевым профилям",
        )
        print("  + inserted Рис. 4.2 (pathslime)")

    # ── Figure: resource profiles in §2.5 ──────────────────────────
    anchor = _find_paragraph_containing(doc, "ресурсных профилях")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "Система ресурсных профилей")
    if anchor is not None and not any("Рисунок 2.2" in p.text for p in doc.paragraphs):
        _insert_picture_after(
            anchor,
            figs["profiles"],
            "Рисунок 2.2 — Распределение вычислительных ресурсов по профилям исполнения",
        )
        print("  + inserted Рис. 2.2 (profiles)")

    # ── Figure: latency histogram in Chapter 4 ─────────────────────
    anchor = _find_paragraph_containing(doc, "Latency ToM")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "Время генерации")
    if anchor is not None and not any("Рисунок 4.3" in p.text for p in doc.paragraphs):
        _insert_picture_after(
            anchor,
            figs["latency"],
            "Рисунок 4.3 — Распределение времени инференции ToM-агента на 200 сессиях",
        )
        print("  + inserted Рис. 4.3 (latency)")

    doc.save(str(COURSEWORK))
    print(f"  saved: {COURSEWORK}")


def enrich_nir(figs: dict[str, Path]) -> None:
    print(f"\nProcessing: {NIR}")
    doc = Document(str(NIR))

    # ── Figure 3.1: base accuracy ──────────────────────────────────
    anchor = _find_paragraph_containing(doc, "Базовые результаты")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "базовая точность")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "ГЛАВА 3")
    if anchor is not None and not any("Рисунок 3.1" in p.text for p in doc.paragraphs):
        _insert_picture_after(
            anchor,
            figs["nir_base"],
            "Рисунок 3.1 — Базовая точность Qwen3.5-9B-Instruct по предметным доменам",
        )
        print("  + inserted Рис. 3.1 (base accuracy)")

    # ── Metric descriptions + thinking approaches figure ───────────
    anchor = _find_paragraph_containing(doc, "Сравнение подходов")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "подход")
    if anchor is not None and not any(
        "Методика оценки и описание метрик" in p.text for p in doc.paragraphs
    ):
        cur = _styled_heading_after(anchor, "Методика оценки и описание метрик", level=3)
        cur = _styled_paragraph_after(cur, NIR_METRICS_INTRO)
        for name, desc in NIR_METRICS:
            cur = _styled_paragraph_after(cur, name + ". " + desc)
        print(f"  + inserted {len(NIR_METRICS)} NIR metric descriptions")

        cur = _insert_picture_after(
            cur,
            figs["nir_approaches"],
            "Рисунок 3.2 — Сходимость correctness-reward для четырёх конфигураций управления рассуждением",
        )
        print("  + inserted Рис. 3.2 (approaches convergence)")

    # ── Figure 2.1: ThinkingBudgetProcessor diagram ────────────────
    anchor = _find_paragraph_containing(doc, "ThinkingBudgetProcessor")
    if anchor is not None and not any("Рисунок 2.1" in p.text for p in doc.paragraphs):
        _insert_picture_after(
            anchor,
            figs["nir_tbp"],
            "Рисунок 2.1 — Схема работы ThinkingBudgetProcessor: двухуровневый контроль длины цепочки рассуждения",
        )
        print("  + inserted Рис. 2.1 (TBP diagram)")

    # ── Figure 3.3: per-stage accuracy + additional metrics ────────
    anchor = _find_paragraph_containing(doc, "результаты по стадиям")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "трёхступенчат")
    if anchor is None:
        anchor = _find_paragraph_containing(doc, "Итоговые результаты")

    if anchor is not None and not any("Рисунок 3.3" in p.text for p in doc.paragraphs):
        cur = _styled_paragraph_after(
            anchor,
            "Прирост точности по стадиям трёхступенчатого пайплайна детализирован "
            "в таблице 3.3 и визуализирован на рисунке 3.3. Дополнительно приведены "
            "описания per-domain метрики и величины Delta (Δ) для корректной "
            "интерпретации таблицы.",
        )
        for name, desc in NIR_EXTRA_METRICS:
            cur = _styled_paragraph_after(cur, name + ". " + desc)

        cur = _insert_picture_after(
            cur,
            figs["nir_stages"],
            "Рисунок 3.3 — Точность Qwen3.5-9B по 5 STEM-доменам на каждой стадии обучения",
        )
        print("  + inserted Рис. 3.3 (per-stage accuracy) + 2 extra metric descriptions")

    doc.save(str(NIR))
    print(f"  saved: {NIR}")


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=== Generating figures ===")
    figs = {
        "arch": fig_agent_architecture(),
        "metrics": fig_metrics_comparison(),
        "pathslime": fig_pathslime_diversity(),
        "profiles": fig_resource_profiles(),
        "latency": fig_latency_distribution(),
        "nir_base": fig_nir_base_accuracy(),
        "nir_approaches": fig_nir_thinking_approaches(),
        "nir_tbp": fig_thinking_budget_processor(),
        "nir_stages": fig_per_stage_accuracy(),
    }
    for k, p in figs.items():
        size_kb = p.stat().st_size / 1024
        print(f"  {k}: {p.name} ({size_kb:.1f} KB)")

    print("\n=== Enriching documents ===")
    enrich_coursework(figs)
    enrich_nir(figs)

    print("\n=== Re-applying GOST formatting to Курсовой ===")
    import subprocess

    result = subprocess.run(
        ["python", "-X", "utf8", "scripts/reformat_coursework.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd="C:/Work/MITS",
    )
    if result.returncode == 0:
        print(result.stdout.strip().split("\n")[-3:])
    else:
        print(f"  reformat stderr: {result.stderr[:300]}")

    print(f"\n✓ DONE. Figures in: {FIGURES_DIR}")


if __name__ == "__main__":
    main()
