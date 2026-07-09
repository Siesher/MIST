"""
MITS Structured Knowledge Index (SKI)

Replaces chunk-based RAG with structured knowledge cards for tutoring.
Each card represents a well-defined topic with formulas, examples,
prerequisites, and common errors — ideal for tool-based retrieval.

Cards are loaded from JSON files in data/knowledge/textbooks/.
Indexing uses O(1) dictionaries by topic/skill/domain/tag.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default path for knowledge cards
try:
    from src.config import settings
    DEFAULT_DATA_PATH = getattr(
        settings, 'KNOWLEDGE_TEXTBOOKS_PATH',
        Path('./data/knowledge/textbooks')
    )
except ImportError:
    DEFAULT_DATA_PATH = Path('./data/knowledge/textbooks')


@dataclass
class KnowledgeCard:
    """A structured knowledge unit for a single topic."""

    id: str
    topic: str                              # e.g. "quadratic_equations"
    domain: str                             # e.g. "math", "physics", "cs"
    skill: str                              # matches skill_graph.json keys
    difficulty: str                         # "easy", "medium", "hard"
    prerequisites: List[str] = field(default_factory=list)
    definition: str = ""
    key_formulas: List[Dict[str, str]] = field(default_factory=list)
    notation: Dict[str, str] = field(default_factory=dict)
    worked_examples: List[Dict[str, Any]] = field(default_factory=list)
    common_errors: List[Dict[str, str]] = field(default_factory=list)
    source_reference: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # Textbook grounding fields
    solution_methods: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {method_id, name, applicability, steps: [{step, action, formula}],
    #          when_to_use, common_pitfalls}

    problem_templates: List[Dict[str, Any]] = field(default_factory=list)
    # Format: {template_id, pattern, parameters: {name: {type, range, exclude}},
    #          constraints, answer_template, solution_method_id, difficulty}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize card to dict."""
        return {
            "id": self.id,
            "topic": self.topic,
            "domain": self.domain,
            "skill": self.skill,
            "difficulty": self.difficulty,
            "prerequisites": self.prerequisites,
            "definition": self.definition,
            "key_formulas": self.key_formulas,
            "notation": self.notation,
            "worked_examples": self.worked_examples,
            "common_errors": self.common_errors,
            "source_reference": self.source_reference,
            "tags": self.tags,
            "solution_methods": self.solution_methods,
            "problem_templates": self.problem_templates,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeCard":
        """Deserialize card from dict."""
        return cls(
            id=data["id"],
            topic=data["topic"],
            domain=data.get("domain", "math"),
            skill=data.get("skill", data["topic"]),
            difficulty=data.get("difficulty", "medium"),
            prerequisites=data.get("prerequisites", []),
            definition=data.get("definition", ""),
            key_formulas=data.get("key_formulas", []),
            notation=data.get("notation", {}),
            worked_examples=data.get("worked_examples", []),
            common_errors=data.get("common_errors", []),
            source_reference=data.get("source_reference", {}),
            tags=data.get("tags", []),
            solution_methods=data.get("solution_methods", []),
            problem_templates=data.get("problem_templates", []),
        )


class StructuredKnowledgeIndex:
    """
    In-memory index over KnowledgeCards with O(1) lookups.

    Indexes:
    - _by_topic: topic string → list of cards
    - _by_skill: skill string → list of cards
    - _by_domain: domain string → list of cards
    - _by_tag: tag string → list of cards
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = Path(data_path) if data_path else DEFAULT_DATA_PATH
        self._cards: List[KnowledgeCard] = []
        self._by_topic: Dict[str, List[KnowledgeCard]] = {}
        self._by_skill: Dict[str, List[KnowledgeCard]] = {}
        self._by_domain: Dict[str, List[KnowledgeCard]] = {}
        self._by_tag: Dict[str, List[KnowledgeCard]] = {}

        self._load_all()
        logger.info(
            "SKI initialized: %d cards from %s",
            len(self._cards), self.data_path
        )

    # ── Loading ──────────────────────────────────────────────────

    def _load_all(self) -> None:
        """Load all JSON files from data_path."""
        if not self.data_path.exists():
            logger.warning("SKI data path not found: %s", self.data_path)
            return

        for json_file in sorted(self.data_path.glob("*.json")):
            if json_file.name.startswith("."):
                continue  # Skip cache files
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                cards_data = data if isinstance(data, list) else data.get("cards", [data])
                for item in cards_data:
                    card = KnowledgeCard.from_dict(item)
                    self._index_card(card)

                logger.debug("Loaded %d cards from %s", len(cards_data), json_file.name)
            except Exception as e:
                logger.error("Failed to load %s: %s", json_file, e)

    def _index_card(self, card: KnowledgeCard) -> None:
        """Add a card to all indexes."""
        self._cards.append(card)

        self._by_topic.setdefault(card.topic.lower(), []).append(card)
        self._by_skill.setdefault(card.skill.lower(), []).append(card)
        self._by_domain.setdefault(card.domain.lower(), []).append(card)
        for tag in card.tags:
            self._by_tag.setdefault(tag.lower(), []).append(card)

    def add_card(self, card: KnowledgeCard) -> None:
        """Add a single card at runtime."""
        self._index_card(card)

    # ── Lookups (O(1)) ───────────────────────────────────────────

    def lookup_by_topic(
        self, topic: str, domain: Optional[str] = None
    ) -> List[KnowledgeCard]:
        """Get cards by exact topic, optionally filtered by domain."""
        cards = self._by_topic.get(topic.lower(), [])
        if domain:
            cards = [c for c in cards if c.domain.lower() == domain.lower()]
        return cards

    def lookup_by_skill(self, skill: str) -> List[KnowledgeCard]:
        """Get cards matching a skill_graph key."""
        return self._by_skill.get(skill.lower(), [])

    def get_formulas(self, topic: str) -> List[Dict[str, str]]:
        """Get all formulas for a topic."""
        formulas = []
        for card in self.lookup_by_topic(topic):
            formulas.extend(card.key_formulas)
        return formulas

    def get_worked_examples(
        self, topic: str, difficulty: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get worked examples for a topic, optionally by difficulty."""
        examples = []
        for card in self.lookup_by_topic(topic):
            for ex in card.worked_examples:
                if difficulty and ex.get("difficulty", card.difficulty) != difficulty:
                    continue
                examples.append(ex)
        return examples

    def get_prerequisites(self, topic: str) -> List[str]:
        """Get prerequisite topics (deduplicated, ordered)."""
        seen = set()
        result = []
        for card in self.lookup_by_topic(topic):
            for prereq in card.prerequisites:
                if prereq not in seen:
                    seen.add(prereq)
                    result.append(prereq)
        return result

    def get_solution_methods(
        self, topic: str, method_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get solution methods for a topic, optionally filtered by method_id."""
        methods = []
        for card in self.lookup_by_topic(topic):
            for m in card.solution_methods:
                if method_id and m.get("method_id") != method_id:
                    continue
                methods.append(m)
        return methods

    def get_problem_templates(
        self, topic: str, difficulty: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get problem templates for a topic, optionally filtered by difficulty."""
        templates = []
        for card in self.lookup_by_topic(topic):
            for t in card.problem_templates:
                if difficulty and t.get("difficulty") != difficulty:
                    continue
                templates.append(t)
        return templates

    def get_notation_context(self, topic: str) -> Dict[str, str]:
        """Merge notation dicts from all cards for a topic."""
        merged: Dict[str, str] = {}
        for card in self.lookup_by_topic(topic):
            merged.update(card.notation)
        return merged

    def get_common_errors(self, topic: str) -> List[Dict[str, str]]:
        """Get common student errors for a topic."""
        errors = []
        for card in self.lookup_by_topic(topic):
            errors.extend(card.common_errors)
        return errors

    # ── Keyword Search (fallback) ────────────────────────────────

    def search(
        self,
        query: str,
        domain: Optional[str] = None,
        limit: int = 5,
    ) -> List[KnowledgeCard]:
        """
        Keyword-based search across topics, definitions, and tags.

        Scoring: topic match (+3), tag match (+2), definition substring (+1).
        """
        query_lower = query.lower()
        query_terms = query_lower.split()

        scored: List[tuple] = []
        candidates = self._cards
        if domain:
            candidates = self._by_domain.get(domain.lower(), [])

        for card in candidates:
            score = 0

            # Topic match
            if query_lower in card.topic.lower():
                score += 3
            elif any(t in card.topic.lower() for t in query_terms):
                score += 2

            # Tag match
            card_tags_lower = [t.lower() for t in card.tags]
            for term in query_terms:
                if term in card_tags_lower:
                    score += 2

            # Skill match
            if query_lower in card.skill.lower():
                score += 2

            # Definition substring
            if query_lower in card.definition.lower():
                score += 1

            if score > 0:
                scored.append((card, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [card for card, _ in scored[:limit]]

    # ── Stats ────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "total_cards": len(self._cards),
            "topics": list(self._by_topic.keys()),
            "domains": list(self._by_domain.keys()),
            "skills": list(self._by_skill.keys()),
        }


# ── Global Instance ──────────────────────────────────────────────

_ski_instance: Optional[StructuredKnowledgeIndex] = None


def get_ski() -> StructuredKnowledgeIndex:
    """Get or create global SKI instance."""
    global _ski_instance
    if _ski_instance is None:
        _ski_instance = StructuredKnowledgeIndex()
    return _ski_instance
