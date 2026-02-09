# Implementation Plan: MITS Comprehensive Improvements

**Branch**: `013-comprehensive-improvements` | **Date**: 2026-02-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/013-comprehensive-improvements/spec.md`

## Summary

Three-month improvement plan transforming MITS from a prototype into a research-grade ITS. Key deliverables: fine-tuned LLM for Socratic tutoring (QLoRA on Colab A100), trained DKT on ASSISTments dataset, ML-based emotion detection (RuBERT), evaluation pipeline with automated benchmarks, analytics dashboard, handwritten solution OCR, A/B experiment framework, and production infrastructure (session persistence, JWT auth, Docker).

## Technical Context

**Language/Version**: Python 3.11+ (backend, ML), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, Next.js 14, PyTorch, Transformers, Unsloth, PEFT, TRL, SQLAlchemy, Recharts
**Storage**: SQLite (sessions, auth, analytics), filesystem (model weights, training data)
**Testing**: pytest (backend), manual validation (ML notebooks), quickstart.md scenarios
**Target Platform**: Windows local (inference), Google Colab Pro+ A100 (training), Docker (deployment)
**Project Type**: Web application (backend + frontend + ML notebooks)
**Performance Goals**: LLM cache reduces latency by 30%+, DKT AUC > 0.75, Affect F1 > 0.65
**Constraints**: Colab A100 for training only, local RTX for inference, backward compatible with existing modes
**Scale/Scope**: 20-30 students for A/B experiment, 1000+ synthetic dialogs, 12 months of analytics data

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Socratic Pedagogy | PASS | Fine-tuning improves Socratic behavior; evaluation measures Telling Rate |
| II. Multi-Agent Architecture | PASS | Pipeline preserved for guided_learning; chat/task_gen bypass is existing behavior |
| III. Knowledge-Grounded Responses | PASS | RAG integration maintained; new training data is grounded in math knowledge |
| IV. Hardware Constraint Compliance | JUSTIFIED | Training uses Colab A100 (exceeds RTX 2080), but inference stays within limits. Vision model loaded on-demand. See Complexity Tracking. |
| V. Metrics-Driven Quality | PASS | Evaluation pipeline directly implements all required metrics (Success@10, Telling@10, KT AUC) |
| VI. STEM Domain Coverage | PASS | Synthetic dialogs cover 5 math topics; DKT trained on multi-skill dataset |

## Project Structure

### Documentation (this feature)

```text
specs/013-comprehensive-improvements/
├── plan.md              # This file
├── research.md          # Phase 0 output — technical decisions
├── data-model.md        # Phase 1 output — entity definitions
├── quickstart.md        # Phase 1 output — validation tests
├── contracts/
│   └── api.yaml         # Phase 1 output — API contracts
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
# Backend (FastAPI)
backend/
├── app/
│   ├── api/v1/
│   │   ├── auth.py              # NEW: JWT auth endpoints
│   │   ├── analytics.py         # NEW: Analytics endpoints
│   │   ├── export.py            # NEW: PDF export endpoint
│   │   ├── evaluation.py        # NEW: Evaluation endpoints
│   │   ├── experiments.py       # NEW: A/B experiment endpoints
│   │   ├── vision.py            # NEW: Handwriting OCR endpoint
│   │   ├── sessions.py          # MODIFIED: auth middleware
│   │   ├── websocket.py         # MODIFIED: auth, image upload
│   │   └── ...existing...
│   ├── models/
│   │   ├── database.py          # NEW: SQLAlchemy engine + session
│   │   ├── tables.py            # NEW: ORM models (User, Session, Message)
│   │   └── auth.py              # NEW: JWT + password utilities
│   ├── services/
│   │   ├── analytics_service.py # NEW: Analytics aggregation
│   │   ├── export_service.py    # NEW: PDF generation
│   │   ├── cache_service.py     # NEW: LLM response cache
│   │   └── orchestrator_service.py # MODIFIED: SQLite persistence, cache
│   └── templates/
│       └── report.html          # NEW: PDF report template
├── migrations/
│   └── versions/                # Alembic migrations
└── requirements.txt             # MODIFIED: new dependencies

# Frontend (Next.js)
frontend/
├── src/
│   ├── app/
│   │   ├── auth/
│   │   │   ├── login/page.tsx   # NEW: Login page
│   │   │   └── register/page.tsx # NEW: Register page
│   │   ├── dashboard/page.tsx   # NEW: Analytics dashboard
│   │   └── ...existing...
│   ├── components/
│   │   ├── analytics/
│   │   │   ├── MasteryChart.tsx     # NEW: Line chart
│   │   │   ├── ActivityHeatmap.tsx  # NEW: GitHub-style heatmap
│   │   │   ├── ErrorDistribution.tsx # NEW: Pie chart
│   │   │   └── Recommendations.tsx  # NEW: ZPD recommendations
│   │   ├── chat/
│   │   │   ├── ImageUpload.tsx      # NEW: Handwriting upload
│   │   │   └── ...existing...
│   │   └── auth/
│   │       └── AuthProvider.tsx     # NEW: JWT context
│   ├── lib/
│   │   └── auth.ts              # NEW: Token management
│   └── ...existing...
└── package.json                 # MODIFIED: recharts, react-activity-calendar

# ML Notebooks (Colab)
notebooks/
├── finetuning_glm.ipynb         # NEW: QLoRA fine-tuning
├── dkt_training.ipynb           # NEW: DKT on ASSISTments
├── affective_rubert.ipynb       # NEW: RuBERT emotion training
├── synthetic_dialogs.ipynb      # NEW: Dialog generation
└── ...existing...

# Evaluation
evaluation/
├── benchmarks/
│   ├── socratic_score.py        # NEW: Tutoring quality metrics
│   ├── knowledge_prediction.py  # NEW: BKT vs DKT comparison
│   ├── affect_accuracy.py       # NEW: Rules vs ML comparison
│   └── latency_benchmark.py     # NEW: Response time benchmarks
├── comparisons/
│   ├── base_vs_finetuned.py     # NEW: Model comparison
│   └── generate_report.py       # NEW: Report generator
└── ...existing...

# Training Data
data/
├── training/
│   ├── synthetic_dialogs.jsonl  # NEW: Generated dialogs
│   └── ...existing...
├── models/
│   ├── dkt_pretrained.pt        # NEW: Trained DKT weights
│   └── rubert_affect/           # NEW: Trained RuBERT weights
└── ...existing...

# Docker
docker-compose.yml               # NEW
backend/Dockerfile               # NEW
frontend/Dockerfile              # NEW
```

**Structure Decision**: Extends existing web application structure (backend/ + frontend/) with ML notebooks for Colab training and evaluation framework. No new top-level directories added — notebooks/ and evaluation/ already exist.

## Complexity Tracking

> Constitution violations that must be justified

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle IV: A100 GPU for training (exceeds RTX 2080 limit) | Fine-tuning 7B model requires >8GB VRAM; DKT/RuBERT training is one-time on Colab | Inference stays within 8GB limit; training is offline, not part of runtime system |
| Principle II: Chat mode bypasses agent pipeline | Already implemented in 012-chat-modes; chat mode serves different pedagogical purpose | Forcing Socratic pipeline on free chat would degrade user experience |
