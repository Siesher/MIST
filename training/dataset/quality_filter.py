"""
MITS Dialog Quality Filter

Filters synthetic dialogs based on quality criteria to ensure
high-quality training data for distillation.
"""

import re
import json
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path
import structlog

from training.dataset.dialog_generator import SyntheticDialog, DialogTurn

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
# Quality Metrics
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class QualityMetrics:
    """Quality metrics for a single dialog."""
    has_valid_json: bool = True
    has_valid_moves: bool = True
    has_latex_math: bool = False
    is_russian: bool = True
    no_answer_leak: bool = True
    appropriate_length: bool = True
    has_diversity: bool = True  # Different moves used
    no_repetition: bool = True  # No repeated responses

    @property
    def score(self) -> float:
        """Calculate quality score (0-1)."""
        checks = [
            self.has_valid_json,
            self.has_valid_moves,
            self.has_latex_math,
            self.is_russian,
            self.no_answer_leak,
            self.appropriate_length,
            self.has_diversity,
            self.no_repetition
        ]
        return sum(checks) / len(checks)

    @property
    def passes_minimum(self) -> bool:
        """Check if passes minimum quality threshold."""
        # Must have: valid JSON, valid moves, Russian, no leaks
        return all([
            self.has_valid_json,
            self.has_valid_moves,
            self.is_russian,
            self.no_answer_leak,
            self.appropriate_length
        ])

    def to_dict(self) -> dict:
        return {
            "has_valid_json": self.has_valid_json,
            "has_valid_moves": self.has_valid_moves,
            "has_latex_math": self.has_latex_math,
            "is_russian": self.is_russian,
            "no_answer_leak": self.no_answer_leak,
            "appropriate_length": self.appropriate_length,
            "has_diversity": self.has_diversity,
            "no_repetition": self.no_repetition,
            "score": self.score,
            "passes": self.passes_minimum
        }


# ═══════════════════════════════════════════════════════════════════════════
# Quality Filter
# ═══════════════════════════════════════════════════════════════════════════

