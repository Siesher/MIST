#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Retriever для MITS.

Извлекает релевантные подсказки и информацию о типичных ошибках
для контекстуализации ответов репетитора.

На основе исследований:
- RAG for Education (2025) - context-aware re-ranking
- Knowledge-Grounded ITS - hint progression tracking
- SocraticLLM (2025) - scaffolding levels
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from src.models.knowledge_tracing import KnowledgeTracker

logger = logging.getLogger(__name__)


class HintLevel(Enum):
    """Уровни подсказок для progressive scaffolding."""

    CONCEPTUAL = "conceptual"  # Концептуальные вопросы
    PROCEDURAL = "procedural"  # Процедурные подсказки
    SPECIFIC = "specific"  # Конкретные указания


# Minimum similarity score for RAG results (fallback threshold)
RAG_SIMILARITY_THRESHOLD = 0.3
RAG_FALLBACK_THRESHOLD = 0.2

# Опциональные зависимости для векторного поиска
try:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False
    logger.info("sentence-transformers не установлен. Используется keyword matching.")

try:
    import chromadb

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


@dataclass
class Hint:
    """Подсказка для репетитора с поддержкой progressive scaffolding."""

    id: str
    skill: str
    level: HintLevel
    trigger: str
    hint_ru: str
    hint_en: str
    follow_up_question: str
    topic: str = ""
    difficulty: str = "medium"
    keywords: List[str] = field(default_factory=list)

    @property
    def content(self) -> str:
        """Основной контент подсказки (русский)."""
        return self.hint_ru

    @property
    def hint_level(self) -> int:
        """Numeric level for backward compatibility."""
        return {HintLevel.CONCEPTUAL: 1, HintLevel.PROCEDURAL: 2, HintLevel.SPECIFIC: 3}.get(
            self.level, 1
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], topic: str = "") -> "Hint":
        # Parse level from string
        level_str = data.get("level", "conceptual").lower()
        try:
            level = HintLevel(level_str)
        except ValueError:
            level = HintLevel.CONCEPTUAL

        return cls(
            id=data.get("id", ""),
            skill=data.get("skill", ""),
            level=level,
            trigger=data.get("trigger", ""),
            hint_ru=data.get("hint_ru", data.get("content", "")),
            hint_en=data.get("hint_en", ""),
            follow_up_question=data.get("follow_up_question", ""),
            topic=topic or data.get("topic", ""),
            difficulty=data.get("difficulty", "medium"),
            keywords=data.get("keywords", []),
        )


@dataclass
class Misconception:
    """Типичная ошибка ученика."""

    id: str
    topic: str
    skill: str
    error_pattern: str
    correct_form: str
    explanation_ru: str
    explanation_en: str
    remediation_strategy: str
    example_ru: str
    example_en: str
    severity: float = 0.5
    frequency: str = "common"

    @property
    def example_wrong(self) -> str:
        """Backward compatibility."""
        return self.error_pattern

    @property
    def example_correct(self) -> str:
        """Backward compatibility."""
        return self.correct_form

    @property
    def correction_question(self) -> str:
        """Generate a correction question based on the misconception."""
        return f"Давай проверим: {self.example_ru}"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Misconception":
        return cls(
            id=data.get("id", ""),
            topic=data.get("topic", ""),
            skill=data.get("skill", ""),
            error_pattern=data.get("error_pattern", ""),
            correct_form=data.get("correct_form", ""),
            explanation_ru=data.get("explanation_ru", ""),
            explanation_en=data.get("explanation_en", ""),
            remediation_strategy=data.get("remediation_strategy", "scaffolding"),
            example_ru=data.get("example_ru", ""),
            example_en=data.get("example_en", ""),
            severity=_parse_severity(data.get("severity", 0.5)),
            frequency=data.get("frequency", "common"),
        )


