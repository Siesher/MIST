"""Сборка тезисов для XXI Студенческой научной конференции МГТУ им. Н.Э. Баумана 2026.

Соответствует требованиям "Приложение 3 к распоряжению МГТУ им. Н.Э. Баумана":
- Times New Roman 12pt, одинарный интервал, без переносов
- Поля: верх/низ 2 см, лево 2,5 см, право 2 см; абзацный отступ 1,25 см
- Максимум 1,5 страницы A4, без таблиц и рисунков
- Максимум 3 автора, максимум 3 источника (ГОСТ 7.0.5-2008)

Запуск:
    python scripts/diploma/build_thesis_studvesna2026.py
"""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

OUT_PATH = Path(__file__).resolve().parents[2] / "docs" / "diploma" / "Тезисы_StudVesna2026_Сухацкий.docx"

UDC = "УДК 004.852"
TITLE = (
    "Метод управляемого рассуждения при обучении с подкреплением "
    "языковых моделей для STEM-репетитора"
)
AUTHOR_LINES = [
    ("Сухацкий Максим Олегович", "loxterpoi@gmail.com"),
    ("Корлякова Мария Олеговна", "mkorlyakova@yandex.ru"),
]
AFFILIATION = "КФ МГТУ имени Н.Э. Баумана"

BODY = [
    # Para 1 — contextualise problem domain
    "Современные языковые модели (LLM) с режимом рассуждения, такие как DeepSeek-R1 "
    "и Qwen3.5, демонстрируют высокое качество на задачах многошагового логического "
    "вывода благодаря механизму chain-of-thought (CoT), генерирующему промежуточные "
    "шаги в тегах <think>...</think> перед финальным ответом [1]. Применение таких "
    "моделей в интеллектуальных обучающих системах (Intelligent Tutoring Systems, "
    "ITS) по STEM-дисциплинам требует домен-специфичного дообучения методом Group "
    "Relative Policy Optimization (GRPO) [2] и его расширения — Group Sequence "
    "Policy Optimization (GSPO). Работа посвящена решению проблемы несходимости "
    "GRPO-дообучения моделей с режимом рассуждения.",

    # Para 2 — diagnosis of non-convergence
    "Критическая проблема состоит в том, что при rollout-генерации модель входит в "
    "неограниченный цикл рассуждений и не формирует закрывающий тег </think>. "
    "В результате 100% сгенерированных completions обрезаются по максимальной "
    "длине, награда равна нулю, и алгоритм GRPO не может вычислить значимые "
    "преимущества (advantages). Экспериментально проверены четыре подхода: "
    "включение режима рассуждения при MAX_COMPLETION=1024 и 4096 токенах даёт "
    "100% обрезку; отключение рассуждения снижает долю обрезок до 1,6%, однако "
    "корректность падает до нуля за 50 шагов, поскольку модель неспособна решать "
    "STEM-задачи без промежуточных выкладок. Систематический анализ литературы "
    "по RL-дообучению LLM (более 20 публикаций) позволил сформировать стратегию "
    "управляемого рассуждения.",

    # Para 3 — proposed method (with S1 differentiation)
    "Предложенный метод включает три взаимодополняющих компонента. Первый — "
    "ThinkingBudgetProcessor, процессор логитов (LogitsProcessor) HuggingFace "
    "Transformers, отслеживающий число сгенерированных токенов рассуждения по "
    "каждой последовательности батча: при достижении 90% бюджета (1350 из 1500 "
    "токенов) логит токена </think> усиливается на +5,0 (мягкое подталкивание), "
    "а при 100% — все прочие логиты устанавливаются в −∞, что гарантирует "
    "завершение фазы рассуждения. В отличие от подхода S1 [3], где "
    "принудительное завершение применяется на этапе test-time scaling, "
    "ThinkingBudgetProcessor встроен в rollout-генерацию RL и обеспечивает "
    "гарантированное завершение каждой из G completions группы, что "
    "необходимо для корректного вычисления преимуществ (advantages) в GRPO. "
    "Второй компонент — Cold-Start SFT: 200 шагов обучения с учителем на "
    "корректных решениях, отобранных методом rejection sampling из самой "
    "базовой модели с автоматической верификацией (SymPy для математики, "
    "ChemPy для химии); это повышает базовую точность с ≈5% до 15–30% и "
    "обеспечивает GRPO достаточное число положительных примеров. Третий — "
    "дитеринг наград (reward dithering): добавление гауссова шума σ=0,05 к "
    "бинарной награде формирует непрерывный ландшафт, так что группы с "
    "одинаковой нулевой наградой приобретают ненулевую дисперсию и генерируют "
    "обучающий сигнал.",

    # Para 4 — training setup
    "Апробация проводилась на модели Qwen3.5-9B (GPU NVIDIA RTX PRO 6000, "
    "102 ГБ VRAM) в рамках 3-стадийного пайплайна: стадия 1 — GSPO с тройной "
    "GDPO-нормированной наградой (корректность 0,7; формат 0,15; сократический "
    "стиль 0,15); стадия 2 — Kahneman-Tversky Optimization (KTO) для "
    "согласования (alignment) с сократическим методом обучения; стадия 3 — "
    "Direct Preference Optimization (DPO) для финальной полировки стиля. "
    "Ключевые гиперпараметры GSPO: LoRA r=16, α=32, learning rate 5·10⁻⁷, "
    "размер группы G=8, MAX_COMPLETION=2048 токенов, THINKING_BUDGET=1500 "
    "токенов, importance_sampling_level=sequence.",

    # Para 5 — benchmark description + base accuracy
    "Оценочный бенчмарк включает 3678 задач по пяти STEM-дисциплинам "
    "(математика, физика, химия, биология, информатика), собран из MGSM Russian "
    "(250), ruMMLU STEM (3210) и авторского набора (218). Верификация "
    "автоматическая: SymPy с символьным упрощением — для математики, "
    "ChemPy для стехиометрии, регулярные выражения с допуском — для физики, "
    "exact match — для биологии и информатики. Базовая точность Qwen3.5-9B "
    "(macro-average) составила 55,1% со значительным разбросом по доменам: "
    "79,1% — математика, 74,4% — физика, 46,7% — химия, 46,5% — информатика, "
    "28,6% — биология.",

    # Para 6 — results
    "Предложенный метод снижает долю обрезанных completions со 100% до 14,3%, "
    "а корректность на шаге 50 достигает 21,7%, что обеспечивает стабильный "
    "обучающий сигнал. 3-стадийный пайплайн повышает общую точность Qwen3.5-9B "
    "до 66,5%, то есть на 11,4 процентных пункта относительно базовой модели; "
    "по стадиям прирост составил: GSPO +8,4 п.п. (до 63,5%), KTO +1,3 п.п. "
    "(до 64,8%), DPO +1,7 п.п. (до 66,5%). Наибольший относительный прирост "
    "получен в биологии (+14,4 п.п., с 28,6% до 43,0%) и информатике (+12,1 "
    "п.п., с 46,5% до 58,6%) — доменах с низкой базовой точностью, куда "
    "curriculum learning направляет обучающий сигнал. Стадия KTO дополнительно "
    "повышает долю ответов с сократическими вопросами с 34% до 61%.",

    # Para 7 — conclusion
    "Разработанный метод управляемого рассуждения устраняет три ключевых "
    "барьера сходимости GSPO-дообучения thinking-моделей: неограниченное "
    "рассуждение, недостаток положительных примеров и нулевую дисперсию "
    "награды. Полученная модель демонстрирует стабильный прирост во всех пяти "
    "STEM-доменах без деградации в сильных и пригодна для использования в "
    "интеллектуальной обучающей системе для русскоязычных учеников 7–11 "
    "классов.",
]

