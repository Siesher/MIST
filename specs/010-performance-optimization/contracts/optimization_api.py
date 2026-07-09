"""
Optimization API Contract - Performance Optimization Feature

Internal Python API for context compression, few-shot retrieval, and prefetch.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class CompressionMethod(Enum):
    """Methods for context compression."""
    SLIDING_WINDOW = "sliding_window"
    LLM_SUMMARY = "llm_summary"
    HYBRID = "hybrid"


class ScaffoldingLevel(Enum):
    """Teaching scaffolding levels."""
    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"
    SPECIFIC = "specific"


@dataclass
class ConversationTurn:
    """Single turn in conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    turn_index: int
    is_error: bool = False
    hint_given: bool = False
    strategy_used: Optional[str] = None


@dataclass
class KeyEvent:
    """Extracted key event from conversation."""
    turn_index: int
    event_type: str  # "error", "hint_given", "progress", "stuck_point"
    content: str  # Brief description
    importance_score: float  # 0.0-1.0


@dataclass
class CompressedContext:
    """Compressed conversation context."""
    session_id: str
    original_turns: int
    compressed_turns: int
    original_tokens: int
    compressed_tokens: int
    key_events: List[KeyEvent]
    recent_messages: List[ConversationTurn]  # Last N full messages
    summary: Optional[str]  # LLM-generated if used
    compression_method: CompressionMethod
    compression_ratio: float  # compressed / original


@dataclass
class ContextCompressionRequest:
    """Request to compress context."""
    session_id: str
    conversation: List[ConversationTurn]
    token_threshold: int = 4000
    recent_messages_count: int = 10
    method: CompressionMethod = CompressionMethod.SLIDING_WINDOW


@dataclass
class FewShotExample:
    """Few-shot example for prompting."""
    example_id: str
    topic: str
    subtopic: Optional[str]
    difficulty: str
    problem: str
    student_answer: str
    student_error_type: Optional[str]
    tutor_response: str
    teaching_strategy: str
    relevance_score: float = 0.0  # Computed during retrieval


@dataclass
class FewShotRequest:
    """Request for few-shot examples."""
    current_problem: str
    topic: str
    difficulty: str
    student_answer: Optional[str] = None
    error_type: Optional[str] = None
    count: int = 2
    min_similarity: float = 0.5


@dataclass
class FewShotResponse:
    """Response with selected few-shot examples."""
    examples: List[FewShotExample]
    retrieval_time_ms: float
    from_cache: bool


@dataclass
class PrefetchRequest:
    """Request to prefetch hints."""
    session_id: str
    current_task_id: str
    current_skill: str
    student_mastery: Dict[str, float]  # skill -> mastery level
    max_hints: int = 5


@dataclass
class PrefetchResult:
    """Result of prefetch operation."""
    hints_prefetched: int
    skills_covered: List[str]
    prefetch_time_ms: float
    estimated_savings_ms: float  # How much time saved on future requests


# API Functions (Contract Signatures)

# === Context Compression ===

def should_compress(
    conversation: List[ConversationTurn],
    token_threshold: int = 4000
) -> bool:
    """
    Check if conversation needs compression.

    Args:
        conversation: Full conversation history
        token_threshold: Token limit before compression

    Returns:
        True if compression recommended
    """
    ...


def compress_context(request: ContextCompressionRequest) -> CompressedContext:
    """
    Compress conversation context.

    Args:
        request: Compression request with settings

    Returns:
        CompressedContext with compressed representation

    Algorithm:
        1. Keep last N messages in full
        2. Extract key events from older messages
        3. Optionally generate LLM summary if very long
        4. Compute compression metrics
    """
    ...


def extract_key_events(
    conversation: List[ConversationTurn],
    max_events: int = 10
) -> List[KeyEvent]:
    """
    Extract key learning events from conversation.

    Args:
        conversation: Conversation to analyze
        max_events: Maximum events to extract

    Returns:
        List of KeyEvents sorted by importance

    Events detected:
        - Student errors
        - Hints given
        - Progress markers (correct steps)
        - Stuck points
    """
    ...


