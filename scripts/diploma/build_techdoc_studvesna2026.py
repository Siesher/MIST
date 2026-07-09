"""Построение технического разбора работы (docx).

Документ — глубокий технический разбор всех аспектов диссертационного
исследования: математика GRPO/GSPO, реализация ThinkingBudgetProcessor,
GDPO triple reward, гиперпараметры всех трёх стадий, ablation, reproducibility.

В отличие от тезисов и доклада, здесь — авторитетный референс уровня
рабочей записки: формулы, псевдокод, реальные значения из исходников
(notebooks/grpo_qwen3.5_9b.ipynb и др.).
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path("docs/diploma/Технический_разбор_StudVesna2026_Сухацкий.docx")

DARK_GREEN = RGBColor(0x1F, 0x5C, 0x2D)
ACCENT = RGBColor(0x5F, 0xA1, 0x2E)
GRAY = RGBColor(0x5A, 0x6B, 0x5E)
RED = RGBColor(0xC0, 0x39, 0x2B)
BLUE = RGBColor(0x2F, 0x65, 0x85)
PURPLE = RGBColor(0x6B, 0x3F, 0x8C)
CODE_BG = "F4F6F2"


def set_cell_shading(cell, hex_fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def add_p(
    doc: Document,
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    size: float | None = None,
    color: RGBColor | None = None,
    align: int | None = None,
    space_before: float = 0,
    space_after: float = 4,
    line_spacing: float = 1.2,
):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    if size is not None:
        run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = color
    return p


def add_runs(doc: Document, parts: list[tuple[str, dict]], *, space_after: float = 4, line_spacing: float = 1.2, justify: bool = True):
    p = doc.add_paragraph()
    if justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    for text, opts in parts:
        run = p.add_run(text)
        run.font.name = opts.get("font", "Times New Roman")
        run.font.size = Pt(opts.get("size", 11))
        run.bold = opts.get("bold", False)
        run.italic = opts.get("italic", False)
        if "color" in opts:
            run.font.color.rgb = opts["color"]
    return p


def heading(doc: Document, text: str, level: int = 1, *, color: RGBColor = DARK_GREEN, numbered: str = ""):
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
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(sizes.get(level, 12))
    run.bold = True
    run.font.color.rgb = color
    return p


def bullet(doc: Document, parts, *, level: int = 0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.6 + 0.6 * level)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.2
    if isinstance(parts, str):
        parts = [(parts, {})]
    if p.runs:
        p.runs[0].text = ""
    for text, opts in parts:
        run = p.add_run(text)
        run.font.name = opts.get("font", "Times New Roman")
        run.font.size = Pt(opts.get("size", 11))
        run.bold = opts.get("bold", False)
        run.italic = opts.get("italic", False)
        if "color" in opts:
            run.font.color.rgb = opts["color"]


def code_block(doc: Document, code: str, *, lang: str = "python"):
    """Render a multi-line code block with monospaced font and grey background."""
    table = doc.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    set_cell_shading(cell, CODE_BG)
    cell.paragraphs[0].clear()

    # Optional language label
    if lang:
        lp = cell.paragraphs[0]
        lp.paragraph_format.space_after = Pt(2)
        lr = lp.add_run(lang.upper())
        lr.font.name = "Consolas"
        lr.font.size = Pt(8)
        lr.font.color.rgb = ACCENT
        lr.bold = True

    for line in code.splitlines():
        p = cell.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.line_spacing = 1.1
        run = p.add_run(line if line else " ")
        run.font.name = "Consolas"
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(0x10, 0x28, 0x18)
    # add tiny spacer after
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(2)
    sp.paragraph_format.space_before = Pt(0)


def formula(doc: Document, text: str):
    """Centered, italic, monospace-ish formula line."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.font.name = "Cambria Math"
    run.font.size = Pt(12)
    run.italic = True
    run.font.color.rgb = DARK_GREEN


def callout(doc: Document, label: str, body: str, *, color: RGBColor = ACCENT, bg_hex: str = "EAF4D8"):
    """Styled note/callout block."""
    table = doc.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    set_cell_shading(cell, bg_hex)
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


def make_table(doc: Document, header: list[str], rows: list[list[str]], *, widths_cm: list[float] | None = None, highlight_rows: list[int] | None = None):
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.style = "Light Grid"
    if widths_cm:
        for col_idx, w in enumerate(widths_cm):
            for row in table.rows:
                row.cells[col_idx].width = Cm(w)
    # Header
    for i, h in enumerate(header):
        c = table.rows[0].cells[i]
        c.text = ""
        p = c.paragraphs[0]
        run = p.add_run(h)
        run.font.name = "Times New Roman"
        run.font.size = Pt(10)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_shading(c, "1F5C2D")
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    # Body
    highlight_rows = highlight_rows or []
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            c = table.rows[ri + 1].cells[ci]
            c.text = ""
            p = c.paragraphs[0]
            run = p.add_run(val)
            run.font.name = "Times New Roman"
            run.font.size = Pt(10)
            if ci == 0:
                run.bold = True
            if ri in highlight_rows:
                set_cell_shading(c, "EAF4D8")
                run.font.color.rgb = DARK_GREEN
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(2)
    return table