class DialogQualityFilter:
    """
    Filters dialogs based on quality criteria.

    Criteria:
    - Valid JSON responses from tutor
    - Valid teaching moves (scaffolding, problematize, etc.)
    - Contains LaTeX math formatting
    - Primarily Russian language
    - No premature answer leaks
    - Appropriate length (not too short/long)
    - Move diversity (uses different teaching strategies)
    - No repetitive responses
    """

    VALID_MOVES = {
        "scaffolding", "problematize", "rectify",
        "encourage", "hint", "tell"
    }

    ANSWER_LEAK_PATTERNS = [
        r"ответ\s*[:=]\s*",
        r"правильный ответ",
        r"решение\s*[:=]",
        r"получается\s*[:=]",
        r"итого\s*[:=]",
    ]

    def __init__(
        self,
        min_turns: int = 10,
        max_turns: int = 30,
        require_latex: bool = True,
        min_russian_ratio: float = 0.3,
        min_move_diversity: int = 2,
        min_speaker_ratio: float = 0.3
    ):
        """
        Initialize filter.

        Args:
            min_turns: Minimum dialog turns
            max_turns: Maximum dialog turns
            require_latex: Require LaTeX in tutor responses
            min_russian_ratio: Minimum ratio of Cyrillic characters
            min_move_diversity: Minimum number of different moves used
        """
        self.min_turns = min_turns
        self.max_turns = max_turns
        self.require_latex = require_latex
        self.min_russian_ratio = min_russian_ratio
        self.min_move_diversity = min_move_diversity
        self.min_speaker_ratio = min_speaker_ratio

        # Compile regex patterns
        self.leak_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.ANSWER_LEAK_PATTERNS
        ]

    def evaluate(self, dialog: SyntheticDialog) -> QualityMetrics:
        """
        Evaluate dialog quality.

        Args:
            dialog: Dialog to evaluate

        Returns:
            QualityMetrics with all checks
        """
        tutor_turns = [t for t in dialog.turns if t.role == "tutor"]
        all_content = " ".join(t.content for t in dialog.turns)

        return QualityMetrics(
            has_valid_json=self._check_json_validity(tutor_turns),
            has_valid_moves=self._check_valid_moves(tutor_turns),
            has_latex_math=self._check_latex(tutor_turns),
            is_russian=self._check_russian(all_content),
            no_answer_leak=self._check_no_leak(dialog),
            appropriate_length=self._check_length(dialog),
            has_diversity=self._check_diversity(tutor_turns),
            no_repetition=self._check_no_repetition(tutor_turns)
        )

    def filter_dialogs(
        self,
        dialogs: List[SyntheticDialog],
        min_score: float = 0.0
    ) -> Tuple[List[SyntheticDialog], List[SyntheticDialog], dict]:
        """
        Filter dialogs by quality.

        Args:
            dialogs: List of dialogs to filter
            min_score: Minimum quality score (0-1)

        Returns:
            Tuple of (passed, failed, statistics)
        """
        passed = []
        failed = []
        scores = []

        for dialog in dialogs:
            metrics = self.evaluate(dialog)
            scores.append(metrics.score)

            if metrics.passes_minimum and metrics.score >= min_score:
                passed.append(dialog)
            else:
                failed.append(dialog)

        stats = {
            "total": len(dialogs),
            "passed": len(passed),
            "failed": len(failed),
            "pass_rate": len(passed) / len(dialogs) if dialogs else 0,
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "max_score": max(scores) if scores else 0
        }

        logger.info(
            "quality_filter_complete",
            passed=len(passed),
            failed=len(failed),
            pass_rate=f"{stats['pass_rate']:.1%}"
        )

        return passed, failed, stats

    def _check_json_validity(self, turns: List[DialogTurn]) -> bool:
        """Check if all tutor responses have valid JSON structure."""
        for turn in turns:
            if not turn.content or not turn.move:
                return False
            # Check that content could be valid message
            if len(turn.content.strip()) < 5:
                return False
        return True

    def _check_valid_moves(self, turns: List[DialogTurn]) -> bool:
        """Check if all moves are valid teaching moves."""
        for turn in turns:
            if turn.move and turn.move.lower() not in self.VALID_MOVES:
                return False
        return True

    def _check_latex(self, turns: List[DialogTurn]) -> bool:
        """Check for LaTeX math formatting."""
        if not self.require_latex:
            return True

        for turn in turns:
            # Check for $ delimited math
            if "$" in turn.content:
                return True
            # Check for \( \) delimited math
            if "\\(" in turn.content or "\\[" in turn.content:
                return True
        return False

    def _check_russian(self, text: str) -> bool:
        """Check if text is primarily Russian."""
        if not text:
            return False

        cyrillic_count = len(re.findall(r'[а-яА-ЯёЁ]', text))
        total_alpha = len(re.findall(r'[a-zA-Zа-яА-ЯёЁ]', text))

        if total_alpha == 0:
            return False

        return (cyrillic_count / total_alpha) >= self.min_russian_ratio

    def _check_no_leak(self, dialog: SyntheticDialog) -> bool:
        """Check that answer wasn't leaked prematurely."""
        answer = dialog.task.get("answer", "").lower().strip()

        # Skip short answers (too common)
        if len(answer) < 3:
            return True

        # Clean answer for comparison
        answer_clean = re.sub(r'[^\w\d]', '', answer)

        for turn in dialog.turns:
            if turn.role == "tutor" and turn.move != "tell":
                content_clean = re.sub(r'[^\w\d]', '', turn.content.lower())

                # Check direct answer presence
                if answer_clean and answer_clean in content_clean:
                    return False

                # Check leak patterns
                for pattern in self.leak_patterns:
                    if pattern.search(turn.content):
                        # Found leak pattern, check if answer follows
                        match = pattern.search(turn.content)
                        if match:
                            after_match = turn.content[match.end():match.end()+50]
                            if answer_clean in re.sub(r'[^\w\d]', '', after_match.lower()):
                                return False

        return True

    def _check_length(self, dialog: SyntheticDialog) -> bool:
        """Check if dialog has appropriate length and balanced speakers."""
        num_turns = len(dialog.turns)
        if not (self.min_turns <= num_turns <= self.max_turns):
            return False

        # Balanced speaker ratio
        student = sum(1 for t in dialog.turns if t.role == "student")
        tutor = sum(1 for t in dialog.turns if t.role == "tutor")
        total = student + tutor
        if total == 0:
            return False
        ratio = min(student, tutor) / total
        return ratio >= self.min_speaker_ratio

    def _check_diversity(self, turns: List[DialogTurn]) -> bool:
        """Check if dialog uses diverse teaching moves."""
        moves = set(t.move for t in turns if t.move)
        return len(moves) >= self.min_move_diversity

    def _check_no_repetition(self, turns: List[DialogTurn]) -> bool:
        """Check for repetitive responses."""
        contents = [t.content.lower()[:100] for t in turns]

        # Check for exact duplicates
        if len(contents) != len(set(contents)):
            return False

        # Check for high similarity (simple check)
        for i, c1 in enumerate(contents):
            for c2 in contents[i+1:]:
                # If first 50 chars are identical, likely repetition
                if c1[:50] == c2[:50]:
                    return False

        return True


