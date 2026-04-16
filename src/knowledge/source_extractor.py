"""
Source Extractor: LLM-based knowledge extraction from documents.

Uses Ollama JSON mode to extract structured knowledge — concepts,
formulas, theorems, examples — and their relationships from text.

Two-pass extraction:
  1. Entity pass: identify concepts, formulas, examples
  2. Relation pass: identify relationships between entities

Extracted nodes get confidence < 1.0 to distinguish from manually
verified data. Deduplication by fuzzy title + domain matching.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple

from src.knowledge.knowledge_forge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Extraction Prompts
# ─────────────────────────────────────────────────────────────────────

ENTITY_EXTRACTION_PROMPT = """Analyze the following educational text and extract structured knowledge entities.

For each entity found, provide:
- type: one of "concept", "formula", "theorem", "example", "method"
- title: name in Russian
- title_en: name in English
- content: definition or description (1-3 sentences)
- difficulty: 0.0 to 1.0 (0=trivial, 1=olympiad)
- tags: relevant keywords

Return a JSON object with key "entities" containing a list of entities.

TEXT:
{text}

DOMAIN: {domain}

Return ONLY valid JSON."""

RELATION_EXTRACTION_PROMPT = """Given these knowledge entities extracted from an educational text, identify relationships between them.

ENTITIES:
{entities_json}

For each relationship found, provide:
- source: title of the source entity (exact match from list above)
- target: title of the target entity (exact match from list above)
- type: one of "prerequisite", "derived_from", "part_of", "applies_to", "illustrates", "confused_with", "common_error_for", "proves", "generalizes", "best_taught_after"

Return a JSON object with key "relations" containing a list of relations.

