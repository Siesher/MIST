#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T036: Batch Processor для MITS.

Обрабатывает несколько запросов пакетами для оптимизации инференса.
Полезно для:
- Предварительной загрузки подсказок
- Генерации эмбеддингов для нескольких задач
- Пакетной валидации ответов

Feature 010: Enhanced with time-windowed batch embedding processing.
"""

import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

# Feature 010: Load configuration
try:
    from src.config import settings
    BATCH_SIZE = getattr(settings, 'BATCH_EMBEDDING_SIZE', 16)
    BATCH_TIMEOUT_MS = getattr(settings, 'BATCH_EMBEDDING_TIMEOUT_MS', 50)
except ImportError:
    BATCH_SIZE = 16
    BATCH_TIMEOUT_MS = 50

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class BatchItem(Generic[T]):
    """Элемент в очереди пакетной обработки."""
    id: str
    data: T
    callback: Optional[Callable[[Any], None]] = None
    created_at: float = field(default_factory=time.time)
    priority: int = 0  # Higher = more priority


@dataclass
class BatchResult(Generic[R]):
    """Результат пакетной обработки."""
    id: str
    result: Optional[R] = None
    error: Optional[str] = None
    processing_time_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.error is None


class BatchProcessor(Generic[T, R]):
    """
    Универсальный пакетный процессор.

    Собирает запросы в пакеты и обрабатывает их вместе для эффективности.
    Поддерживает:
    - Автоматическое формирование пакетов по размеру/времени
    - Приоритизацию запросов
    - Асинхронные callback'и
    - Thread-safe очередь

    Example:
        >>> def process_batch(items: List[str]) -> List[str]:
        ...     return [item.upper() for item in items]
        >>>
        >>> processor = BatchProcessor(
        ...     batch_fn=process_batch,
        ...     max_batch_size=10,
        ...     max_wait_ms=100
        ... )
        >>> processor.start()
        >>> result = processor.submit("hello")
        >>> print(result.result)  # "HELLO"
    """

    def __init__(
        self,
        batch_fn: Callable[[List[T]], List[R]],
        max_batch_size: int = 8,
        max_wait_ms: int = 50,
        num_workers: int = 2
    ):
        """
        Инициализация процессора.

        Args:
            batch_fn: Функция обработки пакета (принимает список, возвращает список)
            max_batch_size: Максимальный размер пакета
            max_wait_ms: Максимальное время ожидания формирования пакета
            num_workers: Количество worker'ов для параллельной обработки
        """
        self.batch_fn = batch_fn
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self.num_workers = num_workers

        self._queue: deque[BatchItem[T]] = deque()
        self._results: Dict[str, BatchResult[R]] = {}
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._executor = ThreadPoolExecutor(max_workers=num_workers)

        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        # Метрики
        self._total_processed = 0
        self._total_batches = 0
        self._total_time_ms = 0.0

        logger.info(
            f"BatchProcessor создан: batch_size={max_batch_size}, "
            f"wait_ms={max_wait_ms}, workers={num_workers}"
        )

    def start(self) -> None:
        """Запуск обработчика."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("BatchProcessor запущен")

    def stop(self) -> None:
        """Остановка обработчика."""
        self._running = False
        with self._condition:
            self._condition.notify_all()

        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)

        self._executor.shutdown(wait=False)
        logger.info("BatchProcessor остановлен")

    def submit(
        self,
        data: T,
        item_id: Optional[str] = None,
        priority: int = 0,
        callback: Optional[Callable[[BatchResult[R]], None]] = None,
        timeout_ms: int = 5000
    ) -> BatchResult[R]:
        """
        Отправить элемент на обработку (синхронно).

        Args:
            data: Данные для обработки
            item_id: Уникальный ID (генерируется автоматически)
            priority: Приоритет (выше = раньше)
            callback: Callback при завершении
            timeout_ms: Таймаут ожидания результата

        Returns:
            BatchResult с результатом или ошибкой
        """
        if item_id is None:
            item_id = f"batch_{time.time_ns()}"

        item = BatchItem(
            id=item_id,
            data=data,
            callback=callback,
            priority=priority
        )

        with self._condition:
            # Вставляем с учётом приоритета
            self._queue.append(item)
            self._condition.notify()

        # Ждём результата
        deadline = time.time() + (timeout_ms / 1000.0)
        while True:
            with self._lock:
                if item_id in self._results:
                    result = self._results.pop(item_id)
                    return result

            if time.time() > deadline:
                return BatchResult(
                    id=item_id,
                    error="Timeout waiting for batch processing"
                )

            time.sleep(0.01)

    def submit_async(
        self,
        data: T,
        item_id: Optional[str] = None,
        priority: int = 0,
        callback: Optional[Callable[[BatchResult[R]], None]] = None
    ) -> str:
        """
        Отправить элемент на асинхронную обработку.

        Args:
            data: Данные для обработки
            item_id: Уникальный ID
            priority: Приоритет
            callback: Callback при завершении

        Returns:
            ID элемента для последующего получения результата
        """
        if item_id is None:
            item_id = f"batch_{time.time_ns()}"

        item = BatchItem(
            id=item_id,
            data=data,
            callback=callback,
            priority=priority
        )

        with self._condition:
            self._queue.append(item)
            self._condition.notify()

        return item_id

    def get_result(self, item_id: str, timeout_ms: int = 1000) -> Optional[BatchResult[R]]:
        """
        Получить результат асинхронной обработки.

        Args:
            item_id: ID элемента
            timeout_ms: Таймаут ожидания

        Returns:
            BatchResult или None если не готов
        """
        deadline = time.time() + (timeout_ms / 1000.0)

        while time.time() < deadline:
            with self._lock:
                if item_id in self._results:
                    return self._results.pop(item_id)
            time.sleep(0.01)

        return None

    def _worker_loop(self) -> None:
        """Основной цикл обработки пакетов."""
        while self._running:
            batch = self._collect_batch()

            if not batch:
                continue

            try:
                self._process_batch(batch)
            except Exception as e:
                logger.error(f"Ошибка обработки пакета: {e}")
                # Помечаем все элементы как ошибочные
                for item in batch:
                    result = BatchResult(id=item.id, error=str(e))
                    self._store_result(item, result)

    def _collect_batch(self) -> List[BatchItem[T]]:
        """Собрать пакет элементов для обработки."""
        batch: List[BatchItem[T]] = []
        wait_until = time.time() + (self.max_wait_ms / 1000.0)

        with self._condition:
            while len(batch) < self.max_batch_size:
                # Ждём элементов или таймаута
                remaining = wait_until - time.time()

                if remaining <= 0:
                    break

                if not self._queue:
                    self._condition.wait(timeout=remaining)

                if not self._running:
                    return []

                # Забираем элементы из очереди
                while self._queue and len(batch) < self.max_batch_size:
                    batch.append(self._queue.popleft())

                # Если собрали полный пакет - выходим
                if len(batch) >= self.max_batch_size:
                    break

        # Сортируем по приоритету
        batch.sort(key=lambda x: -x.priority)

        return batch

    def _process_batch(self, batch: List[BatchItem[T]]) -> None:
        """Обработать пакет элементов."""
        if not batch:
            return

        start_time = time.time()

        # Извлекаем данные
        data_list = [item.data for item in batch]

        try:
            # Обрабатываем пакет
            results = self.batch_fn(data_list)

            processing_time = (time.time() - start_time) * 1000

            # Раздаём результаты
            for i, item in enumerate(batch):
                result = BatchResult(
                    id=item.id,
                    result=results[i] if i < len(results) else None,
                    processing_time_ms=processing_time / len(batch)
                )
                self._store_result(item, result)

            # Метрики
            self._total_processed += len(batch)
            self._total_batches += 1
            self._total_time_ms += processing_time

            logger.debug(
                f"Пакет обработан: {len(batch)} элементов за {processing_time:.1f}ms"
            )

        except Exception as e:
            logger.error(f"Ошибка batch_fn: {e}")
            for item in batch:
                result = BatchResult(id=item.id, error=str(e))
                self._store_result(item, result)

    def _store_result(self, item: BatchItem[T], result: BatchResult[R]) -> None:
        """Сохранить результат и вызвать callback."""
        with self._lock:
            self._results[item.id] = result

        if item.callback:
            try:
                item.callback(result)
            except Exception as e:
                logger.warning(f"Ошибка в callback: {e}")

    @property
    def stats(self) -> Dict[str, Any]:
        """Статистика обработки."""
        avg_time = (
            self._total_time_ms / self._total_batches
            if self._total_batches > 0 else 0
        )
        avg_batch_size = (
            self._total_processed / self._total_batches
            if self._total_batches > 0 else 0
        )

        return {
            "total_processed": self._total_processed,
            "total_batches": self._total_batches,
            "avg_batch_time_ms": round(avg_time, 2),
            "avg_batch_size": round(avg_batch_size, 2),
            "queue_size": len(self._queue),
            "pending_results": len(self._results)
        }

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class EmbeddingBatchProcessor:
    """
    Специализированный batch processor для эмбеддингов.

    Оптимизирован для sentence-transformers с автоматическим
    батчингом и кэшированием.

    Feature 010: Enhanced with time-windowed batch collection.
    """

    def __init__(
        self,
        model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2',
        batch_size: int = None,
        cache_size: int = 1000,
        batch_timeout_ms: int = None
    ):
        self.model_name = model_name
        self.batch_size = batch_size or BATCH_SIZE
        self.batch_timeout_ms = batch_timeout_ms or BATCH_TIMEOUT_MS

        # Lazy load модели
        self._model = None
        self._cache: Dict[str, Any] = {}
        self._cache_order: deque = deque(maxlen=cache_size)
        self._lock = threading.Lock()

        # Feature 010: Time-windowed batch collection
        self._pending_batch: List[tuple] = []  # (text, future)
        self._batch_lock = threading.Lock()
        self._batch_timer: Optional[threading.Timer] = None
        self._batch_condition = threading.Condition(self._batch_lock)

        # Metrics
        self._total_encoded = 0
        self._total_batches = 0
        self._cache_hits = 0
        self._cache_misses = 0

        logger.info(
            f"EmbeddingBatchProcessor создан: model={model_name}, "
            f"batch_size={self.batch_size}, timeout_ms={self.batch_timeout_ms}"
        )

    def _get_model(self):
        """Lazy загрузка модели."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Модель эмбеддингов загружена: {self.model_name}")
            except ImportError:
                logger.warning("sentence-transformers не установлен")
                return None
        return self._model

    def encode(self, text: str) -> Optional[Any]:
        """
        Получить эмбеддинг для одного текста (с кэшированием).

        Args:
            text: Входной текст

        Returns:
            numpy array эмбеддинга или None
        """
        with self._lock:
            if text in self._cache:
                return self._cache[text]

        model = self._get_model()
        if model is None:
            return None

        embedding = model.encode(text, convert_to_numpy=True)

        with self._lock:
            self._cache[text] = embedding
            self._cache_order.append(text)

            # Очистка старых записей
            while len(self._cache) > len(self._cache_order):
                old_key = self._cache_order.popleft()
                self._cache.pop(old_key, None)

        return embedding

    def encode_batch(self, texts: List[str]) -> List[Optional[Any]]:
        """
        Получить эмбеддинги для списка текстов.

        Args:
            texts: Список текстов

        Returns:
            Список эмбеддингов (или None для ошибок)
        """
        results = [None] * len(texts)
        to_encode = []
        to_encode_indices = []

        # Проверяем кэш
        with self._lock:
            for i, text in enumerate(texts):
                if text in self._cache:
                    results[i] = self._cache[text]
                else:
                    to_encode.append(text)
                    to_encode_indices.append(i)

        if not to_encode:
            return results

        # Кодируем некэшированные
        model = self._get_model()
        if model is None:
            return results

        try:
            embeddings = model.encode(
                to_encode,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                show_progress_bar=False
            )

            with self._lock:
                for idx, (text, emb) in zip(to_encode_indices, zip(to_encode, embeddings)):
                    results[idx] = emb
                    self._cache[text] = emb
                    self._cache_order.append(text)

        except Exception as e:
            logger.error(f"Ошибка батч-кодирования: {e}")

        return results

    def encode_async(self, text: str) -> Any:
        """
        Добавить текст в очередь на батч-кодирование.

        Feature 010: Time-windowed batch collection.
        Собирает запросы в течение batch_timeout_ms или до batch_size.

        Args:
            text: Текст для кодирования

        Returns:
            Эмбеддинг (ждёт завершения батча)
        """
        import queue
        import threading

        # Check cache first
        with self._lock:
            if text in self._cache:
                self._cache_hits += 1
                return self._cache[text]

        self._cache_misses += 1

        # Create a result holder
        result_queue = queue.Queue()

        with self._batch_lock:
            self._pending_batch.append((text, result_queue))

            # Start timer if this is first item
            if len(self._pending_batch) == 1:
                self._batch_timer = threading.Timer(
                    self.batch_timeout_ms / 1000.0,
                    self._process_pending_batch
                )
                self._batch_timer.start()

            # Process immediately if batch is full
            if len(self._pending_batch) >= self.batch_size:
                if self._batch_timer:
                    self._batch_timer.cancel()
                self._process_pending_batch()

        # Wait for result
        return result_queue.get(timeout=5.0)

    def _process_pending_batch(self) -> None:
        """Process accumulated batch."""
        with self._batch_lock:
            if not self._pending_batch:
                return

            batch = self._pending_batch.copy()
            self._pending_batch.clear()

        if not batch:
            return

        texts = [item[0] for item in batch]
        result_queues = [item[1] for item in batch]

        # Encode batch
        model = self._get_model()
        if model is None:
            for rq in result_queues:
                rq.put(None)
            return

        try:
            embeddings = model.encode(
                texts,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                show_progress_bar=False
            )

            # Cache and distribute results
            with self._lock:
                for text, emb, rq in zip(texts, embeddings, result_queues):
                    self._cache[text] = emb
                    self._cache_order.append(text)
                    rq.put(emb)

            self._total_encoded += len(texts)
            self._total_batches += 1

            logger.debug(
                f"Batch encoded: {len(texts)} texts in batch #{self._total_batches}"
            )

        except Exception as e:
            logger.error(f"Batch encoding error: {e}")
            for rq in result_queues:
                rq.put(None)

    @property
    def stats(self) -> Dict[str, Any]:
        """Статистика."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0

        return {
            "cache_size": len(self._cache),
            "model_loaded": self._model is not None,
            "total_encoded": self._total_encoded,
            "total_batches": self._total_batches,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": round(hit_rate, 3),
            "avg_batch_size": round(
                self._total_encoded / self._total_batches, 2
            ) if self._total_batches > 0 else 0,
            "pending_batch_size": len(self._pending_batch),
        }


