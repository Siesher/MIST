"""
Graph Evolution: manages proposal lifecycle for Living Knowledge Graph.

Proposals accumulate evidence across sessions. When confidence exceeds a
threshold, an optional LLM verifier validates pedagogical soundness, and
the proposal is merged into the canonical graph.

Persistence: proposals stored in `data/knowledge/forge_proposals.json`
alongside `forge.json`. Growth events logged to `forge_growth.jsonl`.
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from src.knowledge.knowledge_forge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)
from src.knowledge.session_analyzer import GraphProposal, ProposalKind

logger = logging.getLogger(__name__)

# Auto-accept threshold: confidence at which proposal merges into graph
AUTO_ACCEPT_CONFIDENCE = 0.85

# Proposal storage paths
DEFAULT_PROPOSALS_PATH = Path("data/knowledge/forge_proposals.json")
DEFAULT_GROWTH_LOG = Path("data/knowledge/forge_growth.jsonl")


# ─────────────────────────────────────────────────────────────────────
# Proposal Queue
# ─────────────────────────────────────────────────────────────────────


class ProposalQueue:
    """Stores pending GraphProposal objects, deduplicated by key.

    Each proposal accumulates evidence across sessions. The queue
    persists to JSON so evidence carries across process restarts.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self._storage_path = storage_path or DEFAULT_PROPOSALS_PATH
        self._items: Dict[str, GraphProposal] = {}
        self._load()

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            data = json.loads(self._storage_path.read_text(encoding="utf-8"))
            for item in data.get("proposals", []):
                item["kind"] = ProposalKind(item["kind"])
                prop = GraphProposal(**item)
                self._items[prop.key()] = prop
            logger.info(f"ProposalQueue loaded: {len(self._items)} pending")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load proposals from {self._storage_path}: {e}")

    def save(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "proposals": [asdict(p) for p in self._items.values()],
        }
        self._storage_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_or_merge(self, proposal: GraphProposal) -> GraphProposal:
        """Add new proposal or merge evidence into existing one."""
        key = proposal.key()
        if key in self._items:
            existing = self._items[key]
            for ev in proposal.evidence:
                existing.evidence.append(ev)
            n = len(existing.evidence)
            existing.confidence = min(0.95, 1.0 - (0.7**n))
            return existing
        self._items[key] = proposal
        return proposal

    def pending(self) -> List[GraphProposal]:
        """All pending proposals."""
        return list(self._items.values())

    def ready_for_review(self, threshold: float = AUTO_ACCEPT_CONFIDENCE) -> List[GraphProposal]:
        """Proposals with confidence >= threshold, ready for verification."""
        return [p for p in self._items.values() if p.confidence >= threshold]

    def remove(self, key: str) -> None:
        """Remove a proposal after it's been accepted or rejected."""
        self._items.pop(key, None)

    def clear(self) -> None:
        self._items.clear()


# ─────────────────────────────────────────────────────────────────────
# Proposal Verifier (rule-based + optional LLM)
# ─────────────────────────────────────────────────────────────────────

VerifierCallback = Callable[[GraphProposal, KnowledgeGraph], Tuple[bool, str]]


def rule_based_verifier(
    proposal: GraphProposal,
    graph: KnowledgeGraph,
) -> Tuple[bool, str]:
    """Fast rule-based verification — no LLM call.

    Returns:
        (accept, reason)
    """
    p = proposal.payload

    if proposal.kind == ProposalKind.NEW_NODE:
        # Reject if node already exists with higher confidence
        existing = graph.get_node(p.get("id", ""))
        if existing and existing.confidence >= proposal.confidence:
            return False, "node already exists with higher confidence"
        # Reject if content too short
        if len(p.get("content", "")) < 15:
            return False, "content too short"
        return True, "new_node passes rules"

    if proposal.kind == ProposalKind.NEW_EDGE:
        src = p.get("source_id")
        tgt = p.get("target_id")
        et = p.get("edge_type")
        # Both nodes must exist
        if not graph.get_node(src) or not graph.get_node(tgt):
            return False, "endpoint node missing"
        # No self-loops
        if src == tgt:
            return False, "self-loop"
        try:
            et_enum = EdgeType(et)
        except ValueError:
            return False, f"unknown edge_type: {et}"
        # Not a duplicate
        if graph.has_edge(src, tgt, et_enum):
            return False, "edge already exists"
        # For PREREQUISITE: check we're not creating a cycle
        if et_enum == EdgeType.PREREQUISITE:
            # Path from tgt back to src would mean src depends on tgt
            path = graph.find_path(tgt, src, edge_types=[EdgeType.PREREQUISITE])
            if path:
                return False, "would create prerequisite cycle"
        return True, "new_edge passes rules"

    return False, f"unknown proposal kind: {proposal.kind}"


# ─────────────────────────────────────────────────────────────────────
# Graph Evolver
# ─────────────────────────────────────────────────────────────────────


