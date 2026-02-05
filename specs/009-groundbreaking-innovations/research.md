# Research: Groundbreaking Innovations for MITS

**Feature**: 009-groundbreaking-innovations
**Date**: 2026-02-03

## 1. Affective State Detection

### Decision: Rule-based + LLM hybrid approach

**Rationale**:
- Pure ML models require large labeled datasets unavailable for Russian educational context
- Rule-based systems are interpretable and configurable
- LLM provides semantic understanding for edge cases

**Implementation**:
```python
class AffectiveSignals:
    # Text-based signals (rule-based)
    message_length: int           # Short = disengagement/frustration
    response_time_ms: int         # Fast + wrong = frustration; Slow = struggle
    punctuation_ratio: float      # "!!!" "???" = frustration
    typo_density: float           # High = rushing/frustration
    question_marks: int           # Asking = engagement
    ellipsis_count: int           # "..." = uncertainty

    # Semantic signals (LLM-analyzed)
    expressed_confusion: bool     # "не понимаю", "что?"
    expressed_frustration: bool   # "опять", "уже", negative words
    expressed_interest: bool      # follow-up questions
```

**Alternatives Considered**:
- BERT/RoBERTa sentiment classifiers — rejected due to domain mismatch and VRAM constraints
- Pure LLM classification — rejected due to latency (need real-time)

### Affective States Taxonomy

| State | Indicators | Tutor Adaptation |
|-------|------------|------------------|
| FRUSTRATED | Short msgs, typos, "!!!", consecutive errors | Simplify, encourage, offer break |
| BORED | Fast correct answers, minimal engagement | Increase difficulty, add challenge |
| CONFUSED | "?", long pauses, "не понимаю" | More scaffolding, examples |
| ENGAGED | Questions, detailed answers, follow-ups | Deepen explanations, add context |
| NEUTRAL | Normal patterns | Standard tutoring |

---

## 2. Generative Task Synthesis

### Decision: LLM + SymPy verification pipeline

**Rationale**:
- LLM generates diverse, natural-language problems
- SymPy guarantees mathematical correctness
- Pipeline allows rejection of invalid generations

**Implementation Flow**:
```
1. LLM generates task structure:
   - Topic: derivatives
   - Difficulty: medium
   - Function type: product of functions

2. LLM proposes concrete function:
   - f(x) = x² · sin(x)

3. SymPy computes answer:
   - from sympy import symbols, diff, simplify
   - x = symbols('x')
   - answer = simplify(diff(x**2 * sin(x), x))
   - # Result: 2x·sin(x) + x²·cos(x)

4. Verification:
   - Parse LLM's proposed answer
   - Compare with SymPy result
   - If match: ACCEPT; else: RETRY or FIX

5. Generate hints using SymPy intermediate steps
```

**Supported Task Types**:

| Category | SymPy Functions | Example |
|----------|----------------|---------|
| Derivatives | `diff()` | d/dx(x³ + 2x) = 3x² + 2 |
| Integrals | `integrate()` | ∫x²dx = x³/3 + C |
| Limits | `limit()` | lim(sin(x)/x, x, 0) = 1 |
| Equations | `solve()` | x² - 4 = 0 → x = ±2 |
| Simplification | `simplify()`, `expand()` | (a+b)² = a² + 2ab + b² |
| Trigonometry | `trigsimp()` | sin²x + cos²x = 1 |

**Alternatives Considered**:
- Pure LLM generation — rejected due to frequent math errors
- Template-based only — rejected due to limited variety

---

## 3. Counterfactual Explanations

### Decision: Skill-gap analysis + LLM explanation generation

**Rationale**:
- Identify specific missing skill from error pattern
- Generate "if-then" counterfactual using LLM
- Link to prerequisite system for recommendations

**Counterfactual Template**:
```
IF you had applied [MISSING_SKILL] at step [N],
THEN you would have obtained [CORRECT_INTERMEDIATE] instead of [STUDENT_ANSWER].

This suggests you need to review: [PREREQUISITE_TOPICS]
```

**Implementation**:
```python
class CounterfactualEngine:
    def analyze_error(self,
                      student_solution: str,
                      correct_solution: str,
                      task: Task) -> CounterfactualExplanation:

        # 1. Parse solutions into steps
        student_steps = self.parse_steps(student_solution)
        correct_steps = self.parse_steps(correct_solution)

        # 2. Find divergence point
        divergence_idx = self.find_divergence(student_steps, correct_steps)

        # 3. Identify missing skill
        missing_skill = self.diagnose_skill_gap(
            student_steps[divergence_idx],
            correct_steps[divergence_idx]
        )

        # 4. Generate counterfactual
        return self.generate_counterfactual(
            missing_skill=missing_skill,
            divergence_step=divergence_idx,
            student_result=student_steps[-1],
            correct_result=correct_steps[-1]
        )
```

**Skill-Error Mapping**:

| Error Pattern | Missing Skill | Counterfactual |
|---------------|---------------|----------------|
| (fg)' = f'g' | product_rule | "Если бы ты применил правило произведения..." |
| ∫f(g(x))dx = F(g(x)) | substitution | "Если бы ты сделал замену u = g(x)..." |
| sin(a+b) = sin(a) + sin(b) | trig_identities | "Если бы ты использовал формулу синуса суммы..." |

---

## 4. Metacognitive Scaffolding

### Decision: Structured question sequences + stuck point tracking

**Rationale**:
- Metacognition improves transfer learning
- Explicit self-monitoring questions train metacognitive skills
- Tracking stuck points enables personalization

