"""
Knowledge Forge: Active Knowledge Graph Construction & Navigation.

Unlike RAG (passive chunk retrieval), Knowledge Forge lets the model
actively extract, organize, and navigate structured knowledge from sources.

The model uses tool calling to:
1. Extract entities and relations from source documents
2. Build a navigable knowledge graph
3. Query the graph at tutoring time for precise information

Architecture:
    Source → Extractor Agent (LLM + tools) → Knowledge Graph → Navigator Tools → Tutor
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Node & Edge Type Definitions
# ─────────────────────────────────────────────────────────────────────


class NodeType(str, Enum):
    """Types of knowledge nodes in the graph."""

    CONCEPT = "concept"  # Definition, core idea (e.g. "derivative")
    FORMULA = "formula"  # Mathematical formula (e.g. "(fg)' = f'g + fg'")
    THEOREM = "theorem"  # Proven statement (e.g. "Fundamental Theorem of Calculus")
    EXAMPLE = "example"  # Worked problem with solution steps
    METHOD = "method"  # Solution strategy (e.g. "substitution method")
    MISCONCEPTION = "misconception"  # Common error pattern with correction


class EdgeType(str, Enum):
    """Types of directed relations between knowledge nodes.

    Organized by tutoring function:
    - Learning path: PREREQUISITE, PART_OF, GENERALIZES
    - Misconception: CONFUSED_WITH, COMMON_ERROR_FOR
    - Method/proof: APPLIES_TO, DERIVED_FROM, PROVES
    - Pedagogy: BEST_TAUGHT_AFTER, ILLUSTRATES
    """

    # ── Learning path edges ──────────────────────────────────────
    PREREQUISITE = "prerequisite"  # A must be understood before B
    PART_OF = "part_of"  # A is a subtopic of B (e.g. chain_rule → derivatives)
    GENERALIZES = "generalizes"  # A is a general case of B (e.g. L'Hopital → limits)

    # ── Misconception edges ──────────────────────────────────────
    CONFUSED_WITH = "confused_with"  # Students often confuse A with B (bidirectional intent)
    COMMON_ERROR_FOR = "common_error_for"  # Misconception A is a typical error for concept B

    # ── Method / proof edges ─────────────────────────────────────
    APPLIES_TO = "applies_to"  # Method A solves/applies to concept B
    DERIVED_FROM = "derived_from"  # B is derived/proven from A
    PROVES = "proves"  # Theorem A proves/establishes B

    # ── Pedagogical edges (the novel part) ───────────────────────
    BEST_TAUGHT_AFTER = "best_taught_after"  # Pedagogically optimal to teach A after B
    ILLUSTRATES = "illustrates"  # Example A demonstrates concept/theorem B


# ─────────────────────────────────────────────────────────────────────
# Core Data Structures
# ─────────────────────────────────────────────────────────────────────


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph.

    Args:
        id: Unique identifier (e.g. "calc:derivative:definition").
        node_type: Type of knowledge this node represents.
        title: Human-readable title (Russian).
        title_en: English title (for code/search).
        content: Main content (definition, formula, steps, etc.).
        domain: Subject domain (math, physics, chemistry, biology, cs).
        tags: Searchable tags.
        difficulty: 0.0 (trivial) to 1.0 (olympiad).
        source: Where this knowledge was extracted from.
        metadata: Additional type-specific data.
        created_at: When this node was created.
        confidence: Extraction confidence (0-1), 1.0 for manually verified.
    """

    id: str
    node_type: NodeType
    title: str
    title_en: str
    content: str
    domain: str = "math"
    tags: List[str] = field(default_factory=list)
    difficulty: float = 0.5
    source: str = ""
    metadata: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = 1.0


@dataclass
class KnowledgeEdge:
    """A directed edge between two knowledge nodes.

    Args:
        source_id: ID of the source node.
        target_id: ID of the target node.
        edge_type: Semantic relation type.
        weight: Strength of relation (0-1).
        metadata: Additional context about the relation.
    """

    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: Dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────
# Knowledge Graph
# ─────────────────────────────────────────────────────────────────────


