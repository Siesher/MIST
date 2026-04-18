# MITS Development Guidelines

Last updated: 2026-03-27

## Active Technologies
- Python 3.11+ + Ollama (tool calling API), existing StudentMemory (BKT), existing LLMClient (016-knowledge-forge)
- JSON file (`data/knowledge/forge.json`) for graph persistence, SQLite for student mastery (existing) (016-knowledge-forge)
- Python 3.11+ + Ollama (JSON-mode inference via `LLMClient.generate()`), existing multi-agent pipeline, Knowledge Forge navigator (017-tom-tutor)
- No new persistence — belief state lives in session memory only (ephemeral) (017-tom-tutor)
- Python 3.11+ + numpy (random walk, vectorization), scipy.stats (Lévy distribution), existing Knowledge Forge / PersonalizedNavigator (018-path-slime)
- In-memory only — алгоритм stateless, не персистит между вызовами (018-path-slime)

### Frontend
- Next.js 14, TypeScript 5.x, Tailwind CSS, shadcn/ui, Zustand

### Backend
- Python 3.11+, FastAPI, SQLAlchemy, SQLite, Alembic, JWT (PyJWT + Argon2)

### Core Logic
- Python 3.11+, Ollama, ChromaDB, sentence-transformers, SymPy, pydantic, structlog

### ML Training (Google Colab A100 80GB)
- Unsloth, TRL (GRPOTrainer, KTOTrainer, DPOTrainer), PEFT, Transformers, bitsandbytes, datasets, sympy, chempy
- Google Drive (checkpoints), HuggingFace Hub (datasets, adapters)

### Evaluation
- evaluate_stage.py (per-stage model evaluation)
- build_eval_benchmark.py (3678-problem benchmark from MGSM + ruMMLU + custom)
- verify_answers.py (SymPy/ChemPy verification)

## Project Structure

```text
frontend/          # Next.js 14 UI
backend/           # FastAPI backend
src/               # Core Python agents + models
training/
  scripts/         # ML pipeline scripts (evaluate_stage.py, etc.)
  data/            # Training data (~1.1GB JSONL)
  Modelfile*       # Ollama model configs
notebooks/         # Active Colab notebooks (GSPO, KTO, DPO)
  archive/         # Legacy notebooks (GLM, Qwen3-4B, RAFT++)
evaluation/        # Evaluation framework + reports + benchmarks
data/              # Knowledge bases (RAG, skill graph, tasks)
docs/              # Documentation + research articles
research/          # Research findings (findings_*.md)
scripts/           # Utility scripts (DB init, Ollama, PDF ingestion)
specs/             # Feature specifications (001-014)
figures/           # Training visualizations (PDF + PNG + TeX)
tests/             # Unit & integration tests
```

## Commands

```bash
cd src; pytest; ruff check .
```

## Code Style

Python 3.11+: Follow standard conventions

## Training Pipeline

3-stage RL pipeline (SFT removed — Instruct base; RAFT++ replaced by KTO):

```
Qwen3.5-9B → GSPO (triple reward) → KTO (Socratic alignment) → DPO (polish)
```

| Stage | Notebook | HF Repo | Key Technique |
|-------|----------|---------|---------------|
| GSPO | grpo_qwen3.5_9b.ipynb | Siesher/mits-qwen3-9b-gspo | Triple GDPO reward (correctness + format + Socratic) |
| KTO | kto_qwen3.5_9b.ipynb | Siesher/mits-qwen3-9b-kto | Kahneman-Tversky Optimization (arXiv 2402.01306) |
| DPO | dpo_polish_qwen3.5_9b.ipynb | Siesher/mits-qwen3-9b-final | Final alignment polish |

## Recent Changes
- 018-path-slime: Added Python 3.11+ + numpy (random walk, vectorization), scipy.stats (Lévy distribution), existing Knowledge Forge / PersonalizedNavigator
- 017-tom-tutor: Added Python 3.11+ + Ollama (JSON-mode inference via `LLMClient.generate()`), existing multi-agent pipeline, Knowledge Forge navigator
- 016-knowledge-forge: Added Python 3.11+ + Ollama (tool calling API), existing StudentMemory (BKT), existing LLMClient

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
