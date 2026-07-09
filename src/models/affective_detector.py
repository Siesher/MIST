"""
Affective State Detection Module

Detects student emotional state from text patterns:
- Frustration: Short messages, typos, "!!!", consecutive errors
- Bored: Fast correct answers, minimal engagement
- Confused: "?", long pauses, "не понимаю"
- Engaged: Questions, detailed answers, follow-ups
- Neutral: Normal patterns

Based on research in educational affect detection.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.config import get_settings
from src.data.schemas import (
    AffectiveSignals,
    AffectiveState,
    AffectiveStateType,
    ConversationTurn,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# RUSSIAN FRUSTRATION/CONFUSION INDICATORS
# ═══════════════════════════════════════════════════════════════════════════

FRUSTRATION_PHRASES_RU = [
    "не понимаю", "не могу", "опять", "снова", "уже", "надоело",
    "сложно", "трудно", "не получается", "ничего не понятно",
    "запутался", "запуталась", "устал", "устала", "бесит",
    "невозможно", "не знаю", "что делать",
]

CONFUSION_PHRASES_RU = [
    "не понимаю", "что это", "как это", "почему", "зачем",
    "объясни", "объясните", "не ясно", "неясно", "непонятно",
    "а что", "а как", "а почему", "хм", "эм",
]

ENGAGEMENT_PHRASES_RU = [
    "интересно", "а если", "а можно", "а что если",
    "понял", "поняла", "ага", "ясно", "логично",
    "круто", "классно", "получилось", "а ещё",
]


# ═══════════════════════════════════════════════════════════════════════════
# TYPO DETECTION (Russian language aware)
# ═══════════════════════════════════════════════════════════════════════════

# Common Russian keyboard typos (adjacent keys)
RUSSIAN_ADJACENT_KEYS = {
    'й': 'цу', 'ц': 'йук', 'у': 'цке', 'к': 'уен', 'е': 'кнг',
    'н': 'егш', 'г': 'ншщ', 'ш': 'гщз', 'щ': 'шзх', 'з': 'щхъ',
    'ф': 'ыв', 'ы': 'фва', 'в': 'ыап', 'а': 'впр', 'п': 'аро',
    'р': 'пол', 'о': 'рлд', 'л': 'одж', 'д': 'лжэ', 'ж': 'дэ',
    'я': 'чс', 'ч': 'ясм', 'с': 'чми', 'м': 'сит', 'и': 'мтт',
    'т': 'иьб', 'ь': 'тбю', 'б': 'ью', 'ю': 'б',
}


@dataclass
class TypoAnalysisResult:
    """Result of typo analysis."""
    typo_count: int = 0
    word_count: int = 0
    typo_density: float = 0.0
    repeated_chars: int = 0
    has_keyboard_smash: bool = False


class AffectiveDetector:
    """
    Detects student affective state from text signals.

    Uses a hybrid approach:
    - Rule-based: Punctuation, message length, response time
    - Semantic: Phrase matching for Russian language
    - Optional LLM: For edge cases (if llm_client provided)
    """

    def __init__(
        self,
        llm_client: Optional[object] = None,
        confidence_threshold: float = 0.6,
        window_size: int = 5
    ):
        """
        Initialize detector.

        Args:
            llm_client: Optional LLM for semantic analysis
            confidence_threshold: Minimum confidence to report state
            window_size: Number of recent messages to analyze
        """
        settings = get_settings()
        self.llm_client = llm_client
        self.confidence_threshold = confidence_threshold or settings.AFFECTIVE_CONFIDENCE_THRESHOLD
        self.window_size = window_size or settings.AFFECTIVE_WINDOW_SIZE

        # State history
        self.state_history: List[AffectiveState] = []
        self.message_history: List[Tuple[str, int, datetime]] = []  # (message, response_time_ms, timestamp)

        # Consecutive counters
        self.consecutive_short_messages = 0
        self.consecutive_errors = 0

        logger.debug(f"AffectiveDetector initialized with threshold={confidence_threshold}, window={window_size}")

    def analyze_message(
        self,
        message: str,
        response_time_ms: int,
        context: List[ConversationTurn],
        was_correct: Optional[bool] = None
    ) -> AffectiveState:
        """
        Analyze a single message for affective signals.

        Args:
            message: Student's message text
            response_time_ms: Time taken to respond in milliseconds
            context: Recent conversation history
            was_correct: Whether the answer was correct (if applicable)

        Returns:
            Detected AffectiveState with recommendations
        """
        # Update error tracking
        if was_correct is not None:
            if not was_correct:
                self.consecutive_errors += 1
            else:
                self.consecutive_errors = 0

        # Extract signals
        signals = self._extract_text_signals(message, response_time_ms, context)

        # Classify state
        state_type, confidence = self._classify_state(signals)

        # Get previous state
        previous_state = self.state_history[-1].state_type if self.state_history else None

        # Calculate state duration
        state_duration = 0
        if previous_state == state_type and self.state_history:
            state_duration = int((datetime.now() - self.state_history[-1].detected_at).total_seconds())

        # Create state object
        state = AffectiveState(
            state_type=state_type,
            confidence=confidence,
            signals=signals,
            should_simplify=state_type == AffectiveStateType.FRUSTRATED and confidence > 0.6,
            should_encourage=state_type in [AffectiveStateType.FRUSTRATED, AffectiveStateType.CONFUSED],
            should_challenge=state_type == AffectiveStateType.BORED and confidence > 0.6,
            should_offer_break=(
                state_type == AffectiveStateType.FRUSTRATED and
                confidence > 0.7 and
                signals.consecutive_errors >= 3
            ),
            previous_state=previous_state,
            state_duration_seconds=state_duration,
        )

        # Update history
        self.state_history.append(state)
        if len(self.state_history) > self.window_size * 2:
            self.state_history = self.state_history[-self.window_size * 2:]

        self.message_history.append((message, response_time_ms, datetime.now()))
        if len(self.message_history) > self.window_size * 2:
            self.message_history = self.message_history[-self.window_size * 2:]

        logger.debug(f"Affective state detected: {state_type.value} (confidence={confidence:.2f})")

        return state

    def _extract_text_signals(
        self,
        message: str,
        response_time_ms: int,
        context: List[ConversationTurn]
    ) -> AffectiveSignals:
        """Extract raw signals from message."""
        msg_lower = message.lower().strip()

        # Basic text signals
        message_length = len(message)
        punctuation_ratio = self._calculate_punctuation_ratio(message)
        typo_result = self._calculate_typo_density(message)

        # Punctuation counts
        question_marks = message.count('?')
        exclamation_marks = message.count('!')
        ellipsis_count = message.count('...')

        # Track short messages
        if message_length < 20:
            self.consecutive_short_messages += 1
        else:
            self.consecutive_short_messages = 0

        # Semantic signals
        expressed_confusion = any(phrase in msg_lower for phrase in CONFUSION_PHRASES_RU)
        expressed_frustration = any(phrase in msg_lower for phrase in FRUSTRATION_PHRASES_RU)
        expressed_interest = any(phrase in msg_lower for phrase in ENGAGEMENT_PHRASES_RU)

        return AffectiveSignals(
            message_length=message_length,
            response_time_ms=response_time_ms,
            punctuation_ratio=punctuation_ratio,
            typo_density=typo_result.typo_density,
            question_marks=question_marks,
            exclamation_marks=exclamation_marks,
            ellipsis_count=ellipsis_count,
            consecutive_short_messages=self.consecutive_short_messages,
            consecutive_errors=self.consecutive_errors,
            expressed_confusion=expressed_confusion,
            expressed_frustration=expressed_frustration,
            expressed_interest=expressed_interest,
        )

    def _calculate_punctuation_ratio(self, message: str) -> float:
        """Calculate ratio of punctuation to total characters."""
        if not message:
            return 0.0
        punctuation_count = sum(1 for c in message if c in '!?.,;:()[]{}...')
        return punctuation_count / len(message)

    def _calculate_typo_density(self, message: str) -> TypoAnalysisResult:
        """
        Estimate typo density in Russian text.

        Uses heuristics:
        - Repeated characters (e.g., "ааааа")
        - Very short words that don't match common patterns
        - Keyboard smash detection
        """
        result = TypoAnalysisResult()

        # Split into words
        words = re.findall(r'[а-яёa-z]+', message.lower())
        result.word_count = len(words)

        if result.word_count == 0:
            return result

        typo_indicators = 0

        for word in words:
            # Check for repeated characters (3+ same char in a row)
            if re.search(r'(.)\1{2,}', word):
                result.repeated_chars += 1
                typo_indicators += 1

            # Check for unlikely consonant clusters (Russian)
            if re.search(r'[бвгджзйклмнпрстфхцчшщ]{4,}', word):
                typo_indicators += 1

            # Very short "words" that are just letters
            if len(word) == 1 and word not in ['а', 'в', 'и', 'к', 'о', 'с', 'у', 'я', 'a', 'i']:
                typo_indicators += 0.5

        # Keyboard smash detection
        if re.search(r'[фывапролджэ]{5,}|[йцукенгшщз]{5,}', message.lower()):
            result.has_keyboard_smash = True
            typo_indicators += 2

        result.typo_count = int(typo_indicators)
        result.typo_density = typo_indicators / max(result.word_count, 1)

        return result

    def _classify_state(
        self,
        signals: AffectiveSignals
    ) -> Tuple[AffectiveStateType, float]:
        """
        Classify affective state based on weighted signals.

        Returns:
            (state_type, confidence)
        """
        # Score each state
        scores: Dict[AffectiveStateType, float] = {
            AffectiveStateType.FRUSTRATED: 0.0,
            AffectiveStateType.BORED: 0.0,
            AffectiveStateType.CONFUSED: 0.0,
            AffectiveStateType.ENGAGED: 0.0,
            AffectiveStateType.NEUTRAL: 0.3,  # Base score for neutral
        }

        # ─────────────────────────────────────────────────────────────
        # FRUSTRATION indicators
        # ─────────────────────────────────────────────────────────────
        if signals.expressed_frustration:
            scores[AffectiveStateType.FRUSTRATED] += 0.4

        if signals.exclamation_marks >= 2:
            scores[AffectiveStateType.FRUSTRATED] += 0.2

        if signals.consecutive_errors >= 2:
            scores[AffectiveStateType.FRUSTRATED] += 0.15 * signals.consecutive_errors

        if signals.typo_density > 0.2:
            scores[AffectiveStateType.FRUSTRATED] += 0.15

        if signals.consecutive_short_messages >= 3:
            scores[AffectiveStateType.FRUSTRATED] += 0.15

        # ─────────────────────────────────────────────────────────────
        # BORED indicators
        # ─────────────────────────────────────────────────────────────
        # Fast response + short message + no questions = possibly bored
        if signals.response_time_ms < 5000 and signals.message_length < 30:
            if signals.question_marks == 0 and not signals.expressed_interest:
                scores[AffectiveStateType.BORED] += 0.25

        # Multiple ellipses can indicate boredom
        if signals.ellipsis_count >= 2:
            scores[AffectiveStateType.BORED] += 0.15

        # ─────────────────────────────────────────────────────────────
        # CONFUSED indicators
        # ─────────────────────────────────────────────────────────────
        if signals.expressed_confusion:
            scores[AffectiveStateType.CONFUSED] += 0.4

        if signals.question_marks >= 2:
            scores[AffectiveStateType.CONFUSED] += 0.2

        # Long response time can indicate confusion
        if signals.response_time_ms > 60000:  # > 1 minute
            scores[AffectiveStateType.CONFUSED] += 0.15

        # ─────────────────────────────────────────────────────────────
        # ENGAGED indicators
        # ─────────────────────────────────────────────────────────────
        if signals.expressed_interest:
            scores[AffectiveStateType.ENGAGED] += 0.4

        # Longer, detailed messages indicate engagement
        if signals.message_length > 100:
            scores[AffectiveStateType.ENGAGED] += 0.2

        # Single question mark (asking clarifying question)
        if signals.question_marks == 1 and not signals.expressed_confusion:
            scores[AffectiveStateType.ENGAGED] += 0.15

        # ─────────────────────────────────────────────────────────────
        # Determine winner
        # ─────────────────────────────────────────────────────────────
        # Normalize scores
        total_score = sum(scores.values())
        if total_score > 0:
            for state in scores:
                scores[state] /= total_score

        # Find highest scoring state
        best_state = max(scores, key=scores.get)
        confidence = scores[best_state]

        # If confidence is too low, default to neutral
        if confidence < self.confidence_threshold:
            return AffectiveStateType.NEUTRAL, 0.5

        return best_state, min(confidence * 1.2, 1.0)  # Slight boost to winner

    def _semantic_analysis(
        self,
        message: str,
        signals: AffectiveSignals
    ) -> Optional[Tuple[AffectiveStateType, float]]:
        """
        Use LLM for semantic analysis (edge cases).

        Called when rule-based classification is uncertain.
        """
        if self.llm_client is None:
            return None

        # This would use the LLM to classify the message
        # For now, return None to use rule-based classification
        logger.debug("LLM semantic analysis not implemented, using rule-based only")
        return None

    def get_adaptation_prompt(self, state: AffectiveState) -> str:
        """
        Get prompt modifier for tutor based on affective state.

        Returns:
            String to append to tutor system prompt
        """
        prompts = {
            AffectiveStateType.FRUSTRATED: (
                "Студент испытывает фрустрацию. "
                "Используй более простой язык, разбивай объяснения на маленькие шаги, "
                "и обязательно похвали за любой прогресс. "
                "Избегай сложных терминов. Будь терпеливым и поддерживающим."
            ),
            AffectiveStateType.BORED: (
                "Студент демонстрирует признаки скуки. "
                "Предложи более сложную задачу или интересный поворот темы. "
                "Добавь элемент соревнования или челленджа."
            ),
            AffectiveStateType.CONFUSED: (
                "Студент испытывает замешательство. "
                "Начни с базовых понятий, используй конкретные примеры, "
                "и задавай наводящие вопросы, чтобы понять источник непонимания."
            ),
            AffectiveStateType.ENGAGED: (
                "Студент вовлечён и заинтересован. "
                "Можно углубиться в тему, добавить дополнительные детали "
                "и связи с другими областями."
            ),
            AffectiveStateType.NEUTRAL: "",
        }

        base_prompt = prompts.get(state.state_type, "")

        if state.should_offer_break:
            base_prompt += " Предложи студенту сделать короткий перерыв."

        return base_prompt

    def reset_session(self) -> None:
        """Reset state tracking for new session."""
        self.state_history.clear()
        self.message_history.clear()
        self.consecutive_short_messages = 0
        self.consecutive_errors = 0
        logger.debug("AffectiveDetector session reset")

    def get_state_history(self) -> List[AffectiveState]:
        """Get history of detected states."""
        return self.state_history.copy()

    def get_dominant_state(self) -> AffectiveStateType:
        """Get the most common state in recent history."""
        if not self.state_history:
            return AffectiveStateType.NEUTRAL

        recent = self.state_history[-self.window_size:]
        state_counts: Dict[AffectiveStateType, int] = {}

        for state in recent:
            state_counts[state.state_type] = state_counts.get(state.state_type, 0) + 1

        return max(state_counts, key=state_counts.get)

    def get_frustration_level(self) -> float:
        """Get current frustration level (0-1)."""
        if not self.state_history:
            return 0.0

        recent = self.state_history[-self.window_size:]
        frustration_count = sum(
            1 for s in recent
            if s.state_type == AffectiveStateType.FRUSTRATED
        )

        return frustration_count / len(recent)


# ═══════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def quick_analyze(message: str, response_time_ms: int = 0) -> AffectiveState:
    """
    Quick analysis of a single message.

    Args:
        message: Message text
        response_time_ms: Response time

    Returns:
        AffectiveState
    """
    detector = AffectiveDetector()
    return detector.analyze_message(message, response_time_ms, [])


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    detector = AffectiveDetector()

    # Test cases
    test_messages = [
        ("Не понимаю!!! Что делать??", 5000),           # Frustrated
        ("ок", 2000),                                     # Bored
        ("А что если мы попробуем по-другому?", 15000),  # Engaged
        ("хм... не ясно как это работает", 30000),       # Confused
        ("Понял, спасибо!", 8000),                       # Neutral/Engaged
    ]

    for msg, time_ms in test_messages:
        state = detector.analyze_message(msg, time_ms, [])
        print(f"\nMessage: '{msg}'")
        print(f"  State: {state.state_type.value}")
        print(f"  Confidence: {state.confidence:.2f}")
        print(f"  Should simplify: {state.should_simplify}")
        print(f"  Should encourage: {state.should_encourage}")
        print(f"  Adaptation: {detector.get_adaptation_prompt(state)[:50]}...")
