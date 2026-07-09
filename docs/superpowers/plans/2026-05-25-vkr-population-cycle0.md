# ВКР Population Cycle 0 (assembler + extraction) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Построить `scripts/assemble_vkr.py` (pandoc-гибрид: каркас + markdown-главы с OMML-формулами) + извлечь НИР/Курсовой в markdown, доказав pipeline на ≥1 реальной секции.

**Architecture:** `build_vkr_skeleton.build_document()` строит каркас в памяти; assembler для каждой секции с `chapters/{id}.md` гонит pandoc (`--reference-doc=образец` → стили + OMML), затем `deepcopy` body-фрагмента (кроме sectPr) после заголовка секции (placeholder удаляется). Маппинг заголовок→id в `SECTION_IDS`.

**Tech Stack:** Python 3.11, python-docx, pandoc 3.9 (`C:\Users\Maksim\AppData\Local\Pandoc\pandoc.exe`), pytest.

> **Spec:** `docs/superpowers/specs/2026-05-25-vkr-population-design.md`

---

## File Structure

| Файл | Ответственность |
|------|-----------------|
| `scripts/build_vkr_skeleton.py` | + `SECTION_IDS` dict, extract `build_document()` |
| `scripts/assemble_vkr.py` | find_pandoc / md_to_fragment / merge_fragment / assemble |
| `scripts/extract_sources.py` | pandoc docx→md (НИР, Курсовой) |
| `tests/test_assemble_vkr.py` | unit: find_pandoc, merge_fragment |
| `docs/diploma/chapters/*.md` | контент секций (markdown + LaTeX) |
| `docs/diploma/_extracted/*.md` | сырой извлечённый markdown (источник для нарезки) |

---

## Task 1: build_vkr_skeleton — SECTION_IDS + build_document()

**Files:** Modify `scripts/build_vkr_skeleton.py`

- [ ] **Step 1: Добавить SECTION_IDS dict** (после STRUCTURE)

```python
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
```

- [ ] **Step 2: Извлечь build_document() из main()**

Заменить текущую `main()` на:

```python
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
```

- [ ] **Step 3: Verify каркас всё ещё строится**

Run: `cd C:/Work/MITS && uv run python scripts/build_vkr_skeleton.py && uv run python scripts/verify_vkr_skeleton.py`
Expected: `[ok] skeleton built`, затем `RESULT: PASS` (13/13).

- [ ] **Step 4: Commit**

```bash
git add scripts/build_vkr_skeleton.py
git commit -m "refactor(019): build_vkr_skeleton — SECTION_IDS map + build_document()

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: assemble_vkr.py — find_pandoc()

**Files:** Create `scripts/assemble_vkr.py`, `tests/test_assemble_vkr.py`

- [ ] **Step 1: Failing-тест**

`tests/test_assemble_vkr.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import assemble_vkr as av


def test_find_pandoc_returns_existing_exe():
    p = av.find_pandoc()
    assert p, "pandoc не найден"
    assert Path(p).exists()
    assert "pandoc" in Path(p).name.lower()
