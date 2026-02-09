# MITS Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-30

## Active Technologies
- Python 3.11+ + Gradio 4.x, Ollama, ChromaDB, sentence-transformers, Unsloth, TRL, bitsandbytes (001-its-integration)
- ChromaDB (vectors), JSON/SQLite (profiles), in-memory (sessions) (001-its-integration)
- Python 3.11+ + Ollama 0.14.3+, ollama-python, Gradio 4.x, pydantic-settings (002-glm-model-integration)
- SQLite (metrics), JSON (config) (002-glm-model-integration)
- Google Drive (checkpoints), local filesystem (GGUF) (003-glm-math-pruning)
- Python 3.11+ + Ollama, huggingface_hub, requests (005-glm-stem-integration)
- Файловая система (GGUF файлы ~13-21GB) (005-glm-stem-integration)
- Python 3.11+ + Ollama, Gradio 4.x, ChromaDB, sentence-transformers, pydantic, structlog, LangChain (006-mits-system-completion)
- SQLite (student profiles, metrics), ChromaDB (RAG vectors), JSON (configs, task banks) (006-mits-system-completion)
- Python 3.11+ (Gradio backend), CSS3, JavaScript ES6 + Gradio 4.x, custom CSS themes (008-claude-ui-redesign)
- localStorage (user preferences), existing SQLite (session data) (008-claude-ui-redesign)
- Python 3.11+ + Gradio 4.x, Ollama, SymPy, sentence-transformers, ChromaDB, pydantic (009-groundbreaking-innovations)
- SQLite (student profiles), ChromaDB (vectors), JSON (configs) (009-groundbreaking-innovations)
- Python 3.11+ + Ollama, Gradio 4.x, ChromaDB, sentence-transformers, pydantic, structlog, SQLite (010-performance-optimization)
- SQLite (metrics, sessions), ChromaDB (vectors), JSON (configs, knowledge base) (010-performance-optimization)
- Python 3.11+ (backend), TypeScript 5.x (frontend) (011-nextjs-ui-migration)
- SQLite (existing), browser localStorage (preferences) (011-nextjs-ui-migration)
- Python 3.11+ (backend), TypeScript 5.x (frontend) + FastAPI, Next.js 14, Zustand, Ollama (012-chat-modes)
- In-memory sessions (StoredSession dataclass), SQLite for persistence (012-chat-modes)
- Python 3.11+ (backend), TypeScript 5.x (frontend) + PyTorch, Transformers, Unsloth, PEFT, Colab Pro+ (013-comprehensive-improvements)
- SQLite (sessions, auth), Docker, WeasyPrint (PDF export) (013-comprehensive-improvements)
- Python 3.11+ (backend, ML), TypeScript 5.x (frontend) + FastAPI, Next.js 14, PyTorch, Transformers, Unsloth, PEFT, TRL, SQLAlchemy, Recharts (013-comprehensive-improvements)
- SQLite (sessions, auth, analytics), filesystem (model weights, training data) (013-comprehensive-improvements)

## Project Structure

```text
src/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 013-comprehensive-improvements: Added Python 3.11+ (backend, ML), TypeScript 5.x (frontend) + FastAPI, Next.js 14, PyTorch, Transformers, Unsloth, PEFT, TRL, SQLAlchemy, Recharts
- 013-comprehensive-improvements: ML training (QLoRA, DKT, RuBERT), evaluation pipeline, analytics dashboard, Docker, JWT auth, session persistence
- 012-chat-modes: Added Python 3.11+ (backend), TypeScript 5.x (frontend) + FastAPI, Next.js 14, Zustand, Ollama


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