def rebuild_context(
    compressed: CompressedContext,
    format: str = "chat"
) -> str:
    """
    Rebuild context string from compressed representation.

    Args:
        compressed: Compressed context
        format: "chat" for conversation format, "summary" for narrative

    Returns:
        Reconstructed context string for LLM prompt
    """
    ...


# === Few-Shot Retrieval ===

def retrieve_few_shot(request: FewShotRequest) -> FewShotResponse:
    """
    Retrieve relevant few-shot examples.

    Args:
        request: Few-shot request with problem context

    Returns:
        FewShotResponse with selected examples

    Algorithm:
        1. Filter by topic and difficulty
        2. Compute semantic similarity to current problem
        3. Boost examples matching error type if provided
        4. Return top N by combined score
    """
    ...


def add_few_shot_example(example: FewShotExample) -> str:
    """
    Add new example to few-shot bank.

    Args:
        example: Example to add

    Returns:
        Example ID

    Notes:
        - Automatically computes embedding
        - Validates Socratic nature of tutor_response
    """
    ...


def get_few_shot_stats() -> Dict[str, Any]:
    """
    Get statistics about few-shot bank.

    Returns:
        Dictionary with:
        - total_examples: int
        - by_topic: Dict[str, int]
        - by_difficulty: Dict[str, int]
        - most_used: List[str] (example IDs)
    """
    ...


def format_few_shot_prompt(
    examples: List[FewShotExample],
    current_problem: str,
    student_answer: Optional[str] = None
) -> str:
    """
    Format few-shot examples into prompt string.

    Args:
        examples: Selected examples
        current_problem: Current problem
        student_answer: Current student answer

    Returns:
        Formatted prompt string with examples
    """
    ...


# === Hint Prefetch ===

def prefetch_hints(request: PrefetchRequest) -> PrefetchResult:
    """
    Prefetch likely-needed hints.

    Args:
        request: Prefetch request with context

    Returns:
        PrefetchResult with stats

    Algorithm:
        1. Get prerequisites of current skill from graph
        2. Get common misconceptions for current task
        3. Prefetch hints for weak skills (low mastery)
        4. Cache embeddings and retrieval results
    """
    ...


def get_prefetch_status(session_id: str) -> Dict[str, Any]:
    """
    Get status of prefetch for a session.

    Args:
        session_id: Session to check

    Returns:
        Dictionary with:
        - hints_cached: int
        - skills_covered: List[str]
        - cache_age_seconds: float
    """
    ...


def clear_prefetch_cache(session_id: str) -> None:
    """
    Clear prefetch cache for a session.

    Args:
        session_id: Session to clear

    Use Case:
        - When task changes
        - When session ends
    """
    ...


# === Chain-of-Thought ===

def should_use_cot(
    problem: str,
    difficulty: str,
    topic: str
) -> bool:
    """
    Determine if CoT prompting should be used.

    Args:
        problem: Problem text
        difficulty: easy/medium/hard
        topic: Math topic

    Returns:
        True if CoT recommended

    Rules:
        - Always for difficulty >= medium
        - Always for multi-step problems
        - Always for proof/derivation tasks
    """
    ...


def get_cot_template(topic: str, language: str = "ru") -> str:
    """
    Get Chain-of-Thought template for a topic.

    Args:
        topic: Math topic
        language: "ru" or "en"

    Returns:
        CoT template string for system prompt
    """
    ...


def format_cot_response(
    response: str,
    show_reasoning: bool = False
) -> str:
    """
    Format CoT response for student.

    Args:
        response: Raw LLM response with reasoning
        show_reasoning: Whether to show full reasoning chain

    Returns:
        Formatted response (may hide intermediate steps)
    """
    ...
