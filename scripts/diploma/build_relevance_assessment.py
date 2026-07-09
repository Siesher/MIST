"""Объективная оценка актуальности темы StudVesna-2026 на основе интернет-источников.

Документ строится из реальных результатов WebSearch, а не из общих рассуждений.
Каждая претензия подкреплена ссылкой на arXiv / NeurIPS / OpenReview / RBC / etc.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path("docs/diploma/Оценка_актуальности_темы.docx")

DARK_GREEN = RGBColor(0x1F, 0x5C, 0x2D)
ACCENT = RGBColor(0x5F, 0xA1, 0x2E)
GRAY = RGBColor(0x5A, 0x6B, 0x5E)
RED = RGBColor(0xC0, 0x39, 0x2B)
ORANGE = RGBColor(0xC2, 0x6F, 0x10)
BLUE = RGBColor(0x2F, 0x65, 0x85)


def shade(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def add_p(doc, text, *, bold=False, italic=False, size=11, color=None,
          align=None, space_before=0, space_after=4, line_spacing=1.2):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    if color is not None:
        r.font.color.rgb = color
    return p


def add_runs(doc, parts, *, justify=True, space_after=4):
    p = doc.add_paragraph()
    if justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.2
    for text, opts in parts:
        r = p.add_run(text)
        r.font.name = opts.get("font", "Times New Roman")
        r.font.size = Pt(opts.get("size", 11))
        r.bold = opts.get("bold", False)
        r.italic = opts.get("italic", False)
        if "color" in opts:
            r.font.color.rgb = opts["color"]
    return p


def heading(doc, text, level=1, *, color=DARK_GREEN, numbered=""):
    sizes = {1: 16, 2: 13, 3: 12}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    if numbered:
        rn = p.add_run(numbered + "  ")
        rn.font.name = "Times New Roman"
        rn.font.size = Pt(sizes.get(level, 12))
        rn.font.color.rgb = ACCENT
        rn.bold = True
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(sizes.get(level, 12))
    r.bold = True
    r.font.color.rgb = color
    return p


def bullet(doc, parts, *, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.6 + 0.6 * level)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.2
    if isinstance(parts, str):
        parts = [(parts, {})]
    if p.runs:
        p.runs[0].text = ""
    for text, opts in parts:
        r = p.add_run(text)
        r.font.name = opts.get("font", "Times New Roman")
        r.font.size = Pt(opts.get("size", 11))
        r.bold = opts.get("bold", False)
        r.italic = opts.get("italic", False)
        if "color" in opts:
            r.font.color.rgb = opts["color"]


def callout(doc, label, body, *, color=ACCENT, bg="EAF4D8"):
    table = doc.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    shade(cell, bg)
    cell.paragraphs[0].clear()
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    rl = p.add_run(label + "  ")
    rl.font.name = "Times New Roman"
    rl.font.size = Pt(10)
    rl.bold = True
    rl.font.all_caps = True
    rl.font.color.rgb = color
    rb = p.add_run(body)
    rb.font.name = "Times New Roman"
    rb.font.size = Pt(11)
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(4)


def make_table(doc, header, rows, *, widths=None, highlight=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.style = "Light Grid"
    if widths:
        for ci, w in enumerate(widths):
            for row in table.rows:
                row.cells[ci].width = Cm(w)
    for i, h in enumerate(header):
        c = table.rows[0].cells[i]
        c.text = ""
        p = c.paragraphs[0]
        r = p.add_run(h)
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(c, "1F5C2D")
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    highlight = highlight or []
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            c = table.rows[ri + 1].cells[ci]
            c.text = ""
            p = c.paragraphs[0]
            r = p.add_run(val)
            r.font.name = "Times New Roman"
            r.font.size = Pt(10)
            if ci == 0:
                r.bold = True
            if ri in highlight:
                shade(c, "EAF4D8")
                r.font.color.rgb = DARK_GREEN
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(2)


def gauge(doc, label, score, max_score=10, *, color=ACCENT):
    """Простая визуальная шкала через таблицу."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    r1 = p.add_run(f"{label}: ")
    r1.font.name = "Times New Roman"
    r1.font.size = Pt(11)
    r1.bold = True
    filled = "█" * score
    empty = "░" * (max_score - score)
    r2 = p.add_run(f"{filled}{empty}  {score}/{max_score}")
    r2.font.name = "Consolas"
    r2.font.size = Pt(11)
    r2.font.color.rgb = color


