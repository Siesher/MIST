# Каркас ВКР .docx — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сгенерировать `docs/diploma/ВКР_Сухацкий_2026.docx` — корректно отформатированный скелет ВКР по образцу (титульник + аннотация + структура 4 глав + 40 источников), готовый под наполнение глава-за-главой.

**Architecture:** Идемпотентный скрипт `scripts/build_vkr_skeleton.py` клонирует образец `ВКР(10) (3).docx` как template: сохраняет титульную таблицу + титульные параграфы (p0-p24) + body-level `sectPr`, удаляет контент образца от «АННОТАЦИЯ» (p25) до конца, наполняет титульник реальными данными и строит структуру через стили образца (`Heading 1/2/3`, `Normal`).

**Tech Stack:** Python 3.11, python-docx, lxml (через python-docx OXML API). Verification — re-open сгенерированного .docx + assert структуры (не unit-test внешнего кода).

> **TDD-адаптация:** «failing test» = verification-функция показывает что структура ещё не построена; «passing test» = после реализации она проходит. Каждый Task: написать функцию → запустить скрипт → re-open .docx и проверить инкремент.

> **Spec:** `docs/superpowers/specs/2026-05-25-vkr-skeleton-design.md`

---

## File Structure

| Файл | Ответственность |
|------|-----------------|
| `scripts/build_vkr_skeleton.py` | Весь генератор каркаса (clone → clear → fill title → build structure → save) |
| `scripts/verify_vkr_skeleton.py` | Verification: re-open .docx + assert headings/styles/bibliography counts |
| `docs/diploma/ВКР_Сухацкий_2026.docx` | Выход (генерируется) |

Источник стилей: `ВКР(10) (3).docx` (read-only template). Источник 40 источников: `docs/diploma/DIPLOMA_PLAN.md` (парсится — DRY, single source of truth).

---

## Task 1: Scaffolding + clone-and-clear (body от cut point, sectPr сохранён)

**Files:**
- Create: `scripts/build_vkr_skeleton.py`

- [ ] **Step 1: Создать скрипт с clone + clear-from-cutpoint**

```python
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
from docx.oxml.ns import qn

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
TEMPLATE = ROOT / "ВКР(10) (3).docx"
PLAN = ROOT / "docs/diploma/DIPLOMA_PLAN.md"
OUT = ROOT / "docs/diploma/ВКР_Сухацкий_2026.docx"

CUT_HEADING = "АННОТАЦИЯ"  # первый контент-параграф образца (Heading 1)


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


def main() -> None:
    doc = Document(str(TEMPLATE))
    clear_content_from_cutpoint(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"[ok] cleared + saved skeleton base -> {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Запустить — verify титульник сохранён, контент удалён**

Run: `cd C:/Work/MITS && uv run python scripts/build_vkr_skeleton.py`
Expected: `[ok] cleared + saved skeleton base -> ...ВКР_Сухацкий_2026.docx`

- [ ] **Step 3: Проверить структуру результата inline**

Run:
```bash
cd C:/Work/MITS && uv run python -c "
from docx import Document
d=Document(r'docs/diploma/ВКР_Сухацкий_2026.docx')
texts=[p.text.strip() for p in d.paragraphs if p.text.strip()]
print('last 3 paras:', texts[-3:])
print('АННОТАЦИЯ present:', 'АННОТАЦИЯ' in texts)
print('НА ТЕМУ present:', any('НА ТЕМУ' in t for t in texts))
print('sectPr count:', len(d.element.body.findall(__import__('docx.oxml.ns',fromlist=['qn']).qn('w:sectPr'))))
"
```
Expected: `НА ТЕМУ present: True`, `АННОТАЦИЯ present: False` (контент удалён), `sectPr count: 1`, last paras = титульник («2025 год» или около).

- [ ] **Step 4: Commit**

```bash
git add scripts/build_vkr_skeleton.py
git commit -m "feat(019): ВКР skeleton — clone template + clear content from cutpoint

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Наполнить титульник (тема, студент, руководитель, год)

**Files:**
- Modify: `scripts/build_vkr_skeleton.py`

- [ ] **Step 1: Добавить helper + fill_title_page()**

Вставить ПЕРЕД `def main()`:

