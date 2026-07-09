#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T037: Hint Prefetcher для MITS.

Предзагружает подсказки в фоновом режиме для мгновенного отклика.
Использует эвристики для предсказания нужных подсказок:
- При выборе задачи загружает все подсказки
- При ошибке студента загружает релевантные hints
- При приближении к mastery загружает следующие темы

Feature 010: Enhanced with skill graph-based prediction
"""

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from queue import PriorityQueue
from typing import Any, Callable, Dict, List, Optional, Set

# Feature 010: Load configuration
try:
    from src.config import settings
    PREFETCH_CACHE_SIZE = getattr(settings, 'CACHE_MAX_SIZE', 200)
except ImportError:
    PREFETCH_CACHE_SIZE = 200

logger = logging.getLogger(__name__)


@dataclass(order=True)
class PrefetchTask:
    """Задача на предзагрузку."""
    priority: int
    task_type: str = field(compare=False)
    key: str = field(compare=False)
    data: Dict[str, Any] = field(compare=False, default_factory=dict)
    created_at: float = field(compare=False, default_factory=time.time)


@dataclass
class PrefetchedHint:
    """Предзагруженная подсказка."""
    key: str
    content: str
    topic: Optional[str] = None
    level: str = "conceptual"  # conceptual, procedural, specific
    source: str = "prefetch"   # prefetch, rag, task_bank
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def touch(self) -> None:
        """Обновить время доступа."""
        self.access_count += 1
        self.last_accessed = time.time()


class HintPrefetcher:
    """
    Фоновый загрузчик подсказок.

    Особенности:
    - Приоритетная очередь задач на загрузку
    - LRU кэш готовых подсказок
    - Эвристики предсказания
    - Thread-safe операции
    - Интеграция с RAG системой

    Example:
        >>> prefetcher = HintPrefetcher()
        >>> prefetcher.start()
        >>>
        >>> # При выборе задачи
        >>> prefetcher.prefetch_for_problem("Решить x + 5 = 10", topic="linear_equations")
        >>>
        >>> # Получение подсказки (мгновенно если prefetched)
        >>> hint = prefetcher.get_hint("linear_equations", level="conceptual")
    """

    def __init__(
        self,
        cache_size: int = 200,
        num_workers: int = 2,
        rag_retriever: Optional[Any] = None
    ):
        """
        Инициализация prefetcher'а.

        Args:
            cache_size: Размер кэша подсказок
            num_workers: Количество фоновых workers
            rag_retriever: RAG система для получения подсказок (опционально)
        """
        self.cache_size = cache_size
        self.num_workers = num_workers
        self.rag_retriever = rag_retriever

        # Кэш подсказок (LRU)
        self._cache: OrderedDict[str, PrefetchedHint] = OrderedDict()
        self._cache_lock = threading.Lock()

        # Очередь задач на prefetch
        self._task_queue: PriorityQueue[PrefetchTask] = PriorityQueue()
        self._pending_keys: Set[str] = set()
        self._pending_lock = threading.Lock()

        # Worker threads
        self._workers: List[threading.Thread] = []
        self._running = False

        # Метрики
        self._hits = 0
        self._misses = 0
        self._prefetched = 0

        # Callbacks для генерации подсказок
        self._hint_generators: Dict[str, Callable] = {}

        logger.info(
            f"HintPrefetcher создан: cache_size={cache_size}, workers={num_workers}"
        )

    def register_generator(self, name: str, generator: Callable) -> None:
        """
        Зарегистрировать генератор подсказок.

        Args:
            name: Имя генератора
            generator: Функция генерации (topic, level, context) -> List[str]
        """
        self._hint_generators[name] = generator
        logger.debug(f"Зарегистрирован генератор: {name}")

    def start(self) -> None:
        """Запустить фоновые workers."""
        if self._running:
            return

        self._running = True

        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"HintPrefetcher-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"HintPrefetcher запущен с {self.num_workers} workers")

    def stop(self) -> None:
        """Остановить workers."""
        self._running = False

        # Добавляем poison pills
        for _ in self._workers:
            self._task_queue.put(PrefetchTask(priority=999, task_type="stop", key=""))

        for worker in self._workers:
            worker.join(timeout=2.0)

        self._workers.clear()
        logger.info("HintPrefetcher остановлен")

    def prefetch_for_problem(
        self,
        problem: str,
        topic: Optional[str] = None,
        hints: Optional[List[str]] = None,
        priority: int = 1
    ) -> None:
        """
        Предзагрузить подсказки для задачи.

        Вызывается при выборе/отображении задачи.

        Args:
            problem: Текст задачи
            topic: Тема задачи
            hints: Готовые подсказки из task bank (опционально)
            priority: Приоритет (меньше = выше)
        """
        # Сразу кэшируем готовые подсказки из task bank
        if hints:
            for i, hint_text in enumerate(hints):
                level = ["conceptual", "procedural", "specific"][min(i, 2)]
                key = self._make_key(topic or "general", level, i)

                hint = PrefetchedHint(
                    key=key,
                    content=hint_text,
                    topic=topic,
                    level=level,
                    source="task_bank"
                )
                self._cache_hint(hint)

        # Добавляем задачу на RAG prefetch
        if self.rag_retriever and topic:
            task = PrefetchTask(
                priority=priority,
                task_type="rag_hints",
                key=self._make_key(topic, "rag", hash(problem)),
                data={
                    "problem": problem,
                    "topic": topic
                }
            )
            self._enqueue_task(task)

    def prefetch_for_error(
        self,
        student_response: str,
        problem: str,
        topic: Optional[str] = None,
        error_type: Optional[str] = None,
        priority: int = 0  # Высокий приоритет
    ) -> None:
        """
        Предзагрузить подсказки после ошибки студента.

        Вызывается когда verifier обнаружил ошибку.

        Args:
            student_response: Ответ студента
            problem: Текст задачи
            topic: Тема
            error_type: Тип ошибки (если известен)
            priority: Приоритет
        """
        task = PrefetchTask(
            priority=priority,
            task_type="error_hints",
            key=self._make_key(topic or "general", "error", hash(student_response)),
            data={
                "problem": problem,
                "student_response": student_response,
                "topic": topic,
                "error_type": error_type
            }
        )
        self._enqueue_task(task)

    def prefetch_next_topics(
        self,
        current_topic: str,
        mastery_level: float,
        priority: int = 2
    ) -> None:
        """
        Предзагрузить подсказки для следующих тем.

        Вызывается когда студент близок к mastery текущей темы.

        Feature 010: Enhanced with skill graph-based prediction.

        Args:
            current_topic: Текущая тема
            mastery_level: Уровень владения (0-1)
            priority: Приоритет
        """
        if mastery_level < 0.7:  # Только если близко к mastery
            return

        # Определяем следующие темы используя граф знаний
        next_topics = self._get_next_topics(current_topic)

        for next_topic in next_topics[:3]:  # Максимум 3 следующих темы
            task = PrefetchTask(
                priority=priority,
                task_type="topic_hints",
                key=self._make_key(next_topic, "intro", 0),
                data={"topic": next_topic}
            )
            self._enqueue_task(task)

    def prefetch_prerequisites(
        self,
        topic: str,
        priority: int = 1
    ) -> None:
        """
        Предзагрузить подсказки для prerequisite навыков.

        Feature 010: Skill graph-based prerequisite prefetching.

        Args:
            topic: Тема для которой нужны prerequisite hints
            priority: Приоритет
        """
        try:
            from src.data.knowledge_graph import SKILL_GRAPH

            if topic not in SKILL_GRAPH:
                return

            prereqs = SKILL_GRAPH[topic].get("prerequisites", [])

            for prereq in prereqs[:2]:  # Максимум 2 prerequisite
                task = PrefetchTask(
                    priority=priority,
                    task_type="topic_hints",
                    key=self._make_key(prereq, "review", 0),
                    data={"topic": prereq, "context": "prerequisite_review"}
                )
                self._enqueue_task(task)

        except ImportError:
            pass  # Skip if knowledge_graph not available

    def prefetch_for_student_profile(
        self,
        weak_skills: List[str],
        current_topic: str,
        priority: int = 2
    ) -> None:
        """
        Предзагрузить подсказки на основе слабых навыков студента.

        Feature 010: Personalized prefetching based on student profile.

        Args:
            weak_skills: Список слабых навыков студента
            current_topic: Текущая тема
            priority: Приоритет
        """
        try:
            from src.data.knowledge_graph import SKILL_GRAPH, get_all_prerequisites

            # Get prerequisites of current topic
            current_prereqs = set()
            if current_topic in SKILL_GRAPH:
                current_prereqs = get_all_prerequisites(current_topic)

            # Find intersection with weak skills
            relevant_weak = [s for s in weak_skills if s in current_prereqs]

            for skill in relevant_weak[:3]:
                task = PrefetchTask(
                    priority=priority,
                    task_type="remediation_hints",
                    key=self._make_key(skill, "remediation", 0),
                    data={"topic": skill, "context": "remediation"}
                )
                self._enqueue_task(task)

        except ImportError:
            pass

    def get_hint(
        self,
        topic: str,
        level: str = "conceptual",
        index: int = 0
    ) -> Optional[str]:
        """
        Получить подсказку из кэша.

        Args:
            topic: Тема
            level: Уровень (conceptual, procedural, specific)
            index: Индекс подсказки на уровне

        Returns:
            Текст подсказки или None если не найдена
        """
        key = self._make_key(topic, level, index)

        with self._cache_lock:
            if key in self._cache:
                hint = self._cache[key]
                hint.touch()
                # Move to end (LRU)
                self._cache.move_to_end(key)
                self._hits += 1
                return hint.content

        self._misses += 1
        return None

    def get_all_hints(self, topic: str) -> List[PrefetchedHint]:
        """
        Получить все кэшированные подсказки по теме.

        Args:
            topic: Тема

        Returns:
            Список подсказок
        """
        results = []

        with self._cache_lock:
            for key, hint in self._cache.items():
                if hint.topic == topic:
                    hint.touch()
                    results.append(hint)

        return sorted(results, key=lambda h: (h.level, h.created_at))

    def _make_key(self, topic: str, level: str, index: Any) -> str:
        """Создать ключ для кэша."""
        raw = f"{topic}:{level}:{index}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _cache_hint(self, hint: PrefetchedHint) -> None:
        """Добавить подсказку в кэш."""
        with self._cache_lock:
            if hint.key in self._cache:
                # Обновляем существующую
                self._cache[hint.key] = hint
                self._cache.move_to_end(hint.key)
            else:
                self._cache[hint.key] = hint

                # Удаляем старые при переполнении
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)

            self._prefetched += 1

    def _enqueue_task(self, task: PrefetchTask) -> None:
        """Добавить задачу в очередь."""
        with self._pending_lock:
            if task.key in self._pending_keys:
                return  # Уже в обработке
            self._pending_keys.add(task.key)

        self._task_queue.put(task)

    def _worker_loop(self) -> None:
        """Цикл обработки задач."""
        while self._running:
            try:
                task = self._task_queue.get(timeout=1.0)

                if task.task_type == "stop":
                    break

                self._process_task(task)

                with self._pending_lock:
                    self._pending_keys.discard(task.key)

            except Exception as e:
                if self._running:  # Не логируем при остановке
                    logger.debug(f"Worker idle or error: {e}")

    def _process_task(self, task: PrefetchTask) -> None:
        """Обработать задачу prefetch."""
        try:
            if task.task_type == "rag_hints":
                self._fetch_rag_hints(task.data)

            elif task.task_type == "error_hints":
                self._fetch_error_hints(task.data)

            elif task.task_type == "topic_hints":
                self._fetch_topic_hints(task.data)

        except Exception as e:
            logger.warning(f"Ошибка prefetch: {task.task_type} - {e}")

    def _fetch_rag_hints(self, data: Dict[str, Any]) -> None:
        """Загрузить подсказки из RAG."""
        if not self.rag_retriever:
            return

        problem = data.get("problem", "")
        topic = data.get("topic")

        try:
            # Используем RAG для получения релевантного контекста
            context = self.rag_retriever.retrieve_context(
                problem=problem,
                student_response="",  # Начальный запрос
                topic=topic
            )

            # Кэшируем найденные подсказки
            if hasattr(context, 'hints'):
                for i, hint in enumerate(context.hints[:5]):
                    level = ["conceptual", "procedural", "specific"][min(i // 2, 2)]
                    key = self._make_key(topic or "general", f"rag_{level}", i)

                    prefetched = PrefetchedHint(
                        key=key,
                        content=hint.content if hasattr(hint, 'content') else str(hint),
                        topic=topic,
                        level=level,
                        source="rag"
                    )
                    self._cache_hint(prefetched)

            logger.debug(f"RAG hints loaded for topic: {topic}")

        except Exception as e:
            logger.warning(f"RAG prefetch error: {e}")

    def _fetch_error_hints(self, data: Dict[str, Any]) -> None:
        """Загрузить подсказки для ошибки."""
        topic = data.get("topic")
        error_type = data.get("error_type")

        # Используем генераторы если есть
        if "error" in self._hint_generators:
            try:
                hints = self._hint_generators["error"](
                    topic=topic,
                    error_type=error_type,
                    context=data
                )
                for i, hint_text in enumerate(hints[:3]):
                    key = self._make_key(topic or "general", "error", i)
                    prefetched = PrefetchedHint(
                        key=key,
                        content=hint_text,
                        topic=topic,
                        level="procedural",
                        source="generator"
                    )
                    self._cache_hint(prefetched)
            except Exception as e:
                logger.warning(f"Error hint generator failed: {e}")

    def _fetch_topic_hints(self, data: Dict[str, Any]) -> None:
        """Загрузить вводные подсказки для темы."""
        topic = data.get("topic")

        if not topic:
            return

        # Используем генераторы если есть
        if "intro" in self._hint_generators:
            try:
                hints = self._hint_generators["intro"](
                    topic=topic,
                    level="conceptual",
                    context=data
                )
                for i, hint_text in enumerate(hints[:2]):
                    key = self._make_key(topic, "intro", i)
                    prefetched = PrefetchedHint(
                        key=key,
                        content=hint_text,
                        topic=topic,
                        level="conceptual",
                        source="generator"
                    )
                    self._cache_hint(prefetched)
            except Exception as e:
                logger.warning(f"Intro hint generator failed: {e}")

    def _get_next_topics(self, current_topic: str) -> List[str]:
        """
        Получить следующие темы по графу знаний.

        Feature 010: Integrated with SKILL_GRAPH from knowledge_graph.py
        """
        try:
            from src.data.knowledge_graph import SKILL_GRAPH

            # Find skills that have current_topic as prerequisite
            next_skills = []
            for skill_id, data in SKILL_GRAPH.items():
                prereqs = data.get("prerequisites", [])
                if current_topic in prereqs:
                    # Add with difficulty for sorting
                    next_skills.append((skill_id, data.get("difficulty", 0.5)))

            # Sort by difficulty (easier first)
            next_skills.sort(key=lambda x: x[1])
            return [s[0] for s in next_skills]

        except ImportError:
            # Fallback to simple mapping
            topic_graph = {
                "linear_equations": ["quadratic_equations", "systems_of_equations"],
                "quadratic_equations": ["polynomial_equations", "inequalities"],
                "derivatives": ["integrals", "optimization"],
                "integrals": ["differential_equations", "area_calculation"],
                "limits": ["derivatives", "continuity"],
                "arrays": ["sorting", "searching", "two_pointers"],
                "sorting": ["binary_search", "merge_sort"],
            }
            return topic_graph.get(current_topic, [])

    @property
    def stats(self) -> Dict[str, Any]:
        """Статистика prefetcher'а."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.cache_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
            "total_prefetched": self._prefetched,
            "pending_tasks": self._task_queue.qsize(),
            "workers_running": len([w for w in self._workers if w.is_alive()])
        }

    def clear(self) -> None:
        """Очистить кэш."""
        with self._cache_lock:
            self._cache.clear()

        self._hits = 0
        self._misses = 0
        logger.info("Hint cache очищен")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Глобальный экземпляр