class TimeWindowedBatchProcessor:
    """
    Feature 010: Time-windowed batch processor for embeddings.

    Collects embedding requests over a time window and processes them
    together for better GPU utilization.
    """

    def __init__(
        self,
        embedding_processor: EmbeddingBatchProcessor,
        window_ms: int = None,
        max_batch_size: int = None
    ):
        self.processor = embedding_processor
        self.window_ms = window_ms or BATCH_TIMEOUT_MS
        self.max_batch_size = max_batch_size or BATCH_SIZE

        self._window_start: Optional[float] = None
        self._pending: List[str] = []
        self._lock = threading.Lock()

        logger.info(
            f"TimeWindowedBatchProcessor: window={self.window_ms}ms, "
            f"max_batch={self.max_batch_size}"
        )

    def add(self, text: str) -> None:
        """Add text to current window."""
        with self._lock:
            if self._window_start is None:
                self._window_start = time.time()
            self._pending.append(text)

    def flush(self) -> List[Any]:
        """
        Flush current window and return embeddings.

        Returns:
            List of embeddings for all pending texts
        """
        with self._lock:
            if not self._pending:
                return []

            texts = self._pending.copy()
            self._pending.clear()
            self._window_start = None

        return self.processor.encode_batch(texts)

    def should_flush(self) -> bool:
        """Check if current window should be flushed."""
        with self._lock:
            if not self._pending:
                return False

            # Flush if max batch size reached
            if len(self._pending) >= self.max_batch_size:
                return True

            # Flush if window expired
            if self._window_start:
                elapsed_ms = (time.time() - self._window_start) * 1000
                if elapsed_ms >= self.window_ms:
                    return True

        return False

    @property
    def pending_count(self) -> int:
        """Number of pending texts."""
        with self._lock:
            return len(self._pending)