```python
THEME = (
    "Разработка интеллектуальной системы обучения STEM-дисциплинам "
    "на основе мультиагентной архитектуры и дообученной языковой модели"
)
STUDENT = "Сухацкий М. О."
SUPERVISOR = "Корлякова М. О."


def set_para_text(p, text: str, bold: bool = False) -> None:
    """Очищает runs параграфа и ставит один run с текстом (стиль/выравнивание сохраняются)."""
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    run = p.add_run(text)
    run.bold = bold


def fill_title_page(doc) -> None:
    """Наполняет пустые слоты титульника: тема, студент, руководитель, год."""
    paras = doc.paragraphs
    # 1) тема — параграф сразу после "НА ТЕМУ:"
    for i, p in enumerate(paras):
        if p.text.strip().startswith("НА ТЕМУ"):
            set_para_text(paras[i + 1], f"«{THEME}»", bold=True)
            break
    # 2) год: "2025 год" -> "Калуга, 2026 г." + вставить студента/руководителя перед ним
    for p in paras:
        if p.text.strip().endswith("год") and "2025" in p.text:
            p.insert_paragraph_before(f"Выполнил: студент группы ________  {STUDENT}")
            p.insert_paragraph_before(f"Руководитель: {SUPERVISOR}")
            set_para_text(p, "Калуга, 2026 г.")
            break
```

И в `main()` добавить вызов после `clear_content_from_cutpoint(doc)`:

```python
    fill_title_page(doc)
```

- [ ] **Step 2: Запустить скрипт**

Run: `cd C:/Work/MITS && uv run python scripts/build_vkr_skeleton.py`
Expected: `[ok] ...`

- [ ] **Step 3: Verify титульник наполнен**

Run:
```bash
cd C:/Work/MITS && uv run python -c "
from docx import Document
d=Document(r'docs/diploma/ВКР_Сухацкий_2026.docx')
txt='\n'.join(p.text for p in d.paragraphs)
print('тема:', 'мультиагентной архитектуры' in txt)
print('студент:', 'Сухацкий М. О.' in txt)
print('руководитель:', 'Корлякова М. О.' in txt)
print('год 2026:', '2026' in txt and '2025' not in txt)
"
```
Expected: все 4 строки `True`.

- [ ] **Step 4: Commit**

