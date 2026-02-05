"""
Context Compression for MITS.

Compresses long conversation histories while preserving key learning events.
Uses sliding window + key event extraction approach.

Feature 010: Performance Optimization
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Approximate tokens per character (for rough estimation)
TOKENS_PER_CHAR = 0.25


@dataclass
class KeyEvent:
    """Key event extracted from conversation."""

    turn_index: int
    event_type: str  # "error", "hint_given", "progress", "stuck_point"
    content: str
    importance_score: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "event_type": self.event_type,
            "content": self.content,
            "importance_score": self.importance_score,
        }


@dataclass
class CompressedContext:
    """Result of context compression."""

    session_id: str
    original_turns: int
    compressed_turns: int
    original_tokens: int
    compressed_tokens: int

    key_events: List[KeyEvent] = field(default_factory=list)
    recent_messages: List[Dict[str, Any]] = field(default_factory=list)
    summary: Optional[str] = None

    compression_method: str = "sliding_window"
    compression_ratio: float = 1.0

    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "original_turns": self.original_turns,
            "compressed_turns": self.compressed_turns,
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "key_events": [e.to_dict() for e in self.key_events],
            "recent_messages": self.recent_messages,
            "summary": self.summary,
            "compression_method": self.compression_method,
            "compression_ratio": self.compression_ratio,
            "created_at": self.created_at.isoformat(),
        }


class ContextCompressor:
    """
    Compresses conversation context while preserving key information.

    Strategy:
    1. Keep last N messages in full (sliding window)
    2. Extract key events from older messages
    3. Optionally generate LLM summary for very long contexts
    """

    # Patterns for detecting key events
    ERROR_PATTERNS = [
        r"неправильн",
        r"ошибк",
        r"не так",
        r"неверн",
        r"wrong",
        r"incorrect",
        r"error",
    ]

    HINT_PATTERNS = [
        r"подсказк",
        r"hint",
        r"попробуй",
        r"подумай",
        r"вспомни",
        r"что если",
    ]

    PROGRESS_PATTERNS = [
        r"правильно",
        r"верно",
        r"молодец",
        r"отлично",
        r"correct",
        r"хорошо",
        r"так держать",
    ]

    STUCK_PATTERNS = [
        r"не понимаю",
        r"не знаю",
        r"помоги",
        r"застрял",
        r"сложно",
        r"трудно",
        r"\?\?\?",
        r"не могу",
    ]

    def __init__(
        self,
        token_threshold: int = 4000,
        recent_messages_count: int = 10,
        max_key_events: int = 10
    ):
        """
        Initialize context compressor.

        Args:
            token_threshold: Token count to trigger compression
            recent_messages_count: Number of recent messages to keep in full
            max_key_events: Maximum key events to extract
        """
        self.token_threshold = token_threshold
        self.recent_count = recent_messages_count
        self.max_key_events = max_key_events

        # Try to load from config
        try:
            from src.config import settings
            self.token_threshold = settings.COMPRESSION_TOKEN_THRESHOLD
            self.recent_count = settings.COMPRESSION_RECENT_MESSAGES
            self.max_key_events = settings.COMPRESSION_MAX_KEY_EVENTS
        except ImportError:
            pass

        logger.info(
            f"ContextCompressor initialized: threshold={self.token_threshold}, "
            f"recent={self.recent_count}, max_events={self.max_key_events}"
        )

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return int(len(text) * TOKENS_PER_CHAR)

    def estimate_conversation_tokens(
        self,
        conversation: List[Dict[str, Any]]
    ) -> int:
        """Estimate total tokens in conversation."""
        total = 0
        for msg in conversation:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
        return total

    def should_compress(
        self,
        conversation: List[Dict[str, Any]],
        token_threshold: Optional[int] = None
    ) -> bool:
        """
        Check if conversation needs compression.

        Args:
            conversation: List of message dicts with 'role' and 'content'
            token_threshold: Override default threshold

        Returns:
            True if compression is recommended
        """
        threshold = token_threshold or self.token_threshold
        estimated_tokens = self.estimate_conversation_tokens(conversation)
        return estimated_tokens > threshold

    def _detect_event_type(self, content: str, role: str) -> Optional[Tuple[str, float]]:
        """Detect event type from message content."""
        content_lower = content.lower()

        # Check for stuck points (student messages)
        if role == "student" or role == "user":
            for pattern in self.STUCK_PATTERNS:
                if re.search(pattern, content_lower):
                    return ("stuck_point", 0.8)

        # Check for errors (tutor messages pointing out errors)
        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern, content_lower):
                return ("error", 0.9)

        # Check for hints
        for pattern in self.HINT_PATTERNS:
            if re.search(pattern, content_lower):
                return ("hint_given", 0.7)

        # Check for progress
        for pattern in self.PROGRESS_PATTERNS:
            if re.search(pattern, content_lower):
                return ("progress", 0.6)

        return None

    def extract_key_events(
        self,
        conversation: List[Dict[str, Any]],
        max_events: Optional[int] = None
    ) -> List[KeyEvent]:
        """
        Extract key learning events from conversation.

        Args:
            conversation: Full conversation history
            max_events: Maximum events to extract

        Returns:
            List of KeyEvent objects sorted by importance
        """
        max_events = max_events or self.max_key_events
        events = []

        for i, msg in enumerate(conversation):
            content = msg.get("content", "")
            role = msg.get("role", "unknown")

            if not isinstance(content, str):
                continue

            event_info = self._detect_event_type(content, role)
            if event_info:
                event_type, importance = event_info

                # Extract summary (first 100 chars)
                summary = content[:100].strip()
                if len(content) > 100:
                    summary += "..."

                events.append(KeyEvent(
                    turn_index=i,
                    event_type=event_type,
                    content=summary,
                    importance_score=importance,
                ))

        # Sort by importance and return top events
        events.sort(key=lambda e: e.importance_score, reverse=True)
        return events[:max_events]

    def compress(
        self,
        session_id: str,
        conversation: List[Dict[str, Any]],
        method: str = "sliding_window"
    ) -> CompressedContext:
        """
        Compress conversation context.

        Args:
            session_id: Session identifier
            conversation: Full conversation history
            method: Compression method ("sliding_window", "hybrid")

        Returns:
            CompressedContext with compressed representation
        """
        original_tokens = self.estimate_conversation_tokens(conversation)
        original_turns = len(conversation)

        # If under threshold, return uncompressed
        if not self.should_compress(conversation):
            return CompressedContext(
                session_id=session_id,
                original_turns=original_turns,
                compressed_turns=original_turns,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                recent_messages=conversation,
                compression_method="none",
                compression_ratio=1.0,
            )

        # Split into old and recent messages
        if len(conversation) <= self.recent_count:
            recent = conversation
            old = []
        else:
            recent = conversation[-self.recent_count:]
            old = conversation[:-self.recent_count]

        # Extract key events from old messages
        key_events = self.extract_key_events(old)

        # Calculate compressed size
        recent_tokens = self.estimate_conversation_tokens(recent)
        events_tokens = sum(self.estimate_tokens(e.content) for e in key_events)
        compressed_tokens = recent_tokens + events_tokens

        compression_ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

        result = CompressedContext(
            session_id=session_id,
            original_turns=original_turns,
            compressed_turns=len(recent),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            key_events=key_events,
            recent_messages=recent,
            compression_method=method,
            compression_ratio=compression_ratio,
        )

        logger.info(
            f"Compressed context: {original_turns} -> {len(recent)} turns, "
            f"{original_tokens} -> {compressed_tokens} tokens "
            f"(ratio={compression_ratio:.2f})"
        )

        return result

    def rebuild_context(
        self,
        compressed: CompressedContext,
        format: str = "chat"
    ) -> str:
        """
        Rebuild context string from compressed representation.

        Args:
            compressed: CompressedContext object
            format: Output format ("chat" or "summary")

        Returns:
            Reconstructed context string for LLM prompt
        """
        parts = []

        # Add key events summary
        if compressed.key_events:
            parts.append("### Ключевые моменты диалога:")
            for event in compressed.key_events:
                event_labels = {
                    "error": "Ошибка",
                    "hint_given": "Подсказка",
                    "progress": "Прогресс",
                    "stuck_point": "Затруднение",
                }
                label = event_labels.get(event.event_type, event.event_type)
                parts.append(f"- [{label}] {event.content}")
            parts.append("")

        # Add LLM summary if available
        if compressed.summary:
            parts.append("### Краткое содержание:")
            parts.append(compressed.summary)
            parts.append("")

        # Add recent messages
        if format == "chat":
            parts.append("### Недавний диалог:")
            for msg in compressed.recent_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                role_label = "Студент" if role in ("student", "user") else "Тьютор"
                parts.append(f"{role_label}: {content}")
        else:
            # Summary format - just concatenate recent content
            parts.append("### Контекст:")
            for msg in compressed.recent_messages:
                parts.append(msg.get("content", ""))

        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get compressor statistics."""
        return {
            "token_threshold": self.token_threshold,
            "recent_messages_count": self.recent_count,
            "max_key_events": self.max_key_events,
        }


# Global compressor instance
_compressor: Optional[ContextCompressor] = None


def get_context_compressor() -> ContextCompressor:
    """Get or create global context compressor."""
    global _compressor
    if _compressor is None:
        _compressor = ContextCompressor()
    return _compressor


def compress_if_needed(
    session_id: str,
    conversation: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Optional[CompressedContext]]:
    """
    Compress conversation if needed, returning usable context.

    Args:
        session_id: Session identifier
        conversation: Full conversation

    Returns:
        Tuple of (messages_to_use, compression_info)
    """
    compressor = get_context_compressor()

    if not compressor.should_compress(conversation):
        return conversation, None

    compressed = compressor.compress(session_id, conversation)
    return compressed.recent_messages, compressed
