"""
MentalModelAgent — Theory-of-Mind агент для MITS (фича 017).

Новая стадия конвейера между Profiler и Planner. На вход принимает
сообщение студента, профиль ошибок, историю диалога и графовый контекст,
на выход — структурированный BeliefState (активная ошибка, модель темы,
предсказанные реакции, уверенность).

Реализация — prompt-only поверх существующего fine-tuned Qwen3.5-9B,
без дополнительного обучения. Источники:
- Kosinski (2023) arXiv:2302.02083 — emergent ToM в LLM
- Strachan et al. (2024) Nature Human Behaviour — state-of-the-art ToM
- Research decision R1 в specs/017-tom-tutor/research.md

Стратегия промпта зависит от активного профиля:
- lite: короткий промпт (~100 input / cap 120 output) — JSON mode для надёжности
- standard/max: полный промпт с 2 few-shot примерами, CoT reasoning, cap 400-500 output

Graceful degradation: при любой ошибке (timeout, invalid JSON, LLM
недоступен) возвращает BeliefState.empty() с confidence=0, не бросает
исключение. Downstream consumers проверяют is_usable() и падают в baseline.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from src.data.schemas import BeliefState, ConversationTurn, StudentProfile

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Шаблоны промптов (русский контент, английские системные инструкции)
# ─────────────────────────────────────────────────────────────────────


SHORT_SYSTEM_PROMPT = (
    "You analyze a student's mental state for a Russian-language STEM tutor. "
    "Output ONE valid JSON object only. No preamble, no markdown. "
    "Content fields in Russian. Field names in English. "
    "Self-assess confidence honestly: 0.9 = student explicitly said it, "
    "0.5 = inferred from error pattern, 0.2 = weak signal."
)

SHORT_USER_TEMPLATE = """Student message: "{message}"
Recent errors: {errors}
Topic: {topic}
Known misconceptions for this topic:
{misconceptions}

Output JSON with these exact keys:
{{
  "active_misconception": "Russian sentence or null",
  "belief_about_topic": "one Russian sentence",
  "predicted_reactions": {{
    "scaffolded": "Russian phrase",
    "conceptual_repair": "Russian phrase",
    "encourage": "Russian phrase"
  }},
  "confidence": 0.0-1.0,
  "reasoning": "one Russian phrase"
}}"""


FULL_SYSTEM_PROMPT = (
    "You are a cognitive scientist modeling a Russian-speaking student's mental state "
    "during STEM tutoring. Your analysis will drive teaching decisions. "
    "Reason step-by-step in 3 stages (misconception → topic belief → reaction prediction), "
    "then output a single JSON object. "
    "All content in Russian. Keys in English. "
    "Confidence rubric: 0.8+ if student explicitly demonstrated, "
    "0.5-0.8 for strong inference from error pattern, 0.2-0.5 for weak signal, "
    "0.0-0.2 if no usable signal. Be conservative — false high confidence misleads the tutor."
)

FULL_FEW_SHOT_EXAMPLES = """### Example 1
Student: "производная произведения равна произведению производных"
Errors: [incorrect product rule application]

Output:
{
  "active_misconception": "Неверный перенос правила суммы на правило произведения",
  "belief_about_topic": "Производная — линейный оператор для всех операций, включая умножение",
  "predicted_reactions": {
    "scaffolded": "Будет искать контрпример самостоятельно при наводящих вопросах",
    "conceptual_repair": "Увидит противоречие на конкретном примере и пересмотрит правило",
    "encourage": "Без контрпримера останется при своей точке зрения"
  },
  "candidate_misconceptions": [],
  "confidence": 0.85,
  "reasoning": "Классический паттерн распространения линейности на нелинейные операции."
}

### Example 2
Student: "я не понимаю что такое предел, что это значит"
Errors: []

