"""API schemas for the MITS backend."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# --- Enums ---


class ChatMode(str, Enum):
    chat = "chat"
    guided_learning = "guided_learning"
    task_generator = "task_generator"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"
    olympiad = "olympiad"


class SessionStatus(str, Enum):
    active = "active"
    completed = "completed"
    abandoned = "abandoned"


class MessageRole(str, Enum):
    user = "user"
    tutor = "tutor"
    system = "system"


class TutorMoveType(str, Enum):
    scaffolding = "scaffolding"
    problematize = "problematize"
    rectify = "rectify"
    encourage = "encourage"
    hint = "hint"
    tell = "tell"
    clarify = "clarify"


# --- Request Schemas ---


class CreateSessionRequest(BaseModel):
    topic: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    custom_problem: Optional[str] = None
    mode: Optional[ChatMode] = ChatMode.guided_learning


class ChangeModeRequest(BaseModel):
    mode: ChatMode


class ChangeModeResponse(BaseModel):
    session_id: str
    previous_mode: ChatMode
    current_mode: ChatMode
    message: str


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class GenerateTaskRequest(BaseModel):
    topic: str
    difficulty: Difficulty
    avoid_recent: bool = True


# --- Response Schemas ---


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    move_type: Optional[TutorMoveType] = None
    is_correct: Optional[bool] = None
    citations: Optional[List[dict]] = None


class TaskResponse(BaseModel):
    id: str
    topic: str
    difficulty: Difficulty
    problem: str
    hints: List[str] = Field(default_factory=list, max_length=3)
    skills: List[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    topic: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    status: SessionStatus
    mode: ChatMode = ChatMode.guided_learning
    message_count: int
    is_solved: bool
    hints_used: int


class SessionWithTaskResponse(SessionResponse):
    task: Optional[TaskResponse] = None
    welcome_message: Optional[str] = None


class SessionDetailResponse(SessionResponse):
    messages: List[MessageResponse] = Field(default_factory=list)
    task: Optional[TaskResponse] = None


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
    total: int
    page: int
    pages: int


class TutorResponseData(BaseModel):
    content: str
    move_type: Optional[TutorMoveType] = None
    is_correct: Optional[bool] = None
    thinking: Optional[str] = None
    citations: Optional[List[dict]] = None


class SessionState(BaseModel):
    is_solved: bool
    hints_used: int
    attempts: int


class ChatResponseSchema(BaseModel):
    message_id: str
    tutor_response: TutorResponseData
    session_state: SessionState
    knowledge_update: Optional[Dict[str, float]] = None


class HintResponseSchema(BaseModel):
    hint_number: int
    hint_text: str
    hints_remaining: int


class SolutionResponseSchema(BaseModel):
    solution: str
    answer: str
    penalty_applied: bool


class TopicInfo(BaseModel):
    id: str
    name: str
    name_ru: str
    difficulties: List[Difficulty]


class TopicsListResponse(BaseModel):
    topics: List[TopicInfo]


class RecommendedTasksResponse(BaseModel):
    tasks: List[TaskResponse]
    reasoning: str


class StudentProfileResponse(BaseModel):
    student_id: str
    total_sessions: int
    success_rate: float
    total_time_minutes: int
    streak_days: int
    mastery_by_topic: Dict[str, float]
    weak_skills: List[str]
    strong_skills: List[str]
    recommended_topic: Optional[str] = None


class ProgressByDay(BaseModel):
    date: str
    sessions: int
    solved: int


class AnalyticsResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    sessions_count: int
    tasks_attempted: int
    tasks_solved: int
    avg_session_minutes: float
    avg_hints_per_task: float
    progress_by_day: List[ProgressByDay]


class KnowledgeStateResponse(BaseModel):
    mastery_by_skill: Dict[str, float]
    skill_dependencies: Dict[str, List[str]]
    recommended_next: List[str]


class HealthComponentStatus(BaseModel):
    status: str
    model: Optional[str] = None


class HealthStatus(BaseModel):
    status: str  # healthy, degraded, unhealthy
    components: Dict[str, HealthComponentStatus]
    version: str = "1.0.0"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
