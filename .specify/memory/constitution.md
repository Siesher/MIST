<!--
=============================================================================
SYNC IMPACT REPORT
=============================================================================
Version Change: N/A (initial) → 1.0.0
Bump Rationale: Initial ratification - first formal constitution for MITS

Modified Principles: N/A (initial creation)

Added Sections:
- Core Principles (6 principles)
- Technical Constraints
- Development Workflow
- Governance

Removed Sections: N/A

Templates Status:
- .specify/templates/plan-template.md: ✅ Compatible (Constitution Check section exists)
- .specify/templates/spec-template.md: ✅ Compatible (no constitution-specific refs)
- .specify/templates/tasks-template.md: ✅ Compatible (no constitution-specific refs)
- .specify/templates/agent-file-template.md: ✅ Compatible (generic template)

Follow-up TODOs: None
=============================================================================
-->

# MITS Constitution

## Core Principles

### I. Socratic Pedagogy (NON-NEGOTIABLE)

The system MUST guide students through questions, never providing direct answers.

- Tutor responses MUST contain guiding questions, not solutions
- Hints MUST be progressive: conceptual → procedural → specific
- The system MUST detect and refuse requests for direct answers
- Success metric: Telling@10 MUST remain below 15%

**Rationale**: The Socratic method develops critical thinking and long-term
retention. Giving answers defeats the educational purpose of the system.

### II. Multi-Agent Architecture

All tutoring logic MUST flow through the GenMentor pipeline pattern.

- Profiler Agent: Diagnoses misconceptions and knowledge gaps
- Planner Agent: Selects teaching strategy based on student profile
- Tutor Agent: Generates pedagogically appropriate responses
- Verifier Agent: Validates response quality before delivery
- Orchestrator: Coordinates agents; no agent bypasses allowed

**Rationale**: Specialized agents enable modular improvements and ensure
consistent quality through multi-stage verification.

### III. Knowledge-Grounded Responses

All tutor responses MUST be grounded in the RAG knowledge base.

- Hints MUST reference entries from `data/knowledge/hints/`
- Error explanations MUST map to `data/knowledge/misconceptions/`
- Skill dependencies MUST follow `data/knowledge/skill_graph.json`
- Responses without knowledge base grounding MUST be flagged

**Rationale**: Grounded responses ensure accuracy and consistency across
all student interactions and prevent hallucinated educational content.

### IV. Hardware Constraint Compliance

All components MUST operate within RTX 2080 (8GB VRAM) limits.

- Primary model MUST use 4-bit quantization (QLoRA)
- Embedding model MUST use less than 0.5GB VRAM
- Total inference VRAM MUST not exceed 6GB to allow OS overhead
- Batch sizes and context lengths MUST be validated against memory budget

**Rationale**: The system targets accessible hardware for broader deployment.
Exceeding limits causes OOM errors and degrades user experience.

### V. Metrics-Driven Quality

System quality MUST be measured by defined educational metrics.

| Metric | Target | Purpose |
|--------|--------|---------|
| Success@10 | >60% | Tasks solved within 10 attempts |
| Telling@10 | <15% | Sessions where answer was revealed |
| Hint Efficiency | <2.5 | Average hints before success |
| KT AUC-ROC | >0.75 | Knowledge state prediction accuracy |

- All changes MUST be evaluated against these metrics
- Regressions in any metric MUST be justified and approved

**Rationale**: Objective metrics prevent subjective quality assessments and
enable data-driven iteration on the tutoring approach.

### VI. STEM Domain Coverage

The system MUST support all five target disciplines with equal depth.

- Mathematics: algebra, calculus, geometry, statistics, trigonometry
- Programming: Python fundamentals, algorithms, data structures, OOP
- Physics: mechanics, thermodynamics, electricity, waves, optics
- Chemistry: atomic structure, reactions, stoichiometry, organic chemistry
- Biology: cell biology, genetics, ecology, evolution, physiology

- Each discipline MUST have dedicated knowledge base entries
- Dialog generation MUST cover all disciplines proportionally
- New disciplines require full knowledge base before activation

**Rationale**: Comprehensive STEM coverage is the core value proposition.
Incomplete discipline support misleads students about system capabilities.

## Technical Constraints

### Language & Framework

- **Language**: Python 3.11+
- **LLM Inference**: Ollama (local) or Cerebras API (cloud generation)
- **UI Framework**: Gradio 4.x
- **Embedding**: sentence-transformers (MiniLM-L12)
- **Training**: Unsloth QLoRA, bitsandbytes 4-bit quantization

### Model Requirements

- **Primary Model**: Qwen3-8B-Instruct (or equivalent MoE with <6GB VRAM)
- **Draft Model** (optional): Qwen-0.5B for speculative decoding
- **Embedding Model**: paraphrase-multilingual-MiniLM-L12-v2

### Data Formats

- Dialog datasets: JSONL with `instruction`, `input`, `output` fields
- Knowledge bases: JSONL with `topic`, `content`, `tags` fields
- Skill graphs: JSON adjacency list with prerequisite edges

## Development Workflow

### Code Changes

1. All agent modifications MUST pass through Verifier validation
2. Knowledge base changes MUST include corresponding test queries
3. Model changes MUST include VRAM profiling results
4. UI changes MUST maintain Gradio component compatibility

### Testing Requirements

- Unit tests for all agent logic in `tests/`
- Integration tests for the full orchestrator pipeline
- Evaluation runs on held-out dialog sets before merge

### Documentation

- Model selection rationale MUST be documented in `docs/architecture/MODEL_SELECTION.md`
- API changes MUST update docstrings and type hints
- New features MUST update `README.md` capabilities section

## Governance

### Amendment Process

1. Propose change via documented rationale
2. Evaluate impact on existing metrics and components
3. Update constitution with version increment
4. Propagate changes to dependent templates

### Version Policy

- **MAJOR**: Principle removal, fundamental architectural change
- **MINOR**: New principle added, significant scope expansion
- **PATCH**: Wording clarification, constraint adjustment

### Compliance Review

- All PRs MUST reference relevant constitution principles
- Violations MUST be justified in Complexity Tracking section of plan
- Periodic audits compare implementation against constitution

**Version**: 1.0.0 | **Ratified**: 2026-01-30 | **Last Amended**: 2026-01-30