def _parse_severity(value: Any) -> float:
    """Normalize a misconception severity into a [0, 1] weight for RAG ranking.

    Accepts a number (clamped to [0, 1]) or a string label ('high'/'medium'/'low').
    Fixes the crash where the data file stores ``"severity": "high"`` and the old
    code did ``float("high")`` → ValueError, silently degrading every misconception.
    """
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    label = str(value).strip().lower()
    # String labels → [0, 1] ranking weights, strictly ordered so RAG surfaces
    # the most severe misconceptions first. "medium" coincides with the 0.5
    # fallback used for unknown/missing labels — i.e. neutral severity.
    severity_map: Dict[str, float] = {"high": 0.9, "medium": 0.5, "low": 0.2}
    return severity_map.get(label, 0.5)


@dataclass
class HintProgressionState:
    """Состояние прогрессии подсказок для сессии."""

    skill: str
    current_level: HintLevel = HintLevel.CONCEPTUAL
    hints_given: int = 0
    last_hint_id: Optional[str] = None

    def advance(self) -> HintLevel:
        """Продвинуть уровень подсказки."""
        self.hints_given += 1
        if self.current_level == HintLevel.CONCEPTUAL and self.hints_given >= 2:
            self.current_level = HintLevel.PROCEDURAL
        elif self.current_level == HintLevel.PROCEDURAL and self.hints_given >= 4:
            self.current_level = HintLevel.SPECIFIC
        return self.current_level


@dataclass
class TutoringContext:
    """Контекст для репетитора, извлечённый из RAG."""

    hints: List[Hint] = field(default_factory=list)
    misconceptions: List[Misconception] = field(default_factory=list)
    related_topics: List[str] = field(default_factory=list)
    hint_progression: Optional[HintProgressionState] = None
    retrieval_scores: List[float] = field(default_factory=list)
    used_fallback: bool = False
    # Чанки прикреплённого источника (document-RAG, этап 2). Наполняются на уровне
    # сервиса по релевантности к вопросу; попадают в промпт первым блоком.
    chunks: List[str] = field(default_factory=list)

    def get_hint_for_level(self, level: HintLevel) -> Optional[Hint]:
        """Получить подсказку определённого уровня."""
        for hint in self.hints:
            if hint.level == level:
                return hint
        return self.hints[0] if self.hints else None

    def get_progressive_hint(self) -> Optional[Hint]:
        """Получить подсказку следующего уровня в прогрессии."""
        if self.hint_progression:
            return self.get_hint_for_level(self.hint_progression.current_level)
        return self.hints[0] if self.hints else None

    def to_prompt_context(self) -> str:
        """Преобразование в текст для добавления в промпт."""
        parts = []

        # Материал из прикреплённого источника — первым: для ответа важнее подсказок.
        if self.chunks:
            parts.append("МАТЕРИАЛ ИЗ ИСТОЧНИКА (используй, если относится к вопросу):")
            for i, chunk in enumerate(self.chunks, 1):
                parts.append(f"  [{i}] {chunk.strip()}")
            parts.append("")

        if self.hints:
            parts.append("ПОДСКАЗКИ ДЛЯ ЭТОЙ ТЕМЫ:")
            # Группируем по уровням
            for level in [HintLevel.CONCEPTUAL, HintLevel.PROCEDURAL, HintLevel.SPECIFIC]:
                level_hints = [h for h in self.hints if h.level == level]
                if level_hints:
                    level_name = {
                        HintLevel.CONCEPTUAL: "Концептуальный",
                        HintLevel.PROCEDURAL: "Процедурный",
                        HintLevel.SPECIFIC: "Конкретный",
                    }[level]
                    for hint in level_hints[:1]:  # Одна подсказка каждого уровня
                        parts.append(f"  - [{level_name}] {hint.content}")
                        if hint.follow_up_question:
                            parts.append(f"    Вопрос: {hint.follow_up_question}")

        if self.misconceptions:
            parts.append("\nТИПИЧНЫЕ ОШИБКИ УЧЕНИКОВ:")
            for misc in self.misconceptions[:2]:  # Максимум 2 ошибки
                parts.append(f"  - Ошибка: {misc.error_pattern}")
                parts.append(f"    Правильно: {misc.correct_form}")
                parts.append(f"    Стратегия: {misc.remediation_strategy}")

        if self.used_fallback:
            parts.append("\n[Внимание: использован fallback - точные совпадения не найдены]")

        return "\n".join(parts) if parts else ""


