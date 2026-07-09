"""
Cognitive Load Estimation Module

Estimates student cognitive load based on multiple signals:
- Response time (compared to expected)
- Error patterns (consecutive errors)
- Hint requests
- Task complexity

Based on research:
- Deep Knowledge Tracing and Cognitive Load Estimation (2025)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CognitiveLoadLevel(str, Enum):
    """Cognitive load levels for adaptive difficulty."""
    LOW = "low"           # Can increase difficulty
    OPTIMAL = "optimal"   # Ideal learning zone
    HIGH = "high"         # Signs of struggle
    OVERLOAD = "overload" # Simplify immediately


@dataclass
class CognitiveLoadSignals:
    """Raw signals used for cognitive load estimation."""

    # Response time
    response_time_ms: int = 0
    expected_time_ms: int = 60000  # 1 minute default

    # Error tracking
    consecutive_errors: int = 0
    total_errors_in_session: int = 0

    # Hint usage
    hint_requests: int = 0
    max_hints_for_task: int = 3

    # Task complexity (0-1 scale)
    task_complexity: float = 0.5

    # Time pressure indicators
    time_on_current_task_ms: int = 0
    interaction_count: int = 0

    @property
    def response_time_ratio(self) -> float:
        """Ratio of actual to expected response time."""
        if self.expected_time_ms == 0:
            return 1.0
        return self.response_time_ms / self.expected_time_ms

    @property
    def hint_usage_ratio(self) -> float:
        """Ratio of hints used to max available."""
        if self.max_hints_for_task == 0:
            return 0.0
        return self.hint_requests / self.max_hints_for_task


@dataclass
class CognitiveLoad:
    """Cognitive load estimation result."""

    level: CognitiveLoadLevel = CognitiveLoadLevel.OPTIMAL
    score: float = 0.5  # 0.0 (low) to 1.0 (overload)
    confidence: float = 0.5

    # Contributing factors
    time_factor: float = 0.0
    error_factor: float = 0.0
    hint_factor: float = 0.0
    complexity_factor: float = 0.0

    # Recommendations
    should_simplify: bool = False
    should_offer_break: bool = False

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "score": self.score,
            "confidence": self.confidence,
            "should_simplify": self.should_simplify,
            "should_offer_break": self.should_offer_break,
        }


class CognitiveLoadEstimator:
    """
    Estimates cognitive load from multiple signals.

    Uses weighted combination of:
    - Response time ratio (40%)
    - Error patterns (30%)
    - Hint requests (20%)
    - Task complexity (10%)
    """

    # Default weights from config
    DEFAULT_WEIGHTS = {
        "response_time": 0.4,
        "error_pattern": 0.3,
        "hint_request": 0.2,
        "task_complexity": 0.1,
    }

    # Thresholds for level determination
    THRESHOLDS = {
        "low": 0.25,
        "optimal": 0.50,
        "high": 0.75,
        # >= 0.75 is overload
    }

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        overload_threshold: float = 0.75,
        consecutive_error_trigger: int = 3
    ):
        """
        Initialize estimator.

        Args:
            weights: Custom weights for factors
            overload_threshold: Score above which overload is detected
            consecutive_error_trigger: Errors that trigger high load
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.overload_threshold = overload_threshold
        self.consecutive_error_trigger = consecutive_error_trigger

        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v / total for k, v in self.weights.items()}

        # History for tracking trends
        self.load_history: List[CognitiveLoad] = []

    def estimate(self, signals: CognitiveLoadSignals) -> CognitiveLoad:
        """
        Estimate cognitive load from signals.

        Args:
            signals: Raw signals for estimation

        Returns:
            CognitiveLoad estimation result
        """
        # Calculate individual factors (0-1 scale)

        # 1. Response time factor
        time_ratio = signals.response_time_ratio
        if time_ratio <= 0.5:
            time_factor = 0.0  # Very quick = low load
        elif time_ratio <= 1.0:
            time_factor = 0.25  # Normal
        elif time_ratio <= 2.0:
            time_factor = 0.6  # Taking longer
        else:
            time_factor = 1.0  # Much longer than expected

        # 2. Error pattern factor
        if signals.consecutive_errors == 0:
            error_factor = 0.0
        elif signals.consecutive_errors == 1:
            error_factor = 0.3
        elif signals.consecutive_errors == 2:
            error_factor = 0.6
        else:
            error_factor = 1.0  # 3+ consecutive errors

        # 3. Hint request factor
        hint_factor = min(signals.hint_usage_ratio, 1.0)

        # 4. Task complexity factor
        complexity_factor = signals.task_complexity

        # Combine factors
        score = (
            self.weights["response_time"] * time_factor +
            self.weights["error_pattern"] * error_factor +
            self.weights["hint_request"] * hint_factor +
            self.weights["task_complexity"] * complexity_factor
        )

        # Determine level
        if score < self.THRESHOLDS["low"]:
            level = CognitiveLoadLevel.LOW
        elif score < self.THRESHOLDS["optimal"]:
            level = CognitiveLoadLevel.OPTIMAL
        elif score < self.THRESHOLDS["high"]:
            level = CognitiveLoadLevel.HIGH
        else:
            level = CognitiveLoadLevel.OVERLOAD

        # Determine confidence based on signal availability
        confidence = self._calculate_confidence(signals)

        # Create result
        result = CognitiveLoad(
            level=level,
            score=score,
            confidence=confidence,
            time_factor=time_factor,
            error_factor=error_factor,
            hint_factor=hint_factor,
            complexity_factor=complexity_factor,
            should_simplify=level in [CognitiveLoadLevel.HIGH, CognitiveLoadLevel.OVERLOAD],
            should_offer_break=self._should_offer_break(signals, level),
        )

        # Track history
        self.load_history.append(result)
        if len(self.load_history) > 20:
            self.load_history = self.load_history[-20:]

        logger.debug(
            f"Cognitive load estimated: {level.value} (score={score:.2f}, confidence={confidence:.2f})"
        )

        return result

    def _calculate_confidence(self, signals: CognitiveLoadSignals) -> float:
        """Calculate confidence in the estimation."""
        confidence = 0.3  # Base confidence

        # More interactions = higher confidence
        if signals.interaction_count > 1:
            confidence += 0.2
        if signals.interaction_count > 5:
            confidence += 0.2

        # Having response time data increases confidence
        if signals.response_time_ms > 0:
            confidence += 0.15

        # Having error data increases confidence
        if signals.total_errors_in_session > 0 or signals.consecutive_errors > 0:
            confidence += 0.15

        return min(confidence, 1.0)

    def _should_offer_break(
        self,
        signals: CognitiveLoadSignals,
        level: CognitiveLoadLevel
    ) -> bool:
        """Determine if a break should be offered."""
        # Offer break if:
        # 1. Overload detected
        if level == CognitiveLoadLevel.OVERLOAD:
            return True

        # 2. Long time on task (> 10 minutes)
        if signals.time_on_current_task_ms > 600000:
            return True

        # 3. Many consecutive errors
        if signals.consecutive_errors >= self.consecutive_error_trigger:
            return True

        # 4. Trend shows increasing load
        if len(self.load_history) >= 3:
            recent_scores = [h.score for h in self.load_history[-3:]]
            if all(recent_scores[i] < recent_scores[i+1] for i in range(len(recent_scores)-1)):
                if recent_scores[-1] > 0.6:
                    return True

        return False

    def get_trend(self) -> str:
        """Get cognitive load trend from history."""
        if len(self.load_history) < 3:
            return "insufficient_data"

        recent = [h.score for h in self.load_history[-5:]]
        avg_first_half = sum(recent[:len(recent)//2]) / (len(recent)//2)
        avg_second_half = sum(recent[len(recent)//2:]) / (len(recent) - len(recent)//2)

        diff = avg_second_half - avg_first_half

        if diff > 0.1:
            return "increasing"
        elif diff < -0.1:
            return "decreasing"
        else:
            return "stable"

    def reset(self):
        """Reset history for new session."""
        self.load_history = []

    def get_average_load(self) -> float:
        """Get average cognitive load from history."""
        if not self.load_history:
            return 0.5
        return sum(h.score for h in self.load_history) / len(self.load_history)


def estimate_task_complexity(
    task_difficulty: str,
    num_steps: int = 1,
    requires_multiple_concepts: bool = False
) -> float:
    """
    Estimate task complexity on 0-1 scale.

    Args:
        task_difficulty: "easy", "medium", "hard", "olympiad"
        num_steps: Number of solution steps
        requires_multiple_concepts: Whether task combines multiple concepts

    Returns:
        Complexity score 0.0 to 1.0
    """
    # Base complexity from difficulty
    difficulty_scores = {
        "easy": 0.2,
        "medium": 0.4,
        "hard": 0.7,
        "olympiad": 0.9,
    }
    base = difficulty_scores.get(task_difficulty.lower(), 0.5)

    # Adjust for steps
    step_factor = min(num_steps / 10, 0.3)  # Max 0.3 from steps

    # Adjust for concept combination
    concept_factor = 0.1 if requires_multiple_concepts else 0.0

    return min(base + step_factor + concept_factor, 1.0)


# Convenience function
def quick_estimate(
    response_time_ms: int,
    consecutive_errors: int = 0,
    hint_requests: int = 0,
    task_difficulty: str = "medium"
) -> CognitiveLoad:
    """
    Quick cognitive load estimation.

    Args:
        response_time_ms: Response time in milliseconds
        consecutive_errors: Number of consecutive errors
        hint_requests: Number of hints requested
        task_difficulty: Task difficulty level

    Returns:
        CognitiveLoad estimation
    """
    estimator = CognitiveLoadEstimator()

    signals = CognitiveLoadSignals(
        response_time_ms=response_time_ms,
        consecutive_errors=consecutive_errors,
        hint_requests=hint_requests,
        task_complexity=estimate_task_complexity(task_difficulty),
    )

    return estimator.estimate(signals)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    estimator = CognitiveLoadEstimator()

    # Scenario 1: Quick correct answer
    signals1 = CognitiveLoadSignals(
        response_time_ms=30000,  # 30 seconds
        consecutive_errors=0,
        hint_requests=0,
        task_complexity=0.3,
    )
    result1 = estimator.estimate(signals1)
    print(f"Scenario 1 (quick correct): {result1.level.value}, score={result1.score:.2f}")

    # Scenario 2: Struggling student
    signals2 = CognitiveLoadSignals(
        response_time_ms=180000,  # 3 minutes
        consecutive_errors=3,
        hint_requests=2,
        max_hints_for_task=3,
        task_complexity=0.6,
    )
    result2 = estimator.estimate(signals2)
    print(f"Scenario 2 (struggling): {result2.level.value}, score={result2.score:.2f}")
    print(f"  Should simplify: {result2.should_simplify}")
    print(f"  Should offer break: {result2.should_offer_break}")

    # Scenario 3: Moderate challenge
    signals3 = CognitiveLoadSignals(
        response_time_ms=90000,  # 1.5 minutes
        consecutive_errors=1,
        hint_requests=1,
        max_hints_for_task=3,
        task_complexity=0.5,
    )
    result3 = estimator.estimate(signals3)
    print(f"Scenario 3 (moderate): {result3.level.value}, score={result3.score:.2f}")

    # Check trend
    print(f"\nLoad trend: {estimator.get_trend()}")