# Глобальный экземпляр
_embedding_processor: Optional[EmbeddingBatchProcessor] = None
_time_windowed_processor: Optional[TimeWindowedBatchProcessor] = None


def get_embedding_processor() -> EmbeddingBatchProcessor:
    """Получить глобальный embedding processor."""
    global _embedding_processor
    if _embedding_processor is None:
        _embedding_processor = EmbeddingBatchProcessor()
    return _embedding_processor


def get_time_windowed_processor() -> TimeWindowedBatchProcessor:
    """Feature 010: Get global time-windowed batch processor."""
    global _time_windowed_processor
    if _time_windowed_processor is None:
        _time_windowed_processor = TimeWindowedBatchProcessor(
            embedding_processor=get_embedding_processor()
        )
    return _time_windowed_processor


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== BatchProcessor Demo ===\n")

    # Простой пример
    def uppercase_batch(items: List[str]) -> List[str]:
        time.sleep(0.1)  # Имитация работы
        return [item.upper() for item in items]

    with BatchProcessor(
        batch_fn=uppercase_batch,
        max_batch_size=5,
        max_wait_ms=200
    ) as processor:
        # Синхронная отправка
        result = processor.submit("hello")
        print(f"Результат: {result.result}")

        # Пакетная отправка
        ids = []
        for word in ["world", "batch", "processing"]:
            ids.append(processor.submit_async(word))

        time.sleep(0.5)

        for item_id in ids:
            result = processor.get_result(item_id)
            if result:
                print(f"Async результат: {result.result}")

        print(f"\nСтатистика: {processor.stats}")
