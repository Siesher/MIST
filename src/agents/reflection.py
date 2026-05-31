"""LLM reflection over recent sessions → rich markdown memory + structured signals.

Runs offline (during a "dream"). It consumes the *full* evidence of recent
sessions — the real problems, the dialogue with Socratic moves and ✓/✗ markers,
pacing — plus the student's current profile, and produces:

1. a multi-section analytical note appended to ``dreams/`` (append-only journal);
2. a **consolidated** durable profile that *supersedes* (does not stack on) the
   previous one — the model is handed the old profile and asked to merge + dedup.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, List

from src.memory.memory_files import StudentMemoryFiles

logger = logging.getLogger(__name__)


@dataclass
class SessionDigest:
    """A single session distilled to everything the reflection can reason over.

    Attributes:
        topic: Session topic (real topic resolved from the task when possible).
        problem: The actual problem statement the student worked on.
        answer: Reference answer/solution, if known.
        difficulty: ``easy`` / ``medium`` / ``hard`` (or empty).
        mode: Session mode (``guided_learning`` / ``chat`` / ``task_generator``).
        subject: STEM subject (``math`` / ``physics`` / ...).
        solved: Whether the session ended solved.
        hints: Hints consumed.
        attempts: Submitted attempts.
        turns: Total messages exchanged.
        duration_min: Wall-clock minutes between session start and last update.
        transcript: Readable dialogue lines (role + move + ✓/✗ + content).
        errors: Short excerpts of messages explicitly marked incorrect.
    """

    topic: str
    problem: str = ""
    answer: str = ""
    difficulty: str = ""
    mode: str = ""
    subject: str = ""
    solved: bool = False
    hints: int = 0
    attempts: int = 0
    turns: int = 0
    duration_min: float = 0.0
    transcript: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class ReflectionResult:
    """Structured output of a reflection pass."""

    reflection_md: str
    profile_md: str = ""
    misconceptions: List[str] = field(default_factory=list)
    next_focus: List[str] = field(default_factory=list)


_SYSTEM = (
    "Ты — опытный наставник-репетитор, который во время «сна» глубоко осмысляет недавние "
    "занятия одного ученика. Тебе дают РЕАЛЬНЫЕ задачи, ПОЛНЫЙ диалог (с пометками ✓/✗ и "
    "сократическими ходами тьютора в [скобках]) и текущий профиль ученика.\n\n"
    "Проанализируй ВСЮ доступную информацию и верни СТРОГО ОДИН JSON-объект (без текста вне JSON) "
    "со следующими ключами:\n"
    "- reflection_md (string): подробная markdown-рефлексия со ВСЕМИ разделами:\n"
    "  ## Что освоено — конкретные сильные стороны С ДОКАЗАТЕЛЬСТВАМИ из диалога;\n"
    "  ## Заблуждения и пробелы — конкретные ошибки/непонимания с указанием момента "
    "(что именно ученик сделал или сказал, по возможности с цитатой);\n"
    "  ## Эмоции и вовлечённость — настойчивость, признаки фрустрации, как ученик "
    "использовал или игнорировал подсказки, темп работы;\n"
    "  ## Что делать дальше — конкретные шаги и какие сократические ходы сработали, а какие нет.\n"
    "- profile_md (string): ПОЛНЫЙ обновлённый durable-профиль ученика в markdown. Объедини "
    "текущий профиль с новыми наблюдениями, УБЕРИ повторы и устаревшее, structure в разделы "
    "(### Сильные стороны / ### Пробелы и заблуждения / ### Подход к обучению). Это ПОЛНАЯ ЗАМЕНА "
    "старого профиля, а не добавка. Держи ёмко (до ~1200 символов).\n"
    "- misconceptions (array<string>): конкретные заблуждения, пригодные как узлы графа знаний.\n"
    "- next_focus (array<string>): 2–5 тем/навыков для следующих занятий.\n\n"
    "Опирайся на ДОКАЗАТЕЛЬСТВА из диалога. Избегай общих фраз вроде «нужен полный перезапуск» — "
    "будь конкретным, точным и полезным."
)


class ReflectionGenerator:
    """Turn recent-session digests into a rich reflection + consolidated profile."""

    def __init__(
        self,
        llm: Any,
        memory: StudentMemoryFiles,
        *,
        thinking: bool = False,
        max_tokens: int = 4096,
    ) -> None:
        """Initialize the generator.

        Args:
            llm: Client exposing ``generate(prompt, system=..., thinking=...,
                max_tokens=...) -> str``.
            memory: Per-student file store to write the dream and profile into.
            thinking: Keep ``False`` — with the model's thinking channel on, the
                reasoning leaks into the response and breaks the strict-JSON
                contract (analytical depth comes from the rich prompt instead).
            max_tokens: Generation budget; sized so the rich multi-section answer
                is not truncated mid-JSON.
        """
        self._llm = llm
        self._mem = memory
        self._thinking = thinking
        self._max_tokens = max_tokens

    def reflect(self, digests: List[SessionDigest]) -> ReflectionResult:
        """Reflect over the given session digests; write memory files; return signals.

        Args:
            digests: Recent sessions distilled for analysis.

        Returns:
            The structured :class:`ReflectionResult`. On LLM error or unparsable
            output, falls back to a heuristic summary (still writes a dream).
        """
        prompt = self._build_prompt(digests)
        fallback = self._fallback(digests)
        try:
            raw = self._llm.generate(
                prompt=prompt,
                system=_SYSTEM,
                thinking=self._thinking,
                max_tokens=self._max_tokens,
            )
            data = json.loads(_strip_fences(raw))
            if not isinstance(data, dict):
                raise ValueError("reflection JSON is not an object")
        except Exception as e:  # LLM error or bad JSON → heuristic fallback
            logger.warning("reflection_fallback: %s", type(e).__name__)
            data = fallback

        reflection_md = str(data.get("reflection_md") or fallback["reflection_md"]).strip()
        self._mem.append_dream(reflection_md)

        # Consolidated profile OVERWRITES the previous one: the model was given the
        # old profile and asked to merge + dedup, so repeated dreams do not stack.
        profile_md = str(data.get("profile_md") or data.get("profile_update_md") or "").strip()
        if profile_md:
            self._mem.write_profile(profile_md)

        return ReflectionResult(
            reflection_md=reflection_md,
            profile_md=profile_md,
            misconceptions=list(data.get("misconceptions") or []),
            next_focus=list(data.get("next_focus") or []),
        )

    def _build_prompt(self, digests: List[SessionDigest]) -> str:
        """Render the full evidence (problems + transcripts + profile) into a prompt."""
        blocks: List[str] = []
        for i, d in enumerate(digests, 1):
            head = f"### Сессия {i} — тема: {d.topic}"
            meta = []
            if d.difficulty:
                meta.append(f"сложность {d.difficulty}")
            if d.mode:
                meta.append(f"режим {d.mode}")
            if meta:
                head += " (" + ", ".join(meta) + ")"
            lines = [head]
            if d.problem:
                lines.append(f"Задача: {d.problem}")
            if d.answer:
                lines.append(f"Эталонный ответ: {d.answer}")
            outcome = "решено" if d.solved else "НЕ решено"
            dur = f", ~{d.duration_min:.0f} мин" if d.duration_min else ""
            lines.append(
                f"Итог: {outcome}; попыток {d.attempts}, подсказок {d.hints}, "
                f"реплик {d.turns}{dur}."
            )
            if d.transcript:
                lines.append("Диалог:")
                lines.extend(d.transcript)
            blocks.append("\n".join(lines))

        prompt = "Недавние занятия ученика (разбери их подробно):\n\n" + "\n\n".join(blocks)
        prof = self._mem.read_profile()
        if prof:
            prompt += (
                "\n\n---\nТекущий профиль ученика (обнови и дедуплицируй его ЦЕЛИКОМ, "
                "не добавляй дубли):\n" + prof
            )
        return prompt

    @staticmethod
    def _fallback(digests: List[SessionDigest]) -> dict:
        """Heuristic summary used when the LLM is unavailable or returns bad JSON."""
        topics = ", ".join(sorted({d.topic for d in digests if d.topic})) or "—"
        solved = sum(1 for d in digests if d.solved)
        md = (
            f"## Сводка\nЗанятий: {len(digests)} (решено {solved}). Темы: {topics}.\n"
            "_(LLM-рефлексия недоступна — эвристическая сводка.)_"
        )
        return {"reflection_md": md, "profile_md": "", "misconceptions": [], "next_focus": []}


def _strip_fences(s: str) -> str:
    """Strip a leading ```json fence (and trailing ```), if present."""
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0]
    return s.strip()
