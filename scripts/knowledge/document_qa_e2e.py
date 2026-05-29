"""Живой E2E-тест: отвечает ли тьютор на вопросы по PDF-статье ПОСЛЕ её изучения.

Демонстрирует достроенное звено document-RAG на реальной модели:
    PDF → текст (fitz) → DocumentRetriever.index() → на каждый вопрос
    retrieve(top-k) → живой mits-tutor отвечает → оценка корректности.

Ключ к достоверности — КОНТРОЛЬНАЯ АБЛЯЦИЯ. Каждый вопрос гоняется через одну и
ту же модель в двух режимах:
    A (closed-book) — без контекста: что модель знает «из головы»;
    B (open-book)   — с извлечёнными чанками изученной статьи.
Если B верен там, где A путается, прирост обусловлен ИЗВЛЕЧЕНИЕМ из источника, а
не априорным знанием модели. Поэтому взята ЧУЖАЯ работа (Фирсов, 3D из 2D, 2025)
— модель её гарантированно не видела.

Требует поднятый llama-swap на :8090 (модель mits-tutor).
Usage: uv run python scripts/knowledge/document_qa_e2e.py
"""

from __future__ import annotations

import sys
import time
from typing import List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

LLAMA_SWAP_URL = "http://127.0.0.1:8090"
MODEL = "mits-tutor"
PDF_PATH = "docs/diploma/Фирсов_ВКР_бакалавр.pdf"
SOURCE_ID = "firsov_vkr"
TOP_K = 5

# Вопросы с эталонными ответами по КОНКРЕТНЫМ фактам документа. key_facts —
# опорные факты для перекрёстной проверки присутствия в ответе.
QUESTIONS = [
    {
        "q": "Какую задачу решает разработанная в работе нейросетевая модель? Какова цель работы?",
        "gold": "Генерация (реконструкция) 3D-сцены на основе 2D-плана.",
        "key_facts": ["3d", "2d", "план"],
    },
    {
        "q": "Что является входом и что выходом нейросетевой модели?",
        "gold": "Вход — растровое изображение плана (стены, двери, окна, элементы интерьера); "
        "выход — полноценная трёхмерная модель, пригодная для CAD-систем.",
        "key_facts": ["план", "изображен", "трёхмерн", "cad"],
    },
    {
        "q": "Кто автор этой выпускной квалификационной работы и кто её научный руководитель?",
        "gold": "Автор — В.П. Фирсов, научный руководитель — М.О. Корлякова.",
        "key_facts": ["фирсов", "корлякова"],
    },
    {
        "q": "Сколько страниц, рисунков и источников содержит работа?",
        "gold": "66 страниц, 49 рисунков, 26 источников (а также 6 таблиц и 7 приложений).",
        "key_facts": ["66", "49", "26"],
    },
    {
        "q": "Какие основные проблемы возникают при решении задачи генерации 3D из 2D-плана? "
        "Назови несколько.",
        "gold": "Качество входных данных (аккуратный чертёж или набросок от руки, надписи); "
        "неоднозначность формы (плоский план без информации о глубине/объёме); высокая степень "
        "детализации; формат представления выхода (многовидовые изображения или облака точек "
        "вместо полноценных 3D-моделей).",
        "key_facts": ["качеств", "форм", "детализац", "выход"],
    },
    {
        "q": "Что такое FID (Fréchet inception distance) и что эта метрика измеряет?",
        "gold": "Метрика качества сгенерированных изображений; оценивает близость сгенерированных "
        "изображений к реальным данным, учитывая fidelity и diversity.",
        "key_facts": ["fid", "сгенерирован", "реальн"],
    },
    {
        "q": "Чем FID отличается от Inception Score и почему считается более надёжной метрикой?",
        "gold": "В отличие от Inception Score, FID учитывает реальные данные при оценке "
        "сгенерированных изображений, поэтому надёжнее и лучше коррелирует с оценкой качества "
        "человеком.",
        "key_facts": ["inception score", "реальн", "надёжн"],
    },
    {
        "q": "В каком вузе и на какой кафедре выполнена работа?",
        "gold": "МГТУ им. Н.Э. Баумана, кафедра «Системы автоматического управления» (ИУК3).",
        "key_facts": ["бауман", "автоматическ"],
    },
]


def _hr(title: str) -> None:
    print("\n" + "═" * 74)
    print(f"  {title}")
    print("═" * 74)


def check_llama_swap() -> bool:
    """Проверяет доступность llama-swap. Печатает инструкцию при сбое."""
    try:
        import requests

        r = requests.get(f"{LLAMA_SWAP_URL}/v1/models", timeout=5)
        models = [m.get("id") for m in r.json().get("data", [])]
        print(f"  llama-swap доступен. Модели: {models}")
        return True
    except Exception as e:
        print(f"  ❌ llama-swap недоступен: {e}")
        print(
            '  Запусти: cd "C:/OpenCode/llama-swap"; '
            "./llama-swap.exe --config llama-swap.yaml --listen :8090"
        )
        return False


def extract_pdf_text(path: str) -> str:
    """Извлекает текстовый слой PDF (vision не нужен — у документа есть текст)."""
    import fitz

    doc = fitz.open(path)
    pages = [doc[p].get_text().strip() for p in range(doc.page_count)]
    text = "\n\n".join(p for p in pages if p)
    print(f"  PDF {doc.page_count} стр. → {len(text)} символов текста извлечено")
    return text