```bash
git add scripts/build_vkr_skeleton.py
git commit -m "feat(019): ВКР skeleton — fill title page (theme/student/supervisor/year)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Построить АННОТАЦИЮ

**Files:**
- Modify: `scripts/build_vkr_skeleton.py`

- [ ] **Step 1: Добавить add_heading1 helper + build_annotation()**

Вставить перед `def main()`:

```python
ANNOTATION = [
    "Расчётно-пояснительная записка на TODO[meta] страницах, TODO[meta] рисунках, TODO[meta] таблицах.",
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


def add_heading1(doc, text: str):
    return doc.add_paragraph(text, style="Heading 1")


def build_annotation(doc) -> None:
    add_heading1(doc, "АННОТАЦИЯ")
    for line in ANNOTATION:
        doc.add_paragraph(line, style="Normal")
```

В `main()` добавить после `fill_title_page(doc)`:

```python
    build_annotation(doc)
```

- [ ] **Step 2: Запустить + verify аннотация перед sectPr**

Run: `cd C:/Work/MITS && uv run python scripts/build_vkr_skeleton.py`

Run:
```bash
cd C:/Work/MITS && uv run python -c "
from docx import Document
from docx.oxml.ns import qn
d=Document(r'docs/diploma/ВКР_Сухацкий_2026.docx')
body=d.element.body
kids=[c.tag.split('}')[-1] for c in body.iterchildren()]
print('last body child is sectPr:', kids[-1]=='sectPr')  # контент НЕ после sectPr
txt='\n'.join(p.text for p in d.paragraphs)
print('АННОТАЦИЯ:', 'АННОТАЦИЯ' in txt)
print('объект:', 'Объект исследования' in txt)
print('4-стадийный:', '4-стадийный' in txt)
"
```
Expected: `last body child is sectPr: True`, `АННОТАЦИЯ: True`, `объект: True`, `4-стадийный: True`.

> Если `last body child is sectPr: False` — python-docx добавил контент после sectPr. Fix: в `build_annotation`/последующих заменить `doc.add_paragraph(...)` на insert-before-sectPr helper:
> ```python
> def add_body_p(doc, text, style):
>     sect = doc.element.body.find(qn("w:sectPr"))
>     p = doc.add_paragraph(text, style=style)
>     sect.addprevious(p._element)
>     return p
> ```
> и использовать его везде вместо `doc.add_paragraph`.

- [ ] **Step 3: Commit**

```bash
git add scripts/build_vkr_skeleton.py
git commit -m "feat(019): ВКР skeleton — build annotation block

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Построить структуру глав (заголовки + placeholder)

**Files:**
- Modify: `scripts/build_vkr_skeleton.py`

- [ ] **Step 1: Добавить STRUCTURE + build_structure()**

Вставить перед `def main()`. Формат записи: `(level, text, placeholder|None)`.

```python
from docx.shared import RGBColor

# (level, heading_text, placeholder_or_None)
STRUCTURE = [
    ("H1", "ВВЕДЕНИЕ", "[Введение: актуальность, цель, задачи, объект, предмет, научная новизна, практическая значимость — 3-4 стр.]"),
    ("H1", "Глава 1. Аналитический обзор", None),
    ("H2", "1.1. Интеллектуальные обучающие системы (ITS)", "[ITS: история, архитектуры, обзор систем (Khan Academy, ALEKS, Khanmigo), таблица сравнения — 4 стр.]"),
    ("H2", "1.2. Педагогические теории в контексте ITS", "[Сократический метод, CLT, ZPD, scaffolding, таксономия Блума — 3 стр.]"),
    ("H2", "1.3. Большие языковые модели для образования", "[GPT/Qwen/DeepSeek, thinking mode, мультиагентные системы, обоснование Qwen3.5-9B — 4 стр.]"),
    ("H2", "1.4. Обучение с подкреплением для языковых моделей", "[RLHF→GRPO→GSPO, rejection sampling, DPO, KTO, curriculum — 4 стр.]"),
    ("H2", "1.5. Отслеживание знаний (Knowledge Tracing)", "[BKT, DKT, гибридные подходы — 3 стр.]"),
    ("H2", "Выводы по главе 1", "[Формулировка требований к разрабатываемой системе]"),
    ("H1", "Глава 2. Проектирование системы", None),
    ("H2", "2.1. Требования к системе", "[Функциональные и нефункциональные требования, use cases — 3 стр.]"),
    ("H2", "2.2. Общая архитектура", "[3-уровневая архитектура Frontend→Backend→AI Core, обоснование технологий — 4 стр.] [Рис.: блок-схема архитектуры]"),
    ("H2", "2.3. Мультиагентная архитектура", "[Конвейер Profiler→Planner→Tutor→Verifier — 5 стр.] [Рис.: блок-схема конвейера]"),
    ("H2", "2.4. Модель ученика и Knowledge Tracing", "[Dual BKT+DKT, граф навыков — 3 стр.]"),
    ("H2", "2.5. RAG-система", "[ChromaDB + embeddings, источники контекста — 2 стр.]"),
    ("H2", "2.6. Система стриминга", "[WebSocket, мост sync→async, парсинг thinking — 3 стр.] [Рис.: sequence diagram]"),
    ("H2", "2.7. Проектирование пайплайна обучения", "[4-стадийная архитектура GSPO→KTO→DPO→V-STaR-DPO — 2 стр.] [Рис.: блок-схема пайплайна]"),
    ("H2", "Выводы по главе 2", "[Спроектированная архитектура удовлетворяет требованиям]"),
    ("H1", "Глава 3. Реализация", None),
    ("H2", "3.1. Реализация фронтенда", "[Next.js 14, Zustand, useChat/useWebSocket, KaTeX — 4 стр.] [Рис.: скриншоты интерфейса]"),
    ("H2", "3.2. Реализация бэкенда", "[FastAPI, JWT+Argon2, SQLAlchemy, WebSocket handler — 4 стр.]"),
    ("H2", "3.3. Реализация мультиагентного ядра", "[BaseAgent, Orchestrator, 4 агента, листинги — 5 стр.]"),
    ("H2", "3.4. Реализация LLM inference", "[LLMClient, Ollama, кеширование — 3 стр.]"),
    ("H2", "3.5. Stage 1 — GSPO с тройной GDPO-наградой", "[7 оптимизаций, ThinkingBudgetProcessor, гиперпараметры — 3 стр.]"),
    ("H2", "3.6. Stage 2 — KTO Socratic alignment", "[Kahneman-Tversky, unpaired preferences, датасет — 3 стр.]"),
    ("H2", "3.7. Stage 3 — DPO базовая polish", "[Preference pairs из KTO, полировка формата — 2 стр.]"),
    ("H2", "3.8. Stage 4 — V-STaR-DPO composite", "[V-STaR generation N=4, composite scorer (correctness/PRM/no-spoiler), within-task pairing — 3-4 стр.]"),
    ("H2", "3.9. Бенчмарк и инструменты оценки", "[build_eval_benchmark, evaluate_stage, SymPy/ChemPy — 2 стр.]"),
    ("H2", "Выводы по главе 3", "[Система полностью реализована]"),
    ("H1", "Глава 4. Экспериментальное исследование", None),
    ("H2", "4.1. Методология эксперимента", "[Бенчмарк 3678 задач, метрики, верификация — 3 стр.]"),
    ("H2", "4.2. Результаты базовой модели", "[Qwen3.5-9B baseline 55,1%, разбивка по доменам — 2 стр.] [Таблица: per-domain baseline]"),
    ("H2", "4.3. Результаты по стадиям обучения", "[Таблица Base→GSPO→KTO→DPO→V-STaR-DPO, кривые обучения — 5 стр.]"),
    ("H2", "4.4. Ablation study", "[Вклад оптимизаций GSPO, KTO β-tuning, V-STaR composite weights — 3 стр.]"),
    ("H2", "4.5. Качественный анализ", "[Примеры сократических диалогов, V-STaR within-task pairs — 3 стр.]"),
    ("H2", "4.6. Анализ Knowledge Tracing", "[BKT vs DKT vs combined, adaptive difficulty — 2 стр.]"),
    ("H2", "4.7. Детальный анализ V-STaR-DPO", "[Pareto-фронт correctness vs no-spoiler, per-domain gains — 3 стр.]"),
    ("H2", "Выводы по главе 4", "[Подтверждение эффективности пайплайна и архитектуры]"),
    ("H1", "ЗАКЛЮЧЕНИЕ", "[Итоги по каждой задаче, достигнутые показатели, ограничения, направления развития — 2-3 стр.]"),
]


def add_placeholder(doc, text: str) -> None:
    """Курсивный серый placeholder-параграф под заголовком."""
    p = doc.add_paragraph(style="Normal")
    run = p.add_run(text)
    run.italic = True
    run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def build_structure(doc) -> None:
    for level, text, placeholder in STRUCTURE:
        style = "Heading 1" if level == "H1" else "Heading 2"
        doc.add_paragraph(text, style=style)
        if placeholder:
            add_placeholder(doc, placeholder)
```

В `main()` добавить после `build_annotation(doc)`:

```python
    build_structure(doc)
```

- [ ] **Step 2: Запустить + verify counts**

Run: `cd C:/Work/MITS && uv run python scripts/build_vkr_skeleton.py`

Run:
```bash
cd C:/Work/MITS && uv run python -c "
from docx import Document
d=Document(r'docs/diploma/ВКР_Сухацкий_2026.docx')
h1=[p.text for p in d.paragraphs if p.style and p.style.name=='Heading 1']
h2=[p.text for p in d.paragraphs if p.style and p.style.name=='Heading 2']
print('H1:', len(h1), h1)
print('H2 count:', len(h2))
"
```
Expected: H1 включает АННОТАЦИЯ, ВВЕДЕНИЕ, 4 главы, ЗАКЛЮЧЕНИЕ (=8). H2 count = 32 (28 нумерованных + 4 «Выводы»).

- [ ] **Step 3: Commit**

```bash
git add scripts/build_vkr_skeleton.py
git commit -m "feat(019): ВКР skeleton — chapter structure with placeholders

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: СПИСОК ЛИТЕРАТУРЫ (парсинг 40 из плана) + ПРИЛОЖЕНИЯ + TOC

**Files:**
- Modify: `scripts/build_vkr_skeleton.py`

- [ ] **Step 1: Добавить parse_bibliography() + build_back_matter() + TOC field**

Вставить перед `def main()`:

```python
from docx.oxml import OxmlElement

APPENDICES = [
    "ПРИЛОЖЕНИЕ А. Скриншоты интерфейса",
    "ПРИЛОЖЕНИЕ Б. Листинги ключевого кода",
    "ПРИЛОЖЕНИЕ В. Таблицы результатов",
    "ПРИЛОЖЕНИЕ Г. Примеры сократических диалогов",
    "ПРИЛОЖЕНИЕ Д. Диаграммы системы",
]


def parse_bibliography(plan_path: Path) -> list[str]:
    """Извлекает пронумерованные источники '1. ...' из DIPLOMA_PLAN.md (DRY)."""
    text = plan_path.read_text(encoding="utf-8")
    items: dict[int, str] = {}
    for m in re.finditer(r"^(\d+)\.\s+(.*)$", text, flags=re.MULTILINE):
        num = int(m.group(1))
        if 1 <= num <= 60:  # источники нумеруются 1..40
            # markdown -> plain: убрать * и [ссылки]
            line = re.sub(r"[*]", "", m.group(2)).strip()
            items[num] = line
    return [items[k] for k in sorted(items)]


def add_toc_field(doc) -> None:
    """Вставляет Word TOC-поле { TOC \\o '1-3' } — собирается по F9 в Word."""
    add_heading1(doc, "СОДЕРЖАНИЕ")
    p = doc.add_paragraph()
    run = p.add_run()
    fld_begin = OxmlElement("w:fldChar"); fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    fld_sep = OxmlElement("w:fldChar"); fld_sep.set(qn("w:fldCharType"), "separate")
    fld_text = OxmlElement("w:t"); fld_text.text = "Оглавление обновится по F9 в Word"
    fld_end = OxmlElement("w:fldChar"); fld_end.set(qn("w:fldCharType"), "end")
    for el in (fld_begin, instr, fld_sep, fld_text, fld_end):
        run._element.append(el)


def build_back_matter(doc) -> None:
    add_heading1(doc, "СПИСОК ЛИТЕРАТУРЫ")
    sources = parse_bibliography(PLAN)
    for i, src in enumerate(sources, 1):
        doc.add_paragraph(f"{i}. {src}", style="Normal")
    for app in APPENDICES:
        add_heading1(doc, app)
        add_placeholder(doc, f"[{app}: содержимое — см. план]")
```

В `main()` — порядок: TOC идёт ПОСЛЕ аннотации, ПЕРЕД введением. Перепишем сборку в `main()`:

```python
def main() -> None:
    doc = Document(str(TEMPLATE))
    clear_content_from_cutpoint(doc)
    fill_title_page(doc)
    build_annotation(doc)
    add_toc_field(doc)        # СОДЕРЖАНИЕ (TOC field)
    build_structure(doc)      # Введение + 4 главы + Заключение
    build_back_matter(doc)    # Литература + приложения
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"[ok] skeleton built -> {OUT}")
```

- [ ] **Step 2: Запустить + verify bibliography 40 + TOC + appendices**

Run: `cd C:/Work/MITS && uv run python scripts/build_vkr_skeleton.py`

Run:
```bash
cd C:/Work/MITS && uv run python -c "
from docx import Document
d=Document(r'docs/diploma/ВКР_Сухацкий_2026.docx')
txt=[p.text for p in d.paragraphs]
bib=[t for t in txt if t and t[0].isdigit() and '. ' in t[:5]]
print('bib lines >=40:', len([t for t in bib if t.split('.')[0].isdigit()])>=40)
print('СОДЕРЖАНИЕ:', 'СОДЕРЖАНИЕ' in txt)
print('СПИСОК ЛИТЕРАТУРЫ:', 'СПИСОК ЛИТЕРАТУРЫ' in txt)
print('Приложений:', sum(1 for t in txt if t.startswith('ПРИЛОЖЕНИЕ')))
"
```
Expected: `bib lines >=40: True`, `СОДЕРЖАНИЕ: True`, `СПИСОК ЛИТЕРАТУРЫ: True`, `Приложений: 5`.

- [ ] **Step 3: Commit**

```bash
git add scripts/build_vkr_skeleton.py
git commit -m "feat(019): ВКР skeleton — TOC field + bibliography(40 parsed) + appendices

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Verification-скрипт + финальная проверка + commit

