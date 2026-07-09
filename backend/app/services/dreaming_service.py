# backend/app/services/dreaming_service.py
"""Background 'sleep' pass: recent sessions -> reflection files + graph augmentation."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from backend.app.services.mastery_service import compute_mastery
from backend.app.services.session_signals import parse_task_json, resolve_topic
from src.agents.reflection import ReflectionGenerator, SessionDigest
from src.memory.memory_files import StudentMemoryFiles

logger = logging.getLogger(__name__)


def _duration_min(created: Any, updated: Any) -> float:
    """Minutes between two datetimes; ``0.0`` when unavailable."""
    try:
        if created and updated:
            return max(0.0, (updated - created).total_seconds() / 60.0)
    except (TypeError, AttributeError):
        pass
    return 0.0


def _transcript(msgs: List[Any], *, max_msgs: int = 16, per_msg: int = 400) -> List[str]:
    """Render messages as readable dialogue lines: role + Socratic move + ✓/✗ + content.

    Long conversations keep the head and tail (the arc) with a skip marker between,
    so the reflection sees how a session opened and how it ended.

    Args:
        msgs: Ordered message rows (each may expose ``role``, ``content``,
            ``move_type``, ``is_correct``).
        max_msgs: Cap on rendered lines before head/tail truncation kicks in.
        per_msg: Per-message content character cap.

    Returns:
        Formatted dialogue lines (indented two spaces).
    """

    def fmt(m: Any) -> str:
        role = getattr(m, "role", "") or ""
        who = "ученик" if role == "user" else ("тьютор" if role == "tutor" else (role or "?"))
        move = getattr(m, "move_type", None)
        ok = getattr(m, "is_correct", None)
        tag = f" [{move}]" if move else ""
        mark = " ✓" if ok is True else (" ✗" if ok is False else "")
        content = (getattr(m, "content", "") or "").strip().replace("\n", " ")
        if len(content) > per_msg:
            content = content[:per_msg] + "…"
        return f"  {who}{tag}{mark}: {content}"

    if len(msgs) <= max_msgs:
        return [fmt(m) for m in msgs]
    head = max_msgs // 2
    tail = max_msgs - head
    lines = [fmt(m) for m in msgs[:head]]
    lines.append(f"  …(пропущено {len(msgs) - max_msgs} реплик)…")
    lines.extend(fmt(m) for m in msgs[-tail:])
    return lines


def _digest_from_rows(rows: List[Any]) -> List[SessionDigest]:
    """Convert ORM session rows into rich, LLM-friendly session digests.

    Pulls everything the reflection can reason over: the real problem and
    reference answer (from ``task_json``), difficulty / mode / subject, the full
    dialogue transcript (with Socratic moves and ✓/✗ markers), pacing (duration,
    turns, attempts, hints) and short excerpts of incorrect messages.

    Args:
        rows: Session rows (``SessionTable`` or compatible stubs) exposing
            ``topic``, ``is_solved``, ``hints_used``, ``messages`` and, when
            available, ``task_json`` / ``difficulty`` / ``mode`` / ``attempts`` /
            ``created_at`` / ``updated_at``.

    Returns:
        A list of :class:`SessionDigest`, one per row.
    """
    digests: List[SessionDigest] = []
    for r in rows:
        msgs = list(getattr(r, "messages", []) or [])
        task = parse_task_json(getattr(r, "task_json", None))
        subject = str(task.get("subject") or "")
        topic = resolve_topic(r)
        answer = task.get("answer") or task.get("solution") or ""
        errors = [m.content[:120] for m in msgs if getattr(m, "is_correct", None) is False]
        digests.append(
            SessionDigest(
                topic=str(topic),
                problem=str(task.get("problem") or "")[:600],
                answer=str(answer)[:300],
                difficulty=str(getattr(r, "difficulty", None) or task.get("difficulty") or ""),
                mode=str(getattr(r, "mode", None) or ""),
                subject=subject,
                solved=bool(getattr(r, "is_solved", False)),
                hints=int(getattr(r, "hints_used", 0) or 0),
                attempts=int(getattr(r, "attempts", 0) or 0),
                turns=len(msgs),
                duration_min=_duration_min(
                    getattr(r, "created_at", None), getattr(r, "updated_at", None)
                ),
                transcript=_transcript(msgs),
                errors=errors[:5],
            )
        )
    return digests


class DreamingService:
    """Consolidate recent sessions into reflection memory and grow the graph."""

    def __init__(self, llm: Any, base_dir: Path | str = "data/students", graph: Any = None) -> None:
        """Initialize the dreaming service.

        Args:
            llm: LLM client exposing ``generate(prompt, system=..., **kw)``.
            base_dir: Root directory for per-student memory files.
            graph: Optional ``KnowledgeGraph`` singleton. When ``None`` the
                graph-augmentation step is skipped.
        """
        self._llm = llm
        self._base = base_dir
        self._graph = graph  # KnowledgeGraph singleton or None (skip graph-grow)

    def dream_from_rows(self, student_id: str, rows: List[Any]) -> dict:
        """Run a full dream pass over the given session rows.

        Args:
            student_id: Safe student identifier (directory-scoped).
            rows: Recent session rows for this student.

        Returns:
            A report dict describing the reflection, structured signals,
            graph changes, and the memory files that were updated.
        """
        mem = StudentMemoryFiles(student_id, base_dir=self._base)
        digests = _digest_from_rows(rows)
        gen = ReflectionGenerator(llm=self._llm, memory=mem)
        mastery = [
            {"topic": s.topic, "p_known": s.p_known, "attempts": s.attempts}
            for s in compute_mastery(rows)
        ]
        result = gen.reflect(digests, mastery=mastery)
        graph_changes = self._augment_graph(result.misconceptions, digests)
        state = mem.read_state()
        state["sessions_seen"] = list(
            {getattr(r, "id", "") for r in rows} | set(state.get("sessions_seen", []))
        )
        state["last_dreamed_at"] = datetime.now(timezone.utc).isoformat()
        mem.write_state(state)
        return {
            "sessions_count": len(rows),
            "reflection_excerpt": result.reflection_md[:400],
            "misconceptions": result.misconceptions,
            "next_focus": result.next_focus,
            "graph_changes": graph_changes,
            "files_updated": [str(p) for p in [mem.root / "profile.md"]],
        }

    def _augment_graph(self, misconceptions: List[str], digests: List[SessionDigest]) -> dict:
        """Add misconception nodes discovered during the dream.

        Uses the verified ``add_node`` API. No-op when no graph is wired or
        no misconceptions were surfaced.

        Args:
            misconceptions: Misconception descriptions from the reflection.
            digests: Session digests (reserved for future domain inference).

        Returns:
            A dict with the number of nodes added (``nodes_added``).
        """
        if self._graph is None or not misconceptions:
            return {"nodes_added": 0}
        from src.knowledge.knowledge_forge import KnowledgeNode, NodeType

        domain = "math"
        added = 0
        for text in misconceptions[:5]:
            slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or uuid.uuid4().hex[:8]
            nid = f"{domain}:dream_{slug}:misconception"
            if self._graph.get_node(nid) is not None:
                continue
            self._graph.add_node(
                KnowledgeNode(
                    id=nid,
                    node_type=NodeType.MISCONCEPTION,
                    title=text[:80],
                    title_en=text[:80],
                    content=text,
                    domain=domain,
                    difficulty=0.5,
                    source="dreaming",
                )
            )
            added += 1
        if added:
            self._graph.save()
        return {"nodes_added": added}
