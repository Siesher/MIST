"""
Personalized Knowledge Navigator.

Bridges the KnowledgeGraph (static structure) with StudentMemory (dynamic
BKT mastery state) to provide intelligent, student-aware navigation.

This is NOT retrieval — the tutor model actively navigates the graph
using tools, making decisions based on the student's current knowledge state.

Key capabilities:
- Learning frontier: concepts at the edge of student's knowledge (ZPD on graph)
- Gap diagnosis: when student fails, find the missing prerequisite
- Optimal path: mastery-weighted shortest path to any target concept
- Next suggestion: best concept to teach right now
"""

import heapq
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from src.knowledge.knowledge_forge import EdgeType, KnowledgeGraph, NodeType

if TYPE_CHECKING:
    from src.data.schemas import BeliefState

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Navigator Output Types
# ─────────────────────────────────────────────────────────────────────


@dataclass
class FrontierNode:
    """A concept at the edge of student's knowledge — ready to learn.

    Attributes:
        node_id: Knowledge graph node ID.
        title: Human-readable title.
        readiness_score: 0-1, how ready the student is for this concept.
        mastered_prereqs: Prerequisite IDs the student has mastered.
        missing_prereqs: Prerequisite IDs the student hasn't mastered.
        prereq_mastery_avg: Average mastery across prerequisites.
        own_mastery: Student's current mastery of this concept.
        difficulty: Concept difficulty (from graph).
    """

    node_id: str
    title: str
    readiness_score: float
    mastered_prereqs: List[str] = field(default_factory=list)
    missing_prereqs: List[str] = field(default_factory=list)
    prereq_mastery_avg: float = 0.0
    own_mastery: float = 0.0
    difficulty: float = 0.5


@dataclass
class GapDiagnosis:
    """Result of diagnosing why a student failed at a concept.

    Attributes:
        failed_concept: The concept the student struggled with.
        missing_prerequisites: Unmastered prereqs, sorted by depth.
        root_gap: The deepest unmastered prerequisite (root cause).
        suggested_review_path: Ordered list of concepts to review.
        misconceptions: Related misconception node IDs.
        confidence: Diagnosis confidence (0-1).
    """

    failed_concept: str
    missing_prerequisites: List[str] = field(default_factory=list)
    root_gap: Optional[str] = None
    suggested_review_path: List[str] = field(default_factory=list)
    misconceptions: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class LearningPath:
    """An optimal path from current knowledge to a target concept.

    Attributes:
        target: Target concept node ID.
        path: Ordered list of node IDs to traverse.
        total_cost: Cumulative cost (lower = easier path).
        estimated_concepts_to_learn: Number of new concepts on the path.
        mastery_along_path: Mastery values for each node on the path.
    """

    target: str
    path: List[str] = field(default_factory=list)
    total_cost: float = 0.0
    estimated_concepts_to_learn: int = 0
    mastery_along_path: List[float] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────
# Mastery Provider Interface
# ─────────────────────────────────────────────────────────────────────


def _node_to_topic(key: str) -> str:
    """'math:linear_equations:definition' -> 'linear_equations'. Прочее — без изменений."""
    if ":" in key:
        parts = key.split(":")
        if len(parts) >= 2:
            return parts[1]
    return key


class _MasteryView(dict):
    """dict мастерства, чей .get() сопоставляет ID узлов графа (domain:topic:type)
    с голыми topic-ключами трекера.

    Решает рассинхрон ключей: Navigator ищет по node.id ('math:derivatives:definition'),
    а StudentMemory хранит мастерство по topic_id ('derivatives' / 'derivatives_basic').
    Без нормализации ВСЕ lookup'ы возвращали 0.0 → персонализация молча отключалась.
    """

    def get(self, key, default=0.0):  # type: ignore[override]
        if key in self:
            return dict.__getitem__(self, key)
        topic = _node_to_topic(key)
        if topic in self:
            return dict.__getitem__(self, topic)
        # fuzzy: префиксное совпадение в обе стороны (derivatives ↔ derivatives_basic)
        for k in self.keys():
            if k.startswith(topic + "_") or topic.startswith(k + "_"):
                return dict.__getitem__(self, k)
        return default


