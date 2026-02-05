# API Contracts: Groundbreaking Innovations

**Feature**: 009-groundbreaking-innovations
**Date**: 2026-02-03

## Internal Python APIs

These are internal module interfaces, not HTTP APIs (MITS is a local application).

---

## 1. Affective State Detection API

### `AffectiveDetector`

```python
class AffectiveDetector:
    """Detects student affective state from text signals."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize detector.

        Args:
            llm_client: Optional LLM for semantic analysis
        """

    def analyze_message(
        self,
        message: str,
        response_time_ms: int,
        context: List[ConversationTurn]
    ) -> AffectiveState:
        """
        Analyze a single message for affective signals.

        Args:
            message: Student's message text
            response_time_ms: Time taken to respond
            context: Recent conversation history

        Returns:
            Detected AffectiveState with recommendations
        """

    def get_adaptation_prompt(
        self,
        state: AffectiveState
    ) -> str:
        """
        Get prompt modifier for tutor based on affective state.

        Returns:
            String to append to tutor system prompt
        """

    def reset_session(self) -> None:
        """Reset state tracking for new session."""
```

---

## 2. Generative Task Synthesis API

### `TaskSynthesizer`

```python
class TaskSynthesizer:
    """Generates and verifies mathematical tasks."""

    def __init__(
        self,
        llm_client: LLMClient,
        verification_enabled: bool = True
    ):
        """
        Initialize synthesizer.

        Args:
            llm_client: LLM for task generation
            verification_enabled: Whether to verify with SymPy
        """

    def generate_task(
        self,
        topic: str,
        difficulty: Difficulty,
        student_profile: Optional[StudentProfile] = None
    ) -> GeneratedTask:
        """
        Generate a new task for the given topic.

        Args:
            topic: Math topic (e.g., "derivatives", "integrals")
            difficulty: Desired difficulty level
            student_profile: Optional student info for personalization

        Returns:
            GeneratedTask with verified solution

        Raises:
            TaskGenerationError: If generation fails after retries
        """

    def generate_variation(
        self,
        task: Task,
        variation_type: str = "similar"
    ) -> GeneratedTask:
        """
        Generate a variation of an existing task.

        Args:
            task: Original task to vary
            variation_type: "similar", "harder", "easier"

        Returns:
            New GeneratedTask based on original
        """

    def verify_task(
        self,
        task: GeneratedTask
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify task solution using SymPy.

        Returns:
            (is_valid, error_message)
        """

    def generate_hints(
        self,
        task: GeneratedTask
    ) -> List[str]:
        """Generate progressive hints for a task."""
```

---

## 3. Counterfactual Explanations API

### `CounterfactualEngine`

```python
class CounterfactualEngine:
    """Generates counterfactual explanations for errors."""

    def __init__(
        self,
        llm_client: LLMClient,
        knowledge_graph: Dict[str, SkillNode]
    ):
        """
        Initialize engine.

        Args:
            llm_client: LLM for explanation generation
            knowledge_graph: Skill prerequisite graph
        """

    def analyze_error(
        self,
        student_answer: str,
        correct_answer: str,
        task: Task,
        student_steps: Optional[List[str]] = None
    ) -> CounterfactualExplanation:
        """
        Analyze an error and generate counterfactual explanation.

        Args:
            student_answer: What student provided
            correct_answer: Expected answer
            task: The task being solved
            student_steps: Optional intermediate steps

        Returns:
            CounterfactualExplanation with diagnosis and recommendations
        """

    def identify_missing_skill(
        self,
        error_pattern: str,
        task_skills: List[str]
    ) -> Tuple[str, float]:
        """
        Identify which skill is missing.

        Returns:
            (skill_id, confidence)
        """

    def get_remediation_tasks(
        self,
        missing_skill: str,
        count: int = 3
    ) -> List[str]:
        """
        Get task IDs for practicing the missing skill.
        """
```

---

## 4. Metacognitive Scaffolding API

### `MetacognitiveTracker`

```python
class MetacognitiveTracker:
    """Tracks and develops metacognitive skills."""

    def __init__(self, memory: StudentMemory):
        """
        Initialize tracker.

        Args:
            memory: Student memory for persistence
        """

    def detect_stuck_point(
        self,
        message: str,
        task: Task,
        conversation: List[ConversationTurn]
    ) -> Optional[StuckPoint]:
        """
        Detect if student is stuck and categorize the stuck point.

        Returns:
            StuckPoint if detected, None otherwise
        """

    def get_metacognitive_prompt(
        self,
        stuck_point: Optional[StuckPoint] = None,
        context: str = "general"
    ) -> str:
        """
        Get appropriate metacognitive question to ask.

        Args:
            stuck_point: Detected stuck point (if any)
            context: "understanding", "strategy", "monitoring", "reflection"

        Returns:
            Metacognitive question in Russian
        """

    def record_intervention(
        self,
        stuck_point: StuckPoint,
        intervention_type: str,
        was_successful: bool
    ) -> None:
        """Record what intervention helped (for learning)."""

    def get_reflection_prompt(
        self,
        session_summary: SessionSummary
    ) -> str:
        """Get end-of-session reflection questions."""

    def update_profile(
        self,
        student_id: str
    ) -> MetacognitiveProfile:
        """Update and return metacognitive profile."""
```

