#!/usr/bin/env python3
"""
Migrate existing MITS knowledge data into Knowledge Forge graph format.

Sources:
  1. src/data/knowledge_graph.py — SKILL_GRAPH (51 skills with prerequisites)
  2. data/knowledge/textbooks/*.json — SKI KnowledgeCards (formulas, examples, methods, errors)

Output:
  data/knowledge/forge.json — Knowledge Forge graph

Usage:
    python scripts/migrate_to_forge.py
"""

import json
import logging
import sys
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.knowledge_graph import SKILL_GRAPH
from src.knowledge.knowledge_forge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path("data/knowledge/forge.json")
TEXTBOOKS_DIR = Path("data/knowledge/textbooks")


def migrate_skill_graph(graph: KnowledgeGraph) -> int:
    """Migrate Python SKILL_GRAPH dict into graph CONCEPT nodes + PREREQUISITE edges.

    Returns:
        Number of concept nodes added.
    """
    added = 0
    skipped = 0

    for skill_id, skill_data in SKILL_GRAPH.items():
        category = skill_data.get("category", "math")
        node_id = f"{category}:{skill_id}:definition"

        if graph.get_node(node_id) is not None:
            skipped += 1
            continue

        node = KnowledgeNode(
            id=node_id,
            node_type=NodeType.CONCEPT,
            title=skill_data.get("name_ru", skill_data["name"]),
            title_en=skill_data["name"],
            content=f"Определение: {skill_data.get('name_ru', skill_data['name'])}",
            domain=category,
            tags=[category, skill_id],
            difficulty=skill_data.get("difficulty", 0.5),
            source="skill_graph_migration",
            metadata={
                "estimated_time_hours": skill_data.get("estimated_time_hours", 0),
                "original_skill_id": skill_id,
            },
            confidence=1.0,
        )
        graph.add_node(node)
        added += 1

    # Second pass: create PREREQUISITE edges
    edges_added = 0
    for skill_id, skill_data in SKILL_GRAPH.items():
        category = skill_data.get("category", "math")
        target_id = f"{category}:{skill_id}:definition"

        for prereq_id in skill_data.get("prerequisites", []):
            # Find the prerequisite node — it might be in a different category
            prereq_data = SKILL_GRAPH.get(prereq_id)
            if prereq_data is None:
                logger.warning(f"Prerequisite '{prereq_id}' not found in SKILL_GRAPH, skipping")
                continue

            prereq_category = prereq_data.get("category", "math")
            source_id = f"{prereq_category}:{prereq_id}:definition"

            if graph.get_node(source_id) is None or graph.get_node(target_id) is None:
                continue
            if graph.has_edge(source_id, target_id, EdgeType.PREREQUISITE):
                continue

            try:
                graph.add_edge(
                    KnowledgeEdge(
                        source_id=source_id,
                        target_id=target_id,
                        edge_type=EdgeType.PREREQUISITE,
                    )
                )
                edges_added += 1
            except KeyError as e:
                logger.warning(f"Edge error {source_id} → {target_id}: {e}")

    logger.info(
        f"SKILL_GRAPH: {added} concepts added, {skipped} skipped, {edges_added} prerequisite edges"
    )
    return added


def migrate_textbook_cards(graph: KnowledgeGraph) -> int:
    """Migrate SKI KnowledgeCards from textbooks/*.json into child nodes.

    Each card decomposes into:
    - key_formulas → FORMULA nodes + DERIVED_FROM edges
    - worked_examples → EXAMPLE nodes + ILLUSTRATES edges
    - solution_methods → METHOD nodes + APPLIES_TO edges
    - common_errors → MISCONCEPTION nodes + COMMON_ERROR_FOR edges

    Returns:
        Number of child nodes added.
    """
    if not TEXTBOOKS_DIR.exists():
        logger.warning(f"Textbooks directory not found: {TEXTBOOKS_DIR}")
        return 0

    total_added = 0

    for json_path in sorted(TEXTBOOKS_DIR.glob("*.json")):
        if json_path.name == "tau_tome2.json":
            # Skip large non-card file
            continue

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read {json_path}: {e}")
            continue

        cards = data.get("cards", [])
        for card in cards:
            total_added += _migrate_single_card(graph, card)

    logger.info(f"Textbook cards: {total_added} child nodes added")
    return total_added