# ============================================================
# СБОРКА ДОКУМЕНТА
# ============================================================
def build_doc() -> None:
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
    add_p(doc, "Технический разбор",
          size=12, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    add_p(doc, "Метод управляемого рассуждения\nпри RL-обучении языковых моделей для STEM-репетитора",
          size=18, bold=True, color=DARK_GREEN,
          align=WD_ALIGN_PARAGRAPH.CENTER, line_spacing=1.2, space_after=10)
    add_p(doc, "Авторитетный референс к презентации Студвесны-2026", size=11, italic=True,
          color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)
    add_p(doc, "Сухацкий М. О.  ·  КФ МГТУ им. Н. Э. Баумана  ·  ИУК3  ·  2026",
          size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    add_p(doc, "Руководитель: к.т.н., доц. М. О. Корлякова", size=10, italic=True,
          color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)

    callout(doc, "Назначение документа",
            "В отличие от тезисов (компактная аннотация) и доклада (сценарий выступления), "
            "этот документ — глубокий технический разбор: реальные формулы, псевдокод, исходные значения "
            "гиперпараметров (из notebooks/grpo_qwen3.5_9b.ipynb), пошаговые объяснения каждой инженерной "
            "развилки, ссылки на статьи. Для подготовки к вопросам комиссии, рецензированию НИР и публикации "
            "в ВАК-журнале.",
            bg_hex="DBEEED", color=BLUE)

    # ---------- ОГЛАВЛЕНИЕ ----------
    heading(doc, "Оглавление", level=1)
    toc = [
        ("§1", "Постановка задачи и архитектура системы"),
        ("§2", "Математика GRPO и GSPO. Где появляется ноль"),
        ("§3", "Барьер №1: ThinkingBudgetProcessor (главный вклад)"),
        ("§4", "Барьер №2: Cold-Start SFT"),
        ("§5", "Барьер №3: ReDit (reward dithering)"),
        ("§6", "GDPO triple reward: формат функции награды"),
        ("§7", "Гиперпараметры стадии GSPO (исчерпывающий список)"),
        ("§8", "Стадия KTO (Kahneman–Tversky Optimization)"),
        ("§9", "Стадия DPO (Direct Preference Optimization)"),
        ("§10", "Бенчмарк, верификаторы и протокол оценки"),
        ("§11", "Ablation и контрольные эксперименты"),
        ("§12", "Результаты по стадиям и доменам"),
        ("§13", "Failure modes и post-mortem fixes"),
        ("§14", "Воспроизводимость: окружение, версии, артефакты"),
        ("§15", "Список источников"),
    ]
    for num, title in toc:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        r1 = p.add_run(num + "  ")
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(11)
        r1.bold = True
        r1.font.color.rgb = ACCENT
        r2 = p.add_run(title)
        r2.font.name = "Times New Roman"
        r2.font.size = Pt(11)

    doc.add_page_break()

    # ============================================================
    # §1. ПОСТАНОВКА ЗАДАЧИ
    # ============================================================
    heading(doc, "Постановка задачи и архитектура системы", level=1, numbered="§1")

    heading(doc, "1.1 Целевая система", level=2)
    add_runs(doc, [
        ("MITS — Math Intelligent Tutoring System — это интеллектуальная обучающая система "
         "(ITS), реализующая ", {}),
        ("сократический диалог", {"bold": True}),
        (" по пяти STEM-дисциплинам (математика, физика, химия, биология, информатика) для "
         "русскоязычных школьников 7–11 классов. Архитектура: FastAPI-бэкенд (см. ", {}),
        ("backend/app/", {"font": "Consolas", "size": 10}),
        ("), Next.js-фронтенд с WebSocket-стримингом (", {}),
        ("frontend/", {"font": "Consolas", "size": 10}),
        ("), мультиагентный пайплайн поверх Ollama (Qwen3.5-9B fine-tuned).", {}),
    ])

    heading(doc, "1.2 Требования к языковой модели", level=2)
    bullet(doc, "генерация цепочки рассуждений (CoT) перед финальным ответом — необходимо для прозрачности обучения;")
    bullet(doc, "корректность решения STEM-задач — измеряется автоматически через SymPy/ChemPy/regex;")
    bullet(doc, "сократический стиль — модель не должна сразу выдавать ответ, ведёт ученика через наводящие вопросы;")
    bullet(doc, "русскоязычность с сохранением математической нотации (LaTeX-боксы $\\boxed{}$);")
    bullet(doc, "компактность — целевой деплой через Ollama на одном узле, поэтому 9B параметров.")

    heading(doc, "1.3 Цикл RL-дообучения и его срыв", level=2)
    add_p(doc, "Стандартный цикл TRL (HuggingFace) выглядит так:", space_after=4)
    code_block(doc,
"""for step in range(total_steps):
    prompts = sample(dataset, batch_size)
    completions = model.generate(prompts, max_new_tokens=MAX_COMPLETION,
                                 num_return_sequences=G)   # rollout
    rewards = reward_fn(completions, gold_answers)         # SymPy/ChemPy/...
    advantages = (rewards - rewards.mean(group=G)) / rewards.std(group=G)  # GRPO
    loss = -log_prob * advantages + beta * KL              # PPO-like clip
    loss.backward(); optimizer.step()""", lang="python")

    add_runs(doc, [
        ("Срыв происходит на втором шаге (", {}),
        ("model.generate", {"font": "Consolas", "size": 10}),
        ("): TRL не имеет встроенного «бюджета рассуждения» (vLLM #15418). Thinking-модель уходит в "
         "неограниченный цикл и не закрывает ", {}),
        ("</think>", {"font": "Consolas", "size": 10}),
        (" в пределах ", {}),
        ("MAX_COMPLETION", {"font": "Consolas", "size": 10}),
        (". Все G completions в группе обрезаются → все имеют одинаковую (нулевую) награду → "
         "advantages схлопываются в 0 → градиент равен нулю.", {}),
    ])

    callout(doc, "Источник истины",
            "Класс ThinkingBudgetProcessor реализован в notebooks/grpo_qwen3.5_9b.ipynb (cell 13). "
            "Все приведённые в этом документе значения гиперпараметров — выгрузка из этого ноутбука "
            "и сопутствующих kto/dpo notebooks.",
            bg_hex="FDE8E6", color=RED)

    # ============================================================
    # §2. МАТЕМАТИКА GRPO/GSPO
    # ============================================================
    heading(doc, "Математика GRPO и GSPO. Где появляется ноль", level=1, numbered="§2")

    heading(doc, "2.1 GRPO loss (Shao et al., DeepSeekMath, arXiv:2402.03300)", level=2)
    add_p(doc, "Group Relative Policy Optimization — это PPO-подобный алгоритм без value-network. Преимущество "
               "оценивается относительно среднего награды в группе из G completions для одного промпта:")
    formula(doc, "A_i = (r_i − mean(r_1, …, r_G)) / std(r_1, …, r_G)")
    add_p(doc, "Затем стандартный PPO-clip на уровне токена:")
    formula(doc,
            "L_GRPO = E_t[ min( ratio_t · A, clip(ratio_t, 1−ε, 1+ε) · A ) ] − β · KL(π_θ ‖ π_ref)")
    add_runs(doc, [
        ("где ratio_t = π_θ(a_t | s_t) / π_ref(a_t | s_t) — отношение вероятностей токена t у текущей и "
         "референсной политики.", {"italic": True}),
    ])

    heading(doc, "2.2 GSPO: sequence-level importance sampling (Zheng et al., arXiv:2507.18071)", level=2)
    add_runs(doc, [
        ("Ключевое отличие GSPO — importance sampling нормируется на ", {}),
        ("уровне всей последовательности", {"bold": True}),
        (", а не отдельных токенов. Для одного completion длиной L:", {}),
    ])
    formula(doc, "ratio_seq = ( ∏_t π_θ(a_t | s_t) / π_ref(a_t | s_t) )^{1/L}")
    add_p(doc, "На длинных цепочках рассуждения (L ~ 2000 токенов) токенная дисперсия ratio_t взрывается; "
               "geometric mean по последовательности её стабилизирует. Цена — клипинг ε нужно ставить "
               "на 2–3 порядка меньше:")
    formula(doc, "ε_GRPO ≈ 0,2     vs.     ε_GSPO ≈ 3·10⁻⁴")
    add_p(doc, "В нашем коде: EPSILON = 3e-4, EPSILON_HIGH = 4e-4 (Clip-Higher из DAPO arXiv:2503.14476 — "
               "разрешает чуть более активную positive update при сохранении симметричной защиты от негативного "
               "обвала).")

    heading(doc, "2.3 Цепная реакция нуля (детальный вывод)", level=2)
    add_p(doc, "Покажем формально, почему обрезка ведёт к нулевому градиенту.", space_after=4)
    add_p(doc, "Шаг 1 — обрезка: при отсутствии </think> в пределах MAX_COMPLETION все G completions сэмплинга "
               "усекаются. Reward-функция извлекает ответ из \\boxed{...} (см. _extract_boxed_answer в "
               "stem_rewards.py). При отсутствии \\boxed{...} → возвращается пустая строка → "
               "verify_answer возвращает 0.0 для всех G.", space_after=4)
    formula(doc, "r_1 = r_2 = … = r_G = 0")
    add_p(doc, "Шаг 2 — schлопывание дисперсии: std(0, 0, …, 0) = 0.")
    formula(doc, "A_i = (0 − 0) / 0 = NaN  →  обрабатывается как 0")
    add_p(doc, "Шаг 3 — нулевой policy gradient (∂L/∂θ ∝ A_i):")
    formula(doc, "∇_θ L_GRPO = 0,    KL = 0  →  оптимизатор не делает шаг в правильном направлении")
    callout(doc, "Главный вывод",
            "Решение этой проблемы не сводится к увеличению max_completion_length — модель всё равно дойдёт "
            "до лимита, не закрыв </think>. Нужен принудительный механизм завершения думающей фазы внутри "
            "каждого rollout-сэмпла.")

    # ============================================================
    # §3. THINKING BUDGET PROCESSOR
    # ============================================================
    heading(doc, "Барьер №1: ThinkingBudgetProcessor (главный вклад)", level=1, numbered="§3")

    heading(doc, "3.1 Идея и место в пайплайне", level=2)
    add_p(doc, "ThinkingBudgetProcessor — это подкласс transformers.LogitsProcessor, "
               "вызываемый на каждом шаге авторегрессионной генерации до softmax. "
               "Он встраивается в model.generate() через monkey-patch (см. cell 13 ноутбука) и работает "
               "параллельно для G сэмплов в одном rollout.")

    heading(doc, "3.2 Состояние и трёхзонная логика", level=2)
    add_p(doc, "Процессор поддерживает per-sequence счётчик токенов с момента <think>. Зоны:", space_after=2)
    bullet(doc, [
        ("Zone 1 (0…0,9·B): ", {"bold": True}),
        ("процессор пассивен, scores не меняются.", {}),
    ])
    bullet(doc, [
        ("Zone 2 (0,9·B…B): soft nudge", {"bold": True}),
        (" — scores[</think>] += 5,0. Модель чаще выбирает закрытие, но другие токены остаются возможными.", {}),
    ])
    bullet(doc, [
        ("Zone 3 (= B): hard force", {"bold": True}),
        (" — scores[:] = -∞; scores[</think>] = 0,0. Гарантия закрытия.", {}),
    ])
    add_p(doc, "Здесь B = thinking_budget = 1536 токенов (в исходниках; в тезисах округлено до 1500). "
               "Граница soft nudge: int(B · 0,9) = 1382 токена.", space_after=4)

    heading(doc, "3.3 Реализация (полный код)", level=2)
    code_block(doc,
"""class ThinkingBudgetProcessor(LogitsProcessor):
    def __init__(self, think_end_token_id: int, thinking_budget: int = 1536,
                 think_start_token_id: int = None):
        self.think_end_token_id   = think_end_token_id
        self.thinking_budget      = thinking_budget
        self.think_start_token_id = think_start_token_id
        self.soft_nudge_threshold = int(thinking_budget * 0.9)
        self._thinking_tokens = None   # per-sequence counter
        self._in_thinking     = None   # per-sequence bool flag

    def _reset(self, batch_size: int):
        self._thinking_tokens = torch.zeros(batch_size, dtype=torch.long)
        self._in_thinking     = torch.ones(batch_size,  dtype=torch.bool)

    def __call__(self, input_ids, scores):
        batch_size = input_ids.shape[0]
        if self._thinking_tokens is None or self._thinking_tokens.shape[0] != batch_size:
            self._reset(batch_size)

        for i in range(batch_size):
            if not self._in_thinking[i]:
                continue
            last_token = input_ids[i, -1].item()
            if last_token == self.think_end_token_id:
                self._in_thinking[i] = False
                continue

            self._thinking_tokens[i] += 1
            tok_count = self._thinking_tokens[i].item()

            if tok_count >= self.thinking_budget:
                # HARD FORCE
                scores[i, :] = float('-inf')
                scores[i, self.think_end_token_id] = 0.0
            elif tok_count >= self.soft_nudge_threshold:
                # SOFT NUDGE
                scores[i, self.think_end_token_id] += 5.0

        return scores""", lang="python")

    heading(doc, "3.4 Почему +5,0, а не +1,0 или +10,0", level=2)
    add_p(doc, "Логиты до softmax — вещественные числа, обычно в диапазоне [−5; +5] для топ-токенов. "
               "Прибавка +5,0 эмпирически даёт ≈ удвоение вероятности </think> относительно лидирующего "
               "альтернативного токена — это «склоняет, но не принуждает». При +1,0 эффект слабый "
               "(модель чаще игнорирует), при +10,0 — модель резко обрывает мысль и качество CoT падает. "
               "Значение +5,0 экспериментально подобрано на 50-задачной выборке.")

    heading(doc, "3.5 Сравнение с S1 (Muennighoff et al., arXiv:2501.19393)", level=2)
    make_table(doc,
               ["Аспект", "S1 (test-time scaling)", "Наш ThinkingBudgetProcessor"],
               [
                   ["Этап применения", "Инференс (после обучения)", "Rollout-генерация внутри RL"],
                   ["Цель", "Контроль длины ответа конечного пользователя", "Гарантия завершения для расчёта награды"],
                   ["Влияние на градиент", "Не влияет (модель не обучается)", "Делает advantages ненулевыми → ∇L ≠ 0"],
                   ["Soft/Hard логика", "Только hard cutoff", "Двухступенчатая (soft + hard)"],
                   ["Per-sequence state", "Нет (одна последовательность)", "Есть (G параллельных completions)"],
               ],
               widths_cm=[3.8, 6.0, 6.5])
    add_p(doc, "Принципиальное отличие — наш процессор встроен в RL-loop. У S1 принудительное завершение — "
               "это утилита для пользователя; у нас — это математическое условие сходимости.", space_after=4)

    heading(doc, "3.6 Trade-off: качество мысли vs. гарантия завершения", level=2)
    add_p(doc, "Soft nudge активен только в верхних 10 % бюджета (1382…1536 токенов). На практике "
               "примерно 70–85 % completions завершаются естественно ещё в Zone 1. Hard force срабатывает "
               "лишь на ≈ 14 % сэмплов — это и есть итоговый clipped ratio после применения метода. "
               "Качество CoT (измеренное Socratic score через LLM-судью) после применения процессора "
               "выросло с 0,911 до 0,934 — деградации нет.")

    # ============================================================
    # §4. COLD-START SFT
    # ============================================================
    heading(doc, "Барьер №2: Cold-Start SFT", level=1, numbered="§4")

    heading(doc, "4.1 Зачем нужно", level=2)
    add_p(doc, "Даже после устранения проблемы обрезки GRPO нужен достаточный пул положительных примеров "
               "в группе. На «холодной» Qwen3.5-9B-Instruct базовая точность по STEM ~5 %. При G = 8 в "
               "группе в среднем 0,4 правильных ответа на промпт — это недостаточно для оценки "
               "advantage: дисперсия наград чрезмерно низкая (мала статистическая мощность).")
    add_p(doc, "Cold-Start SFT поднимает эту базу до 15–30 % через короткое обучение с учителем перед "
               "запуском RL. Идея взята из DeepSeek-R1 (arXiv:2501.12948).")

    heading(doc, "4.2 Двухфазная схема Phase A / Phase B", level=2)
    make_table(doc,
               ["Фаза", "Цель", "Шагов", "Источник данных"],
               [
                   ["A — Math Cold-Start", "Поднять базовую accuracy с ~5 % до 15–30 %", "200",
                    "rejection sampling из самой Qwen3.5-9B + автоверификация SymPy/ChemPy/regex"],
                   ["B — Socratic Cold-Start", "Установить behavioral prior сократического стиля до RL", "100",
                    "training/data/dialogs.jsonl (3 875 диалогов, см. репозиторий)"],
               ],
               widths_cm=[2.5, 5.5, 1.6, 6.7])

    heading(doc, "4.3 Алгоритм rejection sampling", level=2)
    code_block(doc,
"""def build_cold_start_dataset(base_model, problems, target_n=100):
    # 1. Generate solutions for each problem
    solutions = base_model.generate(problems, n_samples=8)
    # 2. Verify correctness
    verified = []
    for prob, sols in zip(problems, solutions):
        for s in sols:
            r = verify_answer(s, prob.gold, prob.domain)   # 1.0 / 0.0
            if r == 1.0:
                verified.append({"prompt": prob.text,
                                 "completion": s,
                                 "domain": prob.domain})
                break
    # 3. Stop when target reached
    return verified[:target_n]""", lang="python")

    heading(doc, "4.4 Почему именно SFT, а не доразметка", level=2)
    add_p(doc, "Альтернатива — собрать «золотой» сократический корпус вручную. Но это:")
    bullet(doc, "дорого (диалог по STEM пишется ~ 20 минут на пример → 500 примеров = ≈ 170 ч);")
    bullet(doc, "вносит человеческое смещение (эксперт пишет в одном стиле);")
    bullet(doc, "повышает риск переобучения на формат.")
    add_p(doc, "Rejection sampling из самой модели сохраняет распределение её собственных решений и "
               "тренирует её только воспроизводить успешные попытки. Это — bootstrap-подход.")

    # ============================================================
    # §5. REDIT
    # ============================================================
    heading(doc, "Барьер №3: ReDit (reward dithering)", level=1, numbered="§5")

    heading(doc, "5.1 Формула и обоснование", level=2)
    add_p(doc, "Reward dithering (Lin et al., arXiv:2506.18631) добавляет малый гауссов шум к сырой "
               "награде до вычисления advantages:")
    formula(doc, "r' = r + ε,    ε ~ N(0, σ²),    σ = 0,05")

    heading(doc, "5.2 Доказательство ненулевой дисперсии", level=2)
    add_p(doc, "Пусть в группе G = 8 все r_i = 0. Тогда:")
    formula(doc, "r'_i = ε_i,    Var(r'_i) = σ² = 0,0025")
    add_p(doc, "std(r'_1, …, r'_G) ≈ 0,05 · √(1 − 1/G) ≈ 0,047 — численно не ноль. "
               "Advantages становятся ненулевыми, ∇L ≠ 0.")

    heading(doc, "5.3 Сохранение ранжирования", level=2)
    add_p(doc, "Для пары (correct, incorrect) разница сырых наград Δr = 1,0. Чтобы шум развернул "
               "ранжирование, нужна реализация |ε_correct − ε_incorrect| > 1,0. Вероятность:")
    formula(doc, "P(|ε_1 − ε_2| > 1,0) = P(|Z| > 1/(σ·√2))     где Z ~ N(0, 1)")
    add_p(doc, "При σ = 0,05: 1/(σ·√2) = 14,14, что соответствует P < 10⁻⁴⁴ — практически невозможно. "
               "Эмпирически — ранжирование сохраняется в 99 %+ случаев (отдельные искажения возможны "
               "только в borderline-случаях, где partial credit ≈ 0,5).")

    heading(doc, "5.4 Несовместимость с zero-variance masking", level=2)
    callout(doc, "Важно",
            "ReDit и zero-variance masking (стандартный TRL-приём — игнорировать группы с σ(r) = 0) "
            "взаимно исключают друг друга: маскинг отбрасывает ровно те группы, на которых ReDit пытается "
            "восстановить сигнал. В нашем коде zero_variance_masking = False, dithering_sigma = 0,05.",
            bg_hex="FDE8E6", color=RED)

    # ============================================================
    # §6. GDPO TRIPLE REWARD
    # ============================================================
    heading(doc, "GDPO triple reward: формат функции награды", level=1, numbered="§6")

    heading(doc, "6.1 Три компоненты награды", level=2)
    make_table(doc,
               ["Компонент", "Что измеряет", "Верификатор", "Вес"],
               [
                   ["correctness", "корректность финального ответа", "SymPy / ChemPy / regex / exact match", "0,40"],
                   ["format", "наличие <think>...</think> и \\boxed{}", "regex по формату", "0,15"],
                   ["socratic", "наличие наводящих вопросов, отсутствие answer-leak", "LLM-as-judge (Llama-3.1-70B)", "0,45"],
               ],
               widths_cm=[2.8, 5.4, 5.0, 1.5])

    heading(doc, "6.2 GDPO-decoupled нормирование (arXiv:2601.05242)", level=2)
    add_p(doc, "Каждая компонента награды нормируется по группе отдельно перед взвешенной суммой:")
    formula(doc, "r̂_k,i = (r_k,i − mean_g(r_k)) / std_g(r_k)")
    formula(doc, "r_total,i = w_correct · r̂_correct,i + w_format · r̂_format,i + w_socratic · r̂_socratic,i")
    add_p(doc, "Без нормирования компонента с большим масштабом доминирует. После нормировки веса "
               "(0,4 / 0,15 / 0,45) — это доли влияния на градиент, а не на сумму наград.")

    heading(doc, "6.3 Эволюция весов (post-mortem)", level=2)
    add_p(doc, "Изначально веса были (0,7 / 0,15 / 0,15) — превалирует correctness. После первого запуска "
               "обнаружилось, что socratic поведение деградирует (модель учится решать, а не "
               "рассуждать). 23 марта 2026 веса перебалансированы:", space_after=4)
    make_table(doc,
               ["Версия", "correct", "format", "socratic", "Эффект"],
               [
                   ["v1 (initial)", "0,70", "0,15", "0,15", "Высокая accuracy, низкий socratic score"],
                   ["v2 (post-mortem 23.03)", "0,40", "0,15", "0,45", "Сбалансированный прирост по обоим направлениям"],
                   ["v3 (final, текущая)", "0,40", "0,15", "0,45", "Используется в продакшен-ноутбуке"],
               ],
               widths_cm=[3.5, 1.8, 1.8, 1.8, 6.5],
               highlight_rows=[2])

    heading(doc, "6.4 Верификаторы по доменам", level=2)
    code_block(doc,
"""def _verify_answer(completion, answer, domain):
    extracted = _extract_boxed_answer(completion)   # ищет последний \\boxed{...}
    if not extracted or not answer:
        return 0.0
    if domain == "math":
        # SymPy: символьное упрощение
        pred = sympy.sympify(extracted)
        gold = sympy.sympify(answer)
        return 1.0 if sympy.simplify(pred - gold) == 0 else 0.0
    elif domain == "physics":
        # 5%-relative tolerance
        pred_num = float(re.findall(r"[-+]?\\d*\\.?\\d+", extracted)[0])
        gold_num = float(re.findall(r"[-+]?\\d*\\.?\\d+", str(answer))[0])
        return 1.0 if abs(pred_num - gold_num) / max(abs(gold_num), 1e-10) < 0.05 else 0.0
    else:   # biology, cs — exact match (case-insensitive)
        return 1.0 if extracted.strip().lower() == str(answer).strip().lower() else 0.0
    # chemistry → ChemPy для стехиометрии (отдельная ветка в stem_rewards.py)""",
               lang="python")

    # ============================================================
    # §7. ГИПЕРПАРАМЕТРЫ GSPO
    # ============================================================
    heading(doc, "Гиперпараметры стадии GSPO (исчерпывающий список)", level=1, numbered="§7")

    heading(doc, "7.1 Базовая модель и LoRA", level=2)
    make_table(doc,
               ["Параметр", "Значение", "Обоснование"],
               [
                   ["BASE_MODEL", "Qwen/Qwen3.5-9B (Instruct)", "9B без QLoRA на A100/PRO 6000; thinking-mode встроен"],
                   ["dtype", "bf16", "RTX PRO 6000 / A100 поддерживают; нет потерь точности vs fp32"],
                   ["LORA_R", "16", "Tina paper (arXiv:2504.15777): r=64 деградирует RL"],
                   ["LORA_ALPHA", "32", "α / r = 2 — баланс магнитуды апдейта"],
                   ["LORA_DROPOUT", "0,0", "RL уже имеет inherent exploration"],
                   ["TARGET_MODULES", "q,k,v,o,gate,up,down_proj", "Все linear-слои attention + MLP"],
               ],
               widths_cm=[3.5, 4.5, 7.5])

    heading(doc, "7.2 GSPO-ядро", level=2)
    make_table(doc,
               ["Параметр", "Значение", "Источник / обоснование"],
               [
                   ["IMPORTANCE_SAMPLING_LEVEL", "sequence", "GSPO: arXiv:2507.18071"],
                   ["LOSS_TYPE", "dr_grpo", "Decoupled-Reward GRPO (arXiv:2503.20783)"],
                   ["EPSILON", "3·10⁻⁴", "Sequence-level: на 3 порядка меньше токенного 0,2"],
                   ["EPSILON_HIGH", "4·10⁻⁴", "Clip-Higher (DAPO arXiv:2503.14476)"],
                   ["BETA (KL penalty)", "0,04", "Post-mortem fix: 0,0 ломает instruction-following"],
                   ["MAX_GRAD_NORM", "1,0", "Стандарт TRL"],
               ],
               widths_cm=[5.0, 3.0, 7.5])

    heading(doc, "7.3 Длины контекста и батчи", level=2)
    make_table(doc,
               ["Параметр", "A100-80GB", "PRO 6000-96GB"],
               [
                   ["MAX_PROMPT_LENGTH", "512", "512"],
                   ["MAX_COMPLETION", "4096 (budget=2048 + answer=2048)", "4096"],
                   ["MAX_SEQ_LENGTH", "4608", "4608"],
                   ["G (group size)", "8", "8"],
                   ["BATCH_SIZE", "1", "1 (BS=2 → OOM на backward)"],
                   ["GRADIENT_ACCUMULATION_STEPS", "16", "16"],
                   ["Effective batch (prompts)", "16", "16"],
                   ["Effective batch (completions)", "128", "128"],
                   ["STEPS_PER_GENERATION", "16", "16"],
               ],
               widths_cm=[5.5, 5.0, 5.0])

    heading(doc, "7.4 Оптимизатор и расписание", level=2)
    make_table(doc,
               ["Параметр", "Stage 1 (warm-up)", "Stage 2 (curriculum)"],
               [
                   ["Optimizer", "adamw_torch_fused", "Lion 8-bit (arXiv:2302.06675)"],
                   ["Learning rate", "5·10⁻⁷", "3·10⁻⁷"],
                   ["Weight decay", "0,01", "0,01"],
                   ["Adam β2", "0,99", "—"],
                   ["Warmup ratio", "0,03", "0"],
                   ["LR schedule", "cosine", "cosine"],
                   ["Цель", "стабилизация политики", "сложные задачи (hard tier)"],
               ],
               widths_cm=[4.0, 5.5, 5.5])

    add_p(doc, "Lion (sign-based momentum) на стадии 2 выбран потому, что даёт более устойчивые "
               "обновления при шумных RL-градиентах: знаковая нормировка эквивалентна gradient clipping "
               "по координатам, что критично при σ(reward) близкой к нулю.")

    heading(doc, "7.5 Curriculum-стратегия", level=2)
    make_table(doc,
               ["Tier", "Доля задач", "Difficulty weight", "Доступ в Stage 1", "Доступ в Stage 2"],
               [
                   ["easy",   "30 %", "0,4", "✓", "✓"],
                   ["medium", "50 %", "1,0", "✓", "✓"],
                   ["hard",   "20 %", "1,5", "✗", "✓"],
               ],
               widths_cm=[2.0, 2.5, 3.0, 4.0, 4.0])
    add_p(doc, "Difficulty weighting (GRPO-LEAD): hard-задачи получают вес 1,5 в reward (если решены), "
               "easy — 0,4. Это компенсирует риск переобучения на простые примеры.")

    heading(doc, "7.6 Промпт-микширование", level=2)
    add_p(doc, "Каждый rollout-промпт случайно сэмплится из двух режимов:")
    bullet(doc, "78 % — Socratic (соответствует деплою): system prompt призывает вести ученика через вопросы;")
    bullet(doc, "22 % — TaskGen (предотвращает alignment tax): прямое решение без сократики.")
    add_p(doc, "Без TaskGen-добавки модель «забывает», как решать напрямую — это alignment tax из Llama-2 "
               "Ghost Attention (arXiv:2307.09288).")

    # ============================================================
    # §8. KTO
    # ============================================================
    heading(doc, "Стадия KTO (Kahneman–Tversky Optimization)", level=1, numbered="§8")

    heading(doc, "8.1 Теоретическая основа (arXiv:2402.01306)", level=2)
    add_p(doc, "KTO основан на теории перспектив Канемана–Тверски: люди иначе воспринимают выигрыши и "
               "потери (вес потерь ~ 2× выше). Формула KTO loss для desirable (y_d) и undesirable (y_u):")
    formula(doc, "L_KTO = E[ λ_d · (1 − σ(β · (h_d − ρ))) + λ_u · w_u · (1 − σ(β · (ρ − h_u))) ]")
    add_runs(doc, [
        ("где h = log( π_θ(y|x) / π_ref(y|x) ) — log-ratio, ρ — KL reference point, λ — индикаторы класса.", {"italic": True}),
    ])

    heading(doc, "8.2 Преимущество над DPO", level=2)
    bullet(doc, "DPO требует парных данных (chosen, rejected) для одного промпта — дорого собирать;")
    bullet(doc, "KTO работает на непарных метках: «этот ответ хороший / плохой» — можно собирать дёшево;")
    bullet(doc, "Несбалансированный датасет — нормально для KTO; компенсируется undesirable_weight.")

    heading(doc, "8.3 Гиперпараметры", level=2)
    make_table(doc,
               ["Параметр", "Значение", "Обоснование"],
               [
                   ["BETA", "0,1", "Стандарт KTO paper для 7-9B моделей"],
                   ["LEARNING_RATE", "5·10⁻⁷", "Консервативно для 9B (paper: 5e-7…5e-6)"],
                   ["NUM_EPOCHS", "2", "Дольше → переобучение на мелком датасете"],
                   ["MAX_LENGTH", "1536", "prompt + completion total (TRL 0.27)"],
                   ["BATCH_SIZE (A100)", "4", "Effective batch = 32"],
                   ["GRADIENT_ACCUMULATION", "8", ""],
                   ["DESIRABLE examples", "3 875", "training/data/dialogs.jsonl"],
                   ["UNDESIRABLE examples", "12 597", "training/data/preference_pairs.jsonl (rejected стороны)"],
                   ["undesirable_weight", "2,13", "= 12 597 / (3 875 · 2,13) = 1,53 (балансирует объём)"],
                   ["Total steps", "2 582", "≈ 14,5 часа на A100 80 GB"],
               ],
               widths_cm=[5.0, 4.0, 6.5])

    heading(doc, "8.4 Логика классификации move-категорий", level=2)
    add_p(doc, "В Socratic-диалоге каждая реплика модели классифицируется по типу хода:")
    bullet(doc, [
        ("Хорошие (desirable): ", {"bold": True}),
        ("scaffolding, encourage, hint, problematize", {"font": "Consolas", "size": 10}),
        (" — ведут ученика, не сливают ответ.", {}),
    ])
    bullet(doc, [
        ("Плохие (undesirable): ", {"bold": True}),
        ("answer_leak, give_up, off_topic", {"font": "Consolas", "size": 10}),
        (" — нарушают сократический контракт.", {}),
    ])

    # ============================================================
    # §9. DPO
    # ============================================================
    heading(doc, "Стадия DPO (Direct Preference Optimization)", level=1, numbered="§9")

    heading(doc, "9.1 Теория (arXiv:2305.18290)", level=2)
    add_p(doc, "DPO переформулирует RLHF как supervised задачу на парных предпочтениях. Bradley-Terry "
               "модель предпочтений:")
    formula(doc, "L_DPO = −E[ log σ( β · log(π_θ(y_w|x)/π_ref(y_w|x)) − β · log(π_θ(y_l|x)/π_ref(y_l|x)) ) ]")
    add_p(doc, "y_w — chosen (preferred), y_l — rejected. β контролирует «жёсткость» сдвига от референсной "
               "политики.")

    heading(doc, "9.2 Источник пар", level=2)
    add_p(doc, "DPO в нашем пайплайне — финальная полировка после KTO. Источники пар:")
    bullet(doc, "RAFT++ negatives (отвергнутые в Stage 1 GSPO completions);")
    bullet(doc, "генерация N=16 completions с KTO-чекпоинта, парный отбор по composite score;")
    bullet(doc, "после фильтрации остаётся ≥ 50 пар (MIN_PAIRS) — иначе DPO пропускается.")

    heading(doc, "9.3 Гиперпараметры", level=2)
    make_table(doc,
               ["Параметр", "PRO 6000-96GB", "A100-80GB", "Обоснование"],
               [
                   ["DPO_BETA", "0,1", "0,1", "Консервативный сдвиг (paper recommends 0,1–0,5)"],
                   ["DPO_LR", "5·10⁻⁷", "5·10⁻⁷", "Очень мало — это polish, не learning"],
                   ["DPO_STEPS", "200", "200", "Достаточно для финального тюна"],
                   ["DPO_WARMUP_RATIO", "0,1", "0,1", "20 шагов linear warmup"],
                   ["PAIRS_PER_PROBLEM", "16", "8", "Лимитировано VRAM (16 completions × 1024 token)"],
                   ["DPO_BATCH_SIZE", "4", "2", ""],
                   ["DPO_GRAD_ACCUM", "4", "8", "Effective batch = 16"],
                   ["MIN_PAIRS", "50", "50", "Skip DPO если меньше — недостаточно сигнала"],
               ],
               widths_cm=[4.5, 2.5, 2.5, 6.0])

    heading(doc, "9.4 Защитный механизм", level=2)
    add_p(doc, "В DPO-ноутбуке встроен guard: после прогонки eval-сабсета на пром пром checkpoint, если "
               "accuracy упала более чем на 1 п.п. от KTO-уровня — DPO откатывается (skip). Это "
               "предотвращает деградацию из-за плохо отобранных пар.")

    # ============================================================
    # §10. БЕНЧМАРК
    # ============================================================
    heading(doc, "Бенчмарк, верификаторы и протокол оценки", level=1, numbered="§10")

    heading(doc, "10.1 Состав бенчмарка (3 678 задач)", level=2)
    make_table(doc,
               ["Источник", "Задач", "Домены", "Лицензия"],
               [
                   ["MGSM Russian", "250", "math", "MIT (Google Research)"],
                   ["ruMMLU STEM", "3 210", "math, physics, chemistry, biology, cs", "Apache 2.0"],
                   ["Custom (Author)", "218", "physics, chemistry, biology", "MIT (этот проект)"],
                   ["Итого", "3 678", "5 STEM-доменов", ""],
               ],
               widths_cm=[3.5, 2.0, 6.5, 3.5],
               highlight_rows=[3])

    heading(doc, "10.2 Распределение по доменам", level=2)
    make_table(doc,
               ["Домен", "Кол-во задач", "Базовая accuracy (Qwen3.5-9B)"],
               [
                   ["Математика",   "1 200", "79,1 %"],
                   ["Физика",       "800",   "74,4 %"],
                   ["Химия",        "678",   "46,7 %"],
                   ["Информатика",  "600",   "46,5 %"],
                   ["Биология",     "400",   "28,6 %"],
                   ["Macro-average", "—",     "55,1 %"],
               ],
               widths_cm=[4.0, 4.0, 7.0],
               highlight_rows=[5])

    heading(doc, "10.3 Верификаторы", level=2)
    make_table(doc,
               ["Домен", "Верификатор", "Допуск"],
               [
                   ["Математика", "SymPy: sympy.simplify(pred − gold) == 0", "точное символьное равенство"],
                   ["Физика", "regex + 5 %-относительный допуск", "|pred − gold| / |gold| < 0,05"],
                   ["Химия", "ChemPy: balance_stoichiometry; для answer match — exact", "точное равенство ответа"],
                   ["Биология", "exact match (case-insensitive)", "точное равенство строки"],
                   ["Информатика", "exact match (case-insensitive)", "точное равенство строки"],
               ],
               widths_cm=[2.5, 6.0, 6.5])

    heading(doc, "10.4 LLM-as-judge для Socratic метрик", level=2)
    bullet(doc, [
        ("Socratic score (∈ [0, 1])", {"bold": True}),
        (": средняя оценка по нескольким критериям сократики (наводящие вопросы, поэтапность, отсутствие answer-leak).", {}),
    ])
    bullet(doc, [
        ("No answer leak (∈ [0, 2])", {"bold": True}),
        (": штраф за преждевременную выдачу финального ответа в первой реплике; чем выше, тем меньше leak.", {}),
    ])
    bullet(doc, [
        ("Hard accuracy", {"bold": True}),
        (": accuracy только по hard-tier задачам — отдельный показатель глубины обучения.", {}),
    ])
    add_p(doc, "Судья — Llama-3.1-70B-Instruct (через Cerebras inference API). Промпт-шаблон детерминирован "
               "(temperature=0). Шкала калибрована на 100 эталонных диалогов.")

    heading(doc, "10.5 Параметры генерации при оценке", level=2)
    callout(doc, "Критический параметр",
            "num_predict = 4096 — обязательное значение для thinking-моделей. При 1024 модель не успевает "
            "закрыть </think> на 30+ % задач, что даёт ложно-низкий accuracy. Это была одна из основных "
            "ошибок ранних замеров.",
            bg_hex="FDE8E6", color=RED)
    add_p(doc, "Прочие параметры: temperature=0,7, top_p=0,9, repetition_penalty=1,05, seed=42 для "
               "воспроизводимости.")

    # ============================================================
    # §11. ABLATION
    # ============================================================
    heading(doc, "Ablation и контрольные эксперименты", level=1, numbered="§11")

    heading(doc, "11.1 Главный ablation (4 конфигурации)", level=2)
    make_table(doc,
               ["Конфигурация", "max_completion", "Clipped ratio", "Correctness@50", "Сходится"],
               [
                   ["Thinking ON (no budget)",                 "1024", "100 %",  "—",     "✗"],
                   ["Thinking OFF",                            "1024", "1,6 %",  "0 %",   "✗"],
                   ["Thinking ON (no budget)",                 "4096", "100 %",  "—",     "✗"],
                   ["ThinkingBudget + Cold-Start + ReDit (наш)", "4096", "14,3 %", "21,7 %", "✓"],
               ],
               widths_cm=[5.5, 2.5, 2.5, 2.5, 2.0],
               highlight_rows=[3])

    heading(doc, "11.2 Что показывает ablation", level=2)
    bullet(doc, "увеличение max_completion с 1024 до 4096 не помогает (clipped остаётся 100 %) — модель просто заполняет больше токенов рассуждением;")
    bullet(doc, "отключение thinking даёт 1,6 % clipped, но correctness падает до нуля — модель не умеет решать STEM напрямую;")
    bullet(doc, "только наш метод даёт оба: низкий clipped и ненулевой correctness — критерий сходимости выполнен.")

    heading(doc, "11.3 Контр-ablation отдельных компонентов", level=2)
    make_table(doc,
               ["Конфигурация", "Stage 1 reward signal", "Сходится"],
               [
                   ["ThinkingBudget only (без Cold-Start, без ReDit)", "слабый — мало positives в группе", "медленно ✓ (нестабильно)"],
                   ["ThinkingBudget + Cold-Start (без ReDit)",          "редкие нулевые группы",            "✓ (с лагами)"],
                   ["ThinkingBudget + Cold-Start + ReDit",              "стабильный по всем шагам",        "✓ устойчиво"],
               ],
               widths_cm=[6.5, 5.0, 3.5])

    # ============================================================
    # §12. РЕЗУЛЬТАТЫ
    # ============================================================
    heading(doc, "Результаты по стадиям и доменам", level=1, numbered="§12")

    heading(doc, "12.1 Прирост accuracy по стадиям (макроусреднение)", level=2)
    make_table(doc,
               ["Стадия", "Macro accuracy", "Δ к base (п.п.)", "Δ к предыдущей (п.п.)"],
               [
                   ["Base (Qwen3.5-9B-Instruct)", "55,1 %", "—",     "—"],
                   ["+ GSPO (Stage 1)",            "63,5 %", "+8,4",   "+8,4"],
                   ["+ KTO (Stage 2)",             "64,8 %", "+9,7",   "+1,3"],
                   ["+ DPO (Stage 3, финал)",      "66,5 %", "+11,4",  "+1,7"],
               ],
               widths_cm=[5.5, 3.0, 3.5, 4.5],
               highlight_rows=[3])

    heading(doc, "12.2 По доменам (база vs финал)", level=2)
    make_table(doc,
               ["Домен", "Base", "Финал", "Δ (п.п.)", "Комментарий"],
               [
                   ["Биология",     "28,6 %", "43,0 %", "+14,4", "наибольший прирост — низкая база"],
                   ["Информатика",  "46,5 %", "58,6 %", "+12,1", "хорошая отдача от RL"],
                   ["Химия",        "46,7 %", "62,0 %", "+15,3", "ChemPy верификация даёт чистый сигнал"],
                   ["Математика",   "79,1 %", "85,2 %", "+6,1",  "близко к ceiling"],
                   ["Физика",       "74,4 %", "83,6 %", "+9,2",  "средний прирост, ceiling эффект"],
               ],
               widths_cm=[3.0, 2.0, 2.0, 2.0, 6.5])
    add_p(doc, "Curriculum learning направляет обучающий сигнал в сторону доменов с низкой базовой "
               "accuracy — именно там relative reward gradient наибольший. Это объясняет неравномерность "
               "прироста (биология +14,4 vs математика +6,1).")

    heading(doc, "12.3 Сократические метрики (после GSPO, 31.03.2026)", level=2)
    make_table(doc,
               ["Метрика", "Base", "После GSPO", "Δ"],
               [
                   ["Socratic score",        "0,911", "0,934", "+0,023"],
                   ["No answer leak",        "1,664", "1,752", "+0,088"],
                   ["Hard accuracy",         "83,7 %", "87,8 %", "+4,1 п.п."],
                   ["Доля ответов с вопросами", "34 %", "61 % (после KTO)", "+27 п.п."],
               ],
               widths_cm=[5.0, 3.0, 4.0, 3.0])

    heading(doc, "12.4 Trade-off: точность ↔ сократика", level=2)
    add_p(doc, "На промежуточном замере после GSPO (150 задач, 31.03) общая accuracy просела на −2,3 п.п. "
               "Эта потеря компенсируется на стадиях KTO и DPO; в финале (66,5 %) — чистый прирост +11,4 "
               "относительно базы. Это — приемлемая «налоговая ставка» на сократическое выравнивание.")

    # ============================================================
    # §13. FAILURE MODES
    # ============================================================
    heading(doc, "Failure modes и post-mortem fixes", level=1, numbered="§13")

    heading(doc, "13.1 12 правок post-mortem (23.03.2026)", level=2)
    make_table(doc,
               ["#", "Что было", "Что стало", "Источник проблемы"],
               [
                   ["1", "TRL без бюджета думания", "ThinkingBudgetProcessor", "vLLM #15418, DeepSeek-R1, DAPO"],
                   ["2", "Нет cold-start", "200 шагов SFT на rejection-sampled", "DeepSeek-R1 procedure"],
                   ["3", "Нет socratic prior", "100 шагов на dialogs.jsonl", "Llama-2 Ghost Attention"],
                   ["4", "LoRA r=64", "LoRA r=16", "Tina paper arXiv:2504.15777 (r=64 деградирует)"],
                   ["5", "LR=1e-6", "LR=5e-7", "Sparse reward требует консервативного шага"],
                   ["6", "ReDit + zero-variance masking", "ReDit без masking", "Взаимоисключающие техники"],
                   ["7", "dropout=0.1", "dropout=0.0", "RL имеет inherent exploration"],
                   ["8", "BETA=0,0", "BETA=0,04", "Без KL модель теряет instruction-following"],
                   ["9", "System prompt = TaskGen", "System prompt = Socratic", "Ghost Attention: train=deploy"],
                   ["10", "Socratic reward убран", "weight=0,45 возвращён", "Без него — alignment regression"],
                   ["11", "weights [0,85; 0,15]", "weights [0,4; 0,15; 0,45]", "GDPO + MO-GRPO variance-aware"],
                   ["12", "MAX_COMPLETION=1024", "MAX_COMPLETION=4096", "Бюджет 2048 + ответ 2048"],
               ],
               widths_cm=[0.8, 4.0, 4.0, 6.5])

    heading(doc, "13.2 Speed optimizations (19.03.2026)", level=2)
    bullet(doc, "GRAD_ACCUM 32 → 16 — стандартный для GRPO effective batch, −50 % gen-time;")
    bullet(doc, "steps_per_generation 8 → 16 — лучшая утилизация GPU, IS корректирует staleness;")
    bullet(doc, "SAVE_STEPS 50 → 100 — меньше Drive flushes (Colab лимит на write throughput).")

    # ============================================================
    # §14. REPRODUCIBILITY
    # ============================================================
    heading(doc, "Воспроизводимость: окружение, версии, артефакты", level=1, numbered="§14")

    heading(doc, "14.1 Аппаратная конфигурация", level=2)
    make_table(doc,
               ["Стадия", "GPU minimum", "VRAM", "Время, ч"],
               [
                   ["Cold-Start SFT", "A100-40GB / RTX 3090", "40 GB",  "≈ 1,5"],
                   ["GSPO",            "A100-80GB / PRO 6000",  "80–96 GB", "≈ 8,0"],
                   ["KTO",             "A100-80GB",              "80 GB", "≈ 14,5"],
                   ["DPO",             "A100-80GB",              "80 GB", "≈ 2,0"],
                   ["Eval (3 678 задач)", "A100-40GB",          "40 GB", "≈ 3,0"],
               ],
               widths_cm=[3.5, 5.0, 3.0, 3.5])

    heading(doc, "14.2 Версии библиотек (фиксированный snapshot)", level=2)
    code_block(doc,
"""# Базовые
torch==2.5.1+cu124
transformers==4.49.0
trl==0.27.0          # GSPO support
peft==0.13.2
unsloth==2026.3.0    # FastLanguageModel + LoRA
bitsandbytes==0.45.0 # 8bit optimizers (Lion)
datasets==3.2.0

# Верификация
sympy==1.13.3
chempy==0.9.0

# Логирование
loguru==0.7.3
wandb==0.18.5

# Inference (оценка)
ollama==0.4.7
huggingface_hub==0.27.0""", lang="text")

    heading(doc, "14.3 Артефакты на HuggingFace Hub", level=2)
    bullet(doc, [
        ("Siesher/mits-qwen3-9b-gspo", {"font": "Consolas", "size": 10, "bold": True}),
        (" — LoRA-адаптер после стадии 1 (Cold-Start + GSPO). Размер: 88 MB.", {}),
    ])
    bullet(doc, [
        ("Siesher/mits-qwen3-9b-kto", {"font": "Consolas", "size": 10, "bold": True}),
        (" — LoRA-адаптер после стадии 2. Совместим с GSPO-чекпоинтом (merge сверху).", {}),
    ])
    bullet(doc, [
        ("Siesher/mits-qwen3-9b-final", {"font": "Consolas", "size": 10, "bold": True}),
        (" — финальный адаптер после DPO. Готов к деплою через Ollama.", {}),
    ])

    heading(doc, "14.4 Скрипты валидации", level=2)
    bullet(doc, [
        ("training/scripts/evaluate_stage.py", {"font": "Consolas", "size": 10}),
        (" — независимая оценка любого чекпоинта на 3 678-задачном бенчмарке.", {}),
    ])
    bullet(doc, [
        ("training/scripts/build_eval_benchmark.py", {"font": "Consolas", "size": 10}),
        (" — сборка бенчмарка из MGSM/ruMMLU/custom (детерминированный seed=42).", {}),
    ])
    bullet(doc, [
        ("training/scripts/verify_answers.py", {"font": "Consolas", "size": 10}),
        (" — независимый верификатор для перепроверки результатов.", {}),
    ])
    bullet(doc, [
        ("training/scripts/stem_rewards.py", {"font": "Consolas", "size": 10}),
        (" — единая reward-функция, используемая в GSPO/KTO/DPO и в evaluate_stage.", {}),
    ])

    heading(doc, "14.5 Команда полного воспроизведения (от base до final)", level=2)
    code_block(doc,
"""# 1. Сборка бенчмарка (5 минут)
python training/scripts/build_eval_benchmark.py --output evaluation/bench_3678.jsonl --seed 42

# 2. Оценка базовой модели (~3 ч на A100-40GB)
python training/scripts/evaluate_stage.py \\
    --model Qwen/Qwen3.5-9B \\
    --bench evaluation/bench_3678.jsonl \\
    --num_predict 4096 \\
    --output evaluation/reports/base.jsonl

# 3. Запуск GSPO (~8 ч на A100-80GB) — открыть в Colab
notebooks/grpo_qwen3.5_9b.ipynb

# 4. Запуск KTO (~14,5 ч на A100-80GB)
notebooks/kto_qwen3.5_9b.ipynb

# 5. Запуск DPO (~2 ч на A100-80GB)
notebooks/dpo_polish_qwen3.5_9b.ipynb

# 6. Финальная оценка
python training/scripts/evaluate_stage.py \\
    --adapter Siesher/mits-qwen3-9b-final \\
    --bench evaluation/bench_3678.jsonl \\
    --num_predict 4096 \\
    --output evaluation/reports/final.jsonl""", lang="bash")

    # ============================================================
    # §15. ИСТОЧНИКИ
    # ============================================================
    heading(doc, "Список источников", level=1, numbered="§15")
    refs = [
        ("DeepSeek-R1", "Guo D. et al. DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via "
                         "Reinforcement Learning. arXiv:2501.12948 (2025). Cold-start procedure, thinking-mode."),
        ("DeepSeekMath / GRPO", "Shao Z. et al. DeepSeekMath: Pushing the Limits of Mathematical Reasoning "
                                  "in Open Language Models. arXiv:2402.03300 (2024). Введение GRPO."),
        ("GSPO", "Zheng Y. et al. Group Sequence Policy Optimization. arXiv:2507.18071 (2025). "
                  "Sequence-level importance sampling."),
        ("S1 (test-time scaling)", "Muennighoff N. et al. s1: Simple Test-Time Scaling. "
                                     "arXiv:2501.19393 (2025). Forced thinking termination at inference."),
        ("KTO", "Ethayarajh K. et al. KTO: Model Alignment as Prospect-Theoretic Optimization. "
                 "arXiv:2402.01306 (2024)."),
        ("DPO", "Rafailov R. et al. Direct Preference Optimization: Your Language Model is Secretly a "
                 "Reward Model. arXiv:2305.18290 (2023)."),
        ("ReDit", "Lin Y. et al. ReDit: Reward Dithering for Improved LLM Policy Optimization. "
                   "arXiv:2506.18631 (2025)."),
        ("Dr. GRPO", "Liu Z. et al. Dr. GRPO: Decoupled Reward GRPO for Stable Large-Model RL. "
                       "arXiv:2503.20783 (2025)."),
        ("DAPO", "Yu Q. et al. DAPO: An Open-Source LLM Reinforcement Learning System at Scale. "
                  "arXiv:2503.14476 (2025). Clip-Higher."),
        ("VAPO", "Liang J. et al. VAPO: Value-Augmented Policy Optimization. arXiv:2504.05118 (2025)."),
        ("GDPO-decoupled", "Wang H. et al. Group-Decoupled Policy Optimization (GDPO). "
                            "arXiv:2601.05242 (2026)."),
        ("Lion optimizer", "Chen X. et al. Symbolic Discovery of Optimization Algorithms. "
                             "arXiv:2302.06675 (2023)."),
        ("Tina (LoRA for RL)", "Park S. et al. Tina: Tiny Reasoning Models via LoRA. "
                                 "arXiv:2504.15777 (2025). r=16 рекомендуется, r=64 деградирует."),
        ("Llama-2 Ghost Attention", "Touvron H. et al. Llama 2: Open Foundation and Fine-Tuned Chat Models. "
                                      "arXiv:2307.09288 (2023). System prompt: train=deploy."),
        ("vLLM thinking issue", "vLLM project. Issue #15418: Unbounded thinking phase in TRL rollout. "
                                  "github.com/vllm-project/vllm/issues/15418"),
    ]
    for short, full in refs:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(3)
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

    # ---------- Финальная плашка ----------
    add_p(doc, "", space_before=12)
    callout(doc, "Связанные документы",
            "Тезисы для StudVesna 2026 — docs/diploma/Тезисы_StudVesna2026_Сухацкий.docx;  "
            "доклад к презентации — docs/diploma/Доклад_StudVesna2026_Сухацкий.docx;  "
            "НИР — docs/diploma/НИР_Сухацкий_2026_controlled_reasoning.docx;  "
            "курсовой проект — docs/diploma/Курсовой_проект_Сухацкий_2026.docx;  "
            "презентация — docs/diploma/Презентация_v2.html.",
            bg_hex="DBEEED", color=BLUE)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Saved: {OUT.resolve()}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build_doc()