REFERENCES = [
    "1. Guo D. et al. DeepSeek-R1: Incentivizing Reasoning Capability in LLMs "
    "via Reinforcement Learning [Electronic resource]. URL: "
    "https://arxiv.org/abs/2501.12948 (access date: 20.03.2026).",

    "2. Shao Z. et al. DeepSeekMath: Pushing the Limits of Mathematical "
    "Reasoning in Open Language Models [Electronic resource]. URL: "
    "https://arxiv.org/abs/2402.03300 (access date: 20.03.2026).",

    "3. Muennighoff N. et al. s1: Simple Test-Time Scaling [Electronic "
    "resource]. URL: https://arxiv.org/abs/2501.19393 (access date: 20.03.2026).",
]


def _set_default_font(doc: Document) -> None:
    """Задаёт Times New Roman 12pt как шрифт по умолчанию для Normal."""
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), "Times New Roman")


def _suppress_hyphens_globally(doc: Document) -> None:
    """Отключает автоматический перенос слов на уровне документа."""
    settings = doc.settings.element
    auto_hyph = OxmlElement("w:autoHyphenation")
    auto_hyph.set(qn("w:val"), "false")
    settings.append(auto_hyph)


def _apply_para_defaults(p, *, indent: bool = True) -> None:
    pf = p.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if indent:
        pf.first_line_indent = Cm(1.25)

    # Per-paragraph belt-and-braces: suppress auto-hyphens
    ppr = p._p.get_or_add_pPr()
    suppress = OxmlElement("w:suppressAutoHyphens")
    suppress.set(qn("w:val"), "true")
    ppr.append(suppress)


def _add_run(p, text: str, *, bold: bool = False) -> None:
    run = p.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    run.bold = bold
    # Ensure Cyrillic also uses Times New Roman
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), "Times New Roman")


def build() -> Path:
    doc = Document()

    # Page margins
    section = doc.sections[0]
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2)

    _set_default_font(doc)
    _suppress_hyphens_globally(doc)

    # УДК — left-aligned, no indent
    p = doc.add_paragraph()
    _apply_para_defaults(p, indent=False)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_run(p, UDC)

    # Title — bold, left-aligned, no indent, no hyphenation
    p = doc.add_paragraph()
    _apply_para_defaults(p, indent=False)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_run(p, TITLE, bold=True)

    # Authors — right-aligned email via tab stop at right margin
    for name, email in AUTHOR_LINES:
        p = doc.add_paragraph()
        _apply_para_defaults(p, indent=False)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        # Tab stop at 16.5 cm (page width 21 − 2.5 left − 2 right = 16.5)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(16.5), WD_TAB_ALIGNMENT.RIGHT)
        _add_run(p, f"{name}\t{email}")

    # Affiliation line
    p = doc.add_paragraph()
    _apply_para_defaults(p, indent=False)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_run(p, AFFILIATION)

    # Body — justified, 1.25 cm indent
    for para_text in BODY:
        p = doc.add_paragraph()
        _apply_para_defaults(p, indent=True)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        _add_run(p, para_text)

    # References heading — centred, no indent
    p = doc.add_paragraph()
    _apply_para_defaults(p, indent=False)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p, "Список литературы")

    # References entries — justified, no indent
    for ref in REFERENCES:
        p = doc.add_paragraph()
        _apply_para_defaults(p, indent=False)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        _add_run(p, ref)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    path = build()
    total_body_chars = sum(len(p) for p in BODY)
    print(f"[OK] Saved: {path}")
    print(f"Body char count: {total_body_chars} (~{total_body_chars / 1800:.2f} A4 pages at 12pt)")
    print(f"References: {len(REFERENCES)} (template allows max 3)")
    print(f"Authors: {len(AUTHOR_LINES)} (template allows max 3)")
