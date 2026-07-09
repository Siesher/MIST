"""Generate the ≤3-page project description (.docx) for Junior ML Contest 2026.

Hybrid results framing: lead with methodology + verified metrics; accuracy reported
honestly from the reproducible n=209 run (no overclaiming). Run from repo root:
    .venv/Scripts/python.exe docs/contest/build_description.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

OUT = Path(__file__).resolve().parent / "MITS_Junior_ML_Contest_2026.docx"

ACCENT = RGBColor(0x3B, 0x3B, 0x6E)  # indigo-ink
MUTED = RGBColor(0x6B, 0x6B, 0x7B)

doc = Document()

# --- base style: Times New Roman 11, tight margins to fit 3 pages ---
style = doc.styles["Normal"]
style.font.name = "Times New Roman"
style.font.size = Pt(10.5)
style.paragraph_format.space_after = Pt(4)
style.paragraph_format.line_spacing = 1.04

for section in doc.sections:
    section.top_margin = section.bottom_margin = Pt(40)
    section.left_margin = section.right_margin = Pt(46)


def h1(text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = ACCENT


def sub(text: str, italic: bool = False, size: float = 11, color=None, center=True) -> None:
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.italic = italic
    r.font.size = Pt(size)
    if color is not None:
        r.font.color.rgb = color
    p.paragraph_format.space_after = Pt(2)


def h2(text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.color.rgb = ACCENT


def body(text: str) -> None:
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def bullets(items: list[str]) -> None:
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(2)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        # support a leading "**Bold:** rest" pattern
        if it.startswith("**") and "**" in it[2:]:
            lead, rest = it[2:].split("**", 1)
            r = p.add_run(lead)
            r.bold = True
            p.add_run(rest)
        else:
            p.add_run(it)


# ============================ HEADER ============================
h1("MITS — Math Intelligent Tutoring System")
sub(
    "AI-репетитор по STEM на дообученной LLM с мультиагентной архитектурой и сократическим методом",
    italic=True,
    size=11,
)
sub("Максим Сухацкий · loxterpoi@gmail.com · Junior ML Contest 2026 (AI Talent Hub)", size=9, color=MUTED)
sub(
    "Репозиторий: github.com/Siesher/MITS · Модели: huggingface.co/Siesher · Стек: Python · PyTorch · FastAPI · Next.js",
    size=9,
    color=MUTED,
)

# ============================ PROBLEM ============================
h2("1. Проблема и актуальность")
body(
    "Массовые онлайн-платформы для обучения выдают готовые ответы, но не формируют навык рассуждения: "
    "увидев решение, студент перестаёт думать. Качественный персональный репетитор, который ведёт "
    "к ответу вопросами, а не подсказывает его, остаётся дорогим и малодоступным. MITS закрывает этот "
    "разрыв: это интеллектуальная обучающая система, которая ведёт студента сократическим диалогом — "
    "задаёт наводящие вопросы, даёт ступенчатые подсказки и символьно проверяет каждый шаг — по пяти "
    "STEM-доменам (математика, физика, химия, биология, информатика). Система построена на открытой "
    "языковой модели: это приватность данных студента, локальный запуск без вендор-лока и полный "
    "контроль над поведением модели."
)

# ============================ SOLUTION ============================
h2("2. Что это и как работает")
body(
    "MITS — это веб-приложение со стримингом ответов в реальном времени (WebSocket). Студент решает "
    "задачу в диалоге; система диагностирует его уровень, строит план занятия по графу знаний, ведёт "
    "сократический диалог и проверяет финальный ответ символьно (SymPy/ChemPy), а не «на доверии» к LLM. "
    "Поддерживается мультимодальный ввод — фотография рукописного решения распознаётся встроенным "
    "зрением модели (OCR). Освоение навыков отслеживается (Knowledge Tracing), что даёт персональные "
    "рекомендации, что повторить дальше. Проект доведён до рабочего продукта и развёртывается онлайн."
)

# ============================ ARCHITECTURE ============================
h2("3. Архитектура: мультиагентная система поверх графа знаний")
bullets(
    [
        "**Конвейер агентов: **Profiler (диагностика) → Planner (план занятия) → Tutor (сократический диалог) → Verifier (символьная проверка ответа).",
        "**Knowledge Forge: **живой граф навыков (83 узла × 88 рёбер, 6 типов узлов, 10 типов связей), который сам достраивается из проведённых сессий; валидность сгенерированных учебных траекторий — 100%.",
        "**ToM-Tutor (Theory of Mind): **агент моделирует пробелы и заблуждения студента и реранжирует навигацию по графу — попадание в корневой пробел выросло с 70% до 95% (A/B, 20 сценариев, 0 регрессий).",
        "**PathSlime: **bio-inspired планировщик (Lévy-Gaussian random walk) генерирует k различных траекторий обучения — разнообразие путей вместо единственного «правильного».",
        "**Knowledge Tracing: **связка BKT + DKT по 40+ навыкам для оценки освоения и рекомендаций.",
        "**Символьная верификация: **SymPy/ChemPy проверяют корректность ответа детерминированно — ключ к доверию к STEM-ассистенту.",
    ]
)

# ============================ ML CORE ============================
h2("4. ML-ядро: трёхстадийный RL-пайплайн дообучения")
body(
    "Базовая модель — Qwen3.5-9B Instruct (bf16, обучение на RTX PRO 6000 Blackwell 96GB через Unsloth/TRL). Цель "
    "дообучения — не «знать больше», а вести себя как наставник: направлять, а не выдавать решение."
)
bullets(
    [
        "**Стадия 1 — GSPO с тройной decoupled-наградой: **корректность (символьная проверка) + формат + сократичность, веса 0.40 / 0.15 / 0.45. Наибольший вес у сократичности — модель целенаправленно учат вести диалог, а не отвечать.",
        "**Стадия 2 — KTO (Kahneman-Tversky Optimization, arXiv 2402.01306): **выравнивание на непарных предпочтениях из реальных диалогов.",
        "**Стадия 3 — DPO: **финальная полировка предпочтений.",
        "**Данные (собственные): **3 875 сократических диалогов и 12 597 preference-пар — авто-генерация и фильтрация в рамках проекта.",
        "**В разработке — Стадия 4 (V-STaR-DPO): **No-Spoiler + Process-Reward-Model для устойчивости к «спойлерам» ответа.",
    ]
)

# ============================ RESULTS ============================
h2("5. Результаты")
body(
    "Оценка ведётся честно — приводятся воспроизводимые и подтверждённые метрики. Главный результат "
    "по решаемости: педагогическая RL-настройка не ухудшает сильную базу — на воспроизводимом прогоне "
    "дообученная модель идёт вровень с базовой при выросшей доле наводящих ходов. Системные метрики "
    "агентов измерены отдельными A/B и валидационными прогонами."
)

tbl = doc.add_table(rows=1, cols=3)
tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
tbl.style = "Light Grid Accent 1"
hdr = tbl.rows[0].cells
for c, t in zip(hdr, ("Метрика", "Значение", "Как измерено")):
    c.paragraphs[0].add_run(t).bold = True
    c.paragraphs[0].runs[0].font.size = Pt(9.5)

rows = [
    (
        "Решаемость задач (дообученная vs база)",
        "70,3% vs 69,4%",
        "воспроизводимый прогон, n=209, self-consistency, llama-server",
    ),
    ("ToM-навигация: попадание в корневой пробел", "70% → 95%", "A/B на 20 сценариях, 0 регрессий"),
    ("Граф знаний: валидность учебных путей", "100% (нарушений границы 0%)", "Knowledge Forge, 83 узла × 88 рёбер"),
    ("Корректность финального ответа", "детерминированная проверка", "SymPy / ChemPy на каждом ответе"),
    ("Расширенная оценка", "бенчмарк из 3 678 задач", "MGSM + ruMMLU + собственные (в дипломной работе)"),
]
for name, val, how in rows:
    cells = tbl.add_row().cells
    for cell, text in zip(cells, (name, val, how)):
        cell.paragraphs[0].add_run(text).font.size = Pt(9.5)

# ============================ STACK ============================
h2("6. Технологический стек")
bullets(
    [
        "**Обучение: **PyTorch, Unsloth, TRL (GSPO/GRPO, KTO, DPO), PEFT, Transformers; SymPy/ChemPy для наград и верификации.",
        "**Инференс: **llama.cpp / llama-server (GGUF Q4_K_M, OpenAI-совместимый API), мультимодальный mmproj для зрения.",
        "**RAG и память: **ChromaDB, sentence-transformers, BKT/DKT, SQLite.",
        "**Backend: **FastAPI, SQLAlchemy, Alembic, JWT (Argon2), WebSocket-стриминг.",
        "**Frontend: **Next.js 14, TypeScript, Tailwind, shadcn/ui, Zustand.",
        "**Инфраструктура: **Docker; публичный доступ через reverse-туннель на VPS.",
    ]
)

# ============================ HOW BUILT ============================
h2("7. Как строился проект")
body(
    "Проект развивался по спецификационному процессу: каждая функция оформлялась как спецификация "
    "(что → план → задачи), реализовывалась и измерялась. Так последовательно выросли около двух "
    "десятков модулей — от ядра сократического диалога до Knowledge Forge, ToM-Tutor и PathSlime. "
    "Решения по архитектуре и обучению принимались по метрикам, а не «на глаз»."
)
bullets(
    [
        "**Итеративное дообучение: **после каждой RL-стадии — прогон бенчмарка и сравнение со стадией ниже; так подбирались веса награды и состав данных.",
        "**Собственные данные: **пайплайн авто-генерации и фильтрации обучающего корпуса (3 875 диалогов + 12 597 preference-пар).",
        "**Собственная оценка: **бенчмарк из 3 678 задач, символьная верификация ответов (SymPy/ChemPy) и self-consistency для устойчивости метрик.",
        "**Эволюция инференса: **от Ollama к llama.cpp / llama-server (GGUF, OpenAI-совместимый API) — ради 32K+ контекста и мультимодальности на доступном железе.",
    ]
)

# ============================ WHY SO ============================
h2("8. Почему проект устроен именно так")
bullets(
    [
        "**Открытая модель (Qwen3.5-9B): **приватность данных студента, локальный/оффлайн-запуск, отсутствие вендор-лока и платы за токен при интенсивном учебном использовании, полный контроль поведения.",
        "**Мультиагент, а не один промпт: **диагностика, планирование, ведение диалога и проверка — разные задачи с разными режимами отказа; разделение повышает надёжность и позволяет измерять каждый этап отдельно.",
        "**RL, а не только SFT: **«быть сократичным» — это поведение, а не знание; его эффективнее формировать наградой и предпочтениями. SFT убран — Instruct-база уже владеет диалогом.",
        "**Decoupled тройная награда: **награда только за корректность схлопывается в «выдать ответ» — противоположность цели; явный сократический сигнал (вес 0.45) удерживает наставническое поведение.",
        "**Символьная верификация, а не самооценка LLM: **в STEM есть эталон, поэтому правильность проверяется детерминированно (SymPy/ChemPy), а не «доверием» к модели, склонной к галлюцинациям.",
        "**Граф знаний + Knowledge Tracing: **персонализация и планирование требуют явной структуры навыков и модели освоения, а не «памяти в промпте».",
    ]
)

# ============================ WHY ============================
h2("9. Почему это сильный проект для трека «Искусственный интеллект»")
bullets(
    [
        "**Полный ML-цикл: **свои данные → дообучение (3 RL-стадии) → агентная система → продакшн-веб → деплой — а не одиночный ноутбук.",
        "**Покрывает сразу несколько направлений конкурса: **генеративный ИИ (LLM + мультимодальность), агентные системы, RAG, AI-ассистент, обучение с подкреплением.",
        "**Исследовательская новизна: **decoupled тройная награда под педагогику, ToM-агент моделирования студента, bio-inspired планировщик траекторий.",
        "**Самостоятельность: **собственная генерация данных, собственная система оценки и инфраструктура инференса.",
    ]
)

try:
    doc.save(OUT)
    print(f"saved: {OUT}")
except PermissionError:
    alt = OUT.with_name(OUT.stem + "_new.docx")
    doc.save(alt)
    print(f"WARNING: {OUT.name} is locked (open in Word?). Saved updated copy to: {alt}")