class MasteryProvider:
    """Interface to obtain student mastery data.

    Decouples navigator from StudentMemory implementation.
    Accepts any object with get_knowledge_state(student_id) method,
    or a plain dict for testing.
    """

    def __init__(self, source):
        """Initialize from StudentMemory instance or mastery dict.

        Args:
            source: Either a StudentMemory (has get_knowledge_state)
                or Dict[str, float] mapping topic_id → mastery.
        """
        self._source = source
        self._is_dict = isinstance(source, dict)

    def get_mastery(self, student_id: str, topic_id: str) -> float:
        """Get mastery for a specific topic (или node.id графа). Returns 0.0 if unknown."""
        # Делегируем в get_all_mastery — нормализация ключей в _MasteryView.get.
        return self.get_all_mastery(student_id).get(topic_id, 0.0)

    def get_all_mastery(self, student_id: str) -> Dict[str, float]:
        """Get mastery dict for all known topics (как _MasteryView с нормализацией ключей)."""
        if self._is_dict:
            return _MasteryView(self._source)

        try:
            state = self._source.get_knowledge_state(student_id)
            if hasattr(state, "topics"):
                return _MasteryView({tid: tm.mastery for tid, tm in state.topics.items()})
            return _MasteryView()
        except Exception:
            return _MasteryView()


# ─────────────────────────────────────────────────────────────────────
# Personalized Navigator
# ─────────────────────────────────────────────────────────────────────

# Mastery thresholds
MASTERY_THRESHOLD = 0.7  # Topic considered "mastered"
MASTERY_WEAK = 0.4  # Below this = significant gap
MASTERY_UNKNOWN = 0.0  # Never attempted


