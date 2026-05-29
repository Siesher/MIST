"""DocumentRetriever — извлечение релевантных фрагментов изученного документа.

Достраивает недостающее звено document-RAG: при ingest полный текст источника
сохраняется, но в путь ответа тьютора попадал только дистиллированный граф
концептов. Этот модуль индексирует исходный текст по чанкам и по вопросу
возвращает top-k релевантных фрагментов — то, что на этапе 2 ляжет в
``TutoringContext.chunks`` и в промпт тьютора.

Два режима извлечения:
  * embeddings (по умолчанию) — sentence-transformers
    ``paraphrase-multilingual-MiniLM-L12-v2`` (та же модель, что у TutoringRAG),
    косинусная близость. Ловит переформулированные вопросы.
  * keyword-fallback — косинус по мешку слов (bag-of-words). Включается, если
    sentence-transformers недоступен или ``use_embeddings=False``.

Чанкинг переиспользует ``chunk_text`` из source_analyzer для согласованности.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

import numpy as np

from src.knowledge.source_analyzer import chunk_text

logger = logging.getLogger(__name__)

# Эмбеддинг-модель проекта (мультиязычная — тянет русский). Совпадает с TutoringRAG.
DEFAULT_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
# Для точного извлечения чанки мельче, чем при графовом анализе (там 6000).
DEFAULT_CHUNK_CHARS = 1000
DEFAULT_OVERLAP = 150

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    """Токенизация в нижний регистр (unicode-слова) для keyword-режима."""
    return _TOKEN_RE.findall(text.lower())


@dataclass
class RetrievedChunk:
    """Извлечённый фрагмент документа с оценкой релевантности."""

    text: str
    source_id: str
    chunk_index: int
    score: float


class DocumentRetriever:
    """Индексирует текст документов и извлекает релевантные чанки по запросу.

    Контракт:
      * ``index(source_id, text)`` — проиндексировать документ (один раз);
      * ``retrieve(query, ...)`` — получить top-k чанков на вопрос;
      * ``to_prompt_context(chunks)`` — собрать блок для промпта тьютора.

    Зависит от sentence-transformers (с graceful fallback на keyword-режим).
    """

    def __init__(
        self,
        use_embeddings: bool = True,
        model_name: str = DEFAULT_EMBED_MODEL,
        chunk_chars: int = DEFAULT_CHUNK_CHARS,
        overlap: int = DEFAULT_OVERLAP,
        embedder: Optional[Any] = None,
    ) -> None:
        """Инициализация ретривера.

        Args:
            use_embeddings: использовать векторный поиск (иначе keyword-fallback).
            model_name: имя sentence-transformers модели.
            chunk_chars: размер чанка в символах.
            overlap: перекрытие соседних чанков в символах.
            embedder: внедрённый эмбеддер с методом ``encode`` (для DI/тестов).
                Если задан, ``use_embeddings`` считается True независимо от модели.
        """
        self._chunk_chars = chunk_chars
        self._overlap = overlap

        # Хранилище проиндексированных чанков (параллельные списки).
        self._texts: List[str] = []
        self._sources: List[str] = []
        self._chunk_indices: List[int] = []
        self._embeddings: List[np.ndarray] = []  # по строке на чанк (нормированные)

        self._embedder = embedder
        self._use_embeddings = bool(use_embeddings or embedder is not None)

        if self._use_embeddings and self._embedder is None:
            self._embedder = self._load_embedder(model_name)
            if self._embedder is None:
                self._use_embeddings = False  # graceful fallback на keyword

        logger.info(
            "DocumentRetriever инициализирован: режим=%s",
            "embeddings" if self._use_embeddings else "keyword",
        )

    @staticmethod
    def _load_embedder(model_name: str) -> Optional[Any]:
        """Пытается загрузить sentence-transformers. None при недоступности."""
        try:
            from sentence_transformers import SentenceTransformer

            return SentenceTransformer(model_name)
        except Exception as e:  # модель/пакет недоступны — переходим на keyword
            logger.warning("sentence-transformers недоступен (%s) → keyword-режим", e)
            return None

    # ── Индексация ──────────────────────────────────────────────────────

    def index(self, source_id: str, text: str) -> int:
        """Индексирует документ: чанкинг (+ эмбеддинг). Возвращает число чанков.

        Args:
            source_id: идентификатор источника (для фильтрации при retrieve).
            text: полный текст документа.

        Returns:
            Количество добавленных чанков (0 для пустого текста).
        """
        chunks = chunk_text(text, self._chunk_chars, self._overlap)
        if not chunks:
            return 0

        if self._use_embeddings:
            matrix = self._encode(chunks)  # (len(chunks), dim), нормированные
        else:
            matrix = [None] * len(chunks)

        for i, chunk in enumerate(chunks):
            self._texts.append(chunk)
            self._sources.append(source_id)
            self._chunk_indices.append(i)
            self._embeddings.append(matrix[i])
        return len(chunks)

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        """Эмбеддинг списка текстов в нормированные векторы (косинус = dot)."""
        return np.asarray(self._embedder.encode(list(texts), normalize_embeddings=True))

    # ── Извлечение ──────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        source_ids: Optional[Sequence[str]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[RetrievedChunk]:
        """Возвращает top-k релевантных чанков по запросу.

        Args:
            query: вопрос/запрос.
            source_ids: ограничить поиск этими источниками (None — все).
            top_k: максимум результатов.
            min_score: минимальный score для включения.

        Returns:
            Список RetrievedChunk, отсортированный по убыванию score.
        """
        if not self._texts:
            return []

        # Индексы чанков, попадающие под фильтр по источнику.
        allowed = set(source_ids) if source_ids is not None else None
        candidates = [
            i for i in range(len(self._texts)) if allowed is None or self._sources[i] in allowed
        ]
        if not candidates:
            return []

        scores = self._score(query, candidates)

        ranked = sorted(zip(candidates, scores), key=lambda p: p[1], reverse=True)
        results: List[RetrievedChunk] = []
        for idx, score in ranked[:top_k]:
            if score < min_score:
                continue
            results.append(
                RetrievedChunk(
                    text=self._texts[idx],
                    source_id=self._sources[idx],
                    chunk_index=self._chunk_indices[idx],
                    score=float(score),
                )
            )
        return results

    def _score(self, query: str, candidates: Sequence[int]) -> List[float]:
        """Оценка релевантности кандидатов запросу (embeddings или keyword)."""
        if self._use_embeddings:
            q = self._encode([query])[0]
            return [float(np.dot(q, self._embeddings[i])) for i in candidates]
        return [self._keyword_score(query, self._texts[i]) for i in candidates]

    @staticmethod
    def _keyword_score(query: str, chunk: str) -> float:
        """Косинус по мешку слов между запросом и чанком (keyword-fallback)."""
        q_counts = Counter(_tokenize(query))
        c_counts = Counter(_tokenize(chunk))
        if not q_counts or not c_counts:
            return 0.0
        common = set(q_counts) & set(c_counts)
        dot = sum(q_counts[t] * c_counts[t] for t in common)
        q_norm = math.sqrt(sum(v * v for v in q_counts.values()))
        c_norm = math.sqrt(sum(v * v for v in c_counts.values()))
        if q_norm == 0 or c_norm == 0:
            return 0.0
        return dot / (q_norm * c_norm)

    # ── Сборка контекста для промпта ────────────────────────────────────

    @staticmethod
    def to_prompt_context(chunks: Sequence[RetrievedChunk]) -> str:
        """Форматирует извлечённые чанки в блок для промпта тьютора."""
        if not chunks:
            return ""
        parts = ["МАТЕРИАЛ ИЗ ИСТОЧНИКА (используй для ответа):"]
        for i, ch in enumerate(chunks, 1):
            parts.append(f"[{i}] {ch.text.strip()}")
        return "\n".join(parts)