_prefetcher: Optional[HintPrefetcher] = None


def get_hint_prefetcher() -> HintPrefetcher:
    """Получить глобальный prefetcher."""
    global _prefetcher
    if _prefetcher is None:
        _prefetcher = HintPrefetcher()
    return _prefetcher


def init_prefetcher(rag_retriever: Optional[Any] = None) -> HintPrefetcher:
    """Инициализировать и запустить prefetcher."""
    global _prefetcher
    _prefetcher = HintPrefetcher(rag_retriever=rag_retriever)
    _prefetcher.start()
    return _prefetcher


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== HintPrefetcher Demo ===\n")

    with HintPrefetcher(cache_size=50, num_workers=1) as prefetcher:
        # Имитируем выбор задачи
        prefetcher.prefetch_for_problem(
            problem="Решите уравнение: 2x + 5 = 15",
            topic="linear_equations",
            hints=[
                "Подумай, что нужно сделать с числом 5?",
                "Перенеси 5 на другую сторону уравнения",
                "После переноса раздели обе части на 2"
            ]
        )

        time.sleep(0.5)

        # Получаем подсказки
        for level in ["conceptual", "procedural", "specific"]:
            hint = prefetcher.get_hint("linear_equations", level)
            if hint:
                print(f"[{level}]: {hint[:50]}...")

        print(f"\nСтатистика: {prefetcher.stats}")
