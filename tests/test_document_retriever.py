"""Юнит-тесты DocumentRetriever (TDD, RED-фаза).

Тестируем keyword-fallback путь (use_embeddings=False) — детерминированный и
быстрый, без скачивания эмбеддинг-модели. Логика ранжирования (сортировка по
score, top_k, фильтр по source) общая с эмбеддинг-путём, поэтому keyword-тесты
валидируют ядро. Реальный эмбеддинг-путь проверяется в E2E-скрипте на живой
модели.
"""

from __future__ import annotations

import numpy as np

from src.knowledge.document_retriever import DocumentRetriever, RetrievedChunk

# Два тематически РАЗНЫХ блока — для проверки релевантности и фильтра по source.
TOPIC_PROG = (
    "Арифметическая прогрессия — это числовая последовательность, в которой каждый "
    "следующий член получается прибавлением одной и той же разности d к предыдущему. "
    "n-й член равен a_1 + (n-1)·d, а сумма первых n членов равна (a_1 + a_n)·n/2."
)
TOPIC_DALAMBER = (
    "Признак Даламбера сходимости ряда: если предел отношения последующего члена к "
    "предыдущему меньше единицы, ряд сходится, если больше единицы — расходится, а "
    "при равенстве единице признак ответа не даёт."
)

# Длинный текст для проверки многокусочного чанкинга.
LONG_TEXT = (TOPIC_PROG + "\n\n" + TOPIC_DALAMBER + "\n\n") * 4


def _kw_retriever(**kw) -> DocumentRetriever:
    """Retriever на keyword-пути (без эмбеддингов) — детерминированный."""
    return DocumentRetriever(use_embeddings=False, **kw)


def test_index_splits_long_text_into_multiple_chunks():
    r = _kw_retriever(chunk_chars=200, overlap=30)
    n = r.index("long", LONG_TEXT)
    assert n >= 2


def test_index_empty_text_returns_zero():
    r = _kw_retriever()
    assert r.index("empty", "") == 0
    assert r.index("blank", "   \n  ") == 0


def test_retrieve_ranks_relevant_chunk_first():
    r = _kw_retriever()
    r.index("prog", TOPIC_PROG)
    r.index("dal", TOPIC_DALAMBER)

    hits = r.retrieve("чему равна разность арифметической прогрессии", top_k=1)

    assert len(hits) == 1
    assert isinstance(hits[0], RetrievedChunk)
    assert "прогресс" in hits[0].text.lower()
    assert hits[0].source_id == "prog"


def test_retrieve_respects_top_k():
    r = _kw_retriever(chunk_chars=200, overlap=30)
    r.index("long", LONG_TEXT)
    hits = r.retrieve("прогрессия", top_k=2)
    assert len(hits) <= 2


def test_retrieve_on_empty_index_returns_empty_list():
    r = _kw_retriever()
    assert r.retrieve("любой вопрос") == []


def test_retrieve_filters_by_source_id():
    r = _kw_retriever()
    r.index("prog", TOPIC_PROG)
    r.index("dal", TOPIC_DALAMBER)

    hits = r.retrieve("сходимость ряда признак", source_ids=["dal"], top_k=5)

    assert hits, "ожидался хотя бы один результат из источника dal"
    assert all(h.source_id == "dal" for h in hits)


def test_to_prompt_context_includes_chunk_text():
    r = _kw_retriever()
    r.index("prog", TOPIC_PROG)
    hits = r.retrieve("арифметическая прогрессия", top_k=1)

    ctx = r.to_prompt_context(hits)

    assert ctx.strip()
    # В контекст должен попасть фрагмент исходного текста.
    assert "прогресс" in ctx.lower()


def test_to_prompt_context_empty_returns_empty_string():
    r = _kw_retriever()
    assert r.to_prompt_context([]) == ""


class _FakeEmbedder:
    """Детерминированный эмбеддер (DI): вектор = [есть «прогресс», есть «даламбер»].

    Позволяет проверить эмбеддинг-путь ранжирования без загрузки реальной модели.
    """

    def encode(self, texts, normalize_embeddings: bool = True, **_):
        vecs = []
        for t in texts:
            tl = t.lower()
            v = np.array([1.0 if "прогресс" in tl else 0.0, 1.0 if "даламбер" in tl else 0.0])
            norm = np.linalg.norm(v)
            vecs.append(v / norm if (normalize_embeddings and norm) else v)
        return np.array(vecs)


def test_retrieve_uses_injected_embedder_for_ranking():
    r = DocumentRetriever(use_embeddings=True, embedder=_FakeEmbedder())
    r.index("prog", TOPIC_PROG)
    r.index("dal", TOPIC_DALAMBER)

    hits = r.retrieve("объясни арифметическую прогрессию", top_k=1)

    assert len(hits) == 1
    assert hits[0].source_id == "prog"
    assert hits[0].score > 0.5
