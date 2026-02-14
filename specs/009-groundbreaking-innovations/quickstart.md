# Quickstart: Groundbreaking Innovations for MITS

**Feature**: 009-groundbreaking-innovations
**Date**: 2026-02-03

## Prerequisites

- Python 3.11+
- Ollama installed and running
- Required models: `glm4-flash`, `minicpm-v` (for OCR)
- Existing MITS installation

## Installation

### 1. Install New Dependencies

```bash
pip install sympy networkx
```

### 2. Pull Vision Model (for Multi-Modal Input)

```bash
ollama pull minicpm-v
```

### 3. Verify Installation

```python
# test_innovations_setup.py
import sympy
import networkx as nx
from sympy import symbols, diff, integrate

# Test SymPy
x = symbols('x')
assert str(diff(x**2, x)) == "2*x"
print("✅ SymPy working")

# Test networkx
G = nx.DiGraph()
G.add_edge("a", "b")
assert nx.has_path(G, "a", "b")
print("✅ NetworkX working")

# Test Ollama vision (optional)
try:
    import ollama
    models = ollama.list()
    vision_available = any("minicpm" in m.model for m in models.models)
    print(f"{'✅' if vision_available else '⚠️'} Vision model: {'available' if vision_available else 'not installed'}")
except:
    print("⚠️ Ollama not accessible")
```

## Quick Usage

### 1. Affective State Detection

```python
from src.models.affective_detector import AffectiveDetector

detector = AffectiveDetector()

# Analyze student message
state = detector.analyze_message(
    message="не понимаю!!!",
    response_time_ms=2000,
    context=[]
)

print(f"State: {state.state_type}")  # FRUSTRATED
print(f"Should simplify: {state.should_simplify}")  # True
```

### 2. Generative Task Synthesis

```python
from src.models.task_synthesizer import TaskSynthesizer
from src.data.schemas import Difficulty

synthesizer = TaskSynthesizer(llm_client=client)

# Generate verified task
task = synthesizer.generate_task(
    topic="derivatives",
    difficulty=Difficulty.MEDIUM
)

print(f"Problem: {task.problem}")
print(f"Answer: {task.answer}")
print(f"Verified: {task.sympy_verified}")  # True
```

### 3. Counterfactual Explanations

```python
from src.models.counterfactual_engine import CounterfactualEngine

engine = CounterfactualEngine(llm_client=client, knowledge_graph=SKILL_GRAPH)

# Analyze error
explanation = engine.analyze_error(
    student_answer="2x * cos(x)",
    correct_answer="2x * sin(x) + x^2 * cos(x)",
    task=task
)

print(f"Missing skill: {explanation.missing_skill}")  # product_rule
print(f"Counterfactual: {explanation.counterfactual_statement_ru}")
# "Если бы ты применил правило произведения (fg)' = f'g + fg', то получил бы..."
```

### 4. Metacognitive Scaffolding

```python
from src.models.metacognitive_tracker import MetacognitiveTracker

tracker = MetacognitiveTracker(memory=student_memory)

# Detect stuck point
stuck = tracker.detect_stuck_point(
    message="что делать дальше?",
    task=current_task,
    conversation=history
)

if stuck:
    prompt = tracker.get_metacognitive_prompt(stuck)
    print(prompt)  # "На каком шаге ты застрял? Что именно непонятно?"
```

### 5. Learning Path Optimization

```python
from src.models.learning_path_optimizer import LearningPathOptimizer

optimizer = LearningPathOptimizer(
    knowledge_graph=SKILL_GRAPH,
    knowledge_tracer=student_model
)

# Create path to target skill
path = optimizer.create_path(
    student_id="student_123",
    target_skill="chain_rule"
)

print(f"Skills to learn: {path.skills_to_learn}")
# ['limits', 'derivatives_basic', 'chain_rule']

print(f"Estimated hours: {path.estimated_total_hours}")
```

### 6. Multi-Modal Math Input