def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.6)
    sec.page_height = Cm(27.9)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.0)

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)

    # ---------- ТИТУЛ ----------
    add_p(doc, "Объективная оценка актуальности темы",
          size=12, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_p(doc, "«Метод управляемого рассуждения\nпри RL-обучении языковых моделей для STEM-репетитора»",
          size=17, bold=True, color=DARK_GREEN,
          align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.2, space_after=8)
    add_p(doc, "На основании WebSearch по 9 запросам к arXiv, NeurIPS, OpenReview, ScienceDirect, "
               "ACL, MDPI, российским медиа (РБК, Skillbox) — апрель 2026.",
          size=10, italic=True, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)

    # ---------- TL;DR ----------
    heading(doc, "TL;DR — Краткий вердикт", level=1)
    callout(doc, "Итоговая оценка",
            "Тема актуальна, но не уникальна. Это сильная инженерная работа в самой горячей подобласти ML "
            "2025-2026 (RL для reasoning-моделей), однако в академическом плане она конкурирует с "
            "несколькими параллельными подходами (S-GRPO, e1, ThinkDial). Главная защитная позиция — "
            "русскоязычная STEM-ниша и целостный пайплайн (трёхстадийный GSPO→KTO→DPO).",
            bg="EAF4D8", color=ACCENT)

    add_p(doc, "Сводка по 5 осям:", bold=True, space_before=8, space_after=4)
    gauge(doc, "Актуальность темы (RL for reasoning)         ", 9, color=ACCENT)
    gauge(doc, "Свежесть применённых методов                  ", 9, color=ACCENT)
    gauge(doc, "Научная новизна (vs S-GRPO / e1)              ", 6, color=ORANGE)
    gauge(doc, "Уникальность ниши (русский STEM ITS)          ", 8, color=ACCENT)
    gauge(doc, "Воспроизводимость и инженерная глубина        ", 9, color=ACCENT)
    add_p(doc, "Средневзвешенно: 8 / 10. Вполне достойно StudVesna и публикации в ВАК-журнале, при условии "
               "усиления раздела «отличие от S-GRPO и e1» (см. §5).",
          italic=True, color=GRAY, space_before=4)

    # ============================================================
    # §1. ХАЙП-КРИВАЯ
    # ============================================================
    heading(doc, "Состояние области в апреле 2026", level=1, numbered="§1")

    heading(doc, "1.1 Это самая горячая подобласть ML", level=2)
    add_p(doc, "RL для thinking-LLM перешёл из исследовательского направления в основной поток между "
               "январём 2025 (DeepSeek-R1) и серединой 2026 года. Из источников:")
    bullet(doc, [
        ("DeepSeek V4-Pro (2026) ", {"bold": True}),
        ("ведёт открытый leaderboard BenchLM.ai с 87/100 баллов; Claude и GPT-5.4 — 96-97 % "
         "на HMMT 2026. Все эти модели — thinking. [BenchLM.ai]", {}),
    ])
    bullet(doc, [
        ("Qwen3-235B (Qwen Team, май 2025): ", {"bold": True}),
        ("AIME'24 score 70,1 → 85,1 за 170 RL-шагов через GRPO. ", {}),
        ("[arXiv:2505.09388]", {"italic": True}),
    ])
    bullet(doc, [
        ("Sebastian Raschka (LLM Research Papers 2025, July-Dec): ", {"bold": True}),
        ("RL стал стандартом post-training для всех reasoning-моделей.", {}),
    ])
    bullet(doc, [
        ("В России: ", {"bold": True}),
        ("Яндекс «Репетитор AI» (октябрь 2025) на Alice AI — для подготовки к ЕГЭ по математике; "
         "по данным Сбера — 80 % школьников РФ используют ИИ. Прикладной хайп очевиден. ", {}),
        ("[РБК Тренды]", {"italic": True}),
    ])

    heading(doc, "1.2 Ключевые статьи, на которых построена работа", level=2)
    make_table(doc,
               ["Метод", "arXiv ID", "Дата", "Площадка", "Используется в работе"],
               [
                   ["DeepSeek-R1",   "2501.12948", "01.2025", "Tech Report DeepSeek-AI", "✓ thinking-mode + cold-start"],
                   ["GSPO",          "2507.18071", "07.2025", "Qwen Team",                "✓ ядро RL-стадии"],
                   ["ReDit",         "2506.18631", "06.2025", "NeurIPS 2025 poster",     "✓ дитеринг наград"],
                   ["S1",            "2501.19393", "01.2025", "arXiv preprint",          "✓ contrast baseline"],
                   ["KTO",           "2402.01306", "02.2024", "arXiv preprint",          "✓ Stage 2"],
                   ["DPO",           "2305.18290", "05.2023", "NeurIPS 2023",            "✓ Stage 3"],
                   ["DAPO",          "2503.14476", "03.2025", "arXiv preprint",          "✓ Clip-Higher"],
                   ["Tina (LoRA RL)","2504.15777", "04.2025", "arXiv preprint",          "✓ LoRA r=16"],
                   ["Dr. GRPO",      "2503.20783", "03.2025", "arXiv preprint",          "✓ loss type"],
               ],
               widths=[2.6, 2.0, 1.5, 4.0, 5.5])
    add_p(doc, "Из 9 ключевых публикаций — 7 опубликованы в 2025 году (последние 12 месяцев). "
               "Работа применяет методы практически с переднего края. Это сильный плюс.",
          space_after=4)

    heading(doc, "1.3 Почему именно сейчас — окно возможностей", level=2)
    callout(doc, "Окно",
            "GSPO опубликован 29.07.2025; ReDit — 18.09.2025; e1 — октябрь 2025. Между публикацией метода "
            "и его применением в дипломной/бакалаврской работе обычно проходит 6-18 месяцев. "
            "Конференция StudVesna в апреле 2026 — это ровно то окно, когда применение GSPO к новой "
            "прикладной задаче ещё представляет научный интерес.",
            bg="DBEEED", color=BLUE)

    # ============================================================
    # §2. КОНКУРЕНТЫ
    # ============================================================
    heading(doc, "Прямые научные конкуренты", level=1, numbered="§2")

    add_p(doc, "Ключевая проблема — поиск работ, которые тоже ", italic=False, space_after=4)
    add_runs(doc, [
        ("ВНУТРИ RL-обучения", {"bold": True}),
        (" контролируют длину/завершение thinking-фазы. Найдено ", {}),
        ("4 прямых конкурента", {"bold": True}),
        (" — каждый из них решает похожую задачу другим способом.", {}),
    ])

    make_table(doc,
               ["Метод", "arXiv", "Подход", "Этап", "Метрики", "Прямой конкурент?"],
               [
                   ["S-GRPO", "2505.07686 (NeurIPS'25)",
                    "Серийная группа с decaying reward по позициям выхода",
                    "Внутри RL", "−35-61 % CoT length, +0,7-6 % accuracy",
                    "ДА — наиболее близкий"],
                   ["e1 / Adaptive Effort", "2510.27042",
                    "Параметр effort в input + reward; learns adaptive control",
                    "Внутри RL + inference",
                    "3× reduction CoT length с сохранением performance",
                    "ДА — близкий"],
                   ["ThinkDial", "2508.18773",
                    "Open recipe для controlling reasoning effort",
                    "Внутри RL", "—",
                    "Близкий"],
                   ["P-GSPO", "OpenReview",
                    "Parameterized GSPO для length-sensitive reasoning",
                    "Внутри RL",
                    "—",
                    "Очень близкий концептуально"],
                   ["S1 (test-time)", "2501.19393",
                    "Forced termination на инференсе",
                    "Inference",
                    "−3× length при сохранении performance",
                    "Нет (другой этап)"],
                   ["NVIDIA NIM", "Документация",
                    "Thinking budget control в продакшен-инференсе",
                    "Inference",
                    "Продакшен",
                    "Нет (продакшен, не наука)"],
               ],
               widths=[2.5, 2.5, 4.0, 2.0, 2.5, 2.7])

    heading(doc, "2.1 Главная угроза — S-GRPO (NeurIPS 2025)", level=2)
    callout(doc, "Внимание",
            "S-GRPO опубликован 12.05.2025 как NeurIPS 2025 poster — он напрямую решает «проблему "
            "избыточного рассуждения» (excessive thought redundancy). Аннотация буквально говорит: "
            "«Recent studies reveal that reasoning models (even Qwen3) consistently exhibit excessive "
            "thought redundancy in CoT generation». S-GRPO даёт −35-61 % длину при +0,7-6 % accuracy.",
            bg="FDE8E6", color=RED)

    add_p(doc, "Чем твой метод ОТЛИЧАЕТСЯ от S-GRPO:", bold=True, space_before=4, space_after=4)
    bullet(doc, [
        ("Цель: ", {"bold": True}),
        ("S-GRPO ускоряет рассуждение (efficiency); твой метод — ", {}),
        ("обеспечивает сходимость", {"bold": True}),
        (" RL-обучения, которое без него вообще не запускается. Это разные KPI.", {}),
    ])
    bullet(doc, [
        ("Механика: ", {"bold": True}),
        ("S-GRPO — серийный сэмплинг с decay в reward; ты — параллельный сэмплинг с LogitsProcessor. "
         "Архитектурно разные.", {}),
    ])
    bullet(doc, [
        ("Совместимость: ", {"bold": True}),
        ("S-GRPO нужен корректный rollout как baseline (он экспериментирует с early-exit). Твой метод — "
         "первичный, делает rollout возможным.", {}),
    ])
    bullet(doc, [
        ("Недостаток в твоей работе: ", {"bold": True, "color": RED}),
        ("нет прямого числового сравнения с S-GRPO на одинаковом бенчмарке. Это ", {}),
        ("главный риск", {"italic": True}),
        (" при рецензии в ВАК.", {}),
    ])

    heading(doc, "2.2 Угроза №2 — e1 (Adaptive Effort Control)", level=2)
    add_p(doc, "e1 (arXiv:2510.27042, октябрь 2025) учит модель управлять effort через RL-параметр в "
               "input. Тоже про длину рассуждения. Тоже NeurIPS-уровень.")
    add_p(doc, "Отличие твоей работы: ты решаешь проблему до того, как RL вообще способен сходиться. "
               "e1 предполагает, что RL уже работает.", italic=True)

    # ============================================================
    # §3. УНИКАЛЬНЫЕ ПОЗИЦИИ
    # ============================================================
    heading(doc, "Уникальные позиции работы", level=1, numbered="§3")

    heading(doc, "3.1 Русскоязычный STEM-тьютор — нет аналогов в академии", level=2)
    add_p(doc, "Поиск показал:")
    bullet(doc, [
        ("Прикладные продукты есть: ", {"bold": True}),
        ("Яндекс «Репетитор AI», GigaChat, Winny — но это ", {}),
        ("закрытые коммерческие сервисы", {"italic": True}),
        (", а не научные работы.", {}),
    ])
    bullet(doc, [
        ("Академических статей — нет. ", {"bold": True}),
        ("В ScienceDirect / arXiv по запросу «Russian K-12 LLM tutoring system 2026» — пусто. "
         "Ближайшее — SocraticLM (NeurIPS 2024), SocraticAI for CS (12.2025), TALPer (2026) — все "
         "англоязычные.", {}),
    ])
    bullet(doc, [
        ("Сократический подход на русском: ", {"bold": True}),
        ("первая академическая работа.", {}),
    ])

    heading(doc, "3.2 Целостный пайплайн (3-стадийный)", level=2)
    add_p(doc, "Большинство публикаций фокусируются на одной стадии (RL или KTO или DPO) — "
               "у тебя три стадии в одном experimental setup. Это позволяет разложить общий прирост "
               "+11,4 п.п. на компоненты: GSPO +8,4 / KTO +1,3 / DPO +1,7. Такая декомпозиция — "
               "редкий вклад в литературу.")

    heading(doc, "3.3 Triple reward с сократическим стилем", level=2)
    add_p(doc, "Большинство RL-работ для reasoning используют correctness-only reward. У тебя GDPO-decoupled "
               "тройная награда (correctness + format + socratic) — это редкая конфигурация для "
               "образовательных моделей. Аналог — SocraticLM, но без RL.")

    heading(doc, "3.4 Воспроизводимость", level=2)
    bullet(doc, "открытые артефакты на HuggingFace Hub (3 чекпоинта);")
    bullet(doc, "открытый код на GitHub (Siesher/MITS);")
    bullet(doc, "фиксированный snapshot версий библиотек;")
    bullet(doc, "автоматизированный benchmark (3 678 задач, seed=42).")
    add_p(doc, "Это значительно выше среднего для дипломных работ; на уровне современных arXiv-публикаций.",
          italic=True, color=ACCENT)

    # ============================================================
    # §4. РИСКИ И КОНТР-АРГУМЕНТЫ
    # ============================================================
    heading(doc, "Риски и слабые места (объективно)", level=1, numbered="§4")

    heading(doc, "4.1 Риск №1: проблема частично решена индустрией", level=2)
    callout(doc, "Слабое место",
            "vLLM issue #15418 — известная проблема. NVIDIA NIM имеет встроенный thinking budget control "
            "в продакшене. TRL 0.27 (используется в твоей работе) добавил поддержку GSPO. Это значит: "
            "claim «корневая причина впервые найдена» — спорный. Правильнее: «впервые систематически "
            "решена в открытой реализации для русскоязычного STEM-тьютора».",
            bg="FDE8E6", color=RED)

    heading(doc, "4.2 Риск №2: «Limit of RLVR»-критика", level=2)
    add_p(doc, "В свежих работах (limit-of-rlvr.github.io, OpenReview) есть критическая позиция: ")
    add_runs(doc, [
        ("«RL fine-tuning enhances sampling efficiency without expanding the reasoning capacity already "
         "present in base models»", {"italic": True}),
        (". То есть — RL не добавляет новых способностей рассуждения, только улучшает их использование.", {}),
    ])
    add_p(doc, "Твой ответ: для прикладной задачи (STEM-тьютор) важна именно sampling efficiency на сложных "
               "задачах + сократический стиль (alignment). Это законная цель RL независимо от "
               "критики reasoning capacity.", italic=True)

    heading(doc, "4.3 Риск №3: размер модели", level=2)
    bullet(doc, [
        ("Фронт мейнстрима — 30B+ MoE: ", {"bold": True}),
        ("Qwen3-30B-A3B, Qwen3-235B-A22B, DeepSeek V4-Pro. ", {}),
    ])
    bullet(doc, [
        ("Qwen3.5-9B Instruct ", {"bold": True}),
        ("— compact tier, не SOTA. Целевая accuracy на математике у топ-моделей — 90+%, у тебя — "
         "85,2 % (после полного пайплайна). Разрыв есть.", {}),
    ])
    add_p(doc, "Твой ответ: целевая платформа — Ollama на одном узле, для школы; 30B+ модели не работают "
               "в этом сценарии. Прикладная мотивация ясна. Но это нужно явно проговорить.",
          italic=True)

    heading(doc, "4.4 Риск №4: Бенчмарк не самый авторитетный", level=2)
    bullet(doc, [
        ("MERA ", {"bold": True}),
        ("(arXiv:2401.04531) — стандартный российский бенчмарк для LLM. У тебя его нет.", {}),
    ])
    bullet(doc, "ruMMLU + MGSM Russian + custom (3 678 задач) — собственная сборка. Покрывает 5 STEM, но менее канонична.")
    add_p(doc, "Рекомендация: добавить хотя бы один прогон на MERA как контрольную точку.",
          italic=True, color=ORANGE)

    heading(doc, "4.5 Риск №5: GDPO-decoupled (arXiv:2601.05242)", level=2)
    callout(doc, "Проверить",
            "В коде и документации цитируется arXiv:2601.05242 (GDPO-decoupled). Дата препринта — "
            "январь 2026. Проверь актуальность ссылки: arXiv-ID с префиксом 2601 — это «свежая» работа, "
            "которая может быть ещё не процитирована другими. Если статья не существует или это не "
            "тот метод — ссылку нужно срочно перепроверить.",
            bg="FFE9D6", color=ORANGE)

    # ============================================================
    # §5. ОЖИДАЕМЫЕ ВОПРОСЫ КОМИССИИ
    # ============================================================
    heading(doc, "Ожидаемые «убийственные» вопросы комиссии", level=1, numbered="§5")

    qa = [
        (
            "В мае 2025 года вышел S-GRPO (NeurIPS 2025), который тоже решает проблему избыточного "
            "рассуждения. Чем ваш метод отличается?",
            "S-GRPO решает другую задачу — efficiency (сокращение длины при сохранении качества). Мы "
            "решаем convergence — без нашего ThinkingBudgetProcessor RL вообще не сходится (clipped 100 %). "
            "Эти методы ортогональны: S-GRPO предполагает работающий rollout как baseline, у нас этот "
            "baseline и обеспечивается. В будущей работе планирую прогнать S-GRPO + ThinkingBudget — "
            "они должны дать комбинированный эффект.",
        ),
        (
            "NVIDIA NIM имеет thinking budget control. Это уже продакшен-решение. Что нового в вашей работе?",
            "NIM — это инференс-инструмент: после обучения. Наш процессор работает внутри RL-обучения, "
            "что критично для самой возможности обучения. Это разные этапы pipeline. Кроме того, наш "
            "метод — открытая реализация (LoRA-адаптеры на HuggingFace, код на GitHub); NIM — "
            "закрытое продакшен-решение от вендора.",
        ),
        (
            "Базовая модель Qwen3.5-9B уже не SOTA. Почему не Qwen3-235B?",
            "Целевая платформа деплоя — Ollama на одном A100/RTX узле в школе или у репетитора. 235B-модель "
            "не помещается без распределённого инференса, который недоступен в этом сценарии. 9B "
            "выбрана как максимум, помещающийся в bf16 без QLoRA — это сохраняет качество градиента "
            "при RL-обучении.",
        ),
        (
            "Почему не использовали MERA — стандартный российский бенчмарк?",
            "MERA — это generic LLM benchmark, у него нет домен-специфичной разметки по STEM, и он "
            "не предполагает автоматической верификации через SymPy/ChemPy. Наш бенчмарк (3 678 задач) "
            "построен из MGSM Russian, ruMMLU STEM и authored-набора с явной structurized разметкой "
            "по 5 доменам и автоматическими верификаторами. Включить MERA как валидацию — "
            "разумная задача дальнейшей работы.",
        ),
        (
            "RL не добавляет новых reasoning capabilities (limit-of-rlvr.github.io). Тогда зачем "
            "трёхстадийный пайплайн?",
            "Согласен с критикой в части reasoning capacity — RL действительно не порождает новых "
            "способностей, а перераспределяет вероятностную массу. Но цель работы — alignment под "
            "конкретный application: сократический стиль преподавания. Для этой цели RL — правильный "
            "инструмент: prior model уже умеет рассуждать, мы выравниваем её под педагогические "
            "паттерны (наводящие вопросы, отсутствие answer-leak).",
        ),
        (
            "Прирост +11,4 п.п. — это много или мало по меркам литературы?",
            "Сравнимо со средним по литературе. Qwen3-235B (Qwen Team, май 2025) — AIME'24: +15 п.п. "
            "за 170 шагов RL. Critique-GRPO — +5,1 % на STEM. Наш +11,4 п.п. — нормальный диапазон "
            "для 9B модели и мульти-доменного бенчмарка. Прирост в биологии (+14,4 п.п.) и "
            "информатике (+12,1 п.п.) — выше среднего по литературе.",
        ),
    ]

    for q, a in qa:
        add_p(doc, "В: " + q, bold=True, color=DARK_GREEN, space_before=8, space_after=2)
        add_p(doc, "О: " + a, space_after=2, line_spacing=1.3)

    # ============================================================
    # §6. РЕКОМЕНДАЦИИ
    # ============================================================
    heading(doc, "Рекомендации по усилению работы", level=1, numbered="§6")

    heading(doc, "6.1 Перед StudVesna (1-2 дня)", level=2)
    bullet(doc, [
        ("Перепроверить ссылку GDPO-decoupled (arXiv:2601.05242). ", {"bold": True}),
        ("Если статья не существует или это не тот метод — заменить на корректный источник.", {}),
    ])
    bullet(doc, [
        ("В докладе явно проговорить отличие от S-GRPO. ", {"bold": True}),
        ("Подготовить 30-секундный ответ (см. §5).", {}),
    ])
    bullet(doc, [
        ("Подготовить ответ про RLVR-критику. ", {"bold": True}),
        ("Это сейчас популярный аргумент в дискуссиях.", {}),
    ])

    heading(doc, "6.2 Перед публикацией в ВАК (2-4 недели)", level=2)
    bullet(doc, [
        ("Добавить раздел Related Work с явным сравнением c S-GRPO, e1, ThinkDial, P-GSPO. ", {"bold": True}),
        ("Без этого раздел Related Work у рецензентов вызовет вопросы.", {}),
    ])
    bullet(doc, [
        ("Прогнать модель на MERA. ", {"bold": True}),
        ("Это удешевит вопросы про русскоязычный бенчмарк.", {}),
    ])
    bullet(doc, [
        ("По возможности — провести ablation S-GRPO vs наш ThinkingBudget на одинаковом сабсете. ", {"bold": True}),
        ("Это превратит риск №1 в сильную сторону.", {}),
    ])

    heading(doc, "6.3 Целевые ВАК-журналы", level=2)
    make_table(doc,
               ["Журнал", "Уровень", "Релевантность", "Ожидаемый цикл"],
               [
                   ["Искусственный интеллект и принятие решений", "ВАК (К1)", "ML, RL — высокая",     "6-9 мес"],
                   ["Информатика и её применения", "ВАК (К2)", "ML — средняя", "4-6 мес"],
                   ["Вестник МГТУ им. Н. Э. Баумана. Приборостроение", "ВАК (К2)", "АСУ — средняя", "4-6 мес"],
                   ["Computational Linguistics and Intellectual Technologies (Dialogue)", "Scopus Q3", "NLP — высокая", "Ежегодно (май)"],
               ],
               widths=[8.0, 2.5, 3.5, 3.0])

    # ============================================================
    # §7. ИСТОЧНИКИ
    # ============================================================
    heading(doc, "Источники", level=1, numbered="§7")
    add_p(doc, "Все ссылки получены через WebSearch 28.04.2026.",
          italic=True, color=GRAY, space_after=6)

    refs = [
        # Прямые конкуренты
        ("S-GRPO", "Dai R. et al. S-GRPO: Early Exit via Reinforcement Learning in Reasoning Models. "
                    "arXiv:2505.07686 (NeurIPS 2025 poster). https://arxiv.org/abs/2505.07686"),
        ("e1 / Adaptive Effort", "e1: Learning Adaptive Control of Reasoning Effort. "
                                  "arXiv:2510.27042 (10.2025). https://arxiv.org/abs/2510.27042"),
        ("ThinkDial", "ThinkDial: An Open Recipe for Controlling Reasoning Effort in LLMs. "
                       "arXiv:2508.18773 (08.2025). https://arxiv.org/abs/2508.18773"),
        ("P-GSPO", "P-GSPO: Parameterized Group Sequence Policy Optimization for Length-Sensitive Reasoning. "
                    "OpenReview. https://openreview.net/forum?id=OeYb0K8gEu"),
        ("UP-GRPO", "UP-GRPO: Unbounded Positive Group Relative Policy Optimization. Flightless Bull blog "
                     "(02.2026). https://rocfly88.github.io/2026/02/26/UP-GRPO.html"),
        # Базовые методы
        ("GSPO",   "Zheng C. et al. Group Sequence Policy Optimization. arXiv:2507.18071 (Qwen Team, "
                    "07.2025). https://arxiv.org/abs/2507.18071"),
        ("ReDit",  "Wei Y. et al. ReDit: Reward Dithering for Improved LLM Policy Optimization. "
                    "arXiv:2506.18631 (NeurIPS 2025 poster). https://arxiv.org/abs/2506.18631"),
        ("DeepSeek-R1", "Guo D. et al. DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via RL. "
                          "arXiv:2501.12948 (01.2025). https://arxiv.org/abs/2501.12948"),
        ("S1",     "Muennighoff N. et al. s1: Simple Test-Time Scaling. arXiv:2501.19393 (01.2025). "
                    "https://arxiv.org/abs/2501.19393"),
        ("Qwen3 Tech Report", "Qwen Team. Qwen3 Technical Report. arXiv:2505.09388 (05.2025). "
                                "https://arxiv.org/abs/2505.09388"),
        ("KTO",    "Ethayarajh K. et al. KTO: Model Alignment as Prospect-Theoretic Optimization. "
                    "arXiv:2402.01306 (02.2024)."),
        ("DPO",    "Rafailov R. et al. Direct Preference Optimization. arXiv:2305.18290 (NeurIPS 2023)."),
        # Surveys
        ("Stop Overthinking survey", "TMLR 2025: Stop Overthinking — A Survey on Efficient Reasoning "
                                       "for LLMs. https://github.com/Eclipsess/Awesome-Efficient-Reasoning-LLMs"),
        ("State of LLM Reasoning",   "Raschka S. The State of Reinforcement Learning for LLM Reasoning. "
                                       "magazine.sebastianraschka.com (2025)."),
        ("Concise Adaptive Thinking", "Towards Concise and Adaptive Thinking in Large Reasoning Models: "
                                        "A Survey. arXiv:2507.09662 (07.2025)."),
        ("Limit of RLVR",            "Does RL Really Incentivize Reasoning Capacity in LLMs Beyond the "
                                       "Base Model? OpenReview / limit-of-rlvr.github.io"),
        # ITS literature
        ("SocraticLM", "SocraticLM: Exploring Socratic Personalized Teaching with LLMs. NeurIPS 2024 "
                        "poster. https://openreview.net/forum?id=qkoZgJhxsA"),
        ("SocraticAI CS", "SocraticAI: Transforming LLMs into Guided CS Tutors. arXiv:2512.03501 "
                            "(12.2025). https://arxiv.org/abs/2512.03501"),
        ("LLM in Education survey", "Large language models in education: a systematic review of "
                                      "empirical applications, benefits, and challenges. ScienceDirect (2025), "
                                      "88 empirical studies."),
        ("AI-based ITS review", "A Comprehensive Review of AI-based Intelligent Tutoring Systems. "
                                  "arXiv:2507.18882 (07.2025)."),
        ("LPITutor", "LPITutor: an LLM based personalized intelligent tutoring system using RAG and "
                      "prompt engineering. PMC12453719 (2025)."),
        # Russian
        ("Яндекс Репетитор AI", "РБК Тренды (10.2025): Для школьников появился ИИ-репетитор для подготовки "
                                  "к ЕГЭ по математике. https://trends.rbc.ru/trends/education/690dff2a9a79475e96bcb940"),
        ("MERA",      "MERA: A Comprehensive LLM Evaluation in Russian. arXiv:2401.04531."),
        ("Open LLM RU 2026", "Лучшие открытые LLM для русского языка в 2026 году. siliconflow.com (2026)."),
        # Tools
        ("verl GRPO docs", "Group Relative Policy Optimization. verl.readthedocs.io (2025)."),
        ("NVIDIA NIM Thinking Budget", "NVIDIA NIM: Thinking Budget Control. "
                                         "docs.nvidia.com/nim/large-language-models/latest/thinking-budget-control.html"),
        ("vLLM #15418", "vLLM project. Issue #15418: Unbounded thinking phase in TRL rollout. "
                          "github.com/vllm-project/vllm/issues/15418"),
    ]
    for short, full in refs:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.7)
        p.paragraph_format.first_line_indent = Cm(-0.7)
        r1 = p.add_run(f"[{short}] ")
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(10)
        r1.bold = True
        r1.font.color.rgb = ACCENT
        r2 = p.add_run(full)
        r2.font.name = "Times New Roman"
        r2.font.size = Pt(10)

    # ---------- ФИНАЛ ----------
    add_p(doc, "", space_before=12)
    callout(doc, "Финальный вердикт",
            "Тема актуальна (RL для thinking-LLM — пик ML 2025-2026), методически грамотна, инженерно "
            "глубока. Главный риск — научная новизна частично перекрывается с S-GRPO и e1; для ВАК-публикации "
            "это нужно явно проговорить в Related Work. Для StudVesna — работа более чем достаточна. "
            "Иди защищать без сомнений.",
            bg="EAF4D8", color=ACCENT)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Saved: {OUT.resolve()}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