class GraphEvolver:
    """Orchestrates proposal → verification → merge pipeline.

    Usage:
        evolver = GraphEvolver(graph, queue)
        evolver.ingest_proposals(proposals_from_sessions)
        stats = evolver.promote_ready()
        evolver.save()
    """

    def __init__(
        self,
        graph: KnowledgeGraph,
        queue: Optional[ProposalQueue] = None,
        llm_verifier: Optional[VerifierCallback] = None,
        growth_log_path: Optional[Path] = None,
    ):
        self._graph = graph
        self._queue = queue or ProposalQueue()
        self._llm_verifier = llm_verifier
        self._growth_log_path = growth_log_path or DEFAULT_GROWTH_LOG

    def ingest_proposals(self, proposals: List[GraphProposal]) -> int:
        """Add proposals to the queue, merging evidence with existing ones."""
        for p in proposals:
            self._queue.add_or_merge(p)
        return len(proposals)

    def promote_ready(
        self,
        threshold: float = AUTO_ACCEPT_CONFIDENCE,
    ) -> Dict[str, int]:
        """Verify and merge proposals that are ready.

        Returns:
            Stats dict with accepted/rejected/skipped counts.
        """
        stats = {"accepted": 0, "rejected": 0, "skipped": 0}

        for proposal in list(self._queue.ready_for_review(threshold)):
            # Step 1: rule-based verifier
            ok, reason = rule_based_verifier(proposal, self._graph)
            if not ok:
                self._log_event("rejected", proposal, reason)
                self._queue.remove(proposal.key())
                stats["rejected"] += 1
                continue

            # Step 2: optional LLM verifier
            if self._llm_verifier is not None:
                try:
                    ok_llm, reason_llm = self._llm_verifier(proposal, self._graph)
                    if not ok_llm:
                        self._log_event("rejected", proposal, f"llm_verifier: {reason_llm}")
                        self._queue.remove(proposal.key())
                        stats["rejected"] += 1
                        continue
                except Exception as e:
                    logger.warning(f"LLM verifier raised: {e}, skipping proposal")
                    stats["skipped"] += 1
                    continue

            # Step 3: merge into graph
            try:
                self._apply_proposal(proposal)
                self._log_event("accepted", proposal, reason)
                self._queue.remove(proposal.key())
                stats["accepted"] += 1
            except Exception as e:
                logger.error(f"Failed to apply proposal {proposal.key()}: {e}")
                stats["skipped"] += 1

        logger.info(f"promote_ready: {stats}")
        return stats

    def _apply_proposal(self, proposal: GraphProposal) -> None:
        """Merge proposal into the canonical graph."""
        p = proposal.payload

        if proposal.kind == ProposalKind.NEW_NODE:
            node = KnowledgeNode(
                id=p["id"],
                node_type=NodeType(p["node_type"]),
                title=p.get("title", ""),
                title_en=p.get("title_en", ""),
                content=p.get("content", ""),
                domain=p.get("domain", "math"),
                tags=p.get("tags", []),
                difficulty=float(p.get("difficulty", 0.5)),
                source=p.get("source", "session_learned"),
                confidence=proposal.confidence,
            )
            self._graph.add_node(node)

            # If the proposal includes a linked_concept, add appropriate edge
            linked = p.get("linked_concept")
            if linked and node.node_type == NodeType.MISCONCEPTION:
                if self._graph.get_node(linked) and not self._graph.has_edge(
                    node.id, linked, EdgeType.COMMON_ERROR_FOR
                ):
                    self._graph.add_edge(
                        KnowledgeEdge(
                            source_id=node.id,
                            target_id=linked,
                            edge_type=EdgeType.COMMON_ERROR_FOR,
                            weight=proposal.confidence,
                        )
                    )

        elif proposal.kind == ProposalKind.NEW_EDGE:
            self._graph.add_edge(
                KnowledgeEdge(
                    source_id=p["source_id"],
                    target_id=p["target_id"],
                    edge_type=EdgeType(p["edge_type"]),
                    weight=proposal.confidence,
                    metadata={
                        "derived_from_sessions": len(proposal.evidence),
                        "origin": proposal.origin,
                    },
                )
            )

    def _log_event(self, action: str, proposal: GraphProposal, reason: str) -> None:
        """Append an event to the growth log (JSONL)."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "kind": proposal.kind.value,
            "payload": proposal.payload,
            "origin": proposal.origin,
            "evidence_count": len(proposal.evidence),
            "confidence": round(proposal.confidence, 3),
            "reason": reason,
        }
        self._growth_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._growth_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def save(self) -> None:
        """Persist queue and graph."""
        self._queue.save()
        # Graph saves automatically via its own .save() if storage_path is set

    @property
    def queue(self) -> ProposalQueue:
        return self._queue

    @property
    def graph(self) -> KnowledgeGraph:
        return self._graph
