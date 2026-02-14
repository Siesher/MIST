# Agent Interface Contracts

**Feature**: 006-mits-system-completion
**Date**: 2026-02-02

## Overview

All agents communicate through the Orchestrator using standardized interfaces. This document defines the contracts for inter-agent communication.

## Base Agent Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class AgentRequest(BaseModel):
    """Standard request to any agent."""
    session_id: str
    student_id: str
    context: Dict[str, Any]
    input_data: Any

class AgentResponse(BaseModel):
    """Standard response from any agent."""
    success: bool
    agent_name: str
    output: Any
    metadata: Dict[str, Any] = {}
    error: Optional[str] = None

class BaseAgent(ABC):
    """Abstract base class for all agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent identifier."""
        pass

    @abstractmethod
    async def process(self, request: AgentRequest) -> AgentResponse:
        """Process a request and return response."""
        pass
```

## Profiler Agent Contract

**Purpose**: Diagnose student errors and assess knowledge state.

### Input

```python
class ProfilerInput(BaseModel):
    """Input to Profiler agent."""
    student_response: str
    current_task: Task
    knowledge_state: KnowledgeState
    session_history: List[Turn]
```

### Output

```python
class ErrorDiagnosis(BaseModel):
    """Profiler's error analysis."""
    error_type: ErrorType
    error_location: Optional[str]  # Specific part of response
    severity: ErrorSeverity
    related_misconceptions: List[str]  # Misconception IDs
    affected_topics: List[str]  # Topic IDs

class ProfilerOutput(BaseModel):
    """Output from Profiler agent."""
    diagnosis: Optional[ErrorDiagnosis]
    is_correct: bool
    partial_credit: float  # 0.0 to 1.0
    cognitive_load: CognitiveLoad
    suggested_topics_for_review: List[str]

class ErrorType(str, Enum):
    NONE = "none"
    CONCEPTUAL = "conceptual"     # Misunderstanding of concept
    PROCEDURAL = "procedural"     # Wrong steps
    CALCULATION = "calculation"   # Arithmetic error
    SYNTAX = "syntax"             # Code syntax error
    LOGIC = "logic"               # Logical error in code

class ErrorSeverity(str, Enum):
    MINOR = "minor"       # Small mistake, close to correct
    MODERATE = "moderate" # Significant error but shows understanding
    MAJOR = "major"       # Fundamental misunderstanding
```

## Planner Agent Contract

**Purpose**: Select teaching strategy based on student profile and current state.

### Input

```python
class PlannerInput(BaseModel):
    """Input to Planner agent."""
    profiler_output: ProfilerOutput
    knowledge_state: KnowledgeState
    learning_style: LearningStyle
    session_context: SessionMemory
```

### Output

```python
class TeachingPlan(BaseModel):
    """Planner's teaching strategy."""
    strategy: TeachingStrategy
    move_sequence: List[TutorMove]
    difficulty_adjustment: DifficultyAdjustment
    focus_topics: List[str]
    hints_to_use: List[str]  # Hint IDs in order

class TeachingStrategy(str, Enum):
    GUIDED_DISCOVERY = "guided_discovery"  # Minimal scaffolding
    SCAFFOLDED = "scaffolded"              # Step-by-step
    ERROR_CORRECTION = "error_correction"  # Focus on fixing error
    CONCEPTUAL_REPAIR = "conceptual_repair" # Address misconception
    ENCOURAGEMENT = "encouragement"        # Boost confidence
    REVIEW = "review"                      # Go back to prerequisites
    DIRECT_INSTRUCTION = "direct"          # Last resort

class DifficultyAdjustment(str, Enum):
    INCREASE = "increase"
    MAINTAIN = "maintain"
    DECREASE = "decrease"
```

## Tutor Agent Contract

**Purpose**: Generate pedagogically appropriate Socratic response.

### Input

```python
class TutorInput(BaseModel):
    """Input to Tutor agent."""
    student_message: str
    teaching_plan: TeachingPlan
    rag_context: TutoringContext  # From RAG retriever
    session_memory: SessionMemory
    knowledge_state: KnowledgeState
```

### Output

```python
class TutorOutput(BaseModel):
    """Output from Tutor agent."""
    response: str
    response_ru: str  # Russian version
    tutor_move: TutorMove
    hints_used: List[str]  # Hint IDs actually used
    follow_up_questions: List[str]  # For continued dialogue
    suggested_next_task: Optional[str]  # Task ID if ready for new task

class TutorMove(str, Enum):
    SCAFFOLDING = "scaffolding"     # Break down problem
    PROBLEMATIZE = "problematize"   # Challenge assumption
    RECTIFY = "rectify"             # Correct error gently
    ENCOURAGE = "encourage"         # Positive reinforcement
    HINT = "hint"                   # Give progressive hint
    TELL = "tell"                   # Direct answer (only when necessary)
```

## Verifier Agent Contract

**Purpose**: Quality control for tutor responses.

### Input

```python
class VerifierInput(BaseModel):
    """Input to Verifier agent."""
    tutor_output: TutorOutput
    original_task: Task
    student_input: str
    teaching_plan: TeachingPlan
```

### Output

```python
class VerificationResult(BaseModel):
    """Verifier's quality assessment."""
    approved: bool
    issues: List[QualityIssue]
    corrections: Optional[str]  # Suggested corrections
    metrics: QualityMetrics

