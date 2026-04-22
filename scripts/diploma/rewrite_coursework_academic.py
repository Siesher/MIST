"""Apply supervisor feedback to Курсовой_проект_Сухацкий_2026.docx:

1. Replace one literary phrase (p77) with strict impersonal academic style.
2. Insert new section "2.1. Формализация агентной архитектуры" after the
   opening of Chapter 2 — formal definition, interface table, dataflow,
   invariants between components.

Run:
    python -X utf8 scripts/rewrite_coursework_academic.py

A .bak copy is kept automatically by the reformat script; this edit is
idempotent (running twice produces same file). Finally re-applies the GOST
formatting pass via reformat_coursework so all fonts/margins stay consistent.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

DOC_PATH = Path("C:/Work/MITS/docs/Курсовой_проект_Сухацкий_2026.docx")


# ─────────────────────────────────────────────────────────────────────
# Content
# ─────────────────────────────────────────────────────────────────────


LITERARY_REPLACE_FROM = "Этот организм в знаменитом эксперименте"

LITERARY_REWRITE_FULL = (
    "Биоинспирированные алгоритмы семейства Slime Mould Algorithm (SMA) [2] "
    "и его варианты 2023–2025 гг. основаны на наблюдаемой динамике миксомицета "
    "Physarum polycephalum. В работе [3] зафиксирована способность колонии данного "
    "организма находить кратчайшие пути в лабиринте посредством адаптивной конкуренции "
    "протоплазматических трубок: участки с повышенным потоком субстрата утолщаются, "
    "неэффективные — деградируют. Формальная модель процесса задаётся уравнением "
    "проводимости dD/dt = f(flow) − r·D, где D — проводимость ребра, flow — текущий "
    "поток через ребро, r — коэффициент деградации."
)


SECTION_TITLE = "2.1. Формализация агентной архитектуры"

SECTION_INTRO = (
    "Реализованная в рамках курсового проекта подсистема представляет собой "
    "композицию программных агентов, каждый из которых инкапсулирует одну "
    "подзадачу персонализированной навигации по графу знаний и формально "
    "описывается кортежем A = ⟨S, A, O, τ, ρ⟩, где S — пространство состояний, "
    "A — пространство действий, O — пространство наблюдений, "
    "τ : O × S → S — функция перехода, ρ : S → A — политика. "
    "Такая декомпозиция обеспечивает модульность, изолируемость отказов и "
    "возможность независимой замены отдельных компонент без модификации "
    "интерфейсов смежных модулей."
)

AGENT_SPECS = [
    (
        "Navigator (модуль Knowledge Forge, §2.2)",
        "Реализует детерминированный поиск кратчайшего пути по графу знаний методом Дейкстры. "
        "Входные параметры: идентификатор обучающегося s_id, целевой концепт t_id. "
        "Выходной объект: кортеж LearningPath = ⟨узлы, рёбра, суммарная стоимость, "
        "ожидаемое время⟩. Внутреннее состояние отсутствует; агент осуществляет "
        "запрос к сервису MasteryProvider и нормализует веса рёбер по текущему "
        "уровню владения концептами.",
    ),
    (
        "PathSlime (модуль бионспирированной оптимизации, §2.4)",
        "Генерирует k диверсифицированных путей к целевому концепту посредством "
        "композиции Lévy-возмущений и Gaussian-мутаций. Входные параметры: граф G, "
        "начальный узел n_s, целевой узел n_t, количество путей k ∈ {2, 3, 5}, "
        "стилевой профиль p ∈ {quick, gradual, example_rich, mixed}. "
        "Выходной объект: список путей, упорядоченный по многокритериальной "
        "fitness-функции. Агент stateless между вызовами; внутренняя динамика "
        "колоний сбрасывается по завершении run().",
    ),
    (
        "MentalModelAgent (модуль ToM-тьютора, §2.3)",
        "Строит модель психического состояния обучающегося (Theory of Mind) "
        "на основе истории диалога. Входные параметры: список сообщений сессии, "
        "текущий целевой концепт. Выходной объект: BeliefState = ⟨gap_concepts, "
        "misconceptions, confidence⟩. Агент stateful в рамках одной сессии; "
        "состояние обновляется монотонно по критерию неубывания уверенности "
        "при повторяющихся наблюдениях.",
    ),
    (
        "SessionAnalyzer (модуль живого графа знаний)",
        "Извлекает предложения по эволюции графа из трассы завершённой сессии. "
        "Входные параметры: SessionTrace с полями {session_id, student_id, "
        "concepts_touched, errors, hints_given, resolved, mastery_before, "
        "mastery_after}. Выходной объект: список объектов GraphProposal с "
        "типами {NEW_NODE, NEW_EDGE, MISCONCEPTION, REORDER}. Агент stateless; "
        "полученные предложения аккумулируются внешней очередью ProposalQueue.",
    ),
    (
        "GraphEvolver (модуль верификации предложений)",
        "Применяет верифицированные предложения к основному графу. "
        "Входные параметры: ProposalQueue, порог уверенности θ ∈ [0.5, 0.95]. "
        "Выходной объект: обновлённый граф G′ и статистика {accepted, rejected, "
        "skipped}. Агент stateful; использует двухуровневую верификацию "
        "(rule_based_verifier → LLM-верификатор) с транзакционной фиксацией "
        "изменений на диск.",
    ),
]


INTERFACE_TABLE = [
    [
        "Агент",
        "Вход",
        "Выход",
        "Состояние",
        "Зависимости",
    ],
    [
        "Navigator",
        "(s_id, t_id)",
        "LearningPath",
        "Отсутствует",
        "KnowledgeGraph, MasteryProvider",
    ],
    [
        "PathSlime",
        "(G, n_s, n_t, k, p)",
        "List[LearningPath]",
        "Отсутствует",
        "Navigator, LevySampler",
    ],
    [
        "MentalModelAgent",
        "messages, target_id",
        "BeliefState",
        "Сессионное",
        "LLMClient, KnowledgeGraph",
    ],
    [
        "SessionAnalyzer",
        "SessionTrace",
        "List[GraphProposal]",
        "Отсутствует",
        "Navigator",
    ],
    [
        "GraphEvolver",
        "ProposalQueue, θ",
        "G′, статистика",
        "Аккумулятивное",
        "rule_based_verifier, LLMClient",
    ],
]

DATAFLOW_DESCRIPTION = (
    "Последовательность вызовов агентов в рамках одного хода взаимодействия "
    "определяется следующим образом. На вход подсистемы поступает сообщение "
    "обучающегося m_t и текущее состояние сессии σ_t. Управление передаётся "
    "агенту Navigator, который вычисляет базовую траекторию обучения. "
    "Полученная траектория используется агентом PathSlime для генерации "
    "k альтернативных вариантов с учётом стилевых предпочтений. Далее "
    "MentalModelAgent обновляет BeliefState на основе m_t и истории диалога. "
    "Параллельно с завершением хода запускается фоновая процедура SessionAnalyzer, "
    "которая по накоплении порогового числа предложений (по умолчанию — 5) "
    "инициирует выполнение GraphEvolver для интеграции верифицированных "
    "изменений в основной граф. Асинхронный характер последней стадии "
    "обеспечивает инвариант отсутствия блокировки пользовательского потока."
)


INVARIANTS_INTRO = (
    "Корректность взаимодействия агентов поддерживается набором инвариантов, "
    "проверяемых на границах модульных интерфейсов:"
)

INVARIANTS = [
    "монотонность уровня владения: для последовательности состояний сессии "
    "σ_0, σ_1, …, σ_T выполняется m(σ_{t+1}) ≥ m(σ_t) − ε, где ε — допустимое "
    "отклонение (ε = 0.05), обусловленное вероятностным характером BKT-оценки;",
    "монотонность доверия ToM: для фиксированного наблюдения o уверенность "
    "BeliefState.confidence не убывает при повторяющихся подтверждающих свидетельствах;",
    "целостность графа: каждое ребро e ∈ E графа G ссылается на существующие "
    "вершины; транзакционная фиксация в методе GraphEvolver._apply_proposal "
    "гарантирует атомарность пары операций (add_node, add_edge);",
    "валидность путей: каждый путь p ∈ PathSlime.run() удовлетворяет условию "
    "предварительности: для любого ребра (u, v) ∈ p выполняется "
    "type((u, v)) ∈ {PREREQUISITE, PART_OF, GENERALIZES}, что исключает "
    "нарушение педагогической последовательности;",
    "идемпотентность верификации: повторное применение метода "
    "GraphEvolver.promote_ready() к одной и той же очереди предложений "
    "ProposalQueue при неизменном графе G даёт эквивалентный результат, "
    "что обеспечивает безопасность перезапуска процедуры.",
]


CLOSING = (
    "Представленная декомпозиция соответствует принципу разделения "
    "ответственности (Single Responsibility Principle) и обеспечивает "
    "возможность независимого тестирования каждого агента. Реализация "
    "интерфейсов описана в §2.2–2.5; экспериментальная проверка "
    "инвариантов приведена в главе 4."
)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _new_paragraph_after(ref_para, text: str, bold: bool = False, size: int = 14, align=None):
    """Insert a paragraph with content immediately after ref_para.

    Returns the new paragraph; text formatting matches GOST body style
    (Times New Roman, 14pt, justify, 1.5 line spacing, 1.25cm first-line indent).
    """
    new_p = OxmlElement("w:p")
    ref_para._p.addnext(new_p)
    # Wrap in a docx.Paragraph by re-accessing via parent
    from docx.text.paragraph import Paragraph

    para = Paragraph(new_p, ref_para._parent)
    run = para.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    if bold:
        run.font.bold = True
    # Set Cyrillic font binding
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(attr), "Times New Roman")

    # Paragraph format
    pf = para.paragraph_format
    pf.line_spacing = 1.5
    pf.first_line_indent = Cm(1.25) if not bold else Cm(0)
    if align is not None:
        para.alignment = align
    else:
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return para


def _new_list_item_after(ref_para, text: str) -> object:
    p = _new_paragraph_after(ref_para, "— " + text, size=14)
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.left_indent = Cm(1.25)
    return p


def _new_heading_after(ref_para, text: str, level: int = 2) -> object:
    """Insert a styled heading paragraph after ref_para."""
    from docx.text.paragraph import Paragraph

    new_p = OxmlElement("w:p")
    ref_para._p.addnext(new_p)
    para = Paragraph(new_p, ref_para._parent)
    # Try to apply Heading 2 style
    try:
        para.style = (
            ref_para.part.document.styles["Heading 2"]
            if level == 2
            else ref_para.part.document.styles["Heading 3"]
        )
    except KeyError:
        pass

    run = para.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.font.bold = True

    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(attr), "Times New Roman")

    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf = para.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(12)
    pf.space_after = Pt(6)
    return para


def _insert_table_after(ref_para, rows: list[list[str]]) -> object:
    """Insert a simple bordered table after ref_para."""

    doc = ref_para.part.document
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"

    for i, row_data in enumerate(rows):
        for j, cell_text in enumerate(row_data):
            cell = table.rows[i].cells[j]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(cell_text)
            run.font.name = "Times New Roman"
            run.font.size = Pt(11)
            if i == 0:
                run.font.bold = True
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = OxmlElement("w:rFonts")
                rPr.append(rFonts)
            for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                rFonts.set(qn(attr), "Times New Roman")
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(0)

    # Move table to after ref_para
    # The table is appended at end; we need to move its XML next to ref_para
    table_xml = table._tbl
    table_xml.getparent().remove(table_xml)
    ref_para._p.addnext(table_xml)
    return table


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print(f"Opening: {DOC_PATH}")
    doc = Document(str(DOC_PATH))

    # ── Pass 1: Replace literary phrase ────────────────────────────
    replaced = False
    for p in doc.paragraphs:
        if LITERARY_REPLACE_FROM in p.text:
            # Clear runs, add new single run with rewritten text
            # (we preserve paragraph-level formatting by not creating a new paragraph)
            for r in list(p.runs):
                r.text = ""
            run = p.add_run(LITERARY_REWRITE_FULL)
            run.font.name = "Times New Roman"
            run.font.size = Pt(14)
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = OxmlElement("w:rFonts")
                rPr.append(rFonts)
            for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                rFonts.set(qn(attr), "Times New Roman")
            replaced = True
            print(f"  ✓ rewrote literary phrase in paragraph: {p.text[:80]}...")
            break
    if not replaced:
        print("  ! literary phrase not found — maybe already rewritten, skipping")

    # ── Pass 2: Insert formal section ──────────────────────────────
    # Find anchor: first Heading 2 after "ГЛАВА 2" heading. We'll insert
    # the new section BEFORE the first 2.1/2.2 heading in chapter 2.

    if any("Формализация агентной архитектуры" in p.text for p in doc.paragraphs):
        print("  ! formalization section already present — skipping insert")
    else:
        anchor = None
        in_chapter_2 = False
        for p in doc.paragraphs:
            txt = p.text.strip()
            if "ГЛАВА 2" in txt.upper():
                in_chapter_2 = True
                continue
            if in_chapter_2 and p.style.name.startswith("Heading 2"):
                anchor = p
                break
        if anchor is None:
            print("  ! could not find Chapter 2 anchor — skipping insert")
        else:
            print(f"  anchor paragraph: '{anchor.text[:60]}'")
            # Build the section in reverse order (each _new_X_after inserts AFTER ref,
            # so we anchor at the original anchor and insert section BEFORE it by
            # inserting at anchor's previous sibling).
            # Easier: insert AFTER a paragraph ABOVE anchor.
            # Find paragraph immediately before anchor to use as ref.
            ref = None
            prev = None
            for p in doc.paragraphs:
                if p._p is anchor._p:
                    ref = prev
                    break
                prev = p
            if ref is None:
                ref = anchor  # fallback — insert after the heading itself

            # Build section in natural order — each new paragraph becomes the next ref
            cur = _new_heading_after(ref, SECTION_TITLE, level=2)
            cur = _new_paragraph_after(cur, SECTION_INTRO)

            # Agent specs
            cur = _new_heading_after(cur, "Состав агентов", level=3)
            for name, desc in AGENT_SPECS:
                cur = _new_paragraph_after(cur, name + ". " + desc)

            # Interface table
            cur = _new_heading_after(cur, "Интерфейсы агентов", level=3)
            cur = _new_paragraph_after(
                cur,
                "Сводные характеристики агентов по входам, выходам, наличию состояния "
                "и межмодульным зависимостям приведены в таблице 2.1.",
            )
            _insert_table_after(cur, INTERFACE_TABLE)
            # insert a dummy paragraph after the table for continuation anchoring
            cur = _new_paragraph_after(
                cur,
                "Таблица 2.1 — Формальные интерфейсы агентов подсистемы.",
                size=12,
                align=WD_ALIGN_PARAGRAPH.CENTER,
            )

            # Dataflow
            cur = _new_heading_after(cur, "Поток данных между агентами", level=3)
            cur = _new_paragraph_after(cur, DATAFLOW_DESCRIPTION)

            # Invariants
            cur = _new_heading_after(cur, "Инварианты взаимодействия", level=3)
            cur = _new_paragraph_after(cur, INVARIANTS_INTRO)
            for inv in INVARIANTS:
                cur = _new_list_item_after(cur, inv)

            cur = _new_paragraph_after(cur, CLOSING)
            print(
                f"  ✓ inserted §2.1 formalization: {5 + len(AGENT_SPECS) + len(INVARIANTS) + 4} paragraphs + 1 table"
            )

    # ── Save ───────────────────────────────────────────────────────
    doc.save(str(DOC_PATH))
    print(f"\nSaved: {DOC_PATH}")

    # ── Re-apply GOST formatting ───────────────────────────────────
    print("\nRe-applying GOST formatting pass...")
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
        print(result.stdout.strip().split("\n")[-3:])  # last 3 lines
    else:
        print(f"  reformat stderr: {result.stderr[:300]}")


if __name__ == "__main__":
    main()