class TutoringRAG:
    """
    RAG система для сократического репетитора.

    Извлекает релевантные подсказки и информацию о типичных ошибках
    на основе текущей задачи и состояния ученика.

    Особенности:
    - Context-aware re-ranking на основе знаний студента
    - Progressive hint scaffolding (conceptual→procedural→specific)
    - Fallback mechanism при низком score
    - Поддержка JSON и JSONL форматов

    Поддерживает два режима:
    1. Keyword matching (без дополнительных зависимостей)
    2. Semantic search (с sentence-transformers и ChromaDB)
    """

    def __init__(
        self,
        knowledge_path: Optional[Path] = None,
        use_embeddings: bool = True,
        knowledge_tracker: Optional["KnowledgeTracker"] = None,
        similarity_threshold: float = RAG_SIMILARITY_THRESHOLD,
        fallback_threshold: float = RAG_FALLBACK_THRESHOLD,
    ):
        """
        Инициализация RAG системы.

        Args:
            knowledge_path: Путь к директории с базой знаний
            use_embeddings: Использовать векторный поиск (требует sentence-transformers)
            knowledge_tracker: KnowledgeTracker для context-aware re-ranking
            similarity_threshold: Минимальный score для результатов
            fallback_threshold: Threshold для fallback механизма
        """
        if knowledge_path is None:
            # Определяем путь относительно текущего файла
            knowledge_path = Path(__file__).parent.parent.parent / "data" / "knowledge"

        self.knowledge_path = Path(knowledge_path)
        self.use_embeddings = use_embeddings and HAS_EMBEDDINGS
        self.knowledge_tracker = knowledge_tracker
        self.similarity_threshold = similarity_threshold
        self.fallback_threshold = fallback_threshold

        # Загружаем данные
        self.hints: Dict[str, List[Hint]] = {}  # topic -> hints
        self.hints_by_skill: Dict[str, List[Hint]] = {}  # skill -> hints
        self.misconceptions: Dict[str, List[Misconception]] = {}  # topic -> misconceptions
        self.misconceptions_by_skill: Dict[str, List[Misconception]] = {}  # skill -> misconceptions
        self.all_hints: List[Hint] = []
        self.all_misconceptions: List[Misconception] = []

        # Hint progression tracking per session
        self._hint_progressions: Dict[
            str, Dict[str, HintProgressionState]
        ] = {}  # student_id -> skill -> state

        self._load_knowledge_base()

        # Инициализируем эмбеддинги если доступны
        self.embedder = None
        self.hint_embeddings = None
        self.misconception_embeddings = None

        if self.use_embeddings:
            self._init_embeddings()

        logger.info(
            f"RAG инициализирован: {len(self.all_hints)} подсказок, "
            f"{len(self.all_misconceptions)} ошибок, embeddings={self.use_embeddings}"
        )

    def set_knowledge_tracker(self, tracker: "KnowledgeTracker"):
        """Set or update the knowledge tracker."""
        self.knowledge_tracker = tracker

    def _load_knowledge_base(self):
        """Загрузка базы знаний из JSON и JSONL файлов."""
        # Загружаем подсказки
        hints_path = self.knowledge_path / "hints"
        if hints_path.exists():
            # JSON files (new format)
            for file in hints_path.glob("*.json"):
                topic = file.stem
                self._load_hints_from_json(file, topic)

            # JSONL files (legacy format)
            for file in hints_path.glob("*.jsonl"):
                topic = file.stem
                self._load_hints_from_jsonl(file, topic)

        # Загружаем типичные ошибки
        misconceptions_path = self.knowledge_path / "misconceptions"
        if misconceptions_path.exists():
            # JSON files (new format)
            for file in misconceptions_path.glob("*.json"):
                self._load_misconceptions_from_json(file)

            # JSONL files (legacy format)
            for file in misconceptions_path.glob("*.jsonl"):
                self._load_misconceptions_from_jsonl(file)

            # Также проверяем поддиректории
            for subdir in misconceptions_path.iterdir():
                if subdir.is_dir():
                    for file in subdir.glob("*.json"):
                        self._load_misconceptions_from_json(file)
                    for file in subdir.glob("*.jsonl"):
                        self._load_misconceptions_from_jsonl(file)

        logger.debug(
            f"Загружено: {len(self.all_hints)} подсказок по {len(self.hints_by_skill)} навыкам, "
            f"{len(self.all_misconceptions)} ошибок"
        )

    def _load_hints_from_json(self, file: Path, topic: str):
        """Load hints from JSON file (new format)."""
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            hints_data = data.get("hints", [])
            if topic not in self.hints:
                self.hints[topic] = []

            for hint_data in hints_data:
                hint = Hint.from_dict(hint_data, topic=topic)
                self.hints[topic].append(hint)
                self.all_hints.append(hint)

                # Index by skill
                skill = hint.skill
                if skill not in self.hints_by_skill:
                    self.hints_by_skill[skill] = []
                self.hints_by_skill[skill].append(hint)

            logger.debug(f"Loaded {len(hints_data)} hints from {file.name}")

        except Exception as e:
            logger.warning(f"Error loading hints from {file}: {e}")

    def _load_hints_from_jsonl(self, file: Path, topic: str):
        """Load hints from JSONL file (legacy format)."""
        try:
            if topic not in self.hints:
                self.hints[topic] = []

            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        hint = Hint.from_dict(data, topic=topic)
                        self.hints[topic].append(hint)
                        self.all_hints.append(hint)

                        skill = hint.skill
                        if skill not in self.hints_by_skill:
                            self.hints_by_skill[skill] = []
                        self.hints_by_skill[skill].append(hint)

        except Exception as e:
            logger.warning(f"Error loading hints from {file}: {e}")

    def _load_misconceptions_from_json(self, file: Path):
        """Load misconceptions from JSON file (new format)."""
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            misconceptions_data = data.get("misconceptions", [])

            for misc_data in misconceptions_data:
                misc = Misconception.from_dict(misc_data)
                topic = misc.topic
                skill = misc.skill

                if topic not in self.misconceptions:
                    self.misconceptions[topic] = []
                self.misconceptions[topic].append(misc)

                if skill not in self.misconceptions_by_skill:
                    self.misconceptions_by_skill[skill] = []
                self.misconceptions_by_skill[skill].append(misc)

                self.all_misconceptions.append(misc)

            logger.debug(f"Loaded {len(misconceptions_data)} misconceptions from {file.name}")

        except Exception as e:
            logger.warning(f"Error loading misconceptions from {file}: {e}")

    def _load_misconceptions_from_jsonl(self, file: Path):
        """Load misconceptions from JSONL file (legacy format)."""
        try:
            with open(file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        misc = Misconception.from_dict(data)
                        topic = misc.topic
                        skill = misc.skill

                        if topic not in self.misconceptions:
                            self.misconceptions[topic] = []
                        self.misconceptions[topic].append(misc)

                        if skill not in self.misconceptions_by_skill:
                            self.misconceptions_by_skill[skill] = []
                        self.misconceptions_by_skill[skill].append(misc)

                        self.all_misconceptions.append(misc)

        except Exception as e:
            logger.warning(f"Error loading misconceptions from {file}: {e}")

    def _init_embeddings(self):
        """Инициализация модели эмбеддингов."""
        try:
            # Используем маленькую многоязычную модель
            self.embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

            # Создаём эмбеддинги для подсказок
            hint_texts = [h.content for h in self.all_hints]
            if hint_texts:
                self.hint_embeddings = self.embedder.encode(hint_texts)

            # Создаём эмбеддинги для ошибок
            misc_texts = [
                m.error_pattern + " " + m.correction_question for m in self.all_misconceptions
            ]
            if misc_texts:
                self.misconception_embeddings = self.embedder.encode(misc_texts)

            logger.info("Эмбеддинги успешно созданы")

        except Exception as e:
            logger.warning(f"Ошибка инициализации эмбеддингов: {e}")
            self.use_embeddings = False

    def retrieve_hints(
        self,
        problem: str,
        topic: Optional[str] = None,
        skill: Optional[str] = None,
        difficulty: Optional[str] = None,
        student_id: Optional[str] = None,
        top_k: int = 3,
    ) -> Tuple[List[Hint], List[float], bool]:
        """
        Извлечение релевантных подсказок с context-aware re-ranking.

        Args:
            problem: Текст задачи или вопроса ученика
            topic: Тема (если известна)
            skill: Конкретный навык
            difficulty: Уровень сложности
            student_id: ID студента для context-aware ranking
            top_k: Максимальное количество подсказок

        Returns:
            Tuple of (hints, scores, used_fallback)
        """
        # Если навык известен, ищем сначала по нему
        candidate_hints = self.all_hints
        used_fallback = False

        if skill and skill in self.hints_by_skill:
            candidate_hints = self.hints_by_skill[skill] + [
                h for h in self.all_hints if h.skill != skill
            ]
        elif topic and topic in self.hints:
            candidate_hints = self.hints[topic] + [h for h in self.all_hints if h.topic != topic]

        # Фильтр по сложности
        if difficulty:
            difficulty_filtered = [h for h in candidate_hints if h.difficulty == difficulty]
            if difficulty_filtered:
                candidate_hints = difficulty_filtered

        # Retrieve hints
        if self.use_embeddings and self.hint_embeddings is not None:
            hints, scores = self._semantic_search_with_scores(
                problem,
                self.hint_embeddings,
                self.all_hints,
                top_k * 2,  # Get more for re-ranking
            )
        else:
            hints, scores = self._keyword_match_with_scores(
                problem, candidate_hints, lambda h: h.keywords + [h.topic, h.skill], top_k * 2
            )

        # Context-aware re-ranking if knowledge tracker available
        if student_id and self.knowledge_tracker and hints:
            hints, scores = self._rerank_by_knowledge_state(hints, scores, student_id)

        # Check threshold and apply fallback if needed
        if not hints or (scores and max(scores) < self.fallback_threshold):
            # Fallback: return hints from the topic/skill regardless of similarity
            fallback_hints = self._get_fallback_hints(topic, skill, top_k)
            if fallback_hints:
                hints = fallback_hints
                scores = [0.1] * len(fallback_hints)
                used_fallback = True
                logger.debug(f"Using fallback hints for {topic}/{skill}")

        return hints[:top_k], scores[:top_k], used_fallback

    def _rerank_by_knowledge_state(
        self, hints: List[Hint], scores: List[float], student_id: str
    ) -> Tuple[List[Hint], List[float]]:
        """
        Re-rank hints based on student's knowledge state.

        Prioritizes hints for skills where the student is struggling.
        """
        try:
            student = self.knowledge_tracker.get_student(student_id, apply_decay=False)

            # Adjust scores based on mastery (lower mastery = higher priority)
            adjusted = []
            for hint, score in zip(hints, scores):
                skill = hint.skill
                mastery = student.get_mastery(skill)

                # Boost score for skills with lower mastery
                mastery_boost = 1.0 - mastery  # 0-1, higher for weak skills
                adjusted_score = score * (1.0 + mastery_boost * 0.5)

                adjusted.append((hint, adjusted_score))

            # Sort by adjusted score
            adjusted.sort(key=lambda x: x[1], reverse=True)

            return [h for h, _ in adjusted], [s for _, s in adjusted]

        except Exception as e:
            logger.warning(f"Re-ranking failed: {e}")
            return hints, scores

    def _get_fallback_hints(
        self, topic: Optional[str], skill: Optional[str], count: int
    ) -> List[Hint]:
        """Get fallback hints when similarity search fails."""
        if skill and skill in self.hints_by_skill:
            return self.hints_by_skill[skill][:count]
        if topic and topic in self.hints:
            return self.hints[topic][:count]
        return self.all_hints[:count] if self.all_hints else []

    def _semantic_search_with_scores(
        self, query: str, embeddings, items: List[Any], top_k: int
    ) -> Tuple[List[Any], List[float]]:
        """Semantic search returning items with scores."""
        if embeddings is None or len(embeddings) == 0:
            return [], []

        query_embedding = self.embedder.encode([query])[0]

        # Косинусное сходство
        similarities = np.dot(embeddings, query_embedding) / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Топ-k индексов
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        scores = []
        for i in top_indices:
            if similarities[i] >= self.fallback_threshold:
                results.append(items[i])
                scores.append(float(similarities[i]))

        return results, scores

    def _keyword_match_with_scores(
        self, query: str, items: List[Any], get_keywords: callable, top_k: int
    ) -> Tuple[List[Any], List[float]]:
        """Keyword matching returning items with scores."""
        query_words = set(query.lower().split())

        scored_items = []
        for item in items:
            keywords = get_keywords(item)
            keyword_set = set(k.lower() for k in keywords if k)

            # Считаем пересечение
            score = len(query_words & keyword_set)

            # Также проверяем вхождение слов запроса в контент
            content = str(
                item.content if hasattr(item, "content") else getattr(item, "error_pattern", "")
            )
            for word in query_words:
                if len(word) > 2 and word in content.lower():
                    score += 0.5

            # Normalize score
            max_possible = len(query_words) + len(query_words) * 0.5
            normalized_score = score / max_possible if max_possible > 0 else 0

            if normalized_score > 0:
                scored_items.append((item, normalized_score))

        # Сортируем по score
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return (
            [item for item, _ in scored_items[:top_k]],
            [score for _, score in scored_items[:top_k]],
        )

    def retrieve_misconceptions(
        self,
        problem: str,
        student_response: Optional[str] = None,
        topic: Optional[str] = None,
        skill: Optional[str] = None,
        student_id: Optional[str] = None,
        top_k: int = 2,
    ) -> Tuple[List[Misconception], List[float], bool]:
        """
        Извлечение релевантных типичных ошибок.

        Args:
            problem: Текст задачи
            student_response: Ответ ученика (для поиска ошибок)
            topic: Тема
            skill: Навык
            student_id: ID студента для context-aware ranking
            top_k: Максимальное количество ошибок

        Returns:
            Tuple of (misconceptions, scores, used_fallback)
        """
        query = problem
        if student_response:
            query = f"{problem} {student_response}"

        used_fallback = False
        candidate_misconceptions = self.all_misconceptions

        if skill and skill in self.misconceptions_by_skill:
            candidate_misconceptions = self.misconceptions_by_skill[skill] + [
                m for m in self.all_misconceptions if m.skill != skill
            ]
        elif topic and topic in self.misconceptions:
            candidate_misconceptions = self.misconceptions[topic] + [
                m for m in self.all_misconceptions if m.topic != topic
            ]

        if self.use_embeddings and self.misconception_embeddings is not None:
            misconceptions, scores = self._semantic_search_with_scores(
                query, self.misconception_embeddings, self.all_misconceptions, top_k * 2
            )
        else:
            misconceptions, scores = self._keyword_match_with_scores(
                query,
                candidate_misconceptions,
                lambda m: [m.topic, m.skill] + m.error_pattern.lower().split()[:5],
                top_k * 2,
            )

        # Fallback if no good matches
        if not misconceptions or (scores and max(scores) < self.fallback_threshold):
            fallback = self._get_fallback_misconceptions(topic, skill, top_k)
            if fallback:
                misconceptions = fallback
                scores = [0.1] * len(fallback)
                used_fallback = True

        return misconceptions[:top_k], scores[:top_k], used_fallback

    def _get_fallback_misconceptions(
        self, topic: Optional[str], skill: Optional[str], count: int
    ) -> List[Misconception]:
        """Get fallback misconceptions when similarity search fails."""
        if skill and skill in self.misconceptions_by_skill:
            return self.misconceptions_by_skill[skill][:count]
        if topic and topic in self.misconceptions:
            return self.misconceptions[topic][:count]
        return self.all_misconceptions[:count] if self.all_misconceptions else []

    def retrieve_context(
        self,
        problem: str,
        student_response: Optional[str] = None,
        topic: Optional[str] = None,
        skill: Optional[str] = None,
        difficulty: Optional[str] = None,
        student_id: Optional[str] = None,
    ) -> TutoringContext:
        """
        Извлечение полного контекста для репетитора.

        Args:
            problem: Текст задачи
            student_response: Последний ответ ученика
            topic: Тема
            skill: Навык
            difficulty: Уровень сложности
            student_id: ID студента

        Returns:
            TutoringContext с подсказками и информацией об ошибках
        """
        hints, hint_scores, hint_fallback = self.retrieve_hints(
            problem, topic, skill, difficulty, student_id
        )
        misconceptions, misc_scores, misc_fallback = self.retrieve_misconceptions(
            problem, student_response, topic, skill, student_id
        )

        # Get hint progression state if student_id provided
        hint_progression = None
        if student_id and skill:
            hint_progression = self.get_hint_progression(student_id, skill)

        return TutoringContext(
            hints=hints,
            misconceptions=misconceptions,
            related_topics=[topic] if topic else [],
            hint_progression=hint_progression,
            retrieval_scores=hint_scores + misc_scores,
            used_fallback=hint_fallback or misc_fallback,
        )

    def get_hint_progression(self, student_id: str, skill: str) -> HintProgressionState:
        """Get or create hint progression state for a student/skill."""
        if student_id not in self._hint_progressions:
            self._hint_progressions[student_id] = {}

        if skill not in self._hint_progressions[student_id]:
            self._hint_progressions[student_id][skill] = HintProgressionState(skill=skill)

        return self._hint_progressions[student_id][skill]

    def advance_hint_progression(
        self, student_id: str, skill: str, hint_id: Optional[str] = None
    ) -> HintLevel:
        """
        Advance hint progression for a student/skill.

        Called when a hint is given to track progression.
        """
        progression = self.get_hint_progression(student_id, skill)
        progression.last_hint_id = hint_id
        return progression.advance()

    def get_next_hint_level(self, student_id: str, skill: str) -> HintLevel:
        """Get the next hint level for progressive scaffolding."""
        progression = self.get_hint_progression(student_id, skill)
        return progression.current_level

    def retrieve_progressive_hint(
        self, problem: str, student_id: str, skill: str, topic: Optional[str] = None
    ) -> Optional[Hint]:
        """
        Retrieve the next hint in the progression sequence.

        Implements progressive scaffolding: conceptual → procedural → specific.
        """
        current_level = self.get_next_hint_level(student_id, skill)

        # Get hints for this skill at the current level
        candidates = []
        if skill in self.hints_by_skill:
            candidates = [h for h in self.hints_by_skill[skill] if h.level == current_level]

        if not candidates and topic and topic in self.hints:
            candidates = [h for h in self.hints[topic] if h.level == current_level]

        if not candidates:
            # Fallback to any hint at this level
            candidates = [h for h in self.all_hints if h.level == current_level]

        if candidates:
            # Select best match using keyword matching
            hints, _ = self._keyword_match_with_scores(
                problem, candidates, lambda h: h.keywords + [h.skill, h.trigger], 1
            )
            if hints:
                self.advance_hint_progression(student_id, skill, hints[0].id)
                return hints[0]

        return None

    def get_hint_chain(self, hint_id: str) -> List[Hint]:
        """
        Получение цепочки подсказок по ID первой.

        Args:
            hint_id: ID начальной подсказки

        Returns:
            Список подсказок в порядке следования
        """
        chain = []
        current_id = hint_id

        # Создаём индекс по ID
        hint_index = {h.id: h for h in self.all_hints}

        while current_id and current_id in hint_index:
            hint = hint_index[current_id]
            chain.append(hint)
            current_id = hint.next_hint

        return chain


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    rag = TutoringRAG()

    # Тест извлечения подсказок
    print("\n=== Тест RAG ===")

    problem = "Решить уравнение x^2 - 5x + 6 = 0"
    context = rag.retrieve_context(
        problem=problem, topic="quadratic_equations", difficulty="medium"
    )

    print(f"\nЗадача: {problem}")
    print(f"\nНайдено подсказок: {len(context.hints)}")
    for hint in context.hints:
        print(f"  - [{hint.hint_level}] {hint.content}")

    print(f"\nНайдено типичных ошибок: {len(context.misconceptions)}")
    for misc in context.misconceptions:
        print(f"  - {misc.error_pattern}")

    print("\n=== Контекст для промпта ===")
    print(context.to_prompt_context())
