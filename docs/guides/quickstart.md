# MITS Quick Start Guide

## Prerequisites

- **Python 3.11+**
- **Ollama** (v0.14.3+)
- **8GB+ RAM** (16GB recommended)
- **GPU** (optional, improves inference speed)

---

## Installation

### 1. Clone and Setup Environment

```bash
# Clone repository
git clone https://github.com/your-org/MITS.git
cd MITS

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Install and Start Ollama

```bash
# Install Ollama (Windows - download from https://ollama.ai)
# Install Ollama (Linux/Mac)
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama server
ollama serve
```

### 3. Pull Required Model

```bash
# Pull the GLM model (or your configured model)
ollama pull glm4:latest

# Verify model is available
ollama list
```

### 4. Configure Environment

Create `.env` file in project root:

```env
# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
MODEL_NAME=glm4:latest

# Database
DATABASE_URL=sqlite:///data/mits.db

# RAG Settings (optional)
CHROMA_PERSIST_DIR=data/chroma
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Logging
LOG_LEVEL=INFO
```

### 5. Initialize Database

```bash
# Run database initialization
python scripts/db/init_db.py
```

---

## Running MITS

### Option 1: Unified Interface (Recommended)

```bash
python interface/unified_app.py
```

Open browser at: **http://localhost:7860**

### Option 2: Gradio App

```bash
python interface/gradio_app.py
```

### Option 3: Command Line

```bash
python run.py
```

---

## Quick Verification

### Test Ollama Connection

```bash
python -c "from src.models.llm_client import LLMClient; c = LLMClient(); print('OK' if c.check_connection() else 'FAIL')"
```

### Run Integration Tests

```bash
pytest tests/test_integration.py -v
```

### Run Evaluation

```bash
python evaluation/run_evaluation.py --sessions 10
```

---

## Features Overview

### 1. Socratic Tutoring
- Math problem assistance via guided questions
- No direct answer leakage
- Progressive scaffolding (conceptual -> procedural -> specific)

### 2. Knowledge Tracking
- BKT (Bayesian Knowledge Tracing) for mastery estimation
- DKT (Deep Knowledge Tracing) for 10+ interactions
- Ebbinghaus forgetting curve for knowledge decay

### 3. RAG-Enhanced Hints
- Context-aware hint retrieval
- Misconception detection
- Grounded responses reducing hallucinations

### 4. Cognitive Load Management
- Response time tracking
- Adaptive difficulty adjustment
- Break suggestions when overload detected

### 5. Multi-Agent Orchestration
- Query type classification
- Intelligent agent routing
- Graceful degradation on failures

### 6. Dual-Memory System
- Session memory (conversation context)
- Student memory (long-term persistence)
- Preference learning

### 7. Russian Language Support
- Full Russian mathematical notation (tg, ctg, lg)
- Localized hint templates
- Automatic language detection

---

## Project Structure

```
MITS/
├── interface/           # UI applications
│   ├── unified_app.py   # Main unified interface
│   └── gradio_app.py    # Alternative Gradio app
├── src/
│   ├── agents/          # Multi-agent system
│   │   ├── orchestrator.py
│   │   ├── tutor_agent.py
│   │   ├── profiler.py
│   │   ├── planner.py
│   │   └── verifier.py
│   ├── memory/          # Dual-memory system
│   │   ├── session_memory.py
│   │   ├── student_memory.py
│   │   └── manager.py
│   ├── models/          # LLM clients and prompts
│   │   ├── llm_client.py
│   │   ├── prompts.py
│   │   ├── knowledge_tracing.py
│   │   └── cognitive_load.py
│   ├── knowledge/       # RAG system
│   │   └── rag_retriever.py
│   └── inference/       # Performance optimization
│       └── cache.py
├── data/
│   ├── knowledge/       # RAG knowledge base
│   │   ├── hints/
│   │   ├── misconceptions/
│   │   └── glossary_ru.json
│   └── training/        # Fine-tuning data
├── evaluation/          # Success metrics
│   └── run_evaluation.py
├── tests/               # Test suite
│   └── test_integration.py
└── scripts/             # Utilities
    ├── init_db.py
    └── precompute_embeddings.py
```

---

## Configuration

### Key Settings in `src/config.py`

| Setting | Default | Description |
|---------|---------|-------------|
| `MODEL_NAME` | `glm4:latest` | Ollama model to use |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `DKT_THRESHOLD` | `10` | Responses before switching to DKT |
| `COGNITIVE_OVERLOAD_THRESHOLD` | `0.8` | Threshold for break suggestions |
| `RAG_SIMILARITY_THRESHOLD` | `0.7` | Minimum similarity for RAG retrieval |

---

## Troubleshooting

### Ollama Connection Failed

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve
```

### Model Not Found

```bash
# List available models
ollama list

# Pull required model
ollama pull glm4:latest
```

### Out of Memory

1. Reduce context window in config
2. Use smaller model variant
3. Enable CPU offloading in Ollama

### Slow Responses

1. Enable RAG caching (enabled by default)
2. Use GPU acceleration
3. Consider smaller model

---

## Success Criteria

The system targets the following metrics:

| Metric | Target | Description |
|--------|--------|-------------|
| Socratic Score | >70% | Responses with guiding questions |
| Telling Rate | <15% | Direct answer leakage rate |
| Error Recovery | >60% | Student success after errors |
| Session Completion | >50% | Students completing sessions |
| Response Latency P95 | <3000ms | 95th percentile response time |

Run evaluation to check:
```bash
python evaluation/run_evaluation.py --sessions 50
```

---

## Next Steps

1. **Customize Knowledge Base**: Add domain-specific hints to `data/knowledge/hints/`
2. **Fine-tune Model**: Use `training/` scripts for custom behavior
3. **Add Topics**: Extend `data/task_bank.json` with new problems
4. **Monitor Performance**: Check `data/mits.db` for student progress

---

## Support

- **Issues**: https://github.com/your-org/MITS/issues
- **Documentation**: `/docs/`
- **API Reference**: `/docs/api/`
