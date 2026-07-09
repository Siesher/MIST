"""
Affective Agent

Agent wrapper for affective state detection that integrates with the orchestrator.
Supports both rule-based and ML-based (RuBERT) detection via config switch.
"""

import logging
from typing import Any, Dict, Optional

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.data.schemas import (
    AffectiveState,
    AffectiveStateType,
)
from src.models.affective_detector import AffectiveDetector

logger = logging.getLogger(__name__)


class AffectiveAgent(BaseAgent):
    """
    Agent that detects and tracks student affective state.

    Integrates with the orchestrator to provide affective context
    for other agents (especially the tutor agent).

    Supports two detector backends:
    - "rules": Rule-based detection (default, no model required)
    - "ml": ML-based RuBERT classifier (requires fine-tuned model)
    """

    def __init__(
        self,
        llm_client: Optional[object] = None,
        confidence_threshold: float = 0.6,
        window_size: int = 5,
        detector_type: Optional[str] = None,
    ):
        """
        Initialize the affective agent.

        Args:
            llm_client: Optional LLM client for semantic analysis
            confidence_threshold: Minimum confidence to report state
            window_size: Number of recent messages to analyze
            detector_type: Override config: 'rules' or 'ml'
        """
        super().__init__(name="affective_agent")

        settings = get_settings()
        self._detector_type = detector_type or settings.AFFECT_DETECTOR_TYPE

        # Always create rule-based detector (used as primary or fallback)
        self.detector = AffectiveDetector(
            llm_client=llm_client,
            confidence_threshold=confidence_threshold,
            window_size=window_size,
        )

        # Optionally load ML detector
        self._ml_detector = None
        if self._detector_type == "ml":
            try:
                from src.models.affective_ml_detector import AffectiveMLDetector
                self._ml_detector = AffectiveMLDetector(
                    model_path=settings.AFFECT_ML_MODEL_PATH,
                )
                if not self._ml_detector.is_available:
                    logger.warning(
                        "ML affect detector not available, falling back to rules"
                    )
                    self._ml_detector = None
            except Exception as e:
                logger.warning(f"Failed to load ML affect detector: {e}")

        mode = "ml" if self._ml_detector else "rules"
        logger.info(f"AffectiveAgent initialized (detector={mode})")

    async def process(
        self,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a message and detect affective state.

        Args:
            message: Student message
            context: Context containing:
                - response_time_ms: Time taken to respond
                - conversation: Recent conversation turns
                - was_correct: Whether answer was correct (optional)

        Returns:
            Dict with:
                - affective_state: Detected state
                - adaptation_prompt: Prompt modifier for tutor
                - recommendations: Dict of recommended adaptations
        """
        response_time_ms = context.get("response_time_ms", 0)
        conversation = context.get("conversation", [])
        was_correct = context.get("was_correct", None)

        # Detect state using rule-based detector (always runs for full signal tracking)
        state = self.detector.analyze_message(
            message=message,
            response_time_ms=response_time_ms,
            context=conversation,
            was_correct=was_correct,
        )

        # Override state_type with ML prediction if available
        if self._ml_detector is not None:
            ml_label, ml_confidence = self._ml_detector.predict(message)
            ml_state_map = {
                "frustrated": AffectiveStateType.FRUSTRATED,
                "confused": AffectiveStateType.CONFUSED,
                "engaged": AffectiveStateType.ENGAGED,
                "confident": AffectiveStateType.ENGAGED,  # map confident → engaged
                "neutral": AffectiveStateType.NEUTRAL,
            }
            ml_state_type = ml_state_map.get(ml_label, AffectiveStateType.NEUTRAL)
            if ml_confidence > state.confidence:
                state.state_type = ml_state_type
                state.confidence = ml_confidence

        # Get adaptation prompt
        adaptation_prompt = self.detector.get_adaptation_prompt(state)

        # Build recommendations
        recommendations = {
            "should_simplify": state.should_simplify,
            "should_encourage": state.should_encourage,
            "should_challenge": state.should_challenge,
            "should_offer_break": state.should_offer_break,
            "dominant_state": self.detector.get_dominant_state().value,
            "frustration_level": self.detector.get_frustration_level(),
        }

        return {
            "affective_state": state,
            "adaptation_prompt": adaptation_prompt,
            "recommendations": recommendations,
        }

    def get_current_state(self) -> Optional[AffectiveState]:
        """Get the most recent affective state."""
        history = self.detector.get_state_history()
        return history[-1] if history else None

    def get_frustration_level(self) -> float:
        """Get current frustration level (0-1)."""
        return self.detector.get_frustration_level()

    def reset(self) -> None:
        """Reset the agent for a new session."""
        self.detector.reset_session()
        logger.debug("AffectiveAgent reset")

    def health_check(self) -> Dict[str, Any]:
        """Check agent health."""
        return {
            "name": self.name,
            "status": "healthy",
            "history_length": len(self.detector.get_state_history()),
            "current_state": (
                self.get_current_state().state_type.value
                if self.get_current_state()
                else "none"
            ),
        }
