"""Генератор каркаса ВКР из образца (clone template, clear content, build structure).

Идемпотентный: перезапуск пересобирает каркас. Источник стилей — образец ВКР,
источник библиографии — DIPLOMA_PLAN.md.

Usage: uv run python scripts/build_vkr_skeleton.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import RGBColor

ROOT = Path(__file__).parent.parent
TEMPLATE = ROOT / "ВКР(10) (3).docx"
PLAN = ROOT / "docs/diploma/DIPLOMA_PLAN.md"
OUT = ROOT / "docs/diploma/ВКР_Сухацкий_2026.docx"

CUT_HEADING = "АННОТАЦИЯ"  # первый контент-параграф образца (Heading 1)

THEME = (
    "Разработка интеллектуальной системы обучения STEM-дисциплинам "
    "на основе мультиагентной архитектуры и дообученной языковой модели"
)
STUDENT = "Сухацкий М. О."
GROUP = "________"  # placeholder — группа (нет данных)
SUPERVISOR = "Корлякова М. О."


def clear_content_from_cutpoint(doc) -> None:
    """Удаляет body-элементы от параграфа CUT_HEADING до конца, сохраняя sectPr."""
    body = doc.element.body
    cut_el = None
    for p in doc.paragraphs:
        if p.text.strip() == CUT_HEADING:
            cut_el = p._element
            break
    if cut_el is None:
        raise RuntimeError(f"cut point {CUT_HEADING!r} not found in template")
    to_remove = []
    el = cut_el
    while el is not None:
        nxt = el.getnext()
        if el.tag != qn("w:sectPr"):  # sectPr (поля страницы) сохраняем
            to_remove.append(el)
        el = nxt
    for el in to_remove:
        body.remove(el)


def set_para_text(p, text: str, bold: bool = False) -> None:
    """Очищает runs параграфа и ставит один run (стиль/выравнивание сохраняются)."""
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    run = p.add_run(text)
    run.bold = bold


def fill_title_page(doc) -> None:
    """Наполняет пустые слоты титульника: тема, блок подписей, год."""
    paras = doc.paragraphs
    # 1) тема — параграф сразу после "НА ТЕМУ:"
    for i, p in enumerate(paras):
        if p.text.strip().startswith("НА ТЕМУ"):
            set_para_text(paras[i + 1], f"«{THEME}»", bold=True)
            break
    # 2) блок подписей + год: найти параграф "2025 год"
    for p in paras:
        if p.text.strip().endswith("год") and "2025" in p.text:
            # блок подписей перед годом (insert_paragraph_before вставляет выше `p`,
            # поэтому порядок вставки даёт сверху-вниз: студент, руководитель, год)
            p.insert_paragraph_before(f"Студент гр. {GROUP}: __________ {STUDENT}")
            p.insert_paragraph_before(f"Руководитель ВКР: __________ {SUPERVISOR}")
            set_para_text(p, "Калуга, 2026 г.")
            break


ANNOTATION = [
    "Расчётно-пояснительная записка на 70 страницах, 14 рисунках, 34 таблицах.",
    f"Тема работы: {THEME}.",
    "Объект исследования: процесс автоматизированного обучения STEM-дисциплинам.",
    "Предмет исследования: мультиагентная архитектура интеллектуальной обучающей системы "
    "с дообученной языковой моделью.",
    "Цель работы: разработка интеллектуальной обучающей системы, реализующей сократический "
    "диалог по пяти STEM-дисциплинам на основе мультиагентной архитектуры и дообученной модели Qwen3.5-9B.",
    "Актуальность работы: рост спроса на персонализированное STEM-образование при нехватке "
    "репетиторов; развитие больших языковых моделей открывает возможности автоматизации "
    "сократического обучения для русскоязычных учеников.",
    "Практическая значимость: готовая к использованию система для русскоязычных учеников 7–11 классов.",
    "Полученные результаты: предложен 4-стадийный пайплайн дообучения (GSPO → KTO → DPO → V-STaR-DPO), "
    "повысивший общую точность модели с 55,1% до 66,5% на STEM-бенчмарке из 3678 задач; "
    "реализована мультиагентная сократическая архитектура с отслеживанием знаний ученика.",
]

# (level, heading_text, placeholder_or_None)
STRUCTURE = [
    (
        "H1",
        "ВВЕДЕНИЕ",
        "[Введение: актуальность, цель, задачи, объект, предмет, научная новизна, практическая значимость — 3-4 стр.]",
    ),
    ("H1", "Глава 1. Аналитический обзор", None),
    (
        "H2",
        "1.1. Интеллектуальные обучающие системы (ITS)",
        "[ITS: история, архитектуры, обзор систем (Khan Academy, ALEKS, Khanmigo), таблица сравнения — 4 стр.]",
    ),
    (
        "H2",
        "1.2. Педагогические теории в контексте ITS",
        "[Сократический метод, CLT, ZPD, scaffolding, таксономия Блума — 3 стр.]",
    ),
    (
        "H2",
        "1.3. Большие языковые модели для образования",
        "[GPT/Qwen/DeepSeek, thinking mode, мультиагентные системы, обоснование Qwen3.5-9B — 4 стр.]",
    ),
    (
        "H2",
        "1.4. Обучение с подкреплением для языковых моделей",
        "[RLHF→GRPO→GSPO, rejection sampling, DPO, KTO, curriculum — 4 стр.]",
    ),
    (
        "H2",
        "1.5. Отслеживание знаний (Knowledge Tracing)",
        "[BKT, DKT, гибридные подходы — 3 стр.]",
    ),
    ("H2", "Выводы по главе 1", "[Формулировка требований к разрабатываемой системе]"),
    ("H1", "Глава 2. Проектирование системы", None),
    (
        "H2",
        "2.1. Требования к системе",
        "[Функциональные и нефункциональные требования, use cases — 3 стр.]",
    ),
    (
        "H2",
        "2.2. Общая архитектура",
        "[3-уровневая архитектура Frontend→Backend→AI Core — 4 стр.] [Рис.: блок-схема архитектуры]",
    ),
    (
        "H2",
        "2.3. Мультиагентная архитектура",
        "[Конвейер Profiler→Planner→Tutor→Verifier — 5 стр.] [Рис.: блок-схема конвейера]",
    ),
    ("H2", "2.4. Модель ученика и Knowledge Tracing", "[Dual BKT+DKT, граф навыков — 3 стр.]"),
    ("H2", "2.5. RAG-система", "[ChromaDB + embeddings, источники контекста — 2 стр.]"),
    (
        "H2",
        "2.6. Система стриминга",
        "[WebSocket, мост sync→async, парсинг thinking — 3 стр.] [Рис.: sequence diagram]",
    ),
    (
        "H2",
        "2.7. Проектирование пайплайна обучения",
        "[4-стадийная архитектура GSPO→KTO→DPO→V-STaR-DPO — 2 стр.] [Рис.: блок-схема пайплайна]",
    ),
    ("H2", "Выводы по главе 2", "[Спроектированная архитектура удовлетворяет требованиям]"),
    ("H1", "Глава 3. Реализация", None),
    (
        "H2",
        "3.1. Реализация фронтенда",
        "[Next.js 14, Zustand, useChat/useWebSocket, KaTeX — 4 стр.] [Рис.: скриншоты интерфейса]",
    ),
    (
        "H2",
        "3.2. Реализация бэкенда",
        "[FastAPI, JWT+Argon2, SQLAlchemy, WebSocket handler — 4 стр.]",
    ),
    (
        "H2",
        "3.3. Реализация мультиагентного ядра",
        "[BaseAgent, Orchestrator, 4 агента, листинги — 5 стр.]",
    ),
    ("H2", "3.4. Реализация LLM inference", "[LLMClient, Ollama, кеширование — 3 стр.]"),
    (
        "H2",
        "3.5. Stage 1 — GSPO с тройной GDPO-наградой",
        "[7 оптимизаций, ThinkingBudgetProcessor, гиперпараметры — 3 стр.]",
    ),
    (
        "H2",
        "3.6. Stage 2 — KTO Socratic alignment",
        "[Kahneman-Tversky, unpaired preferences, датасет — 3 стр.]",
    ),
    (
        "H2",
        "3.7. Stage 3 — DPO базовая polish",
        "[Preference pairs из KTO, полировка формата — 2 стр.]",
    ),
    (
        "H2",
        "3.8. Stage 4 — V-STaR-DPO composite",
        "[V-STaR generation N=4, composite scorer (correctness/PRM/no-spoiler), within-task pairing — 3-4 стр.]",
    ),
    (
        "H2",
        "3.9. Бенчмарк и инструменты оценки",
        "[build_eval_benchmark, evaluate_stage, SymPy/ChemPy — 2 стр.]",
    ),
    ("H2", "Выводы по главе 3", "[Система полностью реализована]"),
    ("H1", "Глава 4. Экспериментальное исследование", None),
    ("H2", "4.1. Методология эксперимента", "[Бенчмарк 3678 задач, метрики, верификация — 3 стр.]"),
    (
        "H2",
        "4.2. Результаты базовой модели",
        "[Qwen3.5-9B baseline 55,1%, разбивка по доменам — 2 стр.] [Таблица: per-domain baseline]",
    ),
    (
        "H2",
        "4.3. Результаты по стадиям обучения",
        "[Таблица Base→GSPO→KTO→DPO→V-STaR-DPO, кривые обучения — 5 стр.]",
    ),
    (
        "H2",
        "4.4. Ablation study",
        "[Вклад оптимизаций GSPO, KTO β-tuning, V-STaR composite weights — 3 стр.]",
    ),
    (
        "H2",
        "4.5. Качественный анализ",
        "[Примеры сократических диалогов, V-STaR within-task pairs — 3 стр.]",
    ),
    (
        "H2",
        "4.6. Анализ Knowledge Tracing",
        "[BKT vs DKT vs combined, adaptive difficulty — 2 стр.]",
    ),
    (
        "H2",
        "4.7. Детальный анализ V-STaR-DPO",
        "[Pareto-фронт correctness vs no-spoiler, per-domain gains — 3 стр.]",
    ),
    ("H2", "Выводы по главе 4", "[Подтверждение эффективности пайплайна и архитектуры]"),
    (
        "H1",
        "ЗАКЛЮЧЕНИЕ",
        "[Итоги по каждой задаче, достигнутые показатели, ограничения, направления развития — 2-3 стр.]",
    ),
]

# Маппинг текста заголовка -> id файла контента (docs/diploma/chapters/{id}.md)
SECTION_IDS = {
    "ВВЕДЕНИЕ": "00_introduction",
    "1.1. Интеллектуальные обучающие системы (ITS)": "01-1_its",
    "1.2. Педагогические теории в контексте ITS": "01-2_pedagogy",
    "1.3. Большие языковые модели для образования": "01-3_llm",
    "1.4. Обучение с подкреплением для языковых моделей": "01-4_rl",
    "1.5. Отслеживание знаний (Knowledge Tracing)": "01-5_kt",
    "2.1. Требования к системе": "02-1_requirements",
    "2.2. Общая архитектура": "02-2_architecture",
    "2.3. Мультиагентная архитектура": "02-3_multiagent",
    "2.4. Модель ученика и Knowledge Tracing": "02-4_kt",
    "2.5. RAG-система": "02-5_rag",
    "2.6. Система стриминга": "02-6_streaming",
    "2.7. Проектирование пайплайна обучения": "02-7_pipeline",
    "3.1. Реализация фронтенда": "03-1_frontend",
    "3.2. Реализация бэкенда": "03-2_backend",
    "3.3. Реализация мультиагентного ядра": "03-3_agents",
    "3.4. Реализация LLM inference": "03-4_inference",
    "3.5. Stage 1 — GSPO с тройной GDPO-наградой": "03-5_gspo",
    "3.6. Stage 2 — KTO Socratic alignment": "03-6_kto",
    "3.7. Stage 3 — DPO базовая polish": "03-7_dpo",
    "3.8. Stage 4 — V-STaR-DPO composite": "03-8_vstar",
    "3.9. Бенчмарк и инструменты оценки": "03-9_benchmark",
    "4.1. Методология эксперимента": "04-1_methodology",
    "4.2. Результаты базовой модели": "04-2_baseline",
    "4.3. Результаты по стадиям обучения": "04-3_per_stage",
    "4.4. Ablation study": "04-4_ablation",
    "4.5. Качественный анализ": "04-5_qualitative",
    "4.6. Анализ Knowledge Tracing": "04-6_kt",
    "4.7. Детальный анализ V-STaR-DPO": "04-7_vstar",
    "ЗАКЛЮЧЕНИЕ": "99_conclusion",
}

APPENDICES = [
    "ПРИЛОЖЕНИЕ А. Скриншоты интерфейса",
    "ПРИЛОЖЕНИЕ Б. Листинги ключевого кода",
    "ПРИЛОЖЕНИЕ В. Таблицы результатов",
    "ПРИЛОЖЕНИЕ Г. Примеры сократических диалогов",
    "ПРИЛОЖЕНИЕ Д. Диаграммы системы",
]


def add_heading1(doc, text: str):
    return doc.add_paragraph(text, style="Heading 1")


def add_placeholder(doc, text: str) -> None:
    """Курсивный серый placeholder-параграф под заголовком."""
    p = doc.add_paragraph(style="Normal")
    run = p.add_run(text)
    run.italic = True
    run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def build_annotation(doc) -> None:
    add_heading1(doc, "АННОТАЦИЯ")
    for line in ANNOTATION:
        doc.add_paragraph(line, style="Normal")


def add_toc_field(doc) -> None:
    """Вставляет Word TOC-поле { TOC \\o '1-3' } — собирается по F9 в Word."""
    add_heading1(doc, "СОДЕРЖАНИЕ")
    p = doc.add_paragraph()
    run = p.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    fld_text = OxmlElement("w:t")
    fld_text.text = "Оглавление обновится по F9 в Word"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    for el in (fld_begin, instr, fld_sep, fld_text, fld_end):
        run._element.append(el)


def build_structure(doc) -> None:
    for level, text, placeholder in STRUCTURE:
        style = "Heading 1" if level == "H1" else "Heading 2"
        doc.add_paragraph(text, style=style)
        if placeholder:
            add_placeholder(doc, placeholder)


def parse_bibliography(plan_path: Path) -> list[str]:
    """Извлекает пронумерованные источники '1. ...' из DIPLOMA_PLAN.md (DRY)."""
    text = plan_path.read_text(encoding="utf-8")
    items: dict[int, str] = {}
    for m in re.finditer(r"^(\d+)\.\s+(.*)$", text, flags=re.MULTILINE):
        num = int(m.group(1))
        if 1 <= num <= 60:
            line = re.sub(r"[*]", "", m.group(2)).strip()
            items[num] = line
    return [items[k] for k in sorted(items)]


def build_back_matter(doc) -> None:
    add_heading1(doc, "СПИСОК ЛИТЕРАТУРЫ")
    for i, src in enumerate(parse_bibliography(PLAN), 1):
        doc.add_paragraph(f"{i}. {src}", style="Normal")
    for app in APPENDICES:
        add_heading1(doc, app)
        add_placeholder(doc, f"[{app}: содержимое — см. план]")


def build_document():
    """Строит документ-каркас в памяти (без сохранения). Возвращает Document."""
    doc = Document(str(TEMPLATE))
    clear_content_from_cutpoint(doc)
    fill_title_page(doc)
    build_annotation(doc)
    add_toc_field(doc)
    build_structure(doc)
    build_back_matter(doc)
    return doc


def main() -> None:
    doc = build_document()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"[ok] skeleton built -> {OUT}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