class KnowledgeGraph:
    """Navigable knowledge graph with persistence.

    Stores concepts, formulas, theorems, examples, methods, and
    misconceptions as nodes, connected by typed directed edges.

    Designed for tool-based navigation by the tutor LLM, not
    for vector similarity search.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize knowledge graph.

        Args:
            storage_path: Path to JSON persistence file.
                If None, graph is in-memory only.
        """
        self._nodes: Dict[str, KnowledgeNode] = {}
        self._edges: List[KnowledgeEdge] = []
        # Adjacency index: node_id -> list of (edge, neighbor_id)
        self._outgoing: Dict[str, List[Tuple[KnowledgeEdge, str]]] = {}
        self._incoming: Dict[str, List[Tuple[KnowledgeEdge, str]]] = {}
        # Domain index
        self._by_domain: Dict[str, Set[str]] = {}
        # Type index
        self._by_type: Dict[NodeType, Set[str]] = {t: set() for t in NodeType}

        self._storage_path = storage_path
        if storage_path and storage_path.exists():
            self._load(storage_path)
            logger.info(
                f"KnowledgeGraph loaded: {len(self._nodes)} nodes, "
                f"{len(self._edges)} edges from {storage_path}"
            )

    # ── CRUD ─────────────────────────────────────────────────────────

    def add_node(self, node: KnowledgeNode) -> None:
        """Add or update a node in the graph."""
        self._nodes[node.id] = node
        self._by_type[node.node_type].add(node.id)
        self._by_domain.setdefault(node.domain, set()).add(node.id)
        if node.id not in self._outgoing:
            self._outgoing[node.id] = []
        if node.id not in self._incoming:
            self._incoming[node.id] = []

    def has_edge(self, source_id: str, target_id: str, edge_type: EdgeType) -> bool:
        """Check if an edge already exists."""
        for edge, nid in self._outgoing.get(source_id, []):
            if nid == target_id and edge.edge_type == edge_type:
                return True
        return False

    def add_edge(self, edge: KnowledgeEdge) -> None:
        """Add a directed edge between existing nodes."""
        if edge.source_id not in self._nodes:
            raise KeyError(f"Source node not found: {edge.source_id}")
        if edge.target_id not in self._nodes:
            raise KeyError(f"Target node not found: {edge.target_id}")

        self._edges.append(edge)
        self._outgoing.setdefault(edge.source_id, []).append((edge, edge.target_id))
        self._incoming.setdefault(edge.target_id, []).append((edge, edge.source_id))

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """Get node by ID."""
        return self._nodes.get(node_id)

    def remove_node(self, node_id: str) -> bool:
        """Remove node and all its edges."""
        if node_id not in self._nodes:
            return False

        node = self._nodes.pop(node_id)
        self._by_type[node.node_type].discard(node_id)
        if node.domain in self._by_domain:
            self._by_domain[node.domain].discard(node_id)

        # Remove edges
        self._edges = [e for e in self._edges if e.source_id != node_id and e.target_id != node_id]
        self._outgoing.pop(node_id, None)
        self._incoming.pop(node_id, None)
        for adj in self._outgoing.values():
            adj[:] = [(e, nid) for e, nid in adj if nid != node_id]
        for adj in self._incoming.values():
            adj[:] = [(e, nid) for e, nid in adj if nid != node_id]

        return True

    # ── Navigation (for LLM tools) ──────────────────────────────────

    def explore(self, node_id: str) -> Optional[Dict]:
        """Get node details + all neighbors. Primary navigation tool.

        Returns:
            Dict with node info and categorized neighbors, or None.
        """
        node = self._nodes.get(node_id)
        if not node:
            return None

        neighbors = {}
        for edge, neighbor_id in self._outgoing.get(node_id, []):
            neighbor = self._nodes[neighbor_id]
            neighbors.setdefault(edge.edge_type.value, []).append(
                {
                    "id": neighbor_id,
                    "title": neighbor.title,
                    "type": neighbor.node_type.value,
                }
            )
        for edge, neighbor_id in self._incoming.get(node_id, []):
            neighbor = self._nodes[neighbor_id]
            inv_label = f"inv_{edge.edge_type.value}"
            neighbors.setdefault(inv_label, []).append(
                {
                    "id": neighbor_id,
                    "title": neighbor.title,
                    "type": neighbor.node_type.value,
                }
            )

        return {
            "node": asdict(node),
            "neighbors": neighbors,
            "degree": len(self._outgoing.get(node_id, [])) + len(self._incoming.get(node_id, [])),
        }

    def find_path(
        self,
        from_id: str,
        to_id: str,
        edge_types: Optional[List[EdgeType]] = None,
    ) -> Optional[List[str]]:
        """BFS shortest path between two nodes.

        Args:
            from_id: Start node.
            to_id: Target node.
            edge_types: Filter by edge types (None = all).

        Returns:
            List of node IDs forming the path, or None.
        """
        if from_id not in self._nodes or to_id not in self._nodes:
            return None

        from collections import deque

        visited = {from_id}
        queue: deque[List[str]] = deque([[from_id]])

        while queue:
            path = queue.popleft()
            current = path[-1]

            if current == to_id:
                return path

            for edge, neighbor_id in self._outgoing.get(current, []):
                if neighbor_id in visited:
                    continue
                if edge_types and edge.edge_type not in edge_types:
                    continue
                visited.add(neighbor_id)
                queue.append(path + [neighbor_id])

        return None

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[EdgeType] = None,
        direction: str = "outgoing",
    ) -> List[Tuple[KnowledgeEdge, KnowledgeNode]]:
        """Get neighbors filtered by edge type and direction.

        Args:
            node_id: Source node.
            edge_type: Filter by relation type.
            direction: "outgoing", "incoming", or "both".

        Returns:
            List of (edge, node) pairs.
        """
        results = []
        if direction in ("outgoing", "both"):
            for edge, nid in self._outgoing.get(node_id, []):
                if edge_type is None or edge.edge_type == edge_type:
                    results.append((edge, self._nodes[nid]))
        if direction in ("incoming", "both"):
            for edge, nid in self._incoming.get(node_id, []):
                if edge_type is None or edge.edge_type == edge_type:
                    results.append((edge, self._nodes[nid]))
        return results

    def search(
        self,
        domain: Optional[str] = None,
        node_type: Optional[NodeType] = None,
        tags: Optional[List[str]] = None,
        difficulty_range: Optional[Tuple[float, float]] = None,
        query: Optional[str] = None,
    ) -> List[KnowledgeNode]:
        """Search nodes by filters. No embeddings — structured filtering.

        Args:
            domain: Filter by domain.
            node_type: Filter by node type.
            tags: Filter by tags (any match).
            difficulty_range: (min, max) difficulty.
            query: Keyword search in title/content.

        Returns:
            Matching nodes, sorted by relevance.
        """
        candidates = set(self._nodes.keys())

        if domain:
            candidates &= self._by_domain.get(domain, set())
        if node_type:
            candidates &= self._by_type.get(node_type, set())

        results = []
        query_lower = query.lower() if query else None

        for nid in candidates:
            node = self._nodes[nid]

            if tags and not any(t in node.tags for t in tags):
                continue
            if difficulty_range:
                lo, hi = difficulty_range
                if not (lo <= node.difficulty <= hi):
                    continue

            score = 1.0
            if query_lower:
                title_match = query_lower in node.title.lower()
                title_en_match = query_lower in node.title_en.lower()
                content_match = query_lower in node.content.lower()
                if not (title_match or title_en_match or content_match):
                    continue
                score = 3.0 if title_match else (2.0 if title_en_match else 1.0)

            results.append((score, node))

        results.sort(key=lambda x: -x[0])
        return [node for _, node in results]

    # ── Statistics ───────────────────────────────────────────────────

    @property
    def stats(self) -> Dict:
        """Graph statistics summary."""
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "by_type": {t.value: len(ids) for t, ids in self._by_type.items() if ids},
            "by_domain": {d: len(ids) for d, ids in self._by_domain.items()},
            "edge_types": dict(
                __import__("collections").Counter(e.edge_type.value for e in self._edges)
            ),
        }

    # ── Persistence ──────────────────────────────────────────────────

    def save(self, path: Optional[Path] = None) -> None:
        """Save graph to JSON file."""
        path = path or self._storage_path
        if not path:
            raise ValueError("No storage path specified")

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "nodes": [asdict(n) for n in self._nodes.values()],
            "edges": [asdict(e) for e in self._edges],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"KnowledgeGraph saved: {len(self._nodes)} nodes, {len(self._edges)} edges")

    def _load(self, path: Path) -> None:
        """Load graph from JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))

        for nd in data.get("nodes", []):
            nd["node_type"] = NodeType(nd["node_type"])
            node = KnowledgeNode(**nd)
            self.add_node(node)

        for ed in data.get("edges", []):
            ed["edge_type"] = EdgeType(ed["edge_type"])
            edge = KnowledgeEdge(**ed)
            self.add_edge(edge)
