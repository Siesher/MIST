"""
Few-Shot Example Bank for MITS.

Feature 010: Few-shot prompting support for quality improvement.

Loads and retrieves few-shot examples for:
- Derivatives
- Integrals
- Limits
- Other math topics

Uses semantic search for example selection.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Load configuration
try:
    from src.config import settings
    FEW_SHOT_PATH = getattr(settings, 'FEW_SHOT_PATH', Path('./data/few_shot'))
    FEW_SHOT_COUNT = getattr(settings, 'FEW_SHOT_COUNT', 2)
    FEW_SHOT_MIN_SIMILARITY = getattr(settings, 'FEW_SHOT_MIN_SIMILARITY', 0.5)
except ImportError:
    FEW_SHOT_PATH = Path('./data/few_shot')
    FEW_SHOT_COUNT = 2
    FEW_SHOT_MIN_SIMILARITY = 0.5


@dataclass
class FewShotExample:
    """A single few-shot example."""
    id: str
    topic: str
    difficulty: str  # easy, medium, hard
    problem: str
    student_input: str
    tutor_response: str
    tags: List[str] = field(default_factory=list)
    embedding: Optional[Any] = None
    skill: str = ""               # matches skill_graph keys, e.g. "calculus.derivatives"
    student_level: str = ""       # "beginner", "intermediate", "advanced"

    def to_prompt_format(self, include_tags: bool = False) -> str:
        """Format example for prompt inclusion."""
        parts = [
            f"**Задача**: {self.problem}",
            f"**Студент**: {self.student_input}",
            f"**Репетитор**: {self.tutor_response}",
        ]
        if include_tags and self.tags:
            parts.append(f"**Теги**: {', '.join(self.tags)}")
        return "\n".join(parts)


class FewShotBank:
    """
    Bank of few-shot examples for tutoring.

    Features:
    - Loads examples from JSON files
    - Semantic retrieval for best matches
    - Topic and difficulty filtering
    - Caching of embeddings
    """

    def __init__(
        self,
        data_path: Optional[Path] = None,
        embedding_processor: Optional[Any] = None
    ):
        self.data_path = data_path or FEW_SHOT_PATH
        self.embedding_processor = embedding_processor

        # Example storage
        self._examples: Dict[str, List[FewShotExample]] = {}  # topic -> examples
        self._all_examples: List[FewShotExample] = []

        # Load examples
        self._load_examples()

        logger.info(
            f"FewShotBank initialized: {len(self._all_examples)} examples "
            f"across {len(self._examples)} topics"
        )

    def _load_examples(self) -> None:
        """Load all examples from JSON files."""
        if not self.data_path.exists():
            logger.warning(f"Few-shot data path not found: {self.data_path}")
            return

        for json_file in self.data_path.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                topic = json_file.stem  # filename without extension

                examples = []
                for i, item in enumerate(data.get("examples", [])):
                    example = FewShotExample(
                        id=f"{topic}_{i}",
                        topic=item.get("topic", topic),
                        difficulty=item.get("difficulty", "medium"),
                        problem=item.get("problem", ""),
                        student_input=item.get("student_input", ""),
                        tutor_response=item.get("tutor_response", ""),
                        tags=item.get("tags", []),
                        skill=item.get("skill", ""),
                        student_level=item.get("student_level", ""),
                    )
                    examples.append(example)
                    self._all_examples.append(example)

                self._examples[topic] = examples
                logger.debug(f"Loaded {len(examples)} examples from {json_file.name}")

            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")

    def _compute_embeddings(self) -> None:
        """Compute embeddings for all examples."""
        if self.embedding_processor is None:
            try:
                from src.inference.batch_processor import get_embedding_processor
                self.embedding_processor = get_embedding_processor()
            except ImportError:
                logger.warning("No embedding processor available")
                return

        # Batch compute embeddings
        texts = [
            f"{ex.problem} {ex.student_input}"
            for ex in self._all_examples
        ]

        embeddings = self.embedding_processor.encode_batch(texts)

        for example, embedding in zip(self._all_examples, embeddings):
            example.embedding = embedding

        logger.info(f"Computed embeddings for {len(self._all_examples)} examples")

    def get_examples_by_topic(
        self,
        topic: str,
        difficulty: Optional[str] = None,
        limit: int = None
    ) -> List[FewShotExample]:
        """
        Get examples by topic.

        Args:
            topic: Math topic (e.g., "derivatives", "integrals")
            difficulty: Filter by difficulty (optional)
            limit: Maximum examples to return

        Returns:
            List of matching examples
        """
        limit = limit or FEW_SHOT_COUNT

        # Try exact topic match first
        examples = self._examples.get(topic, [])

        # Try partial match if not found
        if not examples:
            for t in self._examples:
                if topic.lower() in t.lower() or t.lower() in topic.lower():
                    examples = self._examples[t]
                    break

        # Filter by difficulty
        if difficulty:
            examples = [e for e in examples if e.difficulty == difficulty]

        return examples[:limit]

    def retrieve_structured(
        self,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        skill: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 3,
    ) -> List[FewShotExample]:
        """
        Structured scoring retrieval (no embeddings needed).

        Scoring: topic match (+3), skill match (+2), difficulty match (+1),
        each tag match (+1).

        Args:
            topic: Topic to match (e.g., "derivatives")
            difficulty: Difficulty filter
            skill: Skill graph key (e.g., "calculus.derivatives")
            tags: Tags to boost matching
            limit: Maximum examples to return

        Returns:
            Sorted list of best-matching examples
        """
        scored: List[tuple] = []
        tags_lower = [t.lower() for t in (tags or [])]

        for example in self._all_examples:
            score = 0

            # Topic match (+3)
            if topic:
                topic_lower = topic.lower()
                if topic_lower == example.topic.lower():
                    score += 3
                elif topic_lower in example.topic.lower() or example.topic.lower() in topic_lower:
                    score += 2

            # Skill match (+2)
            if skill and example.skill:
                skill_lower = skill.lower()
                if skill_lower == example.skill.lower():
                    score += 2
                elif skill_lower in example.skill.lower():
                    score += 1

            # Difficulty match (+1)
            if difficulty and example.difficulty == difficulty:
                score += 1

            # Tag matches (+1 each)
            if tags_lower:
                example_tags_lower = [t.lower() for t in example.tags]
                for tag in tags_lower:
                    if tag in example_tags_lower:
                        score += 1

            if score > 0:
                scored.append((example, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [ex for ex, _ in scored[:limit]]

    def retrieve_similar(
        self,
        query: str,
        topic: Optional[str] = None,
        limit: int = None,
        min_similarity: float = None
    ) -> List[FewShotExample]:
        """
        Retrieve semantically similar examples.

        Args:
            query: Query text (problem or student input)
            topic: Filter by topic (optional)
            limit: Maximum examples to return
            min_similarity: Minimum similarity threshold

        Returns:
            List of similar examples sorted by relevance
        """
        limit = limit or FEW_SHOT_COUNT
        min_similarity = min_similarity or FEW_SHOT_MIN_SIMILARITY

        # Ensure embeddings are computed
        if self._all_examples and self._all_examples[0].embedding is None:
            self._compute_embeddings()

        if self.embedding_processor is None:
            # Fallback to topic-based retrieval
            return self.get_examples_by_topic(topic or "general", limit=limit)

        # Compute query embedding
        query_embedding = self.embedding_processor.encode(query)
        if query_embedding is None:
            return self.get_examples_by_topic(topic or "general", limit=limit)

        # Filter by topic if specified
        candidates = self._all_examples
        if topic:
            candidates = [e for e in candidates if topic.lower() in e.topic.lower()]

        # Compute similarities
        scored = []
        for example in candidates:
            if example.embedding is not None:
                try:
                    import numpy as np
                    similarity = np.dot(query_embedding, example.embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(example.embedding)
                    )
                    if similarity >= min_similarity:
                        scored.append((example, similarity))
                except Exception:
                    pass

        # Sort by similarity
        scored.sort(key=lambda x: x[1], reverse=True)

        return [ex for ex, _ in scored[:limit]]

    def format_for_prompt(
        self,
        examples: List[FewShotExample],
        header: str = "Примеры диалога репетитора:"
    ) -> str:
        """
        Format examples for inclusion in prompt.

        Args:
            examples: List of examples to format
            header: Header text

        Returns:
            Formatted string for prompt
        """
        if not examples:
            return ""

        parts = [f"\n### {header}\n"]

        for i, example in enumerate(examples, 1):
            parts.append(f"**Пример {i}:**")
            parts.append(example.to_prompt_format())
            parts.append("")

        parts.append("---\n")

        return "\n".join(parts)

    def add_example(self, example: FewShotExample) -> None:
        """Add a new example to the bank."""
        self._all_examples.append(example)

        topic = example.topic
        if topic not in self._examples:
            self._examples[topic] = []
        self._examples[topic].append(example)

        # Clear embedding to recompute
        example.embedding = None

    def save_examples(self, topic: str) -> Path:
        """
        Save examples for a topic to JSON.

        Args:
            topic: Topic to save

        Returns:
            Path to saved file
        """
        if topic not in self._examples:
            raise ValueError(f"Unknown topic: {topic}")

        output_file = self.data_path / f"{topic}.json"

        data = {
            "topic": topic,
            "examples": [
                {
                    "topic": ex.topic,
                    "difficulty": ex.difficulty,
                    "problem": ex.problem,
                    "student_input": ex.student_input,
                    "tutor_response": ex.tutor_response,
                    "tags": ex.tags,
                    "skill": ex.skill,
                    "student_level": ex.student_level,
                }
                for ex in self._examples[topic]
            ]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self._examples[topic])} examples to {output_file}")
        return output_file

    @property
    def stats(self) -> Dict[str, Any]:
        """Get statistics about the bank."""
        topic_counts = {t: len(examples) for t, examples in self._examples.items()}
        difficulty_counts = {}
        for ex in self._all_examples:
            difficulty_counts[ex.difficulty] = difficulty_counts.get(ex.difficulty, 0) + 1

        return {
            "total_examples": len(self._all_examples),
            "topics": list(self._examples.keys()),
            "topic_counts": topic_counts,
            "difficulty_counts": difficulty_counts,
            "embeddings_computed": any(ex.embedding is not None for ex in self._all_examples),
        }


# Global instance
_few_shot_bank: Optional[FewShotBank] = None


def get_few_shot_bank() -> FewShotBank:
    """Get or create global few-shot bank."""
    global _few_shot_bank
    if _few_shot_bank is None:
        _few_shot_bank = FewShotBank()
    return _few_shot_bank


def get_few_shot_examples(
    query: str,
    topic: Optional[str] = None,
    count: int = None
) -> str:
    """
    Convenience function to get formatted few-shot examples.

    Args:
        query: Query for semantic retrieval
        topic: Topic filter
        count: Number of examples

    Returns:
        Formatted prompt string
    """
    bank = get_few_shot_bank()
    examples = bank.retrieve_similar(query, topic=topic, limit=count)
    return bank.format_for_prompt(examples)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Few-Shot Bank Demo ===\n")

    bank = FewShotBank()
    print(f"Stats: {bank.stats}")

    # Try to get examples
    examples = bank.get_examples_by_topic("derivatives", limit=2)
    if examples:
        print(f"\nDerivatives examples: {len(examples)}")
        for ex in examples:
            print(f"  - {ex.problem[:50]}...")
    else:
        print("\nNo derivatives examples found.")
        print("Create data/few_shot/derivatives.json with example data.")