---

## 5. Learning Path Optimization API

### `LearningPathOptimizer`

```python
class LearningPathOptimizer:
    """Optimizes learning paths through knowledge graph."""

    def __init__(
        self,
        knowledge_graph: Dict[str, SkillNode],
        knowledge_tracer: StudentModel
    ):
        """
        Initialize optimizer.

        Args:
            knowledge_graph: Skill prerequisite graph
            knowledge_tracer: For accessing student mastery
        """

    def create_path(
        self,
        student_id: str,
        target_skill: str
    ) -> LearningPath:
        """
        Create optimized learning path to target skill.

        Args:
            student_id: Student identifier
            target_skill: Skill to achieve

        Returns:
            Optimized LearningPath with ordered skills
        """

    def get_next_skill(
        self,
        path: LearningPath
    ) -> Optional[str]:
        """Get next skill to learn in path."""

    def update_progress(
        self,
        path: LearningPath,
        skill_id: str,
        mastery: float
    ) -> LearningPath:
        """Update path progress after skill practice."""

    def get_prerequisites(
        self,
        skill_id: str
    ) -> List[str]:
        """Get transitive prerequisites for a skill."""

    def visualize_path(
        self,
        path: LearningPath
    ) -> str:
        """Generate ASCII/Mermaid visualization of path."""
```

---

## 6. Multi-Modal Math Input API

### `VisionAnalyzer`

```python
class VisionAnalyzer:
    """Analyzes handwritten math solutions."""

    def __init__(
        self,
        vision_model: str = "minicpm-v",
        ollama_client: Optional[Any] = None
    ):
        """
        Initialize analyzer.

        Args:
            vision_model: Ollama vision model to use
            ollama_client: Optional pre-configured client
        """

    def analyze_image(
        self,
        image_path: str,
        expected_answer: Optional[str] = None
    ) -> HandwrittenSolution:
        """
        Analyze a handwritten solution image.

        Args:
            image_path: Path to image file
            expected_answer: Optional expected answer for verification

        Returns:
            HandwrittenSolution with recognized steps and errors
        """

    def extract_latex(
        self,
        image_path: str
    ) -> List[SolutionStep]:
        """
        Extract LaTeX from each line of handwritten math.

        Returns:
            List of SolutionStep with LaTeX and confidence
        """

    def verify_steps(
        self,
        steps: List[SolutionStep]
    ) -> List[SolutionStep]:
        """
        Verify each step follows from previous using SymPy.

        Returns:
            Steps with is_valid and error_description filled
        """

    def get_unclear_regions(
        self,
        solution: HandwrittenSolution
    ) -> List[Dict]:
        """Get regions that need clarification."""

    def is_available(self) -> bool:
        """Check if vision model is available."""
```

---

## Integration Points

### Tutor Agent Integration

```python
class SocraticTutor:  # Modified
    def __init__(
        self,
        ...
        affective_detector: Optional[AffectiveDetector] = None,
        metacognitive_tracker: Optional[MetacognitiveTracker] = None,
        counterfactual_engine: Optional[CounterfactualEngine] = None,
    ):
        ...

    async def respond(
        self,
        message: str,
        session: TutoringSession,
        response_time_ms: int = 0
    ) -> TutorResponse:
        """
        Generate response with affective and metacognitive awareness.

        1. Detect affective state
        2. Check for stuck point
        3. Generate base response
        4. Apply affective adaptation
        5. Add metacognitive scaffolding if needed
        """
```

### Gradio Interface Integration

```python
# unified_app.py additions

def upload_solution_image(image_file, task_context: str) -> Tuple[str, str]:
    """
    Handle uploaded solution image.

    Returns:
        (recognized_latex, analysis_feedback)
    """

def generate_new_task(topic: str, difficulty: str) -> Dict:
    """
    Generate new task via TaskSynthesizer.

    Returns:
        Task dict for display
    """

def show_learning_path(student_id: str, target_skill: str) -> str:
    """
    Generate and display learning path visualization.

    Returns:
        Mermaid diagram or ASCII art
    """
```
