"""LLM reflection over recent sessions → markdown memory + structured signals."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import List

from src.memory.memory_files import StudentMemoryFiles

logger = logging.getLogger(__name__)


@dataclass
class SessionDigest:
    topic: str
    solved: bool
    hints: int
    errors: List[str] = field(default_factory=list)
    turns: int = 0


@dataclass
class ReflectionResult:
    reflection_md: str
    misconceptions: List[str] = field(default_factory=list)
    next_focus: List[str] = field(default_factory=list)


_SYSTEM = (
    "Ты — наставник, который во время «сна» осмысляет недавние занятия ученика. "
    "Верни СТРОГО JSON с ключами: reflection_md (markdown-рефлексия: что освоено, "
    "над чем работать), profile_update_md (1-3 строки durable-фактов об ученике), "
    "misconceptions (список строк), next_focus (список тем). Без текста вне JSON."
)


class ReflectionGenerator:
    def __init__(self, llm, memory: StudentMemoryFiles) -> None:
        self._llm = llm
        self._mem = memory

    def reflect(self, digests: List[SessionDigest]) -> ReflectionResult:
        prompt = self._build_prompt(digests)
        try:
            raw = self._llm.generate(prompt=prompt, system=_SYSTEM, thinking=False, max_tokens=1200)
            data = json.loads(_strip_fences(raw))
        except Exception as e:  # LLM error or bad JSON → heuristic fallback
            logger.warning("reflection_fallback: %s", e)
            data = self._fallback(digests)

        reflection_md = str(data.get("reflection_md") or self._fallback(digests)["reflection_md"])
        self._mem.append_dream(reflection_md)
        profile_update = str(data.get("profile_update_md") or "").strip()
        if profile_update:
            existing = self._mem.read_profile()
            merged = (existing + "\n" + profile_update).strip() if existing else profile_update
            self._mem.write_profile(merged)
        return ReflectionResult(
            reflection_md=reflection_md,
            misconceptions=list(data.get("misconceptions") or []),
            next_focus=list(data.get("next_focus") or []),
        )

    def _build_prompt(self, digests: List[SessionDigest]) -> str:
        lines = ["Недавние занятия ученика:"]
        for d in digests:
            status = "решено" if d.solved else "не решено"
            errs = ("; ошибки: " + ", ".join(d.errors)) if d.errors else ""
            lines.append(f"- тема {d.topic}: {status}, подсказок {d.hints}, ходов {d.turns}{errs}")
        prof = self._mem.read_profile()
        if prof:
            lines.append("\nЧто уже известно об ученике (profile.md):\n" + prof)
        return "\n".join(lines)

    @staticmethod
    def _fallback(digests: List[SessionDigest]) -> dict:
        topics = ", ".join(sorted({d.topic for d in digests})) or "—"
        solved = sum(1 for d in digests if d.solved)
        md = f"## Сводка\nЗанятий: {len(digests)} (решено {solved}). Темы: {topics}."
        return {
            "reflection_md": md,
            "profile_update_md": "",
            "misconceptions": [],
            "next_focus": [],
        }


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0]
    return s.strip()