class PersonalizedNavigator:
    """Student-aware knowledge graph navigator.

    Overlays BKT mastery state onto the knowledge graph to provide
    personalized navigation: learning frontiers, gap diagnosis,
    optimal learning paths, and next-concept suggestions.

    Usage:
        graph = KnowledgeGraph(Path("data/knowledge/forge.json"))
        memory = StudentMemory("data/mits.db")
        nav = PersonalizedNavigator(graph, memory)

        # What should this student learn next?
        frontier = nav.get_learning_frontier("student_42")

        # Student failed at integration_by_parts — why?
        gap = nav.diagnose_gap("student_42", "calc:integration_by_parts")

        # Build path from current knowledge to target
        path = nav.find_optimal_path("student_42", "calc:definite_integrals")
    """

    def __init__(self, graph: KnowledgeGraph, mastery_source) -> None:
        """Initialize navigator.

        Args:
            graph: The knowledge graph to navigate.
            mastery_source: StudentMemory instance or Dict[str, float]
                for testing.
        """
        self._graph = graph
        self._mastery = MasteryProvider(mastery_source)

    # ── Learning Frontier (ZPD on Graph) ─────────────────────────

    def get_learning_frontier(
        self,
        student_id: str,
        max_results: int = 5,
        domain: Optional[str] = None,
    ) -> List[FrontierNode]:
        """Find concepts at the edge of the student's knowledge.

        A frontier node is a concept where:
        - The student hasn't mastered it yet (mastery < MASTERY_THRESHOLD)
        - Most/all prerequisites ARE mastered (mastery >= MASTERY_THRESHOLD)

        This is Vygotsky's Zone of Proximal Development mapped onto
        the knowledge graph structure.

        Args:
            student_id: Student identifier.
            max_results: Maximum frontier nodes to return.
            domain: Optional domain filter.

        Returns:
            Frontier nodes sorted by readiness_score (highest first).
        """
        all_mastery = self._mastery.get_all_mastery(student_id)
        candidates: List[FrontierNode] = []

        # Search concept nodes (not examples/formulas/misconceptions)
        concept_nodes = self._graph.search(
            domain=domain,
            node_type=NodeType.CONCEPT,
        )

        for node in concept_nodes:
            own_mastery = all_mastery.get(node.id, MASTERY_UNKNOWN)

            # Skip already mastered
            if own_mastery >= MASTERY_THRESHOLD:
                continue

            # Get prerequisites via graph edges
            prereq_edges = self._graph.get_neighbors(
                node.id, edge_type=EdgeType.PREREQUISITE, direction="incoming"
            )
            # Also check BEST_TAUGHT_AFTER (pedagogical prerequisites)
            taught_after_edges = self._graph.get_neighbors(
                node.id, edge_type=EdgeType.BEST_TAUGHT_AFTER, direction="incoming"
            )

            prereq_ids = [n.id for _, n in prereq_edges]
            taught_after_ids = [n.id for _, n in taught_after_edges]
            all_prereq_ids = list(set(prereq_ids + taught_after_ids))

            mastered = [
                pid
                for pid in all_prereq_ids
                if all_mastery.get(pid, MASTERY_UNKNOWN) >= MASTERY_THRESHOLD
            ]
            missing = [pid for pid in all_prereq_ids if pid not in mastered]

            prereq_mastery_avg = (
                sum(all_mastery.get(pid, 0.0) for pid in all_prereq_ids) / len(all_prereq_ids)
                if all_prereq_ids
                else 1.0  # No prereqs = always ready
            )

            # TODO(human): Implement readiness scoring.
            # See the Learn by Doing request below for details.
            readiness = _score_frontier_node(
                own_mastery=own_mastery,
                prereq_mastery_avg=prereq_mastery_avg,
                n_mastered=len(mastered),
                n_total_prereqs=len(all_prereq_ids),
                difficulty=node.difficulty,
            )

            candidates.append(
                FrontierNode(
                    node_id=node.id,
                    title=node.title,
                    readiness_score=readiness,
                    mastered_prereqs=mastered,
                    missing_prereqs=missing,
                    prereq_mastery_avg=prereq_mastery_avg,
                    own_mastery=own_mastery,
                    difficulty=node.difficulty,
                )
            )

        candidates.sort(key=lambda f: -f.readiness_score)
        return candidates[:max_results]

    # ── Gap Diagnosis ────────────────────────────────────────────

    def diagnose_gap(
        self,
        student_id: str,
        failed_concept_id: str,
        belief_state: Optional["BeliefState"] = None,
    ) -> GapDiagnosis:
        """Diagnose why a student failed at a concept.

        Traverses PREREQUISITE edges backward from the failed concept,
        collecting unmastered prerequisites. By default, the deepest
        unmastered prerequisite is returned as root cause.

        When a trustworthy `belief_state` is provided (confidence >= 0.5),
        prerequisites are re-ranked by pedagogical relevance to the active
        misconception — the top-ranked prereq becomes root_gap instead of
        the deepest one. This implements the core ToM-Tutor improvement
        for feature 017.

        Args:
            student_id: Student identifier.
            failed_concept_id: Concept the student struggled with.
            belief_state: Optional BeliefState from MentalModelAgent (017).

        Returns:
            GapDiagnosis with missing prerequisites and review path.
        """
        all_mastery = self._mastery.get_all_mastery(student_id)
        missing: List[Tuple[str, int]] = []  # (node_id, depth)
        visited: Set[str] = set()

        def _collect_gaps(node_id: str, depth: int) -> None:
            if node_id in visited:
                return
            visited.add(node_id)

            prereqs = self._graph.get_neighbors(
                node_id, edge_type=EdgeType.PREREQUISITE, direction="incoming"
            )
            for _, prereq_node in prereqs:
                mastery = all_mastery.get(prereq_node.id, MASTERY_UNKNOWN)
                if mastery < MASTERY_THRESHOLD:
                    missing.append((prereq_node.id, depth + 1))
                    _collect_gaps(prereq_node.id, depth + 1)

        _collect_gaps(failed_concept_id, 0)

        # ToM-aware re-ranking (017): if belief_state is trustworthy,
        # sort by (relevance to misconception DESC, depth DESC) instead
        # of pure depth. Otherwise fall back to baseline (depth only).
        if belief_state is not None and belief_state.is_usable(min_confidence=0.5):
            missing = self._rerank_by_belief(missing, belief_state, all_mastery)
        else:
            # Sort by depth (deepest first = root cause) — baseline behavior
            missing.sort(key=lambda x: -x[1])

        # Find misconceptions linked to the failed concept
        misconception_edges = self._graph.get_neighbors(
            failed_concept_id,
            edge_type=EdgeType.COMMON_ERROR_FOR,
            direction="incoming",
        )
        misconception_ids = [n.id for _, n in misconception_edges]

        # Also check CONFUSED_WITH
        confused_edges = self._graph.get_neighbors(
            failed_concept_id,
            edge_type=EdgeType.CONFUSED_WITH,
            direction="both",
        )
        confused_ids = [n.id for _, n in confused_edges if n.node_type == NodeType.MISCONCEPTION]

        all_misconceptions = list(set(misconception_ids + confused_ids))

        root_gap = missing[0][0] if missing else None
        missing_ids = [m[0] for m in missing]

        # Build review path: from deepest gap → up to the failed concept
        review_path = list(reversed(missing_ids))

        n_prereqs_checked = len(visited)
        confidence = min(1.0, n_prereqs_checked / 3) if missing else 0.3

        return GapDiagnosis(
            failed_concept=failed_concept_id,
            missing_prerequisites=missing_ids,
            root_gap=root_gap,
            suggested_review_path=review_path,
            misconceptions=all_misconceptions,
            confidence=confidence,
        )

    # ── ToM-aware re-ranking (017) ───────────────────────────────

    def _rerank_by_belief(
        self,
        missing: List[Tuple[str, int]],
        belief: "BeliefState",
        all_mastery: Dict[str, float],
    ) -> List[Tuple[str, int]]:
        """Re-rank missing prerequisites by pedagogical relevance to belief state.

        Relevance score combines:
        - Token overlap between active_misconception and prereq tags/title (+2.0)
        - Existence of COMMON_ERROR_FOR edge from misconception → prereq (+1.0)
        - Closeness of prereq difficulty to student mastery level (+0.5)

        Sort key: (relevance DESC, depth DESC) — higher relevance wins;
        ties broken by depth so baseline behavior is preserved for equal scores.
        """
        misc_tokens = _tokenize(belief.active_misconception or "")
        misc_tokens |= _tokenize(belief.belief_about_topic or "")

        # Мастери студента по данной теме — оцениваем difficulty match
        student_avg_mastery = sum(all_mastery.values()) / len(all_mastery) if all_mastery else 0.5

        scored: List[Tuple[float, int, str]] = []
        for node_id, depth in missing:
            node = self._graph.get_node(node_id)
            if node is None:
                scored.append((0.0, depth, node_id))
                continue

            relevance = 0.0

            # Token overlap
            node_tokens = _tokenize(node.title) | _tokenize(node.content or "")
            for tag in node.tags or []:
                node_tokens |= _tokenize(tag)
            overlap = len(misc_tokens & node_tokens)
            if overlap > 0:
                relevance += 2.0 * min(overlap / 3.0, 1.0)  # normalize by expected overlap

            # COMMON_ERROR_FOR edge: misconception node → this prereq
            if belief.active_misconception_node_id:
                if self._graph.has_edge(
                    belief.active_misconception_node_id,
                    node_id,
                    EdgeType.COMMON_ERROR_FOR,
                ):
                    relevance += 1.0

            # Difficulty alignment
            diff_delta = abs(node.difficulty - student_avg_mastery)
            if diff_delta < 0.2:
                relevance += 0.5

            scored.append((relevance, depth, node_id))

        # Threshold-based sort:
        # - If ANY candidate has relevance >= 1.5 (strong signal from
        #   misconception match or COMMON_ERROR_FOR edge), use
        #   (relevance DESC, depth DESC) — ToM wins.
        # - Otherwise (all weak relevance), fall back to depth DESC
        #   to preserve baseline behavior and avoid regressions.
        #
        # Rationale from MVP evaluation: aggressive re-ranking caused
        # regressions on scenarios where misconception text had weak
        # keyword overlap with deeper prereqs. Conservative threshold
        # preserves baseline unless ToM has a clear winning candidate.
        max_relevance = max((s[0] for s in scored), default=0.0)
        if max_relevance >= 1.5:
            scored.sort(key=lambda x: (-x[0], -x[1]))
            logger.info(
                f"tom.rerank.activated max_rel={max_relevance:.2f}, "
                f"top-3: {[(s[2][:40], round(s[0], 2), s[1]) for s in scored[:3]]}"
            )
        else:
            scored.sort(key=lambda x: -x[1])  # depth only
            logger.info(
                f"tom.rerank.skipped max_rel={max_relevance:.2f} (< 1.5 threshold), "
                f"top-3 scores: {[(s[2][:40], round(s[0], 2), s[1]) for s in scored[:3]]}"
            )
        return [(nid, depth) for _, depth, nid in scored]

    # ── Optimal Learning Path ────────────────────────────────────

    def find_optimal_path(
        self,
        student_id: str,
        target_id: str,
    ) -> Optional[LearningPath]:
        """Find the optimal learning path to a target concept.

        Uses Dijkstra's algorithm with mastery-weighted edge costs.
        Nodes the student already knows have low traversal cost;
        unknown nodes have high cost. The result is the path that
        maximizes learning through already-familiar territory.

        Args:
            student_id: Student identifier.
            target_id: Target concept to reach.

        Returns:
            LearningPath with ordered steps, or None if unreachable.
        """
        if not self._graph.get_node(target_id):
            return None

        all_mastery = self._mastery.get_all_mastery(student_id)

        # Find all concepts the student has mastered as start points
        start_nodes: Set[str] = set()
        for node_id in self._graph._nodes:
            node = self._graph._nodes[node_id]
            if node.node_type != NodeType.CONCEPT:
                continue
            if all_mastery.get(node_id, 0.0) >= MASTERY_THRESHOLD:
                start_nodes.add(node_id)

        if target_id in start_nodes:
            return LearningPath(target=target_id, path=[target_id], total_cost=0.0)

        # If no mastered concepts, start from nodes with no prerequisites
        if not start_nodes:
            for node_id, node in self._graph._nodes.items():
                if node.node_type != NodeType.CONCEPT:
                    continue
                prereqs = self._graph.get_neighbors(
                    node_id, edge_type=EdgeType.PREREQUISITE, direction="incoming"
                )
                if not prereqs:
                    start_nodes.add(node_id)

        # Dijkstra from all start nodes simultaneously
        # Cost to reach each node
        dist: Dict[str, float] = {s: 0.0 for s in start_nodes}
        prev: Dict[str, Optional[str]] = {s: None for s in start_nodes}
        # Priority queue: (cost, node_id)
        pq: List[Tuple[float, str]] = [(0.0, s) for s in start_nodes]
        heapq.heapify(pq)
        visited: Set[str] = set()

        while pq:
            cost, current = heapq.heappop(pq)
            if current in visited:
                continue
            visited.add(current)

            if current == target_id:
                break

            # Traverse outgoing PREREQUISITE edges (concept → depends_on)
            # We need to traverse in reverse: prerequisite → concept
            # So we look at nodes that have `current` as prerequisite
            for edge, neighbor in self._graph.get_neighbors(
                current, edge_type=EdgeType.PREREQUISITE, direction="outgoing"
            ):
                if neighbor.id in visited:
                    continue
                neighbor_mastery = all_mastery.get(neighbor.id, MASTERY_UNKNOWN)
                edge_cost = _compute_edge_cost(neighbor_mastery, neighbor.difficulty)
                new_cost = cost + edge_cost

                if new_cost < dist.get(neighbor.id, float("inf")):
                    dist[neighbor.id] = new_cost
                    prev[neighbor.id] = current
                    heapq.heappush(pq, (new_cost, neighbor.id))

            # Also follow BEST_TAUGHT_AFTER edges
            for edge, neighbor in self._graph.get_neighbors(
                current, edge_type=EdgeType.BEST_TAUGHT_AFTER, direction="outgoing"
            ):
                if neighbor.id in visited:
                    continue
                neighbor_mastery = all_mastery.get(neighbor.id, MASTERY_UNKNOWN)
                # Pedagogical edges slightly cheaper (preferred path)
                edge_cost = _compute_edge_cost(neighbor_mastery, neighbor.difficulty) * 0.9
                new_cost = cost + edge_cost

                if new_cost < dist.get(neighbor.id, float("inf")):
                    dist[neighbor.id] = new_cost
                    prev[neighbor.id] = current
                    heapq.heappush(pq, (new_cost, neighbor.id))

        # Reconstruct path
        if target_id not in prev and target_id not in start_nodes:
            return None

        path: List[str] = []
        current = target_id
        while current is not None:
            path.append(current)
            current = prev.get(current)
        path.reverse()

        mastery_along = [all_mastery.get(nid, 0.0) for nid in path]
        new_concepts = sum(1 for m in mastery_along if m < MASTERY_THRESHOLD)

        return LearningPath(
            target=target_id,
            path=path,
            total_cost=dist.get(target_id, 0.0),
            estimated_concepts_to_learn=new_concepts,
            mastery_along_path=mastery_along,
        )

    # ── Alternative Paths (PathSlime, 018) ───────────────────────

    def find_alternative_paths(
        self,
        student_id: str,
        target_id: str,
        k: int = 3,
        style: str = "mixed",
        timeout_ms: Optional[int] = None,
        seed: Optional[int] = None,
    ):
        """Bio-inspired multi-path generation через PathSlime (feature 018).

        В отличие от `find_optimal_path()` (Dijkstra, один оптимум), возвращает
        k diverse learning paths. Позволяет тьютору предложить студенту выбор:
        "короткий путь vs постепенный vs с примерами".

        Args:
            student_id: Student identifier.
            target_id: Target concept to reach.
            k: Number of alternative paths (default 3, clamped to [1, 5]).
            style: Fitness weighting — "quick" / "gradual" / "example_rich" / "mixed".
            timeout_ms: Override default timeout from profile.
            seed: RNG seed for reproducibility.

        Returns:
            AlternativePaths object. On failure returns with error field set
            and empty paths list (no exceptions to caller).
        """
        from src.knowledge.path_slime import (
            AlternativePaths,
            PathSlime,
            PathSlimeConfig,
        )

        # Clamp k
        k = max(1, min(5, k))

        try:
            config = PathSlimeConfig.from_active_profile()
            config.k = k
            if timeout_ms is not None:
                config.timeout_ms = timeout_ms

            mastery = self._mastery.get_all_mastery(student_id)
            engine = PathSlime(graph=self._graph, mastery=mastery, config=config, seed=seed)
            return engine.run(target_id=target_id, style=style)
        except Exception as e:
            logger.error(f"find_alternative_paths failed: {e}")
            return AlternativePaths(
                target=target_id, paths=[], error=f"exception: {type(e).__name__}: {e}"
            )

    # ── Suggest Next Concept ─────────────────────────────────────

    def suggest_next(
        self,
        student_id: str,
        domain: Optional[str] = None,
    ) -> Optional[FrontierNode]:
        """Suggest the single best concept to teach next.

        Combines learning frontier with pedagogical heuristics:
        highest readiness_score wins.

        Args:
            student_id: Student identifier.
            domain: Optional domain filter.

        Returns:
            Best FrontierNode, or None if nothing to suggest.
        """
        frontier = self.get_learning_frontier(student_id, max_results=1, domain=domain)
        return frontier[0] if frontier else None

    # ── Concept Context for Tutor ────────────────────────────────

    def get_concept_context(
        self,
        student_id: str,
        concept_id: str,
    ) -> Optional[Dict]:
        """Get rich context about a concept personalized to the student.

        Returns concept details + student's mastery of prerequisites +
        related misconceptions + applicable methods. This is what the
        tutor LLM receives when it asks "tell me about this concept
        for this student."

        Args:
            student_id: Student identifier.
            concept_id: Concept to get context for.

        Returns:
            Dict with concept info, student state, and related nodes.
        """
        explored = self._graph.explore(concept_id)
        if not explored:
            return None

        all_mastery = self._mastery.get_all_mastery(student_id)
        node = explored["node"]

        # Enrich prerequisites with mastery info
        prereqs = self._graph.get_neighbors(
            concept_id, edge_type=EdgeType.PREREQUISITE, direction="incoming"
        )
        prereq_state = [
            {
                "id": n.id,
                "title": n.title,
                "mastery": all_mastery.get(n.id, 0.0),
                "status": (
                    "mastered"
                    if all_mastery.get(n.id, 0.0) >= MASTERY_THRESHOLD
                    else "weak"
                    if all_mastery.get(n.id, 0.0) >= MASTERY_WEAK
                    else "gap"
                ),
            }
            for _, n in prereqs
        ]

        # Get related misconceptions
        misconceptions = self._graph.get_neighbors(
            concept_id, edge_type=EdgeType.COMMON_ERROR_FOR, direction="incoming"
        )
        confused = self._graph.get_neighbors(
            concept_id, edge_type=EdgeType.CONFUSED_WITH, direction="both"
        )

        # Get applicable methods
        methods = self._graph.get_neighbors(
            concept_id, edge_type=EdgeType.APPLIES_TO, direction="incoming"
        )

        # Get illustrating examples
        examples = self._graph.get_neighbors(
            concept_id, edge_type=EdgeType.ILLUSTRATES, direction="incoming"
        )

        return {
            "concept": {
                "id": node["id"],
                "title": node["title"],
                "content": node["content"],
                "domain": node["domain"],
                "difficulty": node["difficulty"],
            },
            "student": {
                "mastery": all_mastery.get(concept_id, 0.0),
                "prerequisites": prereq_state,
                "has_gaps": any(p["status"] == "gap" for p in prereq_state),
                "weakest_prereq": (
                    min(prereq_state, key=lambda p: p["mastery"]) if prereq_state else None
                ),
            },
            "misconceptions": [
                {"id": n.id, "title": n.title, "content": n.content}
                for _, n in list(misconceptions) + list(confused)
                if n.node_type == NodeType.MISCONCEPTION
            ],
            "methods": [{"id": n.id, "title": n.title, "content": n.content} for _, n in methods],
            "examples": [
                {"id": n.id, "title": n.title, "difficulty": n.difficulty} for _, n in examples
            ],
        }


