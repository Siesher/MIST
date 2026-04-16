# Quickstart: Knowledge Forge

## Prerequisites

- Python 3.11+ with project venv activated
- Existing `data/knowledge/skill_graph.json` and `data/knowledge/textbooks/` present
- Ollama running with a Qwen3.5-9B model (for source extraction only; navigation is pure Python)

## 1. Seed the Knowledge Graph

Run the migration to convert existing skill_graph + SKI cards into the forge graph:

```bash
python scripts/migrate_to_forge.py
```

This creates `data/knowledge/forge.json` with ~40 CONCEPT nodes, prerequisite edges, and linked FORMULA/EXAMPLE/METHOD/MISCONCEPTION nodes from SKI cards.

Verify:
```bash
python -c "
from src.knowledge.knowledge_forge import KnowledgeGraph
from pathlib import Path
g = KnowledgeGraph(Path('data/knowledge/forge.json'))
print(g.stats)
"
```

## 2. Test Navigator with a Mock Student

```python
from pathlib import Path
from src.knowledge.knowledge_forge import KnowledgeGraph
from src.knowledge.navigator import PersonalizedNavigator

graph = KnowledgeGraph(Path("data/knowledge/forge.json"))

# Mock student: mastered algebra, not calculus
mock_mastery = {
    "math:arithmetic:definition": 0.95,
    "math:fractions:definition": 0.90,
    "math:algebra:definition": 0.85,
    "math:linear_equations:definition": 0.80,
    "math:functions:definition": 0.75,
}

nav = PersonalizedNavigator(graph, mock_mastery)

# What should this student learn next?
frontier = nav.get_learning_frontier("mock_student", max_results=3)
for f in frontier:
    print(f"{f.title}: readiness={f.readiness_score:.2f}, missing={f.missing_prereqs}")

# Diagnose a gap
gap = nav.diagnose_gap("mock_student", "math:definite_integrals:definition")
print(f"Root gap: {gap.root_gap}")
print(f"Review path: {gap.suggested_review_path}")
```

## 3. Test with Real Student Memory

```python
from src.memory.student_memory import StudentMemory
from src.knowledge.navigator import PersonalizedNavigator

memory = StudentMemory("data/mits.db")
nav = PersonalizedNavigator(graph, memory)

# Uses real BKT mastery data
frontier = nav.get_learning_frontier("student_42")
```

## 4. Run Tests

```bash
cd src && pytest tests/test_knowledge_forge.py tests/test_navigator.py -v
```

## Key Files

| File | Purpose |
|------|---------|
| `src/knowledge/knowledge_forge.py` | Graph core: nodes, edges, CRUD, persistence |
| `src/knowledge/navigator.py` | Personalized navigator: frontier, gaps, paths |
| `src/tools/navigator_tools.py` | Ollama tool definitions for tutor |
| `src/knowledge/source_extractor.py` | LLM document extraction |
| `scripts/migrate_to_forge.py` | Seed graph from existing data |
| `data/knowledge/forge.json` | Persisted knowledge graph |
