# Quickstart: MITS ITS Integration

**Feature**: 001-its-integration
**Estimated Setup Time**: 15-30 minutes

## Prerequisites

- Python 3.11+
- NVIDIA GPU with 8GB+ VRAM (RTX 2080 or better)
- CUDA 12.x installed
- Ollama installed and running
- Git

## Quick Start

### 1. Clone and Setup Environment

```bash
# Clone repository (if not already)
git clone https://github.com/your-org/MITS.git
cd MITS

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings:
# OLLAMA_HOST=http://localhost:11434
# CEREBRAS_API_KEY=your_key_here  # For data generation only
# LOG_LEVEL=INFO
```

### 3. Download and Setup Model

```bash
# Pull the base model via Ollama
ollama pull qwen2.5:7b-instruct

# Verify model is available
ollama list
```

### 4. Initialize Knowledge Base

```bash
# Run knowledge base indexer
python -m src.knowledge.rag_retriever --index

# Verify indexing (should show ~1500 documents)
python -m src.knowledge.rag_retriever --status
```

### 5. Run the Application

```bash
# Start the Gradio interface
python interface/unified_app.py

# Open browser at http://localhost:7860
```

---

## Verify Installation

### Test Agent Pipeline

```bash
# Run agent integration tests
python -m pytest tests/test_agents.py -v

# Expected output: All tests pass
```

### Test Knowledge Retrieval

```bash
# Run RAG retrieval test
python -m pytest tests/test_rag.py -v

# Expected: Hints and misconceptions retrieved correctly
```

### Test End-to-End

```python
# In Python REPL or notebook:
from src.agents.orchestrator import AgentOrchestrator
from src.agents.orchestrator import NewSessionRequest, Discipline

orchestrator = AgentOrchestrator()

# Create a new session
session = await orchestrator.create_session(
    NewSessionRequest(discipline=Discipline.MATH)
)

# Process a student message
response = await orchestrator.process_message(
    TutoringRequest(
        session_id=session.session_id,
        student_message="Как решить уравнение 2x + 3 = 7?"
    )
)

print(response.tutor_message)
# Should output a guiding question, not the answer
```

---

## Common Issues

### CUDA Out of Memory

```bash
# Reduce batch size in config
# Edit src/config.py:
#   BATCH_SIZE = 1
#   MAX_CONTEXT_LENGTH = 2048

# Or use smaller model:
ollama pull qwen2.5:3b-instruct
```

### Ollama Connection Failed

```bash
# Check Ollama is running
ollama serve

# Check port is accessible
curl http://localhost:11434/api/tags
```

### ChromaDB Initialization Error

```bash
# Clear and reinitialize
rm -rf data/chroma_db
python -m src.knowledge.rag_retriever --index
```

---

## Development Mode

### Run with Hot Reload

```bash
# Gradio with auto-reload
gradio interface/unified_app.py --reload

# Or with uvicorn for API development
uvicorn interface.api:app --reload --port 8000
```

### Run Tests with Coverage

```bash
pytest tests/ -v --cov=src --cov-report=html
# Open htmlcov/index.html for coverage report
```

### Enable Debug Logging

```bash
# Set in .env
LOG_LEVEL=DEBUG

# Or run with verbose flag
python interface/unified_app.py --debug
```

---

## Next Steps

1. **Generate Training Data**:
   ```bash
   python training/scripts/cerebras_dialog_generator.py --discipline math --dialogs-per-combo 5
   ```

2. **Fine-tune Model** (requires Colab Pro+):
   ```bash
   python training/scripts/train_qlora.py --config training/configs/qlora_rtx2080.yaml
   ```

3. **Run Evaluation**:
   ```bash
   python evaluation/evaluate_model.py --test-set data/test_dialogs.jsonl
   ```

---

## Architecture Overview

```
User Input → Gradio UI → Orchestrator
                            ↓
                    ┌───────────────────┐
                    │ 1. ProfilerAgent  │ → Diagnose errors
                    │ 2. PlannerAgent   │ → Select strategy
                    │ 3. TutorAgent     │ → Generate response
                    │ 4. VerifierAgent  │ → Quality check
                    └───────────────────┘
                            ↓
                    ← Tutor Response ←
```

## Support

- GitHub Issues: [https://github.com/your-org/MITS/issues](https://github.com/your-org/MITS/issues)
- Documentation: `docs/` directory
- Model Selection Guide: `docs/architecture/MODEL_SELECTION.md`