**Files:**
- Create: `scripts/verify_vkr_skeleton.py`

- [ ] **Step 1: Написать verification-скрипт (assert полной структуры)**

```python
"""Verify ВКР skeleton: re-open .docx и проверить структуру/стили/счётчики."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(__file__).parent.parent / "docs/diploma/ВКР_Сухацкий_2026.docx"


def main() -> int:
    d = Document(str(OUT))
    txt = [p.text.strip() for p in d.paragraphs]
    joined = "\n".join(txt)
    h1 = [p.text.strip() for p in d.paragraphs if p.style and p.style.name == "Heading 1"]
    h2 = [p.text.strip() for p in d.paragraphs if p.style and p.style.name == "Heading 2"]
    body = d.element.body
    kids = [c.tag.split("}")[-1] for c in body.iterchildren()]

    checks = {
        "тема на титульнике": "мультиагентной архитектуры" in joined,
        "студент": "Сухацкий М. О." in joined,
        "руководитель": "Корлякова М. О." in joined,
        "год 2026 (не 2025)": "2026" in joined and "2025 год" not in joined,
        "АННОТАЦИЯ": "АННОТАЦИЯ" in h1,
        "СОДЕРЖАНИЕ": "СОДЕРЖАНИЕ" in h1,
        "ВВЕДЕНИЕ": "ВВЕДЕНИЕ" in h1,
        "4 главы": sum(1 for t in h1 if t.startswith("Глава")) == 4,
        "ЗАКЛЮЧЕНИЕ": "ЗАКЛЮЧЕНИЕ" in h1,
        "СПИСОК ЛИТЕРАТУРЫ": "СПИСОК ЛИТЕРАТУРЫ" in h1,
        "5 приложений": sum(1 for t in h1 if t.startswith("ПРИЛОЖЕНИЕ")) == 5,
        "H2 >= 32": len(h2) >= 32,
        "sectPr последний": kids[-1] == "sectPr",
        "контент перед sectPr": kids.index("sectPr") == len(kids) - 1,
    }
    ok = all(checks.values())
    for name, val in checks.items():
        print(f"  [{'OK' if val else 'FAIL'}] {name}")
    print(f"\nH1={len(h1)} H2={len(h2)} paras={len(txt)}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Запустить verification**

Run: `cd C:/Work/MITS && uv run python scripts/verify_vkr_skeleton.py`
Expected: все строки `[OK]`, `RESULT: PASS`, exit 0.

- [ ] **Step 3: Открыть .docx визуально (sanity)**

Run: `cd C:/Work/MITS && start "" "docs/diploma/ВКР_Сухацкий_2026.docx"`
Проверить глазами: титульник (министерство-шапка, тема, ФИО, год), аннотация, заголовки глав со стилями, оглавление-поле, 40 источников. Обновить TOC: Ctrl+A → F9 → «Обновить целиком».

- [ ] **Step 4: Commit verification + результат**

```bash
git add scripts/verify_vkr_skeleton.py docs/diploma/ВКР_Сухацкий_2026.docx
git commit -m "feat(019): ВКР skeleton — verification script + generated skeleton .docx