**Metacognitive Question Framework**:

```python
class MetacognitivePrompts:
    UNDERSTANDING_CHECK = [
        "Ты понимаешь, что спрашивается в задаче?",
        "Можешь своими словами объяснить условие?",
        "Какой результат ты ожидаешь получить?"
    ]

    STRATEGY_CHECK = [
        "Какой метод ты планируешь использовать?",
        "Почему именно этот метод подходит?",
        "С чего начнёшь решение?"
    ]

    MONITORING_CHECK = [
        "Результат выглядит разумным?",
        "Можешь проверить ответ подстановкой?",
        "Есть ли другой способ решить?"
    ]

    STUCK_POINT_PROBE = [
        "На каком шаге ты застрял?",
        "Что именно непонятно: условие, метод или вычисления?",
        "Какая часть вызывает затруднения?"
    ]
```

**Stuck Point Tracking**:
```python
@dataclass
class StuckPoint:
    task_id: str
    step_number: int
    stuck_type: Literal["understanding", "strategy", "execution"]
    skill_involved: str
    resolution: Optional[str] = None  # What helped
    timestamp: datetime
```

---

## 5. Learning Path Optimization

### Decision: Topological sort on knowledge graph + mastery-aware filtering

**Rationale**:
- Prerequisites must be satisfied before advancing
- Mastery levels determine readiness
- ZPD (Zone of Proximal Development) guides topic selection

**Knowledge Graph Structure**:
```python
SKILL_GRAPH = {
    "arithmetic": {"prerequisites": [], "difficulty": 0.1},
    "fractions": {"prerequisites": ["arithmetic"], "difficulty": 0.2},
    "linear_equations": {"prerequisites": ["arithmetic"], "difficulty": 0.3},
    "quadratic_equations": {"prerequisites": ["linear_equations"], "difficulty": 0.5},
    "limits": {"prerequisites": ["fractions", "quadratic_equations"], "difficulty": 0.6},
    "derivatives_basic": {"prerequisites": ["limits"], "difficulty": 0.7},
    "product_rule": {"prerequisites": ["derivatives_basic"], "difficulty": 0.75},
    "chain_rule": {"prerequisites": ["derivatives_basic"], "difficulty": 0.8},
    "integrals_basic": {"prerequisites": ["derivatives_basic"], "difficulty": 0.85},
    # ... 40+ skills total
}
```

**Path Optimization Algorithm**:
```python
def optimize_learning_path(student: StudentProfile, target_skill: str) -> List[str]:
    """
    1. Find all prerequisites of target_skill (transitive closure)
    2. Filter out already-mastered skills (mastery > 0.7)
    3. Sort remaining by:
       - Topological order (prerequisites first)
       - Student's learning velocity for similar skills
       - Estimated time to mastery
    4. Return ordered list of skills to learn
    """
```

---

## 6. Multi-Modal Math Input

### Decision: Ollama vision model (minicpm-v) + structured output

**Rationale**:
- minicpm-v is small enough for RTX 2080 (~3GB VRAM)
- Ollama provides unified interface
- Structured output enables step-by-step analysis

**Vision Model Selection**:

| Model | VRAM | Math OCR Quality | Speed |
|-------|------|------------------|-------|
| Qwen2-VL-7B | 6GB+ | Excellent | Slow |
| LLaVA-1.6-7B | 5GB+ | Good | Medium |
| minicpm-v | 3GB | Good | Fast |
| **Selected: minicpm-v** | 3GB | Good | Fast |

**Pipeline**:
```
1. User uploads image
2. Preprocess: resize, enhance contrast
3. Vision model extracts:
   - LaTeX for each line
   - Step structure
   - Potential error locations
4. SymPy validates each step
5. Return analysis with error locations
```

**Prompt for Vision Model**:
```
Analyze this handwritten math solution. For each step:
1. Convert to LaTeX
2. Identify the mathematical operation
3. Check if the result follows from the previous step

Output JSON:
{
  "steps": [
    {"line": 1, "latex": "x^2 + 2x - 3 = 0", "operation": "given"},
    {"line": 2, "latex": "(x+3)(x-1) = 0", "operation": "factoring"},
    ...
  ],
  "potential_errors": [
    {"line": 2, "issue": "factoring may be incorrect"}
  ]
}
```

**Fallback Strategy**:
- If recognition confidence < 80%: ask user to retype unclear parts
- If SymPy can't parse: use LLM for semantic comparison

---

## Dependencies Summary

| Feature | New Dependencies | Existing Used |
|---------|-----------------|---------------|
| Affective Detection | — | pydantic, logging |
| Task Synthesis | sympy | Ollama, pydantic |
| Counterfactuals | — | knowledge_tracing, RAG |
| Metacognitive | — | session_memory, schemas |
| Learning Path | networkx | knowledge_tracing, schemas |
| Multi-Modal | — | Ollama (vision) |

**Total New Dependencies**: `sympy`, `networkx`

---

## VRAM Budget Analysis

| Component | VRAM Usage | Notes |
|-----------|------------|-------|
| GLM-4.7-Flash (primary) | ~4GB | 4-bit quantized |
| minicpm-v (vision) | ~3GB | Only loaded when needed |
| Embeddings | ~0.5GB | MiniLM |
| **Total (concurrent)** | ~4.5GB | Vision model unloaded during chat |
| **Peak (vision active)** | ~7.5GB | May need offload |

**Mitigation**: Load vision model on-demand, unload after use.