# ─────────────────────────────────────────────────────────────────────
# Scoring Functions
# ─────────────────────────────────────────────────────────────────────


def _score_frontier_node(
    own_mastery: float,
    prereq_mastery_avg: float,
    n_mastered: int,
    n_total_prereqs: int,
    difficulty: float,
) -> float:
    """Score how ready a student is to learn a frontier concept.

    Higher score = more ready = should be suggested first.

    Args:
        own_mastery: Student's current mastery of this concept (0-1).
        prereq_mastery_avg: Average mastery across all prerequisites.
        n_mastered: Number of prerequisites the student has mastered.
        n_total_prereqs: Total number of prerequisites.
        difficulty: Concept difficulty from the graph (0-1).

    Returns:
        Readiness score (0-1). Higher = more ready to learn.
    """
    # Entry-point concepts (no prerequisites) — always accessible,
    # score depends on own mastery and difficulty
    if n_total_prereqs == 0:
        novelty = 1.0 - own_mastery
        ease = 1.0 - difficulty * 0.3
        return max(0.0, min(1.0, novelty * ease))

    # Gate: if less than half of prerequisites are mastered, heavily penalize.
    # A single missing foundation can block understanding.
    prereq_ratio = n_mastered / n_total_prereqs
    if prereq_ratio < 0.5:
        return max(0.0, prereq_ratio * 0.3 * (1.0 - own_mastery))

    # Weighted composite score:
    # 1. Prerequisite completeness (40%) — ratio of mastered prereqs
    completeness = prereq_ratio

    # 2. Prerequisite quality (25%) — average mastery (0.71 vs 0.95 matters)
    quality = prereq_mastery_avg

    # 3. Novelty (25%) — lower own mastery = more frontier value
    novelty = 1.0 - own_mastery

    # 4. Difficulty alignment (10%) — penalize hard concepts when prereqs are moderate
    #    If prereq quality is high, difficulty doesn't matter much
    difficulty_fit = 1.0 - max(0.0, difficulty - quality) * 0.5

    score = 0.40 * completeness + 0.25 * quality + 0.25 * novelty + 0.10 * difficulty_fit
    return max(0.0, min(1.0, score))


