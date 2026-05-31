# backend/app/services/mastery_service.py
"""Derive per-student mastery on-read by replaying stored interactions through BKT.

Reuses the existing BKT engine (``src/models/knowledge_tracing.StudentModel``): an
ephemeral in-memory model is fed the student's graded outcomes in time order and the
resulting per-skill ``mastery`` (= p(known)) is read back. No persistence, no DKT
model attached (so ``update_skill`` is pure BKT), no change to the live session path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional

from backend.app.services.session_signals import resolve_topic
from src.models.knowledge_tracing import StudentModel


@dataclass
class MasterySignal:
    """Per-topic mastery distilled from a student's interaction history."""

    topic: str
    p_known: float
    attempts: int
    correct: int
    last_seen: Optional[str] = None  # ISO-8601, or None


def _outcomes(rows: List[Any]) -> tuple[list[tuple[datetime, str, bool]], dict[str, datetime]]:
    """Return chronological (timestamp, topic, is_correct) outcomes and per-topic last_seen.

    Primary signal: messages carrying a non-null ``is_correct`` (one BKT update each).
    Fallback (no graded messages in a session): a single session-level outcome —
    solved → correct; attempted-but-unsolved → incorrect; otherwise skipped.
    """
    outcomes: list[tuple[datetime, str, bool]] = []
    last_seen: dict[str, datetime] = {}
    for r in rows:
        topic = resolve_topic(r)
        msgs = list(getattr(r, "messages", []) or [])
        graded = [m for m in msgs if getattr(m, "is_correct", None) is not None]
        if graded:
            for m in graded:
                ts = getattr(m, "timestamp", None) or datetime.min
                outcomes.append((ts, topic, bool(m.is_correct)))
        else:
            ts = getattr(r, "updated_at", None) or getattr(r, "created_at", None) or datetime.min
            if getattr(r, "is_solved", False):
                outcomes.append((ts, topic, True))
            elif int(getattr(r, "attempts", 0) or 0) > 0:
                outcomes.append((ts, topic, False))
        rts = getattr(r, "updated_at", None) or getattr(r, "created_at", None)
        if rts and (topic not in last_seen or rts > last_seen[topic]):
            last_seen[topic] = rts
    return outcomes, last_seen


def compute_mastery(rows: List[Any]) -> List[MasterySignal]:
    """Compute per-topic BKT mastery for a student's recent session rows.

    Args:
        rows: Session rows exposing ``topic`` / ``task_json``, a ``messages``
            collection (with ``is_correct`` / ``timestamp``), and
            ``is_solved`` / ``attempts`` / ``created_at`` / ``updated_at``.

    Returns:
        One :class:`MasterySignal` per practiced topic, weakest first.
    """
    outcomes, last_seen = _outcomes(rows)
    outcomes.sort(key=lambda o: o[0])
    model = StudentModel(student_id="ephemeral")
    for _ts, topic, is_correct in outcomes:
        model.update_skill(topic, is_correct)

    signals = [
        MasterySignal(
            topic=name,
            p_known=round(skill.mastery, 4),
            attempts=skill.attempts,
            correct=skill.successes,
            last_seen=last_seen[name].isoformat() if name in last_seen else None,
        )
        for name, skill in model.skills.items()
    ]
    signals.sort(key=lambda s: s.p_known)  # weakest first
    return signals


def mastery_by_skill(signals: List[MasterySignal]) -> dict:
    """Flatten signals to a ``{topic: p_known}`` dict for clients."""
    return {s.topic: s.p_known for s in signals}
