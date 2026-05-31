# backend/app/services/dreaming_service.py
"""Background 'sleep' pass: recent sessions -> reflection files + graph augmentation."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

from src.agents.reflection import ReflectionGenerator, SessionDigest
from src.memory.memory_files import StudentMemoryFiles

logger = logging.getLogger(__name__)


def _digest_from_rows(rows: List[Any]) -> List[SessionDigest]:
    """Convert ORM session rows into LLM-friendly session digests.

    Args:
        rows: Session rows exposing ``topic``, ``is_solved``, ``hints_used`` and
            a ``messages`` collection (each message may carry ``content`` and
            ``is_correct``).

    Returns:
        A list of :class:`SessionDigest`, one per row, with up to five error
        excerpts harvested from messages marked ``is_correct == False``.
    """
    digests: List[SessionDigest] = []
    for r in rows:
        msgs = list(getattr(r, "messages", []) or [])
        errors = [m.content[:120] for m in msgs if getattr(m, "is_correct", None) is False]
        digests.append(
            SessionDigest(
                topic=getattr(r, "topic", None) or "general",
                solved=bool(getattr(r, "is_solved", False)),
                hints=int(getattr(r, "hints_used", 0) or 0),
                errors=errors[:5],
                turns=len(msgs),
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
        result = gen.reflect(digests)
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
