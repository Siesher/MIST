#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Слой кэширования для MITS.

Кэширует ответы репетитора для ускорения повторных запросов.
Использует семантическое сходство для поиска похожих запросов.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict
from collections import OrderedDict
import logging
import threading

logger = logging.getLogger(__name__)

# Опциональные зависимости
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False
    logger.info("sentence-transformers не установлен. Семантический кэш недоступен.")


@dataclass
class CacheEntry:
    """Запись в кэше."""
    key: str                          # Хэш ключа
    query: str                        # Исходный запрос
    context: str                      # Контекст (задача)
    response: str                     # Ответ репетитора
    topic: Optional[str] = None       # Тема
    move: Optional[str] = None        # Педагогический ход
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    # Performance Optimization (010) - Extended fields
    context_hash: str = ""            # MD5(topic+difficulty+student_level)
    difficulty: Optional[str] = None  # easy/medium/hard
    student_level: Optional[str] = None  # beginner/intermediate/advanced
    teaching_strategy: Optional[str] = None  # HINT/SCAFFOLD/etc
    response_time_ms: int = 0         # Original generation time
    variant_id: Optional[str] = None  # A/B testing variant

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        # Handle legacy entries without new fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


def compute_context_hash(
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    student_level: Optional[str] = None
) -> str:
    """Compute context hash for cache matching."""
    combined = f"{topic or ''}|{difficulty or ''}|{student_level or ''}"
    return hashlib.md5(combined.encode()).hexdigest()


class LRUCache:
    """
    LRU (Least Recently Used) кэш с ограничением по размеру.

    Thread-safe реализация.
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[CacheEntry]:
        """Получение записи из кэша."""
        with self._lock:
            if key not in self._cache:
                return None

            # Перемещаем в конец (самый недавний)
            entry = self._cache.pop(key)
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._cache[key] = entry

            return entry

    def put(self, key: str, entry: CacheEntry):
        """Добавление записи в кэш."""
        with self._lock:
            if key in self._cache:
                self._cache.pop(key)

            self._cache[key] = entry

            # Удаляем старые записи при переполнении
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def remove(self, key: str) -> bool:
        """Удаление записи из кэша."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        """Очистка кэша."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def items(self):
        """Итератор по записям."""
        with self._lock:
            return list(self._cache.items())

    def values(self):
        """Итератор по значениям."""
        with self._lock:
            return list(self._cache.values())