```

- [ ] **Step 2: Run — FAIL**

Run: `cd C:/Work/MITS && uv run pytest tests/test_assemble_vkr.py -q`
Expected: FAIL — `ModuleNotFoundError: assemble_vkr`.

- [ ] **Step 3: Реализовать find_pandoc**

`scripts/assemble_vkr.py`:
```python
"""Сборка ВКР: skeleton (python-docx) + главы (pandoc md->docx с OMML) -> merge.

Usage: uv run python scripts/assemble_vkr.py
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

sys.path.insert(0, str(Path(__file__).parent))
from build_vkr_skeleton import OUT, TEMPLATE, SECTION_IDS, build_document

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
CHAPTERS = ROOT / "docs/diploma/chapters"


def find_pandoc() -> str:
    """Локатор pandoc: PATH -> %LOCALAPPDATA%\\Pandoc -> Program Files."""
    found = shutil.which("pandoc")
    if found:
        return found
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc" / "pandoc.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Pandoc" / "pandoc.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise RuntimeError("pandoc не найден (PATH/LOCALAPPDATA/ProgramFiles)")
```

- [ ] **Step 4: Run — PASS**

Run: `cd C:/Work/MITS && uv run pytest tests/test_assemble_vkr.py -q`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/assemble_vkr.py tests/test_assemble_vkr.py
git commit -m "feat(019): assemble_vkr — find_pandoc locator + test

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: merge_fragment() — вставка body фрагмента после заголовка

**Files:** Modify `scripts/assemble_vkr.py`, `tests/test_assemble_vkr.py`

- [ ] **Step 1: Failing-тест (синтетика)**

Добавить в `tests/test_assemble_vkr.py`:
```python
from docx import Document


def test_merge_fragment_replaces_placeholder_with_content():
    skel = Document()
    skel.add_paragraph("3.5. GSPO", style="Heading 2")
    skel.add_paragraph("[placeholder: что писать]", style="Normal")
    skel.add_paragraph("3.6. KTO", style="Heading 2")
    frag = Document()
    frag.add_paragraph("Первый абзац контента.", style="Normal")
    frag.add_paragraph("Второй абзац.", style="Normal")

    av.merge_fragment(skel, "3.5. GSPO", frag)
    texts = [p.text for p in skel.paragraphs]
    # placeholder ушёл, контент вставлен между 3.5 и 3.6
    assert "[placeholder: что писать]" not in texts
    i35 = texts.index("3.5. GSPO")
    assert texts[i35 + 1] == "Первый абзац контента."
    assert texts[i35 + 2] == "Второй абзац."
    assert texts[i35 + 3] == "3.6. KTO"
```

- [ ] **Step 2: Run — FAIL**

Run: `cd C:/Work/MITS && uv run pytest tests/test_assemble_vkr.py -q`
Expected: FAIL — нет `merge_fragment`.

- [ ] **Step 3: Реализовать merge_fragment**

Добавить в `scripts/assemble_vkr.py`:
```python
def merge_fragment(doc, heading_prefix: str, fragment_doc) -> int:
    """Вставляет body фрагмента после заголовка heading_prefix, удаляя placeholder.

    Возвращает число вставленных элементов. Raises если заголовок не найден.
    """
    body = doc.element.body
    heading_el = None
    for p in doc.paragraphs:
        if p.text.strip().startswith(heading_prefix):
            heading_el = p._element
            break
    if heading_el is None:
        raise ValueError(f"заголовок {heading_prefix!r} не найден")
    # удалить placeholder-параграф сразу после заголовка (текст начинается с '[')
    nxt = heading_el.getnext()
    if nxt is not None and nxt.tag == qn("w:p"):
        if Paragraph(nxt, doc).text.strip().startswith("["):
            body.remove(nxt)
    # вставить элементы фрагмента (кроме sectPr) после заголовка
    anchor = heading_el
    inserted = 0
    for child in list(fragment_doc.element.body):
        if child.tag == qn("w:sectPr"):
            continue
        new = deepcopy(child)
        anchor.addnext(new)
        anchor = new
        inserted += 1
    return inserted
```

- [ ] **Step 4: Run — PASS**

Run: `cd C:/Work/MITS && uv run pytest tests/test_assemble_vkr.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/assemble_vkr.py tests/test_assemble_vkr.py
git commit -m "feat(019): assemble_vkr — merge_fragment + test

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: md_to_fragment() + assemble() + main()

**Files:** Modify `scripts/assemble_vkr.py`

- [ ] **Step 1: Реализовать md_to_fragment + assemble + main**

Добавить в `scripts/assemble_vkr.py`:
```python
def md_to_fragment(md_path: Path, pandoc: str) -> Path:
    """pandoc md -> временный docx с OMML-формулами и стилями образца."""
    frag = Path(tempfile.gettempdir()) / f"_vkr_frag_{md_path.stem}.docx"
    subprocess.run(
        [pandoc, str(md_path), f"--reference-doc={TEMPLATE}", "-o", str(frag)],
        check=True, capture_output=True, text=True,
    )
    return frag


def assemble() -> None:
    doc = build_document()
    pandoc = find_pandoc()
    populated = []
    for heading, sid in SECTION_IDS.items():
        md = CHAPTERS / f"{sid}.md"
        if md.exists() and md.read_text(encoding="utf-8").strip():
            frag = md_to_fragment(md, pandoc)
            n = merge_fragment(doc, heading, Document(str(frag)))
            populated.append(f"{sid}(+{n})")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"[ok] assembled -> {OUT}")
    print(f"  наполнено секций: {len(populated)}: {populated}")


if __name__ == "__main__":
    assemble()
```

- [ ] **Step 2: Run (chapters/ пуст → пересборка каркаса)**

Run: `cd C:/Work/MITS && mkdir -p docs/diploma/chapters && uv run python scripts/assemble_vkr.py`
Expected: `[ok] assembled`, `наполнено секций: 0: []` (нет .md ещё).

- [ ] **Step 3: Verify каркас цел**

Run: `cd C:/Work/MITS && uv run python scripts/verify_vkr_skeleton.py`
Expected: `RESULT: PASS` (assemble без контента эквивалентен skeleton).

- [ ] **Step 4: Commit**

```bash
git add scripts/assemble_vkr.py
git commit -m "feat(019): assemble_vkr — md_to_fragment + assemble orchestration

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: extract_sources.py — pandoc docx→md

**Files:** Create `scripts/extract_sources.py`

- [ ] **Step 1: Реализовать extraction**

`scripts/extract_sources.py`:
```python
"""Извлечение готовых источников в markdown (pandoc docx->md) для нарезки в главы.