Все проверки PASS: титульник, аннотация, 4 главы, 32 H2, 40 источников, 5 приложений, sectPr сохранён.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (выполнено при написании плана)

**1. Spec coverage:**
- Section 1 (build approach A, clone+clear, sectPr) → Task 1 ✓
- Section 2 титульник → Task 2 ✓; аннотация → Task 3 ✓; структура заголовков → Task 4 ✓; библиография 40 + TOC + приложения → Task 5 ✓; формат-решения (TOC field, регистр, 40 источников) → Tasks 4-5 ✓
- Section 3 YAGNI (placeholder вместо прозы/рисунков, TODO[meta], V-STaR placeholder) → Task 3-4 (placeholder, TODO[meta]) ✓
- Verification (spec) → Task 6 ✓
- Open question (титульник в таблице) → разрешён: таблица [00] сохраняется (cut от p25), Task 1 ✓

**2. Placeholder scan:** `TODO[meta]` в аннотации — intentional (spec-defined). `[Раздел: …]` placeholder-параграфы — это **данные** каркаса (контент-маркеры для наполнения), не plan-failures. Весь код полный, выполнимый.

**3. Type consistency:** helper-имена консистентны: `set_para_text`, `add_heading1`, `add_placeholder`, `add_toc_field`, `parse_bibliography`, `build_*`. `main()` вызывает их в фикс. порядке (Task 5 Step 1). Константы THEME/STUDENT/SUPERVISOR определены в Task 2, переиспользуются в Task 3 (ANNOTATION). `CUT_HEADING`, `STRUCTURE`, `APPENDICES` — module-level. Fallback insert-before-sectPr helper документирован в Task 3 Step 2 на случай если add_paragraph кладёт после sectPr.
