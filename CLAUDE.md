# MITS Development Guidelines

Last updated: 2026-03-05

## Active Technologies

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
training/          # ML pipeline scripts + configs + data
notebooks/         # Colab training notebooks (GSPO, KTO, DPO)
evaluation/        # Model evaluation reports + benchmarks
data/              # Knowledge bases (RAG, skill graph, tasks)
docs/              # Documentation
specs/             # Feature specifications (001-014)
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
- 016: Triple GDPO reward (correctness + format + Socratic), KTO replaces RAFT++
- 015: Migrated to Qwen3.5-9B, A100 80GB bf16, 3-stage pipeline (removed AdaSTaR)
- 014: Removed SFT from pipeline (Instruct model has dialogue abilities built-in)
- 014: Added 4-stage RL pipeline (GSPO → RAFT++ → AdaSTaR → DPO)
- 014: Added evaluation infrastructure (3678-problem benchmark, per-stage reports)
- 013: Next.js 14 + FastAPI migration, JWT auth, session persistence
- 013: ML training (QLoRA, DKT, RuBERT), analytics dashboard, Docker

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
