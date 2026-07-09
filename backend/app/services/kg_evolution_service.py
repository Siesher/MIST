"""Living Knowledge Graph evolution — wires session_analyzer + graph_evolution.

After every chat session, the orchestrator fires `trigger_session_analysis(...)`.
It takes a SessionTrace (reconstructed from stored messages + student profile),
runs the SessionAnalyzer to generate GraphProposals, and queues them.

A background sweep every N proposals (or via /promote endpoint) runs
GraphEvolver.promote_ready() to merge high-confidence proposals into the graph.

Makes "Living" in Living Knowledge Graph actually live — structure evolves from
real student tutoring sessions without manual curation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Singleton service
# ─────────────────────────────────────────────────────────────────────


class KGEvolutionService:
    """Async-safe wrapper around SessionAnalyzer + GraphEvolver."""

    def __init__(self):
        self._navigator = None  # lazy init (needs LLM + graph)
        self._analyzer = None
        self._evolver = None
        self._queue = None
        self._lock = Lock()

        # Stats
        self.sessions_analyzed = 0
        self.proposals_generated = 0
        self.proposals_accepted = 0
        self.proposals_rejected = 0
        self.last_sweep_at = 0.0
        self.last_sweep_stats: dict[str, int] = {}

        # Auto-sweep every N proposals queued
        self.sweep_every = 5

    def _ensure_queue(self):
        """Cheap init — only ProposalQueue (JSON file). No Navigator/LLM deps.

        Safe to call from read-only endpoints like list_proposals / summary.
        """
        if self._queue is not None:
            return
        with self._lock:
            if self._queue is not None:
                return
            try:
                from src.knowledge.graph_evolution import ProposalQueue

                self._queue = ProposalQueue()
                logger.info("KGEvolution: queue initialized (read-only path)")
            except Exception as e:
                logger.warning(f"Proposal queue init failed: {e}")
                # Don't crash read endpoints — leave _queue None, callers return empty
                raise

    def _ensure_initialized(self):
        """Full init — Navigator + Analyzer + Evolver. Needed for analyze/promote."""
        if self._evolver is not None:
            return

        with self._lock:
            if self._evolver is not None:
                return
            try:
                from src.knowledge.graph_evolution import GraphEvolver, ProposalQueue
                from src.knowledge.knowledge_forge import KnowledgeGraph
                from src.knowledge.navigator import PersonalizedNavigator
                from src.knowledge.session_analyzer import SessionAnalyzer

                forge_path = Path("data/knowledge/forge.json")
                graph = KnowledgeGraph(storage_path=forge_path)
                # Empty mastery source — analytics path doesn't need personalization;
                # tool dispatch in chat/guided uses set_mastery_source() separately.
                self._navigator = PersonalizedNavigator(graph, {})
                self._analyzer = SessionAnalyzer(self._navigator)
                if self._queue is None:
                    self._queue = ProposalQueue()
                self._evolver = GraphEvolver(graph=graph, queue=self._queue)
                logger.info("KGEvolutionService fully initialized")
            except Exception as e:
                logger.error(f"KG evolution full init failed: {e}")
                raise

    def build_trace(
        self,
        session_id: str,
        student_id: str,
        topic_id: str,
        concepts_touched: list[str],
        errors: list[dict],
        hints_given: int,
        resolved: bool,
        mastery_before: dict[str, float] | None = None,
        mastery_after: dict[str, float] | None = None,
        duration_sec: float = 0.0,
    ):
        """Package session data into SessionTrace dataclass."""
        from src.knowledge.session_analyzer import SessionTrace

        return SessionTrace(
            session_id=session_id,
            student_id=student_id,
            topic_id=topic_id,
            concepts_touched=concepts_touched,
            errors=errors,
            hints_given=hints_given,
            resolved=resolved,
            mastery_before=mastery_before or {},
            mastery_after=mastery_after or {},
            duration_sec=duration_sec,
        )

    def analyze_session(self, trace) -> int:
        """Run analyzer on a SessionTrace, queue the proposals.

        Returns the count of new proposals generated.
        """
        self._ensure_initialized()
        try:
            proposals = self._analyzer.analyze(trace)
            n = self._evolver.ingest_proposals(proposals)
            self.sessions_analyzed += 1
            self.proposals_generated += n
            # Persist queue state
            self._queue.save()
            logger.info(
                f"Session {trace.session_id} analyzed: +{n} proposals "
                f"(total pending: {len(self._queue.pending())})"
            )
            # Periodic auto-sweep
            if self.proposals_generated % self.sweep_every == 0:
                self.promote_ready()
            return n
        except Exception as e:
            logger.warning(f"Session analysis failed: {e}")
            return 0

    def promote_ready(self, threshold: float = 0.75) -> dict[str, int]:
        """Run evolver sweep: verify + merge high-confidence proposals."""
        self._ensure_initialized()
        try:
            stats = self._evolver.promote_ready(threshold=threshold)
            self.proposals_accepted += stats.get("accepted", 0)
            self.proposals_rejected += stats.get("rejected", 0)
            self.last_sweep_at = time.time()
            self.last_sweep_stats = stats
            self._queue.save()
            # Persist graph if anything was accepted
            if stats.get("accepted", 0) > 0:
                try:
                    self._evolver._graph.save()
                except Exception as e:
                    logger.warning(f"Graph save failed: {e}")
            return stats
        except Exception as e:
            logger.warning(f"Promote sweep failed: {e}")
            return {"accepted": 0, "rejected": 0, "skipped": 0, "error": str(e)}

    def list_proposals(self) -> list[dict[str, Any]]:
        """All pending proposals for UI review.

        Uses queue-only init (cheap). Returns [] on init failure instead of raising.
        """
        from dataclasses import asdict

        try:
            self._ensure_queue()
        except Exception:
            return []
        if self._queue is None:
            return []
        return [asdict(p) for p in self._queue.pending()]

    def manual_decision(self, proposal_key: str, accept: bool) -> bool:
        """Accept or reject one proposal by its key (admin action from UI)."""
        self._ensure_initialized()
        # Find proposal
        target = None
        for p in self._queue.pending():
            if p.key() == proposal_key:
                target = p
                break
        if target is None:
            return False

        if accept:
            try:
                self._evolver._apply_proposal(target)
                self._evolver._log_event("accepted", target, "manual")
                self._queue.remove(proposal_key)
                self.proposals_accepted += 1
                self._queue.save()
                self._evolver._graph.save()
                return True
            except Exception as e:
                logger.error(f"Manual accept failed: {e}")
                return False
        else:
            self._evolver._log_event("rejected", target, "manual")
            self._queue.remove(proposal_key)
            self.proposals_rejected += 1
            self._queue.save()
            return True

    def summary(self) -> dict[str, Any]:
        # Attempt cheap queue init so "pending" is accurate on first call
        try:
            self._ensure_queue()
        except Exception:
            pass
        return {
            "sessions_analyzed": self.sessions_analyzed,
            "proposals_generated": self.proposals_generated,
            "proposals_accepted": self.proposals_accepted,
            "proposals_rejected": self.proposals_rejected,
            "pending": len(self._queue.pending()) if self._queue else 0,
            "last_sweep_at": self.last_sweep_at,
            "last_sweep_stats": self.last_sweep_stats,
        }


# ─────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────


_service: KGEvolutionService | None = None


def get_kg_evolution() -> KGEvolutionService:
    global _service
    if _service is None:
        _service = KGEvolutionService()
    return _service


# ─────────────────────────────────────────────────────────────────────
# Hook: called from orchestrator after response_complete
# ─────────────────────────────────────────────────────────────────────


async def analyze_session_async(
    session_id: str,
    student_id: str,
    topic_id: str,
    concepts_touched: list[str],
    errors: list[dict],
    hints_given: int,
    resolved: bool,
):
    """Non-blocking analyzer — schedule on thread pool so orchestrator doesn't wait."""
    loop = asyncio.get_event_loop()
    svc = get_kg_evolution()

    def _work():
        trace = svc.build_trace(
            session_id=session_id,
            student_id=student_id,
            topic_id=topic_id,
            concepts_touched=concepts_touched,
            errors=errors,
            hints_given=hints_given,
            resolved=resolved,
        )
        return svc.analyze_session(trace)

    try:
        await loop.run_in_executor(None, _work)
    except Exception as e:
        logger.debug(f"Async session analysis failed: {e}")