Return ONLY valid JSON."""


# ─────────────────────────────────────────────────────────────────────
# Source Extractor
# ─────────────────────────────────────────────────────────────────────


class SourceExtractor:
    """Extract structured knowledge from text documents using LLM.

    Uses two-pass extraction: entities first, then relations.
    Results have confidence < 1.0 to flag for human review.

    Args:
        llm_client: Optional LLMClient instance. If None, uses default.
        extraction_confidence: Confidence score for extracted nodes (0-1).
    """

    def __init__(
        self,
        llm_client=None,
        extraction_confidence: float = 0.7,
    ):
        self._llm = llm_client
        self._confidence = extraction_confidence

    def _get_llm(self):
        """Lazy-load LLM client."""
        if self._llm is None:
            from src.models.llm_client import LLMClient

            self._llm = LLMClient()
        return self._llm

    def extract(
        self,
        text: str,
        domain: str = "math",
        source_name: str = "document",
    ) -> Tuple[List[KnowledgeNode], List[KnowledgeEdge]]:
        """Extract knowledge entities and relations from text.

        Args:
            text: Source text (textbook chapter, article, etc.)
            domain: Subject domain (math, physics, chemistry, biology, cs)
            source_name: Attribution for extracted nodes

        Returns:
            Tuple of (nodes, edges) ready for graph ingestion.
        """
        # Pass 1: Extract entities
        entities = self._extract_entities(text, domain)
        if not entities:
            logger.warning("No entities extracted from text")
            return [], []

        # Create nodes
        nodes = []
        title_to_id: Dict[str, str] = {}
        for i, entity in enumerate(entities):
            node_type = self._map_node_type(entity.get("type", "concept"))
            node_id = (
                f"{domain}:{self._slugify(entity.get('title_en', f'entity_{i}'))}:{node_type.value}"
            )

            node = KnowledgeNode(
                id=node_id,
                node_type=node_type,
                title=entity.get("title", f"Entity {i}"),
                title_en=entity.get("title_en", f"entity_{i}"),
                content=entity.get("content", ""),
                domain=domain,
                tags=entity.get("tags", []),
                difficulty=float(entity.get("difficulty", 0.5)),
                source=source_name,
                confidence=self._confidence,
            )
            nodes.append(node)
            title_to_id[entity.get("title", "")] = node_id
            title_to_id[entity.get("title_en", "")] = node_id

        # Pass 2: Extract relations
        relations = self._extract_relations(entities)
        edges = []
        for rel in relations:
            source_id = title_to_id.get(rel.get("source", ""))
            target_id = title_to_id.get(rel.get("target", ""))
            edge_type = self._map_edge_type(rel.get("type", "related_to"))

            if source_id and target_id and edge_type and source_id != target_id:
                edges.append(
                    KnowledgeEdge(
                        source_id=source_id,
                        target_id=target_id,
                        edge_type=edge_type,
                    )
                )

        logger.info(
            f"Extracted {len(nodes)} entities, {len(edges)} relations from {source_name} ({domain})"
        )
        return nodes, edges

    def ingest(
        self,
        graph: KnowledgeGraph,
        text: str,
        domain: str = "math",
        source_name: str = "document",
    ) -> Dict[str, int]:
        """Extract and add knowledge to the graph.

        Args:
            graph: Target knowledge graph.
            text: Source text.
            domain: Subject domain.
            source_name: Attribution.

        Returns:
            Summary dict with added/skipped/merged counts.
        """
        nodes, edges = self.extract(text, domain, source_name)

        added, skipped, merged = 0, 0, 0
        for node in nodes:
            existing = graph.get_node(node.id)
            if existing is not None:
                # Check if existing has lower confidence — merge
                if existing.confidence < node.confidence:
                    graph.add_node(node)  # Overwrite
                    merged += 1
                else:
                    skipped += 1
            else:
                # Check fuzzy duplicate by title
                dupes = graph.search(query=node.title, domain=node.domain)
                if dupes and dupes[0].title.lower() == node.title.lower():
                    skipped += 1
                    logger.debug(f"Skipped duplicate: {node.title}")
                else:
                    graph.add_node(node)
                    added += 1

        edges_added = 0
        for edge in edges:
            if (
                graph.get_node(edge.source_id) is not None
                and graph.get_node(edge.target_id) is not None
                and not graph.has_edge(edge.source_id, edge.target_id, edge.edge_type)
            ):
                graph.add_edge(edge)
                edges_added += 1

        summary = {
            "nodes_added": added,
            "nodes_skipped": skipped,
            "nodes_merged": merged,
            "edges_added": edges_added,
        }
        logger.info(f"Ingestion complete: {summary}")
        return summary

    # ── LLM Calls ───────────────────────────────────────────────

    def _extract_entities(self, text: str, domain: str) -> List[Dict]:
        """Pass 1: Extract entities from text using LLM."""
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text[:3000], domain=domain)

        try:
            llm = self._get_llm()
            response = llm.generate(prompt, format="json")
            data = json.loads(response)
            return data.get("entities", [])
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []

    def _extract_relations(self, entities: List[Dict]) -> List[Dict]:
        """Pass 2: Extract relations between entities using LLM."""
        if len(entities) < 2:
            return []

        entities_json = json.dumps(
            [{"title": e.get("title", ""), "type": e.get("type", "")} for e in entities],
            ensure_ascii=False,
        )
        prompt = RELATION_EXTRACTION_PROMPT.format(entities_json=entities_json)

        try:
            llm = self._get_llm()
            response = llm.generate(prompt, format="json")
            data = json.loads(response)
            return data.get("relations", [])
        except Exception as e:
            logger.error(f"Relation extraction failed: {e}")
            return []

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _map_node_type(type_str: str) -> NodeType:
        """Map string to NodeType enum."""
        mapping = {
            "concept": NodeType.CONCEPT,
            "formula": NodeType.FORMULA,
            "theorem": NodeType.THEOREM,
            "example": NodeType.EXAMPLE,
            "method": NodeType.METHOD,
            "misconception": NodeType.MISCONCEPTION,
        }
        return mapping.get(type_str.lower(), NodeType.CONCEPT)

    @staticmethod
    def _map_edge_type(type_str: str) -> Optional[EdgeType]:
        """Map string to EdgeType enum."""
        mapping = {
            "prerequisite": EdgeType.PREREQUISITE,
            "derived_from": EdgeType.DERIVED_FROM,
            "part_of": EdgeType.PART_OF,
            "applies_to": EdgeType.APPLIES_TO,
            "illustrates": EdgeType.ILLUSTRATES,
            "confused_with": EdgeType.CONFUSED_WITH,
            "common_error_for": EdgeType.COMMON_ERROR_FOR,
            "proves": EdgeType.PROVES,
            "generalizes": EdgeType.GENERALIZES,
            "best_taught_after": EdgeType.BEST_TAUGHT_AFTER,
        }
        return mapping.get(type_str.lower())

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-safe slug for node IDs."""
        import re

        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        return slug.strip("_")[:50]
