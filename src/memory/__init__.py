"""
MITS Memory Module

Provides dual-memory system:
- SessionMemory: Short-term, in-memory storage for current session
- StudentMemory: Long-term, persistent storage for student profiles
- MemoryManager: Coordinates both memory systems

Based on:
- Dual-Memory ITS Architecture (2025)
- Ebbinghaus Forgetting Curve for knowledge decay
- Preference learning for personalization
"""

from .interfaces import ISessionMemory, IStudentMemory, MemoryContext
from .session_memory import (
    SessionMemory,
    create_session_memory,
    TurnType,
    Turn,
    SessionContext
)
from .student_memory import (
    StudentMemory,
    create_student_memory
)
from .manager import (
    MemoryManager,
    create_memory_manager,
    MemoryEvent,
    SessionStartedEvent,
    SessionEndedEvent
)

__all__ = [
    # Interfaces
    "ISessionMemory",
    "IStudentMemory",
    "MemoryContext",
    # Session Memory
    "SessionMemory",
    "create_session_memory",
    "TurnType",
    "Turn",
    "SessionContext",
    # Student Memory
    "StudentMemory",
    "create_student_memory",
    # Memory Manager
    "MemoryManager",
    "create_memory_manager",
    "MemoryEvent",
    "SessionStartedEvent",
    "SessionEndedEvent",
]