# ═══════════════════════════════════════════════════════════════════════════
# Dataset Statistics
# ═══════════════════════════════════════════════════════════════════════════

def analyze_dataset(dialogs: List[SyntheticDialog]) -> dict:
    """
    Analyze dataset statistics.

    Args:
        dialogs: List of dialogs

    Returns:
        Dictionary with statistics
    """
    if not dialogs:
        return {"error": "No dialogs to analyze"}

    # Basic stats
    num_dialogs = len(dialogs)
    total_turns = sum(len(d.turns) for d in dialogs)
    avg_turns = total_turns / num_dialogs

    # Move distribution
    move_counts = {}
    for dialog in dialogs:
        for turn in dialog.turns:
            if turn.role == "tutor" and turn.move:
                move_counts[turn.move] = move_counts.get(turn.move, 0) + 1

    total_moves = sum(move_counts.values())
    move_distribution = {
        k: v / total_moves for k, v in move_counts.items()
    } if total_moves > 0 else {}

    # Topic distribution
    topic_counts = {}
    for dialog in dialogs:
        topic = dialog.task.get("topic", "unknown")
        topic_counts[topic] = topic_counts.get(topic, 0) + 1

    # Difficulty distribution
    difficulty_counts = {}
    for dialog in dialogs:
        diff = dialog.task.get("difficulty", "unknown")
        difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1

    # Persona distribution
    persona_counts = {}
    for dialog in dialogs:
        persona = dialog.student_persona
        persona_counts[persona] = persona_counts.get(persona, 0) + 1

    # Outcome stats
    solved = sum(1 for d in dialogs if d.metadata.get("solved", False))
    told = sum(1 for d in dialogs if d.metadata.get("told_answer", False))

    return {
        "num_dialogs": num_dialogs,
        "total_turns": total_turns,
        "avg_turns_per_dialog": round(avg_turns, 2),
        "move_distribution": move_distribution,
        "topic_distribution": topic_counts,
        "difficulty_distribution": difficulty_counts,
        "persona_distribution": persona_counts,
        "solved_rate": solved / num_dialogs if num_dialogs > 0 else 0,
        "told_answer_rate": told / num_dialogs if num_dialogs > 0 else 0
    }


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json
    from pathlib import Path

    # Example: Load and filter dialogs
    raw_path = Path("data/distillation/raw_dialogs/dialogs.jsonl")

    if raw_path.exists():
        dialogs = []
        with open(raw_path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                dialog = SyntheticDialog(
                    id=data["id"],
                    task=data["task"],
                    student_persona=data["student_persona"],
                    turns=[DialogTurn(**t) for t in data["turns"]],
                    metadata=data.get("metadata", {})
                )
                dialogs.append(dialog)

        # Filter
        filter = DialogQualityFilter()
        passed, failed, stats = filter.filter_dialogs(dialogs)

        print("\nFilter Statistics:")
        print(json.dumps(stats, indent=2))

        print("\nDataset Statistics:")
        print(json.dumps(analyze_dataset(passed), indent=2, ensure_ascii=False))
    else:
        print(f"No dialogs found at {raw_path}")
        print("Run generate_dataset.py first to create dialogs.")
