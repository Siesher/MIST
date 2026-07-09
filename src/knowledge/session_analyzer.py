"""
Session Analyzer: extracts graph-refinement signals from tutoring sessions.

Reads session logs and identifies:
- Prerequisite gaps the current graph missed (student failed X, but graph
  didn't flag the actual missing skill)
- Repeated misconceptions (observed in multiple sessions)
- Confusion patterns (student consistently confused A with B)
- Pedagogical ordering signals (concept taught faster after learning Y)

Output: list of GraphProposal objects with evidence.
The GraphEvolution layer accumulates evidence and promotes proposals
to verified graph nodes/edges.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List

from src.knowledge.knowledge_forge import EdgeType, NodeType
from src.knowledge.navigator import MASTERY_THRESHOLD, PersonalizedNavigator

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Proposal Types
# ─────────────────────────────────────────────────────────────────────


class ProposalKind(str, Enum):
    """What the proposal suggests changing in the graph."""

    NEW_NODE = "new_node"  # Add a new node (e.g. discovered misconception)
    NEW_EDGE = "new_edge"  # Add edge between existing nodes
    STRENGTHEN_EDGE = "strengthen_edge"  # Increase weight of existing edge
    WEAKEN_EDGE = "weaken_edge"  # Decrease weight (evidence against)


@dataclass
class GraphProposal:
    """A proposed change to the knowledge graph, backed by evidence.

    Proposals accumulate evidence across sessions before being verified
    and merged into the canonical graph.

    Attributes:
        kind: What kind of change is proposed.
        payload: Details of the proposal (node dict, edge fields).
        evidence: List of (session_id, timestamp, reason) tuples.
        confidence: 0-1 score, grows with evidence.
        origin: Which signal detector produced this proposal.
    """

    kind: ProposalKind
    payload: Dict
    evidence: List[Dict] = field(default_factory=list)
    confidence: float = 0.3
    origin: str = ""

    def key(self) -> str:
        """Deterministic key for deduplication across sessions."""
        if self.kind == ProposalKind.NEW_NODE:
            return f"node:{self.payload.get('id', '')}"
        if self.kind in (
            ProposalKind.NEW_EDGE,
            ProposalKind.STRENGTHEN_EDGE,
            ProposalKind.WEAKEN_EDGE,
        ):
            return (
                f"edge:{self.payload.get('source_id', '')}"
                f":{self.payload.get('target_id', '')}"
                f":{self.payload.get('edge_type', '')}"
            )
        return f"unknown:{id(self)}"

    def add_evidence(self, session_id: str, reason: str) -> None:
        """Add an evidence record and bump confidence."""
        self.evidence.append(
            {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "reason": reason,
            }
        )
        # Confidence grows: 0.3 → 0.5 → 0.7 → 0.85 → 0.95 (saturating)
        n = len(self.evidence)
        self.confidence = min(0.95, 1.0 - (0.7**n))


# ─────────────────────────────────────────────────────────────────────
# Session Trace Format
# ─────────────────────────────────────────────────────────────────────


@dataclass
class SessionTrace:
    """Minimal session representation for analysis.

    Decouples the analyzer from specific storage formats.
    """

    session_id: str
    student_id: str
    topic_id: str  # Primary concept of the session
    concepts_touched: List[str] = field(default_factory=list)
    errors: List[Dict] = field(default_factory=list)  # {concept_id, description, turn}
    hints_given: int = 0
    resolved: bool = False  # Did student succeed?
    mastery_before: Dict[str, float] = field(default_factory=dict)
    mastery_after: Dict[str, float] = field(default_factory=dict)
    duration_sec: float = 0.0


# ─────────────────────────────────────────────────────────────────────
# Session Analyzer
# ─────────────────────────────────────────────────────────────────────


class SessionAnalyzer:
    """Analyzes tutoring session traces to propose graph refinements.

    Takes a PersonalizedNavigator (to compare graph predictions with
    actual outcomes) and generates GraphProposal objects.
    """

    def __init__(self, navigator: PersonalizedNavigator) -> None:
        self._nav = navigator
        self._graph = navigator._graph

    # ── Main entry point ─────────────────────────────────────────

    def analyze(self, trace: SessionTrace) -> List[GraphProposal]:
        """Extract all graph-refinement proposals from one session."""
        proposals: List[GraphProposal] = []

        proposals.extend(self._detect_missed_prerequisites(trace))
        proposals.extend(self._detect_new_misconceptions(trace))
        proposals.extend(self._detect_confusion_patterns(trace))
        proposals.extend(self._detect_pedagogical_ordering(trace))

        logger.info(f"Session {trace.session_id}: analyzed, produced {len(proposals)} proposals")
        return proposals

    # ── Signal 1: Missed prerequisites ───────────────────────────

    def _detect_missed_prerequisites(self, trace: SessionTrace) -> List[GraphProposal]:
        """Student failed at topic X, but graph didn't predict the gap.

        Logic:
        - Run diagnose_gap on topic_id with mastery_before
        - If student also struggled with concept C during session, but C
          was not in graph's predicted missing prereqs, propose adding
          PREREQUISITE edge C → topic_id.
        """
        if trace.resolved or not trace.errors:
            return []

        gap = self._nav.diagnose_gap(trace.student_id, trace.topic_id)
        predicted_missing = set(gap.missing_prerequisites)

        proposals: List[GraphProposal] = []
        for error in trace.errors:
            err_concept = error.get("concept_id")
            if not err_concept or err_concept == trace.topic_id:
                continue
            if err_concept in predicted_missing:
                continue  # Graph already knows
            if not self._graph.get_node(err_concept):
                continue
            # Graph missed this — propose new PREREQUISITE edge
            if self._graph.has_edge(err_concept, trace.topic_id, EdgeType.PREREQUISITE):
                continue

            prop = GraphProposal(
                kind=ProposalKind.NEW_EDGE,
                payload={
                    "source_id": err_concept,
                    "target_id": trace.topic_id,
                    "edge_type": EdgeType.PREREQUISITE.value,
                },
                origin="missed_prerequisite",
            )
            prop.add_evidence(
                trace.session_id,
                reason=f"Student failed {trace.topic_id} and also struggled with "
                f"{err_concept}, but graph did not predict this gap",
            )
            proposals.append(prop)

        return proposals

    # ── Signal 2: New misconceptions ─────────────────────────────

    def _detect_new_misconceptions(self, trace: SessionTrace) -> List[GraphProposal]:
        """Student errors that don't match existing MISCONCEPTION nodes.

        Proposal: new MISCONCEPTION node + COMMON_ERROR_FOR edge.
        """
        existing_miscs = self._graph.search(domain=None, node_type=NodeType.MISCONCEPTION)
        existing_texts = [m.content.lower() for m in existing_miscs]

        proposals: List[GraphProposal] = []
        for error in trace.errors:
            description = error.get("description", "").strip()
            if len(description) < 20:
                continue
            err_concept = error.get("concept_id") or trace.topic_id
            concept_node = self._graph.get_node(err_concept)
            if not concept_node:
                continue

            # Simple novelty check: not a substring match with existing
            desc_low = description.lower()
            is_novel = all(not (desc_low in et or et in desc_low) for et in existing_texts)
            if not is_novel:
                continue

            # Build proposal — use content-hash so the SAME misconception
            # observed across different sessions accumulates evidence
            import hashlib

            content_hash = hashlib.md5(desc_low.encode("utf-8"), usedforsecurity=False).hexdigest()[
                :10
            ]
            misc_id = (
                f"{concept_node.domain}:{err_concept.split(':')[1]}"
                f":misconception:observed_{content_hash}"
            )
            prop = GraphProposal(
                kind=ProposalKind.NEW_NODE,
                payload={
                    "id": misc_id,
                    "node_type": NodeType.MISCONCEPTION.value,
                    "title": description[:100],
                    "title_en": f"Misconception in {err_concept}",
                    "content": description,
                    "domain": concept_node.domain,
                    "tags": [err_concept, "misconception", "session_derived"],
                    "difficulty": concept_node.difficulty,
                    "source": f"session_{trace.session_id}",
                    "linked_concept": err_concept,
                },
                origin="new_misconception",
            )
            prop.add_evidence(
                trace.session_id,
                reason=f"Novel error pattern observed for {err_concept}",
            )
            proposals.append(prop)

        return proposals

    # ── Signal 3: Confusion patterns ─────────────────────────────

    def _detect_confusion_patterns(self, trace: SessionTrace) -> List[GraphProposal]:
        """Student alternated between two concepts while erring.

        If errors switched between concepts A and B within one session,
        propose CONFUSED_WITH edge.
        """
        err_concepts = [
            e.get("concept_id")
            for e in trace.errors
            if e.get("concept_id") and self._graph.get_node(e.get("concept_id"))
        ]
        if len(err_concepts) < 2:
            return []

        # Pairs with both appearing at least once
        seen = set(err_concepts)
        if len(seen) < 2:
            return []

        proposals: List[GraphProposal] = []
        pairs = set()
        for a in seen:
            for b in seen:
                if a == b:
                    continue
                key = tuple(sorted([a, b]))
                if key in pairs:
                    continue
                pairs.add(key)

                if self._graph.has_edge(a, b, EdgeType.CONFUSED_WITH):
                    continue
                if self._graph.has_edge(b, a, EdgeType.CONFUSED_WITH):
                    continue

                prop = GraphProposal(
                    kind=ProposalKind.NEW_EDGE,
                    payload={
                        "source_id": a,
                        "target_id": b,
                        "edge_type": EdgeType.CONFUSED_WITH.value,
                    },
                    origin="confusion_pattern",
                )
                prop.add_evidence(
                    trace.session_id,
                    reason=f"Student errors alternated between {a} and {b}",
                )
                proposals.append(prop)

        return proposals

    # ── Signal 4: Pedagogical ordering ───────────────────────────

    def _detect_pedagogical_ordering(self, trace: SessionTrace) -> List[GraphProposal]:
        """Concept was learned faster when taught after another concept.

        Heuristic: if mastery_after[topic] - mastery_before[topic] > 0.3
        AND there's a concept C in mastery_before with mastery > 0.7
        AND no PREREQUISITE edge C → topic exists,
        propose BEST_TAUGHT_AFTER edge.
        """
        topic_before = trace.mastery_before.get(trace.topic_id, 0.0)
        topic_after = trace.mastery_after.get(trace.topic_id, 0.0)
        growth = topic_after - topic_before

        if growth < 0.3:
            return []

        proposals: List[GraphProposal] = []
        for concept, mastery in trace.mastery_before.items():
            if concept == trace.topic_id or mastery < MASTERY_THRESHOLD:
                continue
            if not self._graph.get_node(concept):
                continue
            if self._graph.has_edge(concept, trace.topic_id, EdgeType.PREREQUISITE):
                continue
            if self._graph.has_edge(concept, trace.topic_id, EdgeType.BEST_TAUGHT_AFTER):
                continue

            prop = GraphProposal(
                kind=ProposalKind.NEW_EDGE,
                payload={
                    "source_id": concept,
                    "target_id": trace.topic_id,
                    "edge_type": EdgeType.BEST_TAUGHT_AFTER.value,
                },
                origin="pedagogical_ordering",
            )
            prop.add_evidence(
                trace.session_id,
                reason=f"Student made {growth:.2f} mastery gain on {trace.topic_id} "
                f"after mastering {concept}",
            )
            proposals.append(prop)

        return proposals


# ─────────────────────────────────────────────────────────────────────
# Batch analyzer
# ─────────────────────────────────────────────────────────────────────


def analyze_sessions(
    navigator: PersonalizedNavigator,
    traces: List[SessionTrace],
) -> List[GraphProposal]:
    """Analyze multiple sessions and deduplicate proposals by key.

    Accumulates evidence across sessions for the same proposal.

    Args:
        navigator: PersonalizedNavigator instance.
        traces: List of session traces.

    Returns:
        Deduplicated list of proposals with accumulated evidence.
    """
    analyzer = SessionAnalyzer(navigator)
    by_key: Dict[str, GraphProposal] = {}

    for trace in traces:
        proposals = analyzer.analyze(trace)
        for prop in proposals:
            k = prop.key()
            if k in by_key:
                # Merge evidence
                for ev in prop.evidence:
                    by_key[k].evidence.append(ev)
                # Recompute confidence
                n = len(by_key[k].evidence)
                by_key[k].confidence = min(0.95, 1.0 - (0.7**n))
            else:
                by_key[k] = prop

    result = list(by_key.values())
    logger.info(f"Batch analyzed {len(traces)} sessions: {len(result)} unique proposals")
    return result