class ResponseCache:
    """
    Кэширование ответов репетитора с семантическим поиском.

    Особенности:
    - LRU кэш с ограничением по размеру
    - Семантический поиск похожих запросов через эмбеддинги
    - Персистентность (сохранение на диск)
    - Thread-safe
    - Метрики эффективности (hit rate)

    Example:
        >>> cache = ResponseCache(max_size=1000)
        >>> cache.add_response(
        ...     student_input="не знаю как начать",
        ...     problem_context="Решить уравнение x + 5 = 10",
        ...     response='{"move": "scaffolding", "message": "Давай разберём..."}'
        ... )
        >>> cached = cache.get_similar_response(
        ...     student_input="с чего начать?",
        ...     problem_context="Решить уравнение x + 5 = 10"
        ... )
    """

    def __init__(
        self,
        max_size: int = 1000,
        similarity_threshold: float = 0.90,  # Increased from 0.85 for accuracy
        cache_dir: Optional[Path] = None,
        use_embeddings: bool = True,
        use_context_matching: bool = True  # New: match context hash
    ):
        """
        Инициализация кэша.

        Args:
            max_size: Максимальное количество записей
            similarity_threshold: Порог сходства для семантического поиска (0-1)
            cache_dir: Директория для персистентного хранения
            use_embeddings: Использовать семантический поиск
            use_context_matching: Учитывать context_hash при matching
        """
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold
        self.use_embeddings = use_embeddings and HAS_EMBEDDINGS
        self.use_context_matching = use_context_matching

        # Основной LRU кэш
        self._cache = LRUCache(max_size)

        # Метрики (extended for 010)
        self._hits = 0
        self._misses = 0
        self._semantic_hits = 0
        self._context_matches = 0  # New: count context-aware hits
        self._total_lookup_time_ms = 0.0
        self._lookup_count = 0

        # Эмбеддинги
        self._embedder = None
        self._embeddings: Dict[str, np.ndarray] = {}

        if self.use_embeddings:
            self._init_embeddings()

        # Персистентность
        self.cache_dir = cache_dir
        if cache_dir:
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

        logger.info(
            f"ResponseCache инициализирован: "
            f"max_size={max_size}, threshold={similarity_threshold}, "
            f"semantic={self.use_embeddings}, context_matching={use_context_matching}"
        )

    def _init_embeddings(self):
        """Инициализация модели эмбеддингов."""
        try:
            # Маленькая многоязычная модель (~90MB)
            self._embedder = SentenceTransformer(
                'paraphrase-multilingual-MiniLM-L12-v2'
            )
            logger.info("Модель эмбеддингов загружена")
        except Exception as e:
            logger.warning(f"Ошибка загрузки модели эмбеддингов: {e}")
            self.use_embeddings = False

    def _make_key(self, student_input: str, problem_context: str) -> str:
        """Создание ключа для кэша."""
        combined = f"{problem_context.strip()}|{student_input.strip()}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Получение эмбеддинга текста."""
        if not self.use_embeddings or self._embedder is None:
            return None
        return self._embedder.encode(text, convert_to_numpy=True)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Косинусное сходство между векторами."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def add_response(
        self,
        student_input: str,
        problem_context: str,
        response: str,
        topic: Optional[str] = None,
        move: Optional[str] = None,
        # Performance Optimization (010) - Extended parameters
        difficulty: Optional[str] = None,
        student_level: Optional[str] = None,
        teaching_strategy: Optional[str] = None,
        response_time_ms: int = 0,
        variant_id: Optional[str] = None
    ):
        """
        Добавление ответа в кэш.

        Args:
            student_input: Ввод ученика
            problem_context: Контекст задачи
            response: Ответ репетитора (JSON строка или текст)
            topic: Тема (опционально)
            move: Педагогический ход (опционально)
            difficulty: Сложность задачи (easy/medium/hard)
            student_level: Уровень студента
            teaching_strategy: Используемая стратегия
            response_time_ms: Время генерации ответа в мс
            variant_id: ID A/B варианта
        """
        key = self._make_key(student_input, problem_context)

        # Compute context hash for context-aware matching
        ctx_hash = compute_context_hash(topic, difficulty, student_level)

        entry = CacheEntry(
            key=key,
            query=student_input,
            context=problem_context,
            response=response,
            topic=topic,
            move=move,
            # Extended fields
            context_hash=ctx_hash,
            difficulty=difficulty,
            student_level=student_level,
            teaching_strategy=teaching_strategy,
            response_time_ms=response_time_ms,
            variant_id=variant_id
        )

        self._cache.put(key, entry)

        # Сохраняем эмбеддинг
        if self.use_embeddings:
            combined_text = f"{problem_context} {student_input}"
            embedding = self._get_embedding(combined_text)
            if embedding is not None:
                self._embeddings[key] = embedding

        logger.debug(f"Добавлена запись в кэш: {key[:8]}... context_hash={ctx_hash[:8]}")

    def get_exact_response(
        self,
        student_input: str,
        problem_context: str
    ) -> Optional[str]:
        """
        Получение точного совпадения из кэша.

        Args:
            student_input: Ввод ученика
            problem_context: Контекст задачи

        Returns:
            Кэшированный ответ или None
        """
        key = self._make_key(student_input, problem_context)
        entry = self._cache.get(key)

        if entry:
            self._hits += 1
            logger.debug(f"Cache HIT (exact): {key[:8]}...")
            return entry.response
        else:
            self._misses += 1
            return None

    def get_similar_response(
        self,
        student_input: str,
        problem_context: str,
        threshold: Optional[float] = None,
        # Context-aware matching (010)
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        student_level: Optional[str] = None
    ) -> Optional[Tuple[str, float]]:
        """
        Получение семантически похожего ответа из кэша.

        Args:
            student_input: Ввод ученика
            problem_context: Контекст задачи
            threshold: Порог сходства (по умолчанию self.similarity_threshold)
            topic: Тема для context-aware matching
            difficulty: Сложность для context-aware matching
            student_level: Уровень студента для context-aware matching

        Returns:
            Tuple (ответ, сходство) или None если не найдено
        """
        start_time = time.time()
        self._lookup_count += 1

        # Сначала пробуем точное совпадение
        exact = self.get_exact_response(student_input, problem_context)
        if exact:
            self._total_lookup_time_ms += (time.time() - start_time) * 1000
            return (exact, 1.0)

        if not self.use_embeddings or not self._embeddings:
            self._total_lookup_time_ms += (time.time() - start_time) * 1000
            return None

        threshold = threshold or self.similarity_threshold

        # Compute target context hash for filtering
        target_ctx_hash = None
        if self.use_context_matching and (topic or difficulty or student_level):
            target_ctx_hash = compute_context_hash(topic, difficulty, student_level)

        # Семантический поиск
        combined_text = f"{problem_context} {student_input}"
        query_embedding = self._get_embedding(combined_text)

        if query_embedding is None:
            self._total_lookup_time_ms += (time.time() - start_time) * 1000
            return None

        best_match = None
        best_score = 0.0
        best_key = None

        for key, embedding in self._embeddings.items():
            # Context-aware filtering: prefer entries with matching context
            entry = self._cache._cache.get(key)
            if entry and target_ctx_hash and self.use_context_matching:
                # Boost score for matching context
                context_match = entry.context_hash == target_ctx_hash
            else:
                context_match = False

            score = self._cosine_similarity(query_embedding, embedding)

            # Apply context boost (5% bonus for matching context)
            effective_score = score + (0.05 if context_match else 0)

            if effective_score > best_score and score >= threshold:
                best_score = effective_score
                best_key = key

        lookup_time = (time.time() - start_time) * 1000
        self._total_lookup_time_ms += lookup_time

        if best_key:
            entry = self._cache.get(best_key)
            if entry:
                self._semantic_hits += 1
                if target_ctx_hash and entry.context_hash == target_ctx_hash:
                    self._context_matches += 1
                logger.debug(
                    f"Cache HIT (semantic): {best_key[:8]}... "
                    f"(similarity={best_score:.3f}, lookup_ms={lookup_time:.1f})"
                )
                return (entry.response, min(best_score, 1.0))

        return None

    def invalidate_by_topic(self, topic: str):
        """Инвалидация всех записей по теме."""
        to_remove = []
        for key, entry in self._cache.items():
            if entry.topic == topic:
                to_remove.append(key)

        for key in to_remove:
            self._cache.remove(key)
            if key in self._embeddings:
                del self._embeddings[key]

        logger.info(f"Инвалидировано {len(to_remove)} записей для темы '{topic}'")

    def clear(self):
        """Полная очистка кэша."""
        self._cache.clear()
        self._embeddings.clear()
        self._hits = 0
        self._misses = 0
        self._semantic_hits = 0
        logger.info("Кэш очищен")

    @property
    def stats(self) -> Dict[str, Any]:
        """Статистика кэша."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        avg_lookup_time = (
            self._total_lookup_time_ms / self._lookup_count
            if self._lookup_count > 0 else 0
        )

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "semantic_hits": self._semantic_hits,
            "context_matches": self._context_matches,  # New
            "hit_rate": hit_rate,
            "semantic_enabled": self.use_embeddings,
            "context_matching_enabled": self.use_context_matching,  # New
            "embeddings_count": len(self._embeddings),
            "similarity_threshold": self.similarity_threshold,  # New
            "avg_lookup_time_ms": round(avg_lookup_time, 2),  # New
            "total_lookups": self._lookup_count  # New
        }

    @property
    def hit_rate(self) -> float:
        """Convenience property for hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def _save_to_disk(self):
        """Сохранение кэша на диск."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / "response_cache.jsonl"

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                for entry in self._cache.values():
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + '\n')

            logger.info(f"Кэш сохранён: {len(self._cache)} записей")
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша: {e}")

    def _load_from_disk(self):
        """Загрузка кэша с диска."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / "response_cache.jsonl"
        if not cache_file.exists():
            return

        try:
            loaded = 0
            with open(cache_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        entry = CacheEntry.from_dict(data)
                        self._cache.put(entry.key, entry)

                        # Восстанавливаем эмбеддинги
                        if self.use_embeddings:
                            combined = f"{entry.context} {entry.query}"
                            emb = self._get_embedding(combined)
                            if emb is not None:
                                self._embeddings[entry.key] = emb

                        loaded += 1

            logger.info(f"Кэш загружен: {loaded} записей")
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша: {e}")

    def warm_up(self, entries: List[Dict[str, Any]] = None) -> int:
        """
        Прогрев кэша примерами.

        Args:
            entries: Список записей для добавления. Если None, загружает с диска.

        Returns:
            Количество добавленных записей
        """
        if entries is None:
            # Load from disk if available
            self._load_from_disk()
            return len(self._cache)

        added = 0
        for entry_data in entries:
            try:
                self.add_response(
                    student_input=entry_data.get("query", ""),
                    problem_context=entry_data.get("context", ""),
                    response=entry_data.get("response", ""),
                    topic=entry_data.get("topic"),
                    move=entry_data.get("move"),
                    difficulty=entry_data.get("difficulty"),
                    student_level=entry_data.get("student_level"),
                    teaching_strategy=entry_data.get("teaching_strategy"),
                    response_time_ms=entry_data.get("response_time_ms", 0),
                    variant_id=entry_data.get("variant_id")
                )
                added += 1
            except Exception as e:
                logger.warning(f"Failed to warm up cache entry: {e}")

        logger.info(f"Cache warmed up with {added} entries")
        return added

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._save_to_disk()

    def __len__(self) -> int:
        return len(self._cache)


class TutoringCacheManager:
    """
    Менеджер кэширования для репетиторской системы.

    Объединяет несколько кэшей:
    - response_cache: Кэш ответов репетитора
    - hint_cache: Кэш подсказок из RAG
    - profile_cache: Кэш профилей учеников
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, cache_dir: Optional[Path] = None):
        if self._initialized:
            return

        # Load settings from config (010 optimization)
        try:
            from src.config import settings
            max_size = settings.CACHE_MAX_SIZE
            similarity_threshold = settings.CACHE_SIMILARITY_THRESHOLD
        except ImportError:
            max_size = 1000
            similarity_threshold = 0.90

        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent / "data" / "cache"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Основной кэш ответов (with 010 optimization settings)
        self.response_cache = ResponseCache(
            max_size=max_size,
            similarity_threshold=similarity_threshold,
            cache_dir=self.cache_dir / "responses",
            use_context_matching=True  # Enable context-aware matching
        )

        # Кэш подсказок (без семантики для скорости)
        self.hint_cache = LRUCache(max_size=500)

        self._initialized = True
        logger.info(
            f"TutoringCacheManager инициализирован: "
            f"max_size={max_size}, threshold={similarity_threshold}"
        )

    def get_or_generate(
        self,
        student_input: str,
        problem_context: str,
        generator: callable,
        topic: Optional[str] = None
    ) -> str:
        """
        Получение ответа из кэша или генерация нового.

        Args:
            student_input: Ввод ученика
            problem_context: Контекст задачи
            generator: Функция генерации ответа
            topic: Тема (опционально)

        Returns:
            Ответ (из кэша или сгенерированный)
        """
        # Пробуем кэш
        result = self.response_cache.get_similar_response(
            student_input, problem_context
        )

        if result:
            response, similarity = result
            logger.info(f"Cache hit (similarity={similarity:.2f})")
            return response

        # Генерируем новый ответ
        response = generator()

        # Сохраняем в кэш
        self.response_cache.add_response(
            student_input=student_input,
            problem_context=problem_context,
            response=response,
            topic=topic
        )

        return response

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики всех кэшей."""
        return {
            "response_cache": self.response_cache.stats,
            "hint_cache_size": len(self.hint_cache),
        }

    def clear_all(self):
        """Очистка всех кэшей."""
        self.response_cache.clear()
        self.hint_cache.clear()
        logger.info("Все кэши очищены")


# === T056: RAG Query Cache ===

class RAGQueryCache:
    """
    Специализированный кэш для RAG запросов.

    Кэширует:
    - Эмбеддинги запросов
    - Результаты retrieval
    - Контекстные объекты

    Оптимизирует:
    - Повторные запросы к ChromaDB
    - Вычисление эмбеддингов
    - Сборку контекста
    """

    def __init__(
        self,
        embedding_cache_size: int = 500,
        retrieval_cache_size: int = 200,
        embedding_ttl: int = 7200,  # 2 часа
        retrieval_ttl: int = 1800   # 30 минут
    ):
        """
        Инициализация RAG кэша.

        Args:
            embedding_cache_size: Размер кэша эмбеддингов
            retrieval_cache_size: Размер кэша retrieval
            embedding_ttl: TTL для эмбеддингов
            retrieval_ttl: TTL для retrieval результатов
        """
        self._embedding_cache = LRUCache(max_size=embedding_cache_size)
        self._retrieval_cache = LRUCache(max_size=retrieval_cache_size)

        self._embedding_ttl = embedding_ttl
        self._retrieval_ttl = retrieval_ttl

        # TTL tracking
        self._embedding_timestamps: Dict[str, float] = {}
        self._retrieval_timestamps: Dict[str, float] = {}

        logger.info(
            f"RAGQueryCache инициализирован: embeddings={embedding_cache_size}, "
            f"retrieval={retrieval_cache_size}"
        )

    def _make_key(self, *args, **kwargs) -> str:
        """Генерация ключа кэша."""
        key_data = json.dumps(
            {"args": args, "kwargs": kwargs},
            sort_keys=True,
            default=str
        )
        return hashlib.md5(key_data.encode()).hexdigest()

    def _is_expired(self, key: str, timestamps: Dict[str, float], ttl: int) -> bool:
        """Проверка истечения TTL."""
        if key not in timestamps:
            return True
        age = time.time() - timestamps[key]
        return age > ttl

    def get_embedding(self, text: str) -> Optional[Any]:
        """Получить кэшированный эмбеддинг."""
        key = self._make_key(text=text)

        if self._is_expired(key, self._embedding_timestamps, self._embedding_ttl):
            self._embedding_cache.remove(key)
            return None

        entry = self._embedding_cache.get(key)
        return entry.response if entry else None

    def set_embedding(self, text: str, embedding: Any) -> None:
        """Кэшировать эмбеддинг."""
        key = self._make_key(text=text)
        entry = CacheEntry(
            key=key,
            query=text,
            context="embedding",
            response=embedding
        )
        self._embedding_cache.put(key, entry)
        self._embedding_timestamps[key] = time.time()

    def get_retrieval(
        self,
        problem: str,
        student_response: str,
        topic: Optional[str] = None
    ) -> Optional[Any]:
        """Получить кэшированный результат retrieval."""
        key = self._make_key(
            problem=problem,
            student_response=student_response,
            topic=topic
        )

        if self._is_expired(key, self._retrieval_timestamps, self._retrieval_ttl):
            self._retrieval_cache.remove(key)
            return None

        entry = self._retrieval_cache.get(key)
        return entry.response if entry else None

    def set_retrieval(
        self,
        problem: str,
        student_response: str,
        topic: Optional[str],
        result: Any
    ) -> None:
        """Кэшировать результат retrieval."""
        key = self._make_key(
            problem=problem,
            student_response=student_response,
            topic=topic
        )
        entry = CacheEntry(
            key=key,
            query=student_response,
            context=problem,
            response=result,
            topic=topic
        )
        self._retrieval_cache.put(key, entry)
        self._retrieval_timestamps[key] = time.time()

    def clear(self) -> None:
        """Очистить все кэши."""
        self._embedding_cache.clear()
        self._retrieval_cache.clear()
        self._embedding_timestamps.clear()
        self._retrieval_timestamps.clear()
        logger.info("RAG кэши очищены")

    @property
    def stats(self) -> Dict[str, Any]:
        """Статистика кэша."""
        return {
            "embedding_cache_size": len(self._embedding_cache),
            "retrieval_cache_size": len(self._retrieval_cache),
            "embedding_ttl": self._embedding_ttl,
            "retrieval_ttl": self._retrieval_ttl
        }


# Глобальный экземпляр RAG кэша
_rag_cache: Optional[RAGQueryCache] = None


def get_rag_cache() -> RAGQueryCache:
    """Получение глобального RAG кэша."""
    global _rag_cache
    if _rag_cache is None:
        _rag_cache = RAGQueryCache()
    return _rag_cache


# Фабричная функция
def get_cache_manager() -> TutoringCacheManager:
    """Получение синглтона TutoringCacheManager."""
    return TutoringCacheManager()


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Response Cache Demo ===\n")

    cache = ResponseCache(max_size=100, similarity_threshold=0.8)

    # Добавляем несколько ответов
    cache.add_response(
        student_input="не знаю как начать",
        problem_context="Решить уравнение x + 5 = 10",
        response='{"move": "scaffolding", "message": "Давай разберём это уравнение вместе..."}',
        topic="linear_equations",
        move="scaffolding"
    )

    cache.add_response(
        student_input="что делать с пятёркой?",
        problem_context="Решить уравнение x + 5 = 10",
        response='{"move": "hint", "message": "Подумай, какую операцию нужно выполнить..."}',
        topic="linear_equations",
        move="hint"
    )

    # Точное совпадение
    exact = cache.get_exact_response(
        "не знаю как начать",
        "Решить уравнение x + 5 = 10"
    )
    print(f"Точное совпадение: {exact is not None}")

    # Семантический поиск
    similar = cache.get_similar_response(
        "с чего начать решение?",  # Похожий запрос
        "Решить уравнение x + 5 = 10"
    )
    if similar:
        response, score = similar
        print(f"Семантическое совпадение (score={score:.2f}): {response[:50]}...")
    else:
        print("Семантическое совпадение не найдено")

    # Статистика
    print(f"\nСтатистика: {cache.stats}")
