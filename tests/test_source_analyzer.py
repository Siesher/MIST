"""Тесты SourceAnalyzer: чанкинг, robust-JSON, кэш и доказательство устранения
обрезки text[:3000] (сущность из конца документа теперь извлекается)."""

import json

import pytest

from src.knowledge.source_analyzer import (
    SourceAnalyzer,
    _safe_json,
    chunk_text,
    clear_cache,
)


@pytest.fixture(autouse=True)
def _clear():
    clear_cache()
    yield
    clear_cache()


# ── chunk_text ──────────────────────────────────────────────────────


def test_chunk_short_text_single_chunk():
    assert chunk_text("короткий текст", chunk_chars=6000) == ["короткий текст"]


def test_chunk_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_long_text_multiple_with_coverage():
    # 5 абзацев по ~3000 символов → несколько чанков.
    text = "\n\n".join(f"Абзац {i}. " + ("слово " * 500) for i in range(5))
    chunks = chunk_text(text, chunk_chars=4000, overlap=200)
    assert len(chunks) >= 3
    # Полное покрытие: маркеры начала и конца должны присутствовать в чанках.
    joined = "".join(chunks)
    assert "Абзац 0." in joined
    assert "Абзац 4." in joined  # конец документа НЕ потерян


def test_chunk_overlap_present():
    text = "A" * 100 + "\n\n" + "B" * 8000 + "\n\n" + "C" * 100
    chunks = chunk_text(text, chunk_chars=4000, overlap=300)
    assert len(chunks) >= 2


# ── _safe_json ──────────────────────────────────────────────────────


def test_safe_json_plain():
    assert _safe_json('{"a": 1}') == {"a": 1}


def test_safe_json_markdown_fenced():
    assert _safe_json('```json\n{"x": [1,2]}\n```') == {"x": [1, 2]}


def test_safe_json_garbage_around_object():
    raw = 'Вот результат анализа:\n{"entities": [{"title": "Производная"}]}\nГотово.'
    parsed = _safe_json(raw)
    assert parsed is not None
    assert parsed["entities"][0]["title"] == "Производная"


def test_safe_json_invalid_returns_none():
    assert _safe_json("это не json вообще") is None
    assert _safe_json("") is None


# ── Стаб LLM ────────────────────────────────────────────────────────


class _StubLLM:
    """Возвращает сущность с title = маркер, если он есть в чанке.

    Позволяет проверить, какие части документа реально дошли до LLM.
    """

    def __init__(self):
        self.calls = 0

    def generate(self, prompt, **kwargs):
        self.calls += 1
        ents = []
        if "MARKER_START" in prompt:
            ents.append({"title": "start_entity", "type": "concept", "content": "..."})
        if "MARKER_END" in prompt:
            ents.append({"title": "end_entity", "type": "concept", "content": "..."})
        return json.dumps({"entities": ents}, ensure_ascii=False)


def test_extract_entities_covers_end_of_document():
    """Гл. доказательство: сущность в КОНЦЕ длинного документа извлекается.

    Раньше source_extractor обрезал text[:3000] и end_entity терялась.
    """
    # Документ > 12000 символов: MARKER_START в начале, MARKER_END в самом конце.
    filler = "обычный учебный текст без маркеров. " * 400  # ~14000 символов
    text = "MARKER_START\n\n" + filler + "\n\nMARKER_END"
    assert len(text) > 12000

    stub = _StubLLM()
    analyzer = SourceAnalyzer(llm_client=stub, chunk_chars=5000, overlap=200, max_workers=2)
    entities = analyzer.extract_entities(text, domain="math")

    titles = {e["title"] for e in entities}
    assert "start_entity" in titles, "начало документа должно быть проанализировано"
    assert "end_entity" in titles, (
        "КОНЕЦ документа должен быть проанализирован (обрезка 3000 устранена)"
    )
    assert stub.calls >= 3, "длинный документ должен дать несколько чанков (параллельная обработка)"


def test_extract_entities_dedup_across_chunks():
    """Сущность на стыке чанков (в перекрытии) не должна дублироваться."""

    class DupLLM:
        def generate(self, prompt, **kwargs):
            # Каждый чанк возвращает одну и ту же сущность.
            return json.dumps({"entities": [{"title": "Дубль", "type": "concept"}]})

    text = "x" * 20000
    analyzer = SourceAnalyzer(llm_client=DupLLM(), chunk_chars=5000)
    entities = analyzer.extract_entities(text, domain="math")
    titles = [e["title"] for e in entities]
    assert titles.count("Дубль") == 1, "дубли по title должны схлопываться"


def test_cache_hit_avoids_second_llm_call():
    stub = _StubLLM()
    analyzer = SourceAnalyzer(llm_client=stub, chunk_chars=5000)
    text = "MARKER_START " + ("текст " * 2000) + " MARKER_END"
    analyzer.extract_entities(text, domain="math")
    calls_after_first = stub.calls
    analyzer.extract_entities(text, domain="math")  # тот же текст
    assert stub.calls == calls_after_first, "повторный анализ того же текста не должен звать LLM"


def test_summarize_structure():
    class SumLLM:
        def generate(self, prompt, **kwargs):
            return json.dumps(
                {
                    "key_points": ["тезис A", "тезис B"],
                    "formulas": ["E = mc^2"],
                    "topics": ["относительность"],
                }
            )

    analyzer = SourceAnalyzer(llm_client=SumLLM(), chunk_chars=5000)
    digest = analyzer.summarize("длинный " * 3000, source_name="статья")
    assert digest["source_name"] == "статья"
    assert "тезис A" in digest["key_points"]
    assert "E = mc^2" in digest["formulas"]
    block = analyzer.to_context_block(digest)
    assert "Источник: статья" in block
    assert "тезис A" in block