```python
from src.models.vision_analyzer import VisionAnalyzer

analyzer = VisionAnalyzer(vision_model="minicpm-v")

# Check availability
if analyzer.is_available():
    # Analyze handwritten solution
    solution = analyzer.analyze_image(
        image_path="solution.jpg",
        expected_answer="x^2 + C"
    )

    print(f"Recognized: {solution.final_answer_latex}")
    print(f"Correct: {solution.is_correct}")

    if solution.error_steps:
        print(f"Errors at steps: {solution.error_steps}")
```

## Integration with Existing MITS

### Tutor Agent Enhancement

```python
# In tutor_agent.py
from src.models.affective_detector import AffectiveDetector
from src.models.metacognitive_tracker import MetacognitiveTracker

class SocraticTutor:
    def __init__(self, ...):
        # Add new components
        self.affective_detector = AffectiveDetector()
        self.metacognitive_tracker = MetacognitiveTracker(memory)

    async def respond(self, message, session, response_time_ms=0):
        # 1. Detect affective state
        state = self.affective_detector.analyze_message(
            message, response_time_ms, session.conversation
        )

        # 2. Check for stuck point
        stuck = self.metacognitive_tracker.detect_stuck_point(
            message, session.task, session.conversation
        )

        # 3. Adapt response based on state
        if state.should_simplify:
            # Use simpler language, more scaffolding
            ...

        if stuck:
            # Add metacognitive prompt
            ...
```

### Gradio UI Additions

```python
# In unified_app.py

# Add image upload for Multi-Modal Input
with gr.Tab("📷 Проверка решения"):
    image_input = gr.Image(type="filepath", label="Загрузите фото решения")
    analyze_btn = gr.Button("Проанализировать")
    analysis_output = gr.Markdown()

# Add task generation
with gr.Tab("🎲 Новая задача"):
    topic_select = gr.Dropdown(choices=TOPICS, label="Тема")
    difficulty_select = gr.Dropdown(choices=["easy", "medium", "hard"])
    generate_btn = gr.Button("Сгенерировать")
    task_display = gr.Markdown()

# Add learning path visualization
with gr.Tab("🗺️ Путь обучения"):
    target_skill = gr.Dropdown(choices=SKILLS, label="Целевой навык")
    create_path_btn = gr.Button("Построить путь")
    path_display = gr.Markdown()  # Mermaid diagram
```

## Configuration

Add to `.env`:

```env
# Innovations settings
AFFECTIVE_DETECTION_ENABLED=true
TASK_SYNTHESIS_ENABLED=true
COUNTERFACTUAL_ENABLED=true
METACOGNITIVE_ENABLED=true
LEARNING_PATH_ENABLED=true
VISION_ANALYZER_ENABLED=true

# Vision model
VISION_MODEL=minicpm-v
VISION_VRAM_LIMIT_GB=3

# Task synthesis
TASK_SYNTHESIS_MAX_RETRIES=3
TASK_SYNTHESIS_VERIFY_WITH_SYMPY=true
```

## Testing

```bash
# Run all innovation tests
pytest tests/unit/test_affective_detector.py -v
pytest tests/unit/test_task_synthesizer.py -v
pytest tests/unit/test_counterfactual.py -v
pytest tests/unit/test_metacognitive.py -v
pytest tests/unit/test_learning_path.py -v
pytest tests/unit/test_vision_analyzer.py -v

# Integration test
pytest tests/integration/test_innovations_pipeline.py -v
```

## Troubleshooting

### SymPy Parse Error

```python
# If SymPy can't parse generated expression:
from sympy.parsing.sympy_parser import parse_expr

try:
    expr = parse_expr(generated_expr)
except:
    # Fallback to LLM comparison
    ...
```

### Vision Model OOM

```bash
# If VRAM exhausted, unload main model first:
ollama stop glm4-flash
# Then run vision analysis
# Then reload main model
```

### Affective Detection False Positives

```python
# Increase confidence threshold:
detector = AffectiveDetector(confidence_threshold=0.7)
```
