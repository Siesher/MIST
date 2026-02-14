# Implementation Plan: ITS Integration

**Branch**: `001-its-integration` | **Date**: 2026-01-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-its-integration/spec.md`

## Summary

Build a complete Intelligent Tutoring System (ITS) with multi-agent architecture (Profiler → Planner → Tutor → Verifier) using the GenMentor pattern. The system guides students through STEM problems using Socratic questioning, never revealing direct answers. Core technologies: Qwen2.5-7B-Instruct with QLoRA fine-tuning, hybrid RAG (BM25 + Dense + RRF), Bayesian Knowledge Tracing with optional LSTM enhancement, all running within RTX 2080 (8GB VRAM) constraints.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Gradio 4.x, Ollama, ChromaDB, sentence-transformers, Unsloth, TRL, bitsandbytes
**Storage**: ChromaDB (vectors), JSON/SQLite (profiles), in-memory (sessions)
**Testing**: pytest, ruff (linting)
**Target Platform**: Windows/Linux with NVIDIA GPU (RTX 2080+)
**Project Type**: single (unified backend + Gradio frontend)
**Performance Goals**: <5s response latency (p95), Success@10 >60%, Telling@10 <15%
**Constraints**: <6GB VRAM inference, 8GB total for training on local GPU, Colab Pro+ (L4/A100) for full fine-tuning
**Scale/Scope**: Single user sessions, ~1500 knowledge base documents, 5 STEM disciplines

## Constitution Check

*GATE: PASS - All 6 constitutional principles satisfied*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Socratic Pedagogy | ✅ PASS | 4-level graduated hints, Verifier blocks direct answers, Telling@10 <15% target |
| II. Multi-Agent Architecture | ✅ PASS | GenMentor pipeline: Profiler → Planner → Tutor → Verifier → Orchestrator |
| III. Knowledge-Grounded Responses | ✅ PASS | Hybrid RAG with BM25+Dense+RRF, hints from `data/knowledge/hints/`, misconceptions mapped |
| IV. Hardware Constraint Compliance | ✅ PASS | Qwen2.5-7B 4-bit quantization, <6GB VRAM inference, embedding model <0.5GB |
| V. Metrics-Driven Quality | ✅ PASS | Success@10, Telling@10, Hint Efficiency, KT AUC-ROC all tracked |
| VI. STEM Domain Coverage | ✅ PASS | Math + Coding as MVP (P1+P2), Physics/Chemistry/Biology expansion planned (P4) |

## Project Structure

### Documentation (this feature)

```text
specs/001-its-integration/
├── plan.md              # This file
├── research.md          # Phase 0 output - consolidated findings
├── data-model.md        # Phase 1 output - 9 entities defined
├── quickstart.md        # Phase 1 output - setup guide
├── contracts/           # Phase 1 output
│   ├── orchestrator-api.yaml   # Internal Python API
│   └── gradio-interface.yaml   # UI components
└── tasks.md             # Phase 2 output (run /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── agents/
│   ├── orchestrator.py     # Agent coordination
│   ├── profiler.py         # Error diagnosis
│   ├── planner.py          # Strategy selection
│   ├── tutor_agent.py      # Response generation
│   └── verifier.py         # Quality control
├── data/
│   ├── task_bank.py        # Task management
│   └── algo_task_bank.py   # Coding tasks
├── execution/
│   └── sandbox.py          # Code execution
├── inference/
│   └── ollama_client.py    # LLM interface
├── knowledge/
│   ├── rag_retriever.py    # Hybrid RAG
│   └── knowledge_tracing.py # BKT implementation
├── logging/
│   └── metrics_logger.py   # Success@10, Telling@10
└── config.py               # Configuration

data/
├── knowledge/
│   ├── hints/              # JSONL hint files
│   └── misconceptions/     # Error patterns
├── tasks/                  # Task definitions
└── training/               # Dialog datasets

interface/
├── unified_app.py          # Main Gradio app
└── assets/                 # UI assets

training/
├── scripts/
│   ├── cerebras_dialog_generator.py
│   └── train_qlora.py
└── configs/
    └── qlora_rtx2080.yaml

tests/
├── test_agents.py
├── test_rag.py
└── test_coding.py

