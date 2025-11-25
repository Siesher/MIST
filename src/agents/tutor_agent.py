"""
MITS Socratic Tutor Agent

The core tutoring agent that implements the Socratic method.
Guides students through questions, not answers.
"""

from typing import Optional, List, Dict, Any
import json

from src.agents.base_agent import BaseAgent
from src.models.llm_client import LLMClient
from src.models.prompts import SOCRATIC_TUTOR_SYSTEM, TUTOR_RESPONSE_PROMPT
from src.data.schemas import (
    Task, TutorMove, TutorResponse, ConversationTurn,
    TutoringSession, StudentProfile, VerificationResult
)
from src.config import settings


class SocraticTutorAgent(BaseAgent):
    """
    Main tutoring agent implementing the Socratic method.
    
    Teaching Structure (from SocraticLLM):
    1. Review - Understand student's current state
    2. Guidance/Heuristic - Lead with questions
    3. Rectification - Correct misconceptions gently
    4. Summarization - Reinforce learning after success
    """
    
    def __init__(self, llm_client: LLMClient):
        super().__init__(
            name="SocraticTutor",
            llm_client=llm_client,
            system_prompt=SOCRATIC_TUTOR_SYSTEM
        )
        
        # Strategy thresholds
        self.max_attempts_before_hint = 2
        self.max_hints_before_tell = settings.MAX_HINTS
        self.frustration_threshold = 3
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process student message and generate tutoring response.
        
        Args:
            input_data: {
                "session": TutoringSession,
                "student_message": str,
                "student_profile": StudentProfile (optional),
                "verification": VerificationResult (optional)
            }
            
        Returns:
            {"response": TutorResponse}
        """
        session = input_data["session"]
        student_message = input_data["student_message"]
        student_profile = input_data.get("student_profile")
        verification = input_data.get("verification")
        
        response = self.generate_response(
            session=session,
            student_message=student_message,
            student_profile=student_profile,
            verification_result=verification
        )
        
        return {"response": response}
    
    def generate_response(
        self,
        session: TutoringSession,
        student_message: str,
        student_profile: Optional[StudentProfile] = None,
        verification_result: Optional[VerificationResult] = None
    ) -> TutorResponse:
        """
        Generate a Socratic tutoring response.
        
        Args:
            session: Current tutoring session
            student_message: Latest student message
            student_profile: Student's profile (optional)
            verification_result: Verification of student's answer (optional)
            
        Returns:
            TutorResponse with move and message
        """
        # 1. Analyze current situation
        situation = self._analyze_situation(
            session, student_message, verification_result
        )
        
        # 2. Select teaching strategy
        strategy = self._select_strategy(situation, session)
        
        self._log_action("strategy_selected", {
            "strategy": strategy,
            "situation": situation
        })
        
        # 3. Generate response using LLM
        prompt = self._build_prompt(
            session=session,
            student_message=student_message,
            situation=situation,
            strategy=strategy,
            student_profile=student_profile
        )
        
        raw_response = self._call_llm(prompt, json_mode=True)
        
        # 4. Parse and validate response
        try:
            response_data = json.loads(raw_response)
            
            response = TutorResponse(
                move=TutorMove(response_data.get("move", strategy)),
                message=response_data["message"],
                internal_reasoning=response_data.get("reasoning"),
                hint_number=session.hints_used + 1 if strategy == "hint" else None,
                is_telling=response_data.get("move") == "tell"
            )
            
            # ⚠️ Safety check: Ensure we're not accidentally revealing the answer
            if self._is_revealing_answer(response.message, session.task):
                self.logger.warning("answer_leak_detected", move=response.move)
                response = self._sanitize_response(response, session.task)
            
            self._log_action("response_generated", {
                "move": response.move.value,
                "is_telling": response.is_telling
            })
            
            return response
            
        except json.JSONDecodeError:
            # Fallback to simple scaffolding response
            self.logger.warning("json_parse_failed", response=raw_response[:200])
            return TutorResponse(
                move=TutorMove.SCAFFOLDING,
                message=raw_response,
                is_telling=False
            )
    
    def _analyze_situation(
        self,
        session: TutoringSession,
        student_message: str,
        verification: Optional[VerificationResult]
    ) -> Dict[str, Any]:
        """Analyze current tutoring situation."""
        
        situation = {
            "attempts": session.attempts,
            "hints_used": session.hints_used,
            "conversation_length": len(session.conversation),
            "student_state": "working"
        }
        
        # Check verification result
        if verification:
            if verification.is_correct:
                situation["student_state"] = "solved"
            elif verification.is_partial:
                situation["student_state"] = "partial_progress"
            elif verification.has_error:
                situation["student_state"] = "made_error"
                situation["error_type"] = verification.error_type
        
        # Check for frustration signals
        frustration_keywords = [
            "don't understand", "confused", "stuck", 
            "help me", "give up", "i can't", "no idea"
        ]
        msg_lower = student_message.lower()
        if any(kw in msg_lower for kw in frustration_keywords):
            situation["emotional_state"] = "frustrated"
        
        # Check if student is asking a question
        if "?" in student_message:
            situation["is_asking_question"] = True
        
        return situation
    
    def _select_strategy(
        self,
        situation: Dict[str, Any],
        session: TutoringSession
    ) -> str:
        """
        Select tutoring strategy based on situation.
        
        Priority:
        1. Student solved → encourage
        2. Student frustrated → hint or tell (last resort)
        3. Student made error → rectify
        4. Student making progress → encourage + scaffold
        5. Student asking question → problematize
        6. Too many attempts → hint
        7. Default → scaffolding
        """
        
        # Student solved it!
        if situation.get("student_state") == "solved":
            return "encourage"
        
        # Student is frustrated - be supportive
        if situation.get("emotional_state") == "frustrated":
            if session.hints_used < self.max_hints_before_tell:
                return "hint"
            else:
                return "tell"  # ⚠️ Last resort
        
        # Student made an error
        if situation.get("student_state") == "made_error":
            return "rectify"
        
        # Student is making progress
        if situation.get("student_state") == "partial_progress":
            return "encourage"
        
        # Student is asking a question - answer with a question!
        if situation.get("is_asking_question"):
            return "problematize"
        
        # Too many attempts without progress
        if session.attempts > self.max_attempts_before_hint:
            if session.hints_used < self.max_hints_before_tell:
                return "hint"
            elif session.hints_used >= self.max_hints_before_tell:
                return "tell"  # ⚠️ Only after all hints exhausted
        
        # Default: Guide with questions
        return "scaffolding"
    
    def _build_prompt(
        self,
        session: TutoringSession,
        student_message: str,
        situation: Dict[str, Any],
        strategy: str,
        student_profile: Optional[StudentProfile]
    ) -> str:
        """Build prompt for LLM."""
        
        # Format conversation history (last 10 turns)
        history_turns = session.conversation[-10:]
        history = "\n".join([
            f"{turn.role.upper()}: {turn.content}"
            for turn in history_turns
        ]) if history_turns else "No previous conversation."
        
        # Get available hints
        available_hints = session.task.hints[session.hints_used:] if session.task.hints else []
        hints_str = "\n".join([
            f"{i+1}. {hint}" 
            for i, hint in enumerate(available_hints)
        ]) if available_hints else "No hints available."
        
        # Build common mistakes string
        mistakes_str = "\n".join(session.task.common_mistakes) if session.task.common_mistakes else "None specified."
        
        prompt = TUTOR_RESPONSE_PROMPT.format(
            problem=session.task.problem,
            solution=session.task.solution,
            answer=session.task.answer,
            common_mistakes=mistakes_str,
            conversation_history=history,
            student_message=student_message,
            attempts=session.attempts,
            hints_used=session.hints_used,
            max_hints=len(session.task.hints) if session.task.hints else 0,
            student_state=situation.get("student_state", "unknown"),
            strategy=strategy,
            available_hints=hints_str
        )
        
        return prompt
    
    def _is_revealing_answer(self, message: str, task: Task) -> bool:
        """
        Check if response accidentally reveals the answer.
        
        This is a safety check to ensure we maintain Socratic method.
        """
        answer_str = str(task.answer).lower().strip()
        message_lower = message.lower()
        
        # Skip check for very short answers (could be coincidental)
        if len(answer_str) < 3:
            return False
        
        # Direct answer check
        if answer_str in message_lower:
            return True
        
        # Check for solution-revealing patterns
        revealing_patterns = [
            f"the answer is",
            f"solution is",
            f"equals {answer_str}",
            f"= {answer_str}",
            f"result is {answer_str}",
        ]
        
        for pattern in revealing_patterns:
            if pattern in message_lower:
                return True
        
        return False
    
    def _sanitize_response(
        self,
        response: TutorResponse,
        task: Task
    ) -> TutorResponse:
        """
        Sanitize response that might reveal the answer.
        
        Replace with a safe scaffolding response.
        """
        safe_message = (
            "Let's think about this step by step. "
            "What approach have you tried so far? "
            "What do you think is the key insight needed here?"
        )
        
        return TutorResponse(
            move=TutorMove.SCAFFOLDING,
            message=safe_message,
            internal_reasoning="Original response sanitized to avoid answer leak",
            is_telling=False
        )