Output:
{
  "active_misconception": null,
  "belief_about_topic": "У студента нет чёткой модели понятия предела — открытое непонимание",
  "predicted_reactions": {
    "scaffolded": "Начнёт строить понимание через конкретные примеры",
    "conceptual_repair": "Не сработает — нет ошибочной модели, которую надо чинить",
    "encourage": "Поможет начать задавать вопросы без стеснения"
  },
  "candidate_misconceptions": [],
  "confidence": 0.7,
  "reasoning": "Прямое признание непонимания, не конкретная ошибка — нужна опора."
}
"""

FULL_USER_TEMPLATE = """## Context
Topic: {topic}
Student's recent errors: {errors}
Mastery in related concepts: {mastery}
Known misconceptions for this topic:
{misconceptions}
Recent conversation (last {n_history} turns):
{history}

## Student's latest message
"{message}"

{examples}

## Your task
Reason in 3 steps internally, then output ONLY the final JSON object:

Step 1: Identify active misconception (check against known list first, null if none)
Step 2: State how student models the topic — ONE clear Russian sentence
Step 3: Predict reactions to each strategy: scaffolded, conceptual_repair, encourage

Output ONLY valid JSON matching the schema from examples above."""


# ─────────────────────────────────────────────────────────────────────
# Агент
# ─────────────────────────────────────────────────────────────────────


class MentalModelAgent:
    """Theory-of-Mind агент для выведения BeliefState студента.

    Использует LLM с режимом JSON для структурированного вывода. Выбирает
    стратегию промпта (short / full) по активному resource profile.

    Все ошибки LLM (таймаут, невалидный JSON, недоступность) обрабатываются
    внутри класса — в орчестратор никогда не вылетают исключения.
    """

    def __init__(
        self,
        llm_client: Any,
        knowledge_graph: Any = None,
    ) -> None:
        """
        Args:
            llm_client: Экземпляр LLMClient (или совместимый mock).
            knowledge_graph: Опциональный KnowledgeGraph для доступа к
                misconception-узлам. Если None — промпт не включит граф.
        """
        self._llm = llm_client
        self._graph = knowledge_graph

        # Активный профиль (подтягиваем лениво — можно переключить на тестах)
        try:
            from src.resource_profiles import get_active_profile

            self._profile = get_active_profile()
        except ImportError:
            self._profile = None

    # ── Основной метод ────────────────────────────────────────────

    def infer(
        self,
        student_message: str,
        student_profile: Optional[StudentProfile] = None,
        history: Optional[List[ConversationTurn]] = None,
        graph_context: Optional[Dict] = None,
        topic: str = "",
    ) -> BeliefState:
        """Вывести BeliefState из текущего хода.

        Args:
            student_message: Последнее сообщение студента (русский).
            student_profile: Профиль из Profiler (ошибки, confidence).
            history: Последние ходы диалога (до 3).
            graph_context: Результат Navigator.get_concept_context(), если есть.
            topic: Название текущей темы (русский).

        Returns:
            BeliefState — валидный всегда, confidence=0 при проблемах.
        """
        profile_name = self._profile.name.value if self._profile else "unknown"

        # Пустое сообщение — нет смысла инферить
        if not student_message or not student_message.strip():
            logger.debug("MentalModel: empty student message, skipping inference")
            return BeliefState.empty(profile_name=profile_name)

        logger.info(
            "tom.invoked",
            extra={"profile": profile_name, "msg_len": len(student_message)},
        )

        t0 = time.perf_counter()

        try:
            # Выбор стратегии промпта
            style = self._profile.tom_prompt_style if self._profile else "full"
            output_cap = self._profile.tom_output_cap if self._profile else 400

            if style == "short":
                system, user = self._build_prompt_short(
                    student_message, student_profile, graph_context, topic
                )
            else:
                system, user = self._build_prompt_full(
                    student_message, student_profile, history, graph_context, topic
                )

            # Вызов LLM (одна попытка JSON mode, одна попытка repair)
            raw = self._llm_call(system, user, output_cap=output_cap)
            parsed = self._parse_json(raw)

            # Если первая попытка дала невалидный JSON — один repair проход
            if parsed is None:
                logger.debug("tom.repair_attempt: retrying with repair prompt")
                repair_prompt = user + "\n\nRe-output valid JSON only, no other text:"
                raw2 = self._llm_call(system, repair_prompt, output_cap=output_cap)
                parsed = self._parse_json(raw2)

            if parsed is None:
                latency_ms = (time.perf_counter() - t0) * 1000
                logger.warning(
                    "tom.fallback",
                    extra={"reason": "invalid_json_after_repair", "latency_ms": latency_ms},
                )
                return BeliefState.empty(profile_name=profile_name)

            # Собираем BeliefState из распарсенного JSON
            belief = self._build_belief(parsed, profile_name)

            # Привязка к графу: попытаться найти node_id для misconception
            if belief.active_misconception and self._graph is not None:
                belief.active_misconception_node_id = self._lookup_misconception_node(
                    belief.active_misconception, topic
                )

            latency_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "tom.completed",
                extra={
                    "confidence": belief.confidence,
                    "latency_ms": round(latency_ms, 1),
                    "misconception_detected": belief.active_misconception is not None,
                },
            )
            return belief

        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning(
                "tom.fallback",
                extra={"reason": f"exception: {type(e).__name__}: {e}", "latency_ms": latency_ms},
            )
            return BeliefState.empty(profile_name=profile_name)

    # ── Построение промптов ───────────────────────────────────────

    def _build_prompt_short(
        self,
        student_message: str,
        profile: Optional[StudentProfile],
        graph_context: Optional[Dict],
        topic: str,
    ) -> tuple[str, str]:
        """Короткий промпт для lite profile (~80 input tokens)."""
        errors_str = self._format_errors(profile, short=True)
        misc_str = self._format_misconceptions(graph_context, limit=3, short=True)
        topic_str = topic or "Неизвестно"

        user = SHORT_USER_TEMPLATE.format(
            message=student_message[:300],  # жёсткий лимит для lite
            errors=errors_str,
            topic=topic_str,
            misconceptions=misc_str,
        )
        return SHORT_SYSTEM_PROMPT, user

    def _build_prompt_full(
        self,
        student_message: str,
        profile: Optional[StudentProfile],
        history: Optional[List[ConversationTurn]],
        graph_context: Optional[Dict],
        topic: str,
    ) -> tuple[str, str]:
        """Полный промпт для standard/max с few-shot."""
        errors_str = self._format_errors(profile, short=False)
        mastery_str = self._format_mastery(profile)
        misc_str = self._format_misconceptions(graph_context, limit=5, short=False)
        history_str = self._format_history(history or [], limit=3)
        topic_str = topic or "Неизвестно"

        user = FULL_USER_TEMPLATE.format(
            topic=topic_str,
            errors=errors_str,
            mastery=mastery_str,
            misconceptions=misc_str,
            n_history=min(len(history or []), 3),
            history=history_str,
            message=student_message,
            examples=FULL_FEW_SHOT_EXAMPLES,
        )
        return FULL_SYSTEM_PROMPT, user

    # ── Форматирование контекста ──────────────────────────────────

    @staticmethod
    def _format_errors(profile: Optional[StudentProfile], short: bool) -> str:
        if profile is None:
            return "[]"
        # StudentProfile from profiler.py has errors attribute
        errors = getattr(profile, "errors", None) or []
        if not errors:
            return "[]"
        if short:
            descriptions = [getattr(e, "description", str(e))[:80] for e in errors[:2]]
            return str(descriptions)
        descriptions = [
            f"- {getattr(e, 'error_type', '')}: {getattr(e, 'description', str(e))}"
            for e in errors[:5]
        ]
        return "\n".join(descriptions)

    @staticmethod
    def _format_mastery(profile: Optional[StudentProfile]) -> str:
        if profile is None:
            return "{}"
        mastery = getattr(profile, "mastery_by_skill", None) or {}
        if not mastery:
            return "{}"
        items = [f"  {k}: {v:.2f}" for k, v in list(mastery.items())[:6]]
        return "{\n" + "\n".join(items) + "\n}"

    @staticmethod
    def _format_misconceptions(graph_context: Optional[Dict], limit: int, short: bool) -> str:
        if not graph_context:
            return "(не предоставлены)" if not short else "none"
        miscs = graph_context.get("misconceptions", []) if isinstance(graph_context, dict) else []
        if not miscs:
            return "(не предоставлены)" if not short else "none"
        if short:
            titles = [m.get("title", "")[:50] for m in miscs[:limit]]
            return "; ".join(t for t in titles if t)
        lines = []
        for m in miscs[:limit]:
            title = m.get("title", "")
            content = m.get("content", "")[:100]
            if title:
                lines.append(f"- {title}: {content}")
        return "\n".join(lines) if lines else "none"

    @staticmethod
    def _format_history(history: List[ConversationTurn], limit: int) -> str:
        if not history:
            return "(нет предыдущих ходов)"
        lines = []
        for turn in history[-limit:]:
            role = getattr(turn, "role", "?")
            content = getattr(turn, "content", "")[:150]
            lines.append(f"  [{role}] {content}")
        return "\n".join(lines)

    # ── Взаимодействие с LLM ─────────────────────────────────────

    def _llm_call(self, system: str, user: str, output_cap: int) -> str:
        """Вызов LLM.generate() с JSON mode и ограничением output tokens.

        Thinking mode отключен: thinking-модели вроде Qwen3.5-think
        тратят токены на <think>...</think> блок, что вытесняет JSON
        из max_tokens budget. Для structured output thinking контрпродуктивен.
        """
        return self._llm.generate(
            prompt=user,
            system=system,
            json_mode=True,
            max_tokens=output_cap,
            temperature=0.3,  # низкая для стабильности JSON
            thinking=False,  # КРИТИЧНО: отключить thinking для ToM
        )

    @staticmethod
    def _parse_json(raw: str) -> Optional[Dict]:
        """Парсинг JSON с пост-обработкой типичных артефактов LLM."""
        if not raw or not raw.strip():
            return None

        text = raw.strip()
        # Уберём markdown-fence если есть
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
            # Отрежем хвостовой ```
            if "```" in text:
                text = text.split("```")[0]

        # Найдём первый { и последний }
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        candidate = text[start : end + 1]

        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None

    # ── Сборка BeliefState ───────────────────────────────────────

    def _build_belief(self, data: Dict, profile_name: str) -> BeliefState:
        """Конвертирует распарсенный dict в BeliefState, заполняя пропуски."""
        try:
            return BeliefState(
                active_misconception=data.get("active_misconception"),
                belief_about_topic=str(data.get("belief_about_topic", ""))[:500],
                predicted_reactions={
                    k: str(v)[:200]
                    for k, v in (data.get("predicted_reactions") or {}).items()
                    if isinstance(k, str) and isinstance(v, (str, int, float))
                },
                candidate_misconceptions=[
                    str(x)[:200] for x in (data.get("candidate_misconceptions") or [])[:3]
                ],
                confidence=max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
                reasoning=str(data.get("reasoning", ""))[:500],
                profile_used=profile_name,
            )
        except (TypeError, ValueError) as e:
            logger.warning(f"tom.build_belief_failed: {e}")
            return BeliefState.empty(profile_name=profile_name)

    # ── Привязка misconception к графу ────────────────────────────

    def _lookup_misconception_node(self, misconception_text: str, topic: str) -> Optional[str]:
        """Найти MISCONCEPTION-узел в графе, совпадающий по содержимому.

        Простая эвристика: keyword overlap между текстом misconception и
        контентом узлов. Без эмбеддингов — требование Lite-профиля.
        """
        if not self._graph or not misconception_text:
            return None

        from src.knowledge.knowledge_forge import NodeType

        # Токенизация (простая — split + lower + длина > 3)
        words = {w.lower() for w in misconception_text.split() if len(w) > 3}
        if not words:
            return None

        best_id = None
        best_score = 0
        try:
            misc_nodes = self._graph.search(node_type=NodeType.MISCONCEPTION)
            for node in misc_nodes:
                node_words = {
                    w.lower()
                    for w in (node.content or "").split() + (node.title or "").split()
                    if len(w) > 3
                }
                overlap = len(words & node_words)
                if overlap > best_score:
                    best_score = overlap
                    best_id = node.id
        except Exception as e:
            logger.debug(f"tom.lookup_node_failed: {e}")
            return None

        # Минимум 2 общих слова, иначе ненадёжно
        return best_id if best_score >= 2 else None
