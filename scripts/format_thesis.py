"""Reformat thesis article according to StudVesna2026 competition requirements (Приложение №3).

Source: C:\\Work\\MITS\\docs\\diploma\\Тезисы_StudVesna2026_Сухацкий.docx
Output: C:\\Work\\MITS\\docs\\diploma\\Тезисы_StudVesna2026_Сухацкий_v2.docx

Changes applied:
  - Font: Times New Roman 14pt (was 12pt)
  - Title: centered + bold
  - Author info: expanded (ФИО, affiliation, city, country, email)
  - Abstract added (Аннотация — раскрывающая основное содержание)
  - Keywords added (Ключевые слова)
  - References sorted alphabetically by first author surname
  - In-text citations renumbered: [2] (Shao) → [3], [3] (Muennighoff) → [2]
  - No подстрочные сноски (footnotes); все ссылки затекстовые
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Cm, Pt

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT_PATH = Path(r"C:\Work\MITS\docs\diploma\Тезисы_StudVesna2026_Сухацкий_v2.docx")

FONT_NAME = "Times New Roman"
FONT_SIZE = Pt(14)
LINE_SPACING = 1.15

# ─── Content ───────────────────────────────────────────────────────────

TITLE = (
    "Метод управляемого рассуждения при обучении с подкреплением "
    "языковых моделей для STEM-репетитора"
)

AUTHORS_LINE = "Сухацкий М. О., Корлякова М. О."
AFFILIATION = "Калужский филиал МГТУ им. Н. Э. Баумана, Калуга, Российская Федерация"
EMAILS = "loxterpoi@gmail.com, mkorlyakova@yandex.ru"

ABSTRACT = (
    "Аннотация. Рассматривается задача дообучения языковых моделей с режимом "
    "рассуждения (DeepSeek-R1, Qwen3.5) методом обучения с подкреплением "
    "для применения в интеллектуальной обучающей системе по STEM-дисциплинам. "
    "Показано, что прямое применение алгоритмов GRPO и GSPO к thinking-моделям "
    "приводит к 100% обрезке генерируемых completions из-за неограниченного "
    "рассуждения, что блокирует сходимость алгоритма. Предложен метод "
    "управляемого рассуждения, включающий три компонента: ThinkingBudgetProcessor "
    "для гарантированного завершения фазы рассуждения, Cold-Start SFT для "
    "обеспечения положительных примеров и дитеринг наград (reward dithering) "
    "для устранения нулевой дисперсии. Апробация на модели Qwen3.5-9B в "
    "3-стадийном пайплайне GSPO → KTO → DPO снизила долю обрезок со 100% до "
    "14,3% и повысила общую точность модели на STEM-бенчмарке из 3678 задач "
    "с 55,1% до 66,5%."
)

KEYWORDS = (
    "Ключевые слова: обучение с подкреплением; языковые модели; режим "
    "рассуждения; GSPO; STEM-репетитор; ThinkingBudgetProcessor; "
    "интеллектуальная обучающая система."
)

# Body — citations renumbered to match alphabetically sorted references.
# Original: [1]=Guo, [2]=Shao, [3]=Muennighoff
# Sorted:   [1]=Guo, [2]=Muennighoff, [3]=Shao
# Swap: [2]↔[3]
BODY_PARAGRAPHS = [
    # Originally [1] (Guo) stays [1], [2] (Shao=GRPO) becomes [3]
    "Современные языковые модели (LLM) с режимом рассуждения, такие как "
    "DeepSeek-R1 и Qwen3.5, демонстрируют высокое качество на задачах "
    "многошагового логического вывода благодаря механизму chain-of-thought "
    "(CoT), генерирующему промежуточные шаги в тегах <think>...</think> перед "
    "финальным ответом [1]. Применение таких моделей в интеллектуальных "
    "обучающих системах (Intelligent Tutoring Systems, ITS) по STEM-дисциплинам "
    "требует домен-специфичного дообучения методом Group Relative Policy "
    "Optimization (GRPO) [3] и его расширения — Group Sequence Policy "
    "Optimization (GSPO). Работа посвящена решению проблемы несходимости "
    "GRPO-дообучения моделей с режимом рассуждения.",
    "Критическая проблема состоит в том, что при rollout-генерации модель "
    "входит в неограниченный цикл рассуждений и не формирует закрывающий тег "
    "</think>. В результате 100% сгенерированных completions обрезаются по "
    "максимальной длине, награда равна нулю, и алгоритм GRPO не может "
    "вычислить значимые преимущества (advantages). Экспериментально проверены "
    "четыре подхода: включение режима рассуждения при MAX_COMPLETION=1024 и "
    "4096 токенах даёт 100% обрезку; отключение рассуждения снижает долю "
    "обрезок до 1,6%, однако корректность падает до нуля за 50 шагов, "
    "поскольку модель неспособна решать STEM-задачи без промежуточных "
    "выкладок. Систематический анализ литературы по RL-дообучению LLM (более "
    "20 публикаций) позволил сформировать стратегию управляемого рассуждения.",
    # Originally [3] (Muennighoff=S1) becomes [2]
    "Предложенный метод включает три взаимодополняющих компонента. Первый — "
    "ThinkingBudgetProcessor, процессор логитов (LogitsProcessor) HuggingFace "
    "Transformers, отслеживающий число сгенерированных токенов рассуждения по "
    "каждой последовательности батча: при достижении 90% бюджета (1350 из "
    "1500 токенов) логит токена </think> усиливается на +5,0 (мягкое "
    "подталкивание), а при 100% — все прочие логиты устанавливаются в −∞, "
    "что гарантирует завершение фазы рассуждения. В отличие от подхода S1 [2], "
    "где принудительное завершение применяется на этапе test-time scaling, "
    "ThinkingBudgetProcessor встроен в rollout-генерацию RL и обеспечивает "
    "гарантированное завершение каждой из G completions группы, что необходимо "
    "для корректного вычисления преимуществ (advantages) в GRPO. Второй "
    "компонент — Cold-Start SFT: 200 шагов обучения с учителем на корректных "
    "решениях, отобранных методом rejection sampling из самой базовой модели "
    "с автоматической верификацией (SymPy для математики, ChemPy для химии); "
    "это повышает базовую точность с ≈5% до 15–30% и обеспечивает GRPO "
    "достаточное число положительных примеров. Третий — дитеринг наград "
    "(reward dithering): добавление гауссова шума σ=0,05 к бинарной награде "
    "формирует непрерывный ландшафт, так что группы с одинаковой нулевой "
    "наградой приобретают ненулевую дисперсию и генерируют обучающий сигнал.",
    "Для оценки вклада каждого компонента метода проведена абляция: "
    "исключение ThinkingBudgetProcessor возвращает долю обрезанных completions "
    "к 100%, что подтверждает его роль как ключевого механизма "
    "гарантированного завершения фазы рассуждения. Исключение Cold-Start SFT "
    "снижает базовую корректность с 21,7% до 4,2% к шагу 50 и лишает GRPO "
    "положительных примеров, необходимых для обучения preference-функции. "
    "Исключение дитеринга наград приводит к появлению 47% групп с нулевой "
    "дисперсией и пятикратному замедлению сходимости. Три компонента "
    "действуют ортогонально: их совместное применение обеспечивает "
    "синергетический эффект, при котором итоговая сходимость становится "
    "возможной в условиях, где каждый компонент по отдельности недостаточен.",
    "Апробация проводилась на модели Qwen3.5-9B (GPU NVIDIA RTX PRO 6000, "
    "102 ГБ VRAM) в рамках 3-стадийного пайплайна: стадия 1 — GSPO с тройной "
    "GDPO-нормированной наградой (корректность 0,7; формат 0,15; сократический "
    "стиль 0,15); стадия 2 — Kahneman-Tversky Optimization (KTO) для "
    "согласования (alignment) с сократическим методом обучения; стадия 3 — "
    "Direct Preference Optimization (DPO) для финальной полировки стиля. "
    "Ключевые гиперпараметры GSPO: LoRA r=16, α=32, learning rate 5·10⁻⁷, "
    "размер группы G=8, MAX_COMPLETION=2048 токенов, THINKING_BUDGET=1500 "
    "токенов, importance_sampling_level=sequence.",
    "Оценочный бенчмарк включает 3678 задач по пяти STEM-дисциплинам "
    "(математика, физика, химия, биология, информатика), собран из MGSM "
    "Russian (250), ruMMLU STEM (3210) и авторского набора (218). Верификация "
    "автоматическая: SymPy с символьным упрощением — для математики, ChemPy "
    "для стехиометрии, регулярные выражения с допуском — для физики, exact "
    "match — для биологии и информатики. Базовая точность Qwen3.5-9B "
    "(macro-average) составила 55,1% со значительным разбросом по доменам: "
    "79,1% — математика, 74,4% — физика, 46,7% — химия, 46,5% — информатика, "
    "28,6% — биология.",
    "Предложенный метод снижает долю обрезанных completions со 100% до 14,3%, "
    "а корректность на шаге 50 достигает 21,7%, что обеспечивает стабильный "
    "обучающий сигнал. 3-стадийный пайплайн повышает общую точность Qwen3.5-9B "
    "до 66,5%, то есть на 11,4 процентных пункта относительно базовой модели; "
    "по стадиям прирост составил: GSPO +8,4 п.п. (до 63,5%), KTO +1,3 п.п. "
    "(до 64,8%), DPO +1,7 п.п. (до 66,5%). Наибольший относительный прирост "
    "получен в биологии (+14,4 п.п., с 28,6% до 43,0%) и информатике "
    "(+12,1 п.п., с 46,5% до 58,6%) — доменах с низкой базовой точностью, "
    "куда curriculum learning направляет обучающий сигнал. Стадия KTO "
    "дополнительно повышает долю ответов с сократическими вопросами с 34% до "
    "61%.",
    "Интеграция модели в интеллектуальную обучающую систему (ИОС) реализована "
    "через сократический протокол: вместо прямого ответа модель формирует "
    "наводящие вопросы на основе профиля освоения навыков ученика, "
    "поддерживаемого алгоритмом байесовского трекинга знаний (Bayesian "
    "Knowledge Tracing). Граф навыков охватывает 40+ STEM-компетенций с "
    "автоматической проверкой prerequisite-связей перед предъявлением задачи "
    "и адаптивной маршрутизацией по slime-mold алгоритму, что обеспечивает "
    "индивидуализацию траектории обучения для каждого ученика.",
    "Разработанный метод управляемого рассуждения устраняет три ключевых "
    "барьера сходимости GSPO-дообучения thinking-моделей: неограниченное "
    "рассуждение, недостаток положительных примеров и нулевую дисперсию "
    "награды. Полученная модель демонстрирует стабильный прирост во всех "
    "пяти STEM-доменах без деградации в сильных и пригодна для использования "
    "в интеллектуальной обучающей системе для русскоязычных учеников "
    "7–11 классов.",
]

# References sorted alphabetically by first-author surname (Guo, Muennighoff, Shao)
REFERENCES = [
    "1. Guo D. et al. DeepSeek-R1: Incentivizing Reasoning Capability in LLMs "
    "via Reinforcement Learning [Electronic resource]. URL: "
    "https://arxiv.org/abs/2501.12948 (access date: 20.03.2026).",
    "2. Muennighoff N. et al. s1: Simple Test-Time Scaling [Electronic "
    "resource]. URL: https://arxiv.org/abs/2501.19393 (access date: 20.03.2026).",
    "3. Shao Z. et al. DeepSeekMath: Pushing the Limits of Mathematical "
    "Reasoning in Open Language Models [Electronic resource]. URL: "
    "https://arxiv.org/abs/2402.03300 (access date: 20.03.2026).",
]

# ─── Builders ──────────────────────────────────────────────────────────


def _set_run_font(run, *, bold: bool = False, italic: bool = False) -> None:
    run.font.name = FONT_NAME
    run.font.size = FONT_SIZE
    run.bold = bold
    run.italic = italic
    # East Asia hint — ensures Cyrillic renders correctly with TNR
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts")
    if rFonts is None:
        from docx.oxml.ns import qn

        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.append(rFonts)
    from docx.oxml.ns import qn

    rFonts.set(qn("w:eastAsia"), FONT_NAME)
    rFonts.set(qn("w:hAnsi"), FONT_NAME)
    rFonts.set(qn("w:ascii"), FONT_NAME)
    rFonts.set(qn("w:cs"), FONT_NAME)


def _add_para(
    doc: Document,
    text: str,
    *,
    align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    bold: bool = False,
    italic: bool = False,
    first_line_indent: Cm | None = Cm(1.25),
    space_after: Pt = Pt(6),
):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = LINE_SPACING
    pf.space_after = space_after
    if first_line_indent is not None:
        pf.first_line_indent = first_line_indent

    run = p.add_run(text)
    _set_run_font(run, bold=bold, italic=italic)
    return p


# ─── Build document ────────────────────────────────────────────────────


def main() -> None:
    doc = Document()

    # Page setup — A4 + standard academic margins
    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2)

    # Set default style font (catches any stray runs)
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = FONT_SIZE

    # ─── Header section ───
    _add_para(
        doc,
        "УДК 004.852",
        align=WD_ALIGN_PARAGRAPH.LEFT,
        first_line_indent=None,
        space_after=Pt(12),
    )

    _add_para(
        doc,
        TITLE,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        first_line_indent=None,
        space_after=Pt(6),
    )

    _add_para(
        doc,
        AUTHORS_LINE,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        first_line_indent=None,
        space_after=Pt(2),
    )
    _add_para(
        doc,
        AFFILIATION,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        italic=True,
        first_line_indent=None,
        space_after=Pt(2),
    )
    _add_para(
        doc,
        EMAILS,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        first_line_indent=None,
        space_after=Pt(12),
    )

    # ─── Abstract & keywords ───
    _add_para(doc, ABSTRACT, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    _add_para(doc, KEYWORDS, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=Pt(12))

    # ─── Body ───
    for para in BODY_PARAGRAPHS:
        _add_para(doc, para, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

    # ─── References ───
    _add_para(
        doc,
        "Список литературы",
        align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True,
        first_line_indent=None,
        space_after=Pt(6),
    )
    for ref in REFERENCES:
        _add_para(
            doc,
            ref,
            align=WD_ALIGN_PARAGRAPH.JUSTIFY,
            first_line_indent=None,
            space_after=Pt(2),
        )

    # Save
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_PATH)

    # Verify char count
    full_text = (
        TITLE
        + AUTHORS_LINE
        + AFFILIATION
        + EMAILS
        + ABSTRACT
        + KEYWORDS
        + "".join(BODY_PARAGRAPHS)
        + "Список литературы"
        + "".join(REFERENCES)
    )
    char_count = len(full_text)
    print(f"[OK] Saved to: {OUT_PATH}")
    print(f"[INFO] Total chars (incl. spaces): {char_count} / 10000 limit")
    print(f"[INFO] Font: {FONT_NAME} {int(FONT_SIZE.pt)}pt")
    print(f"[INFO] Line spacing: {LINE_SPACING}")
    print("[INFO] References sorted alphabetically: Guo, Muennighoff, Shao")


if __name__ == "__main__":
    main()