class QualityIssue(BaseModel):
    """Specific quality issue found."""
    issue_type: IssueType
    description: str
    severity: IssueSeverity
    location: Optional[str]

class IssueType(str, Enum):
    ANSWER_LEAK = "answer_leak"           # Gave away answer
    NON_SOCRATIC = "non_socratic"         # Direct instead of questioning
    INCORRECT_CONTENT = "incorrect_content"
    POOR_FORMATTING = "poor_formatting"
    WRONG_LANGUAGE = "wrong_language"
    TOO_LONG = "too_long"
    TOO_SHORT = "too_short"
    OFF_TOPIC = "off_topic"

class QualityMetrics(BaseModel):
    """Quality metrics for the response."""
    socratic_score: float  # 0-1, higher is more Socratic
    clarity_score: float   # 0-1
    relevance_score: float # 0-1
    contains_question: bool
    estimated_cognitive_load: CognitiveLoadLevel
```

## Task Generator Agent Contract

**Purpose**: Generate appropriate practice tasks.

### Input

```python
class TaskGenInput(BaseModel):
    """Input to Task Generator agent."""
    knowledge_state: KnowledgeState
    target_topics: List[str]
    target_difficulty: Difficulty
    exclude_task_ids: List[str]  # Already attempted
    session_context: SessionMemory
```

### Output

```python
class TaskGenOutput(BaseModel):
    """Output from Task Generator agent."""
    task: Task
    rationale: str  # Why this task was chosen
    expected_difficulty_for_student: float  # 0-1
    prerequisite_check: PrerequisiteStatus

class PrerequisiteStatus(BaseModel):
    """Whether student has prerequisites for task."""
    ready: bool
    missing_prerequisites: List[str]  # Topic IDs
    recommended_review: List[str]     # Task IDs for review
```

## Orchestrator Contract

**Purpose**: Coordinate all agents and manage session flow.

### Input

```python
class OrchestratorInput(BaseModel):
    """Input to Orchestrator."""
    session: TutoringSession
    student_input: str
    mode: OrchestratorMode = OrchestratorMode.FULL

class OrchestratorMode(str, Enum):
    FULL = "full"           # All agents
    FAST = "fast"           # Tutor + Verifier only
    DIAGNOSTIC = "diagnostic" # Profiler + Planner only
```

### Output

```python
class OrchestratorOutput(BaseModel):
    """Output from Orchestrator."""
    response: str
    session: TutoringSession  # Updated session
    pipeline_trace: PipelineTrace  # For debugging

class PipelineTrace(BaseModel):
    """Trace of agent pipeline execution."""
    agents_called: List[str]
    execution_time_ms: int
    profiler_output: Optional[ProfilerOutput]
    planner_output: Optional[TeachingPlan]
    tutor_output: Optional[TutorOutput]
    verifier_output: Optional[VerificationResult]
    retries: int
```

## RAG Retriever Contract

**Purpose**: Retrieve relevant educational content.

### Input

```python
class RAGQuery(BaseModel):
    """Query to RAG system."""
    query: str
    topic_filter: Optional[str]
    hint_level: Optional[HintLevel]
    query_type: RAGQueryType
    k: int = 5

class RAGQueryType(str, Enum):
    HINT = "hint"
    MISCONCEPTION = "misconception"
    EXAMPLE = "example"
    ALL = "all"
```

### Output

```python
class RAGResult(BaseModel):
    """Result from RAG retrieval."""
    hints: List[Hint]
    misconceptions: List[Misconception]
    examples: List[WorkedExample]
    scores: Dict[str, float]  # ID -> relevance score

class TutoringContext(BaseModel):
    """Bundled context for tutor."""
    relevant_hints: List[Hint]
    detected_misconceptions: List[Misconception]
    similar_examples: List[WorkedExample]
    topic_info: Topic
```

## Knowledge Tracer Contract

**Purpose**: Track and predict student knowledge.

### Input

```python
class KTUpdate(BaseModel):
    """Update to knowledge tracer."""
    student_id: str
    topic_id: str
    correct: bool
    response_time_ms: int
    difficulty: float
    hints_used: int
```

### Output

```python
class KTState(BaseModel):
    """Knowledge tracer output."""
    student_id: str
    topic_masteries: Dict[str, float]
    predicted_success: Dict[str, float]  # Probability of success per topic
    recommended_topics: List[str]  # Ordered by learning benefit
    use_dkt: bool  # Whether DKT model is active
```

## Error Handling

All agents must handle errors gracefully:

```python
class AgentError(Exception):
    """Base exception for agent errors."""
    def __init__(self, agent_name: str, message: str, recoverable: bool = True):
        self.agent_name = agent_name
        self.message = message
        self.recoverable = recoverable
        super().__init__(f"[{agent_name}] {message}")

# Orchestrator handles errors:
try:
    result = await agent.process(request)
except AgentError as e:
    if e.recoverable:
        # Use fallback strategy
        result = await fallback_agent.process(request)
    else:
        # Log and return error response
        return OrchestratorOutput(
            response="Извините, произошла ошибка. Попробуйте ещё раз.",
            session=session,
            pipeline_trace=PipelineTrace(error=str(e))
        )
```