evaluation/
└── evaluate_model.py
```

**Structure Decision**: Single project structure with unified backend. Gradio serves both UI and handles session state. Training scripts separate for Colab Pro+ execution.

## Implementation Phases

### Phase 1: Core Agent Pipeline (P1 - Math Tutoring)

**Goal**: Implement basic tutoring flow with all 4 agents

**Deliverables**:
1. `AgentOrchestrator` - coordinate agent pipeline
2. `ProfilerAgent` - diagnose errors (6 error types)
3. `PlannerAgent` - select teaching strategy (7 strategies)
4. `TutorAgent` - generate Socratic responses
5. `VerifierAgent` - block answer leaks
6. Basic RAG retrieval with ChromaDB
7. Gradio interface for math problems

**Success Criteria**:
- Agent pipeline processes messages end-to-end
- Verifier correctly blocks direct answers
- Basic hints retrieved from knowledge base

---

### Phase 2: Knowledge & Tracking (P2 - Coding + Adaptive)

**Goal**: Add code execution, BKT, and improved RAG

**Deliverables**:
1. Code sandbox with timeout and security
2. Bayesian Knowledge Tracing (BKT) implementation
3. Hybrid RAG with BM25 + Dense + RRF fusion
4. Skill graph and mastery tracking
5. Coding task bank with test cases

**Success Criteria**:
- Code executes safely with proper feedback
- BKT updates mastery after each attempt
- Hybrid RAG improves hint relevance

---

### Phase 3: Fine-tuning & Evaluation (Quality)

**Goal**: Train custom model, achieve metric targets

**Deliverables**:
1. Synthetic dialog generation (Cerebras API)
2. QLoRA fine-tuning script (Colab Pro+)
3. Evaluation framework (Success@10, Telling@10)
4. Misconception detection improvements
5. LSTM enhancement for BKT (optional)

**Success Criteria**:
- 10K+ quality dialogs generated
- Fine-tuned model improves metrics
- Success@10 >60%, Telling@10 <15%

---

### Phase 4: STEM Expansion (P4 - Multi-discipline)

**Goal**: Extend to all 5 STEM disciplines

**Deliverables**:
1. Physics knowledge base and tasks
2. Chemistry knowledge base and tasks
3. Biology knowledge base and tasks
4. Discipline-specific prompting
5. Cross-discipline student profiles

**Success Criteria**:
- All 5 disciplines functional
- Per-discipline skill tracking
- Consistent tutoring quality across disciplines

---

## Technical Decisions

### Model Selection

**Decision**: Qwen2.5-7B-Instruct

**Rationale**:
- 8.4M HuggingFace downloads (proven reliability)
- Strong instruction-following (MMLU: 76.89)
- Multilingual support (Russian prompts)
- Unsloth official support for QLoRA
- 4-bit quantization fits RTX 2080

**Alternatives Rejected**:
- Llama 3.2 8B: Inferior multilingual support
- Mistral 7B: Weaker mathematical reasoning

### RAG Architecture

**Decision**: Hybrid Search with RRF Fusion (k=60)

**Rationale**:
- BM25 excels at exact terminology (math symbols)
- Dense retrieval captures semantic similarity
- RRF adds 8-10% accuracy with zero tuning
- ChromaDB sufficient for <100K documents

### Knowledge Tracing

**Decision**: BKT with optional LSTM enhancement

**Rationale**:
- BKT provides interpretable 4-parameter model
- LSTM adds sequential pattern learning
- Maintains explainability requirement
- Low additional compute cost

### Training Environment

**Decision**: Colab Pro+ with L4/A100 for full fine-tuning

**Rationale**:
- Local RTX 2080 insufficient for training larger batches
- VS Code integration via Colab extension
- L4 (24GB) or A100 (40GB) handles 7B model training
- Estimated 45-90 minutes for 5K dialogs

## Complexity Tracking

*No constitution violations requiring justification.*

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| VRAM overflow | Medium | High | Monitor nvidia-smi, reduce context to 2048 |
| Math hallucinations | Medium | High | RAG grounding, Verifier checks |
| Training data quality | Medium | Medium | Quality filtering, human review sample |
| Cerebras API changes | Low | Medium | Backup: local Nemotron generation |

## Generated Artifacts

| Artifact | Status | Description |
|----------|--------|-------------|
| `research.md` | ✅ Complete | 100+ papers consolidated, technical decisions |
| `data-model.md` | ✅ Complete | 9 entities, enums, relationships |
| `contracts/orchestrator-api.yaml` | ✅ Complete | Internal Python API |
| `contracts/gradio-interface.yaml` | ✅ Complete | UI component definitions |
| `quickstart.md` | ✅ Complete | Setup guide, troubleshooting |
| `CLAUDE.md` | ✅ Complete | Agent context file |

## Next Steps

1. Run `/speckit.tasks` to generate task list
2. Begin Phase 1 implementation
3. Set up Colab Pro+ environment for Phase 3

---

*Plan generated: 2026-01-30 | Constitution v1.0.0 compliant*