def _compute_edge_cost(mastery: float, difficulty: float) -> float:
    """Compute traversal cost for Dijkstra path finding.

    Low cost = easy to traverse (student knows this or it's easy).
    High cost = hard to traverse (unknown + difficult).

    Args:
        mastery: Student's mastery of the target node (0-1).
        difficulty: Node difficulty (0-1).

    Returns:
        Edge cost > 0. Lower means preferred path.
    """
    # Already-mastered nodes are nearly free to traverse
    # Unknown nodes cost proportional to difficulty
    knowledge_cost = 1.0 - mastery
    difficulty_factor = 0.5 + 0.5 * difficulty  # Range [0.5, 1.0]
    return max(0.01, knowledge_cost * difficulty_factor)


# ─────────────────────────────────────────────────────────────────────
# Text tokenizer for ToM re-ranking (017)
# ─────────────────────────────────────────────────────────────────────

# Русские и английские стоп-слова (короткий список, без внешних зависимостей)
_STOPWORDS = frozenset(
    {
        "и",
        "в",
        "на",
        "с",
        "что",
        "это",
        "как",
        "для",
        "не",
        "но",
        "же",
        "то",
        "по",
        "из",
        "от",
        "до",
        "the",
        "a",
        "an",
        "is",
        "are",
        "of",
        "to",
        "in",
        "for",
        "with",
    }
)


def _tokenize(text: str) -> Set[str]:
    """Простая токенизация для keyword-overlap без эмбеддингов.

    Разбивает текст на слова длиннее 3 символов, нижний регистр,
    без стоп-слов. Работает для русского и английского.
    Ограничение для Lite-профиля: никаких внешних NLP-зависимостей.

    Args:
        text: Входной текст (русский или английский).

    Returns:
        Множество токенов в нижнем регистре.
    """
    if not text:
        return set()

    # Разбиваем по небуквенным символам
    import re

    words = re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
    return {w for w in words if len(w) > 3 and w not in _STOPWORDS}