def ask_model(client, question: str, context: Optional[str] = None) -> str:
    """Один вопрос к живой модели. context=None → closed-book, иначе open-book."""
    if context:
        prompt = (
            f"{context}\n\n"
            "Опираясь СТРОГО на материал из источника выше, ответь кратко и по существу "
            "на вопрос. Если в материале нет ответа — так и скажи.\n\n"
            f"Вопрос: {question}"
        )
    else:
        prompt = (
            "Ответь кратко и по существу на вопрос. Если не располагаешь точной "
            "информацией — честно скажи об этом, не выдумывай.\n\n"
            f"Вопрос: {question}"
        )
    try:
        resp = client.generate(prompt, temperature=0.3, max_tokens=1024, thinking=False)
    except TypeError:
        resp = client.generate(prompt)
    return (resp or "").strip()


def grade_answer(answer: str, gold: str, key_facts: List[str]) -> dict:
    """Оценивает ответ модели относительно эталона. Возвращает вердикт.

    Args:
        answer: ответ модели.
        gold: эталонный ответ.
        key_facts: опорные факты (подстроки в нижнем регистре), которые должны
            присутствовать в корректном ответе.

    Returns:
        dict с ключами:
            "verdict": "correct" | "partial" | "wrong"
            "reason": краткое обоснование (str)
            "matched": сколько key_facts найдено (int)
    """
    ans = (answer or "").lower()
    if not ans.strip():
        return {"verdict": "wrong", "reason": "пустой ответ", "matched": 0}

    matched = sum(1 for f in key_facts if f.lower() in ans)
    total = len(key_facts)

    # Детектор «отказ / не знаю» — в closed-book это ожидаемое поведение и
    # должно давать wrong, а не ломать оценку.
    refusal_markers = (
        "не распола",
        "не знаю",
        "нет информац",
        "не могу",
        "недостаточно",
        "не указан",
        "не приведен",
        "затрудняюсь",
        "неизвестно",
        "не содержит",
        "не имею",
        "к сожалению",
    )
    refused = any(m in ans for m in refusal_markers)

    if total == 0:  # защитная ветка: нет опорных фактов
        verdict = "wrong" if refused else "partial"
        return {"verdict": verdict, "reason": "нет key_facts для проверки", "matched": 0}

    ratio = matched / total

    # Отказ при неполном покрытии фактов → wrong (хеджирование, не частичный ответ).
    if refused and ratio < 0.75:
        return {
            "verdict": "wrong",
            "reason": f"модель отказалась/не уверена; {matched}/{total} фактов",
            "matched": matched,
        }

    if ratio >= 0.75:
        verdict = "correct"
    elif matched >= 1:
        verdict = "partial"
    else:
        verdict = "wrong"

    return {
        "verdict": verdict,
        "reason": f"{matched}/{total} ключевых фактов найдено (ratio={ratio:.2f})",
        "matched": matched,
    }


def main() -> int:
    _hr("0. Проверка llama-swap (:8090)")
    if not check_llama_swap():
        return 2

    from src.knowledge.document_retriever import DocumentRetriever
    from src.models.openai_llm_client import OpenAICompatLLMClient

    _hr(f"1. Изучение статьи: {PDF_PATH}")
    text = extract_pdf_text(PDF_PATH)

    retriever = DocumentRetriever()  # эмбеддинги paraphrase-multilingual-MiniLM
    n_chunks = retriever.index(SOURCE_ID, text)
    print(f"  Проиндексировано чанков: {n_chunks} (режим эмбеддингов)")

    client = OpenAICompatLLMClient(model=MODEL)

    _hr("2. Контрольная абляция: closed-book (A) vs open-book (B)")
    rows = []
    for i, item in enumerate(QUESTIONS, 1):
        q = item["q"]
        print(f"\n  ── Вопрос {i}/{len(QUESTIONS)} ──")
        print(f"  Q: {q}")
        print(f"  Эталон: {item['gold']}")

        t0 = time.time()
        ans_a = ask_model(client, q, context=None)
        chunks = retriever.retrieve(q, source_ids=[SOURCE_ID], top_k=TOP_K)
        ctx = retriever.to_prompt_context(chunks)
        ans_b = ask_model(client, q, context=ctx)
        dt = time.time() - t0

        print(f"  [A closed-book] {ans_a[:280]}")
        print(f"  [B open-book ]  {ans_b[:280]}")
        top_score = chunks[0].score if chunks else 0.0
        print(f"  (top-{TOP_K} чанков, лучший score={top_score:.3f}, {dt:.1f}с)")

        try:
            g_a = grade_answer(ans_a, item["gold"], item["key_facts"])
            g_b = grade_answer(ans_b, item["gold"], item["key_facts"])
            print(f"  Вердикт: A={g_a['verdict']}  →  B={g_b['verdict']}")
            rows.append((i, g_a["verdict"], g_b["verdict"]))
        except NotImplementedError:
            print("  ⏳ grade_answer не реализован (TODO(human)) — вердикт пропущен.")
            rows.append((i, "—", "—"))

    _hr("3. Итог: эффект изучения статьи (A → B)")
    if rows and rows[0][1] != "—":
        a_correct = sum(1 for _, a, _ in rows if a == "correct")
        b_correct = sum(1 for _, _, b in rows if b == "correct")
        print(f"  Closed-book (A) корректных: {a_correct}/{len(rows)}")
        print(f"  Open-book   (B) корректных: {b_correct}/{len(rows)}")
        gained = sum(1 for _, a, b in rows if a != "correct" and b == "correct")
        print(f"  Вопросов, где изучение статьи дало корректный ответ (A✗→B✓): {gained}")
        ok = b_correct > a_correct
        print(
            f"\n  {'✅ ИЗУЧЕНИЕ СТАТЬИ УЛУЧШАЕТ ОТВЕТЫ' if ok else '⚠️  прироста нет — см. ответы'}"
        )
        return 0 if ok else 1

    print("  Вердикты не посчитаны: реализуй grade_answer (TODO(human)) и перезапусти.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