def _migrate_single_card(graph: KnowledgeGraph, card: dict) -> int:
    """Migrate a single KnowledgeCard into graph nodes and edges."""
    added = 0
    skill = card.get("skill", card.get("topic", "unknown"))
    domain = card.get("domain", "math")
    parent_id = f"{domain}:{skill}:definition"

    # Ensure parent concept exists
    if graph.get_node(parent_id) is None:
        # Create concept from card if not already in graph from SKILL_GRAPH
        definition = card.get("definition", f"Определение: {skill}")
        diff_map = {"easy": 0.3, "medium": 0.5, "hard": 0.7}
        difficulty = diff_map.get(card.get("difficulty", "medium"), 0.5)

        graph.add_node(
            KnowledgeNode(
                id=parent_id,
                node_type=NodeType.CONCEPT,
                title=card.get("topic", skill),
                title_en=skill,
                content=definition,
                domain=domain,
                difficulty=difficulty,
                tags=card.get("tags", []),
                source="textbook_migration",
                confidence=1.0,
            )
        )
        added += 1

    # Update parent content with definition if richer
    parent = graph.get_node(parent_id)
    if parent and card.get("definition") and len(card["definition"]) > len(parent.content):
        parent.content = card["definition"]

    # ── key_formulas → FORMULA nodes ─────────────────────────────
    for i, formula in enumerate(card.get("key_formulas", [])):
        formula_id = f"{domain}:{skill}:formula:{i}"
        if graph.get_node(formula_id) is not None:
            continue

        name = formula.get("name", f"Формула {i + 1}")
        latex = formula.get("latex", "")
        content = f"{name}: {latex}" if latex else name

        graph.add_node(
            KnowledgeNode(
                id=formula_id,
                node_type=NodeType.FORMULA,
                title=name,
                title_en=formula.get("name_en", name),
                content=content,
                domain=domain,
                tags=[skill, "formula"],
                difficulty=parent.difficulty if parent else 0.5,
                source="textbook_migration",
                metadata={"latex": latex},
                confidence=1.0,
            )
        )
        graph.add_edge(
            KnowledgeEdge(
                source_id=parent_id,
                target_id=formula_id,
                edge_type=EdgeType.DERIVED_FROM,
            )
        )
        added += 1

    # ── worked_examples → EXAMPLE nodes ──────────────────────────
    for i, example in enumerate(card.get("worked_examples", [])):
        example_id = f"{domain}:{skill}:example:{i}"
        if graph.get_node(example_id) is not None:
            continue

        title = example.get("title", example.get("problem", f"Пример {i + 1}"))
        if isinstance(title, dict):
            title = str(title)
        content = (
            json.dumps(example, ensure_ascii=False) if isinstance(example, dict) else str(example)
        )

        graph.add_node(
            KnowledgeNode(
                id=example_id,
                node_type=NodeType.EXAMPLE,
                title=title[:100],
                title_en=f"Example {i + 1}: {skill}",
                content=content[:500],
                domain=domain,
                tags=[skill, "example"],
                difficulty=parent.difficulty if parent else 0.5,
                source="textbook_migration",
                confidence=1.0,
            )
        )
        graph.add_edge(
            KnowledgeEdge(
                source_id=example_id,
                target_id=parent_id,
                edge_type=EdgeType.ILLUSTRATES,
            )
        )
        added += 1

    # ── solution_methods → METHOD nodes ──────────────────────────
    for i, method in enumerate(card.get("solution_methods", [])):
        method_id = f"{domain}:{skill}:method:{i}"
        if graph.get_node(method_id) is not None:
            continue

        name = method.get("name", f"Метод {i + 1}")
        steps = method.get("steps", [])
        content = f"{name}\n" + "\n".join(f"  {j + 1}. {s}" for j, s in enumerate(steps))

        graph.add_node(
            KnowledgeNode(
                id=method_id,
                node_type=NodeType.METHOD,
                title=name,
                title_en=method.get("method_id", name),
                content=content,
                domain=domain,
                tags=[skill, "method"],
                difficulty=parent.difficulty if parent else 0.5,
                source="textbook_migration",
                metadata={"when_to_use": method.get("when_to_use", "")},
                confidence=1.0,
            )
        )
        graph.add_edge(
            KnowledgeEdge(
                source_id=method_id,
                target_id=parent_id,
                edge_type=EdgeType.APPLIES_TO,
            )
        )
        added += 1

    # ── common_errors → MISCONCEPTION nodes ──────────────────────
    for i, error in enumerate(card.get("common_errors", [])):
        error_id = f"{domain}:{skill}:misconception:{i}"
        if graph.get_node(error_id) is not None:
            continue

        if isinstance(error, dict):
            title = error.get("error", error.get("name", f"Ошибка {i + 1}"))
            correction = error.get("correction", error.get("fix", ""))
            content = f"{title}\nИсправление: {correction}" if correction else title
        else:
            title = str(error)[:100]
            content = str(error)

        graph.add_node(
            KnowledgeNode(
                id=error_id,
                node_type=NodeType.MISCONCEPTION,
                title=title[:100],
                title_en=f"Error {i + 1}: {skill}",
                content=content[:500],
                domain=domain,
                tags=[skill, "misconception"],
                difficulty=parent.difficulty if parent else 0.5,
                source="textbook_migration",
                confidence=1.0,
            )
        )
        graph.add_edge(
            KnowledgeEdge(
                source_id=error_id,
                target_id=parent_id,
                edge_type=EdgeType.COMMON_ERROR_FOR,
            )
        )
        added += 1

    return added


def main() -> None:
    logger.info("=" * 60)
    logger.info("Knowledge Forge Migration")
    logger.info("=" * 60)

    # Load existing graph or create new
    graph = KnowledgeGraph(OUTPUT_PATH) if OUTPUT_PATH.exists() else KnowledgeGraph()

    # Phase 1: SKILL_GRAPH → CONCEPT nodes + PREREQUISITE edges
    migrate_skill_graph(graph)

    # Phase 2: Textbook cards → child nodes
    migrate_textbook_cards(graph)

    # Save
    graph.save(OUTPUT_PATH)

    # Summary
    stats = graph.stats
    logger.info("")
    logger.info("=" * 60)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total nodes: {stats['total_nodes']}")
    logger.info(f"Total edges: {stats['total_edges']}")
    logger.info(f"By type: {stats['by_type']}")
    logger.info(f"By domain: {stats['by_domain']}")
    logger.info(f"Edge types: {stats['edge_types']}")
    logger.info(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