Usage: uv run python scripts/extract_sources.py
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from assemble_vkr import find_pandoc

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
EXTRACTED = ROOT / "docs/diploma/_extracted"
SOURCES = {
    "nir.md": ROOT / "docs/diploma/НИР_Сухацкий_2026_controlled_reasoning.docx",
    "kursovoy.md": ROOT / "docs/diploma/Курсовой_проект_Сухацкий_2026.docx",
}


def main() -> None:
    pandoc = find_pandoc()
    EXTRACTED.mkdir(parents=True, exist_ok=True)
    for out_name, src in SOURCES.items():
        out = EXTRACTED / out_name
        subprocess.run(
            [pandoc, str(src), "-t", "markdown", "--wrap=none", "-o", str(out)],
            check=True, capture_output=True, text=True,
        )
        n_lines = len(out.read_text(encoding="utf-8").splitlines())
        print(f"[ok] {src.name} -> {out} ({n_lines} строк)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run extraction**

Run: `cd C:/Work/MITS && uv run python scripts/extract_sources.py`
Expected: `[ok] НИР_... -> ...nir.md (N строк)`, `[ok] Курсовой_... -> ...kursovoy.md (M строк)`.

- [ ] **Step 3: Verify извлечённый markdown содержит формулы**

Run:
```bash
cd C:/Work/MITS && uv run python -c "
from pathlib import Path
nir = Path('docs/diploma/_extracted/nir.md').read_text(encoding='utf-8')
print('строк:', len(nir.splitlines()))
print('LaTeX-формулы (\$):', nir.count('\$'))
print('заголовки (#):', sum(1 for l in nir.splitlines() if l.startswith('#')))
"
```
Expected: строк > 100, формулы `$` > 0, заголовки > 0.

- [ ] **Step 4: Commit**

```bash
git add scripts/extract_sources.py docs/diploma/_extracted/nir.md docs/diploma/_extracted/kursovoy.md
git commit -m "feat(019): extract_sources — pandoc docx->md (НИР, Курсовой)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Demo — наполнить 1 секцию реальным контентом + verify pipeline

**Files:** Create `docs/diploma/chapters/03-5_gspo.md`

- [ ] **Step 1: Создать chapters/03-5_gspo.md из извлечённого НИР**

Открыть `docs/diploma/_extracted/nir.md`, найти секцию про ThinkingBudgetProcessor / GSPO (НИР 2.2/2.5). Скопировать релевантные абзацы + формулы в `docs/diploma/chapters/03-5_gspo.md`. Убедиться что есть ≥1 LaTeX-формула (например бюджет рассуждения или награда). Минимум — 2-3 абзаца + 1 формула. Пример структуры файла:

```markdown
Первая стадия дообучения — GSPO (Group Sequence Policy Optimization) с тройной
GDPO-нормированной наградой. Награда задаётся выражением:

$$R = 0{,}7 \cdot r_{\text{correct}} + 0{,}15 \cdot r_{\text{format}} + 0{,}15 \cdot r_{\text{socratic}}$$

Ключевой компонент — ThinkingBudgetProcessor: при достижении $90\%$ бюджета
(1350 из 1500 токенов) логит токена `</think>` усиливается на $+5{,}0$.
```

(Точный текст — из извлечённого nir.md, адаптированный под секцию 3.5.)

- [ ] **Step 2: Пересобрать ВКР с контентом**

Run: `cd C:/Work/MITS && uv run python scripts/assemble_vkr.py`
Expected: `наполнено секций: 1: ['03-5_gspo(+N)']` (N>0).

- [ ] **Step 3: Verify секция 3.5 наполнена + OMML присутствует + каркас цел**

Run:
```bash
cd C:/Work/MITS && uv run python -c "
from docx import Document
from docx.oxml.ns import qn
d = Document('docs/diploma/ВКР_Сухацкий_2026.docx')
paras = [p.text for p in d.paragraphs]
i = next(k for k,t in enumerate(paras) if t.strip().startswith('3.5.'))
after = paras[i+1].strip()
print('после 3.5:', repr(after[:50]))
print('placeholder убран:', not after.startswith('['))
print('OMML формул:', len(d.element.body.findall('.//'+qn('m:oMath'))))
" && uv run python scripts/verify_vkr_skeleton.py | tail -1
```
Expected: `placeholder убран: True`, `OMML формул: >0`, `RESULT: PASS`.

- [ ] **Step 4: Commit**

```bash
git add docs/diploma/chapters/03-5_gspo.md "docs/diploma/ВКР_Сухацкий_2026.docx"
git commit -m "feat(019): ВКР population — demo секция 3.5 GSPO (pandoc OMML pipeline доказан)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (выполнено при написании плана)

**1. Spec coverage:**
- assemble_vkr.py (pandoc-гибрид) → Tasks 2-4 ✓
- chapters/{id}.md + SECTION_IDS маппинг → Task 1 ✓
- Извлечение НИР/Курсовой → Task 5 ✓
- Идемпотентная пересборка → assemble() Task 4 ✓
- OMML формулы доказаны на реальном контенте → Task 6 ✓
- verify (skeleton цел) → Task 4 Step 3, Task 6 Step 3 ✓
- Полное наполнение всех глав — НЕ в этом цикле (spec: последующие циклы) ✓

**2. Placeholder scan:** Task 6 Step 1 содержит реальный пример md + указание извлечь точный текст из nir.md (контент-работа, не plan-failure — структура и формат заданы). Остальной код полный.

**3. Type consistency:** `find_pandoc()->str`, `md_to_fragment(md_path, pandoc)->Path`, `merge_fragment(doc, heading_prefix, fragment_doc)->int`, `assemble()->None`, `build_document()->Document`. Импорты из build_vkr_skeleton: `OUT, TEMPLATE, SECTION_IDS, build_document`. Консистентны между Tasks 1-6 и тестами. `CHAPTERS`/`EXTRACTED` пути согласованы.
