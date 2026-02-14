# Quickstart: MITS System Completion

**Feature**: 006-mits-system-completion
**Date**: 2026-02-02

## Prerequisites

- Python 3.11+
- Ollama installed and running
- 8GB+ VRAM GPU (RTX 2080 or better)
- ~20GB disk space for models

## 1. Environment Setup

```bash
# Clone and navigate to project
cd C:\Work\MITS

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

## 2. Model Setup

```bash
# Ensure Ollama is running
ollama serve

# Pull required model (in another terminal)
ollama pull glm-4.7-flash

# Verify model is available
ollama list
```

Expected output:
```
NAME                    SIZE
glm-4.7-flash:latest    19GB
```

## 3. Configuration

Create `.env` file in project root:

```env
# Ollama Configuration
OLLAMA_HOST=http://localhost:11434

# Model Selection
MODEL_NAME=glm-4.7-flash
MODEL_FALLBACK=deepseek-r1:8b

# Paths
DATA_DIR=./data
CHROMADB_PATH=./data/chromadb
SQLITE_PATH=./data/mits.db

# Logging
LOG_LEVEL=INFO
```

## 4. Initialize Knowledge Base

```bash
# Create required directories
mkdir -p data/knowledge/hints
mkdir -p data/knowledge/misconceptions
mkdir -p data/students
mkdir -p data/chromadb

# Initialize ChromaDB with embeddings
python -c "from src.knowledge.rag_retriever import RAGRetriever; r = RAGRetriever(); r.initialize()"
```

## 5. Run Tests

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/test_coding.py -v
pytest tests/test_glm_stem.py -v

# Run with coverage
pytest --cov=src
```

## 6. Start Application

```bash
# Main unified interface (recommended)
python run.py

# Or specific interfaces
python run.py coding  # Algorithm focus
python run.py math    # Math focus
```

Access the application at: `http://localhost:7860`

## 7. Verify System Components

### Test Knowledge Tracing

```python
from src.models.knowledge_tracing import KnowledgeTracer

tracer = KnowledgeTracer()
# Initialize for a student
tracer.initialize_student("test-student-1")

# Update after interaction
tracer.update("test-student-1", topic="algebra.quadratic", correct=True)

# Get current mastery
state = tracer.get_state("test-student-1")
print(f"Algebra mastery: {state['algebra.quadratic']:.2f}")
```

### Test RAG Retrieval

```python
from src.knowledge.rag_retriever import RAGRetriever

rag = RAGRetriever()
# Search for relevant hints
hints = rag.search_hints(
    query="student makes sign error in quadratic formula",
    topic="algebra.quadratic",
    k=3
)
for hint in hints:
    print(f"- {hint.content_ru}")
```

### Test Agent Pipeline

```python
from src.agents.orchestrator import Orchestrator
from src.data.schemas import TutoringSession

# Initialize orchestrator
orchestrator = Orchestrator()

# Create session
session = TutoringSession(student_id="test-student-1")

# Process a student query
response = orchestrator.process(
    session=session,
    student_input="Помоги решить уравнение x² - 5x + 6 = 0"
)
print(response.tutor_response)
```

## 8. Development Workflow

### Adding New Hints

1. Create hint in `data/knowledge/hints/{topic}.json`:
```json
{
  "hint_id": "algebra.quadratic.factoring.001",
  "content_ru": "Какие два числа дают в сумме -5, а в произведении 6?",
  "topic_id": "algebra.quadratic",
  "hint_level": "conceptual",
  "hint_type": "question"
}
```

2. Re-index knowledge base:
```bash
python -c "from src.knowledge.rag_retriever import RAGRetriever; RAGRetriever().reindex()"
```

### Adding New Misconceptions

1. Create in `data/knowledge/misconceptions/{topic}.json`:
```json
{
  "misconception_id": "algebra.quadratic.sign_error",
  "name_ru": "Ошибка знака в формуле корней",
  "error_patterns": ["sign", "minus", "plus"],
  "correction_question_ru": "Проверь знаки в формуле. Какой знак должен быть перед b²?"
}
```

2. Re-index:
```bash
python -c "from src.knowledge.rag_retriever import RAGRetriever; RAGRetriever().reindex()"
```

### Running Code Quality Checks

```bash
# Linting
ruff check src/

# Type checking
mypy src/

# Format check
black --check src/
```

## 9. Monitoring

### View Session Logs

```bash
# Real-time log viewing
tail -f data/logs/sessions.log

# Or use structured log viewer
python -c "
from src.logging.session_logger import SessionLogger
logger = SessionLogger()
logger.print_recent_sessions(n=5)
"
```

### Check System Metrics

```python
from src.inference.metrics import MetricsCollector

metrics = MetricsCollector()
print(f"Avg response time: {metrics.avg_response_time:.2f}s")
print(f"RAG hit rate: {metrics.rag_hit_rate:.2%}")
print(f"Telling rate: {metrics.telling_rate:.2%}")
```

## 10. Troubleshooting

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama stop
ollama serve
```

### Out of Memory Errors

1. Reduce `GPU_LAYERS` in config:
```python
# src/config.py
GPU_LAYERS: int = 20  # Reduce from 25
```

2. Or switch to smaller model:
```env
MODEL_NAME=deepseek-r1:8b
```

### ChromaDB Issues

```bash
# Reset ChromaDB
rm -rf data/chromadb/*
python -c "from src.knowledge.rag_retriever import RAGRetriever; RAGRetriever().initialize()"
```

## Quick Command Reference

| Command | Description |
|---------|-------------|
| `python run.py` | Start unified interface |
| `pytest` | Run all tests |
| `ruff check .` | Lint code |
| `ollama list` | List available models |
| `ollama pull <model>` | Download model |

## Next Steps

After basic setup:
1. Populate knowledge base with more hints/misconceptions
2. Configure student profiles
3. Run evaluation on test dialogues
4. Monitor metrics and iterate
