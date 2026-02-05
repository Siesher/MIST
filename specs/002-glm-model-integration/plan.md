# Implementation Plan: GLM Model Integration

**Branch**: `002-glm-model-integration` | **Date**: 2026-01-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-glm-model-integration/spec.md`

## Summary

Integrate GLM-4.7-Flash-REAP-23B-A3B as the primary model for MITS math tutoring, with DeepSeek-R1-8B as fallback. Use partial GPU/CPU offload (25 GPU layers + 22 CPU MoE layers) to fit RTX 2080 8GB + 32GB RAM. Expected improvement: GSM8K 90%+ (from current ~75-85%).

**Key Technical Decisions** (from [research.md](./research.md)):
- Quantization: Q4_K_M (13.5GB) - best quality/size balance
- GPU layers: 25 (fits ~7.2GB VRAM)
- Sampling: temperature=0.2, repetition_penalty=1.0 (fixes GLM issues)
- Backend: Ollama (primary), llama.cpp (advanced users)

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Ollama 0.14.3+, ollama-python, Gradio 4.x, pydantic-settings
**Storage**: SQLite (metrics), JSON (config)
**Testing**: pytest, manual benchmark testing
**Target Platform**: Windows/Linux desktop with RTX 2080 8GB + 32GB RAM
**Project Type**: Single project (existing MITS structure)
**Performance Goals**:
- First token latency: <3 seconds
- Token generation: 5+ tokens/second
- GSM8K accuracy: 90%+
**Constraints**:
- GPU VRAM: ≤8GB
- System RAM: ≤24GB for model + KV cache
- Context length: 4096 tokens
**Scale/Scope**: Single user, interactive tutoring sessions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Socratic Pedagogy** | ✅ PASS | GLM supports reasoning chains; prompts unchanged |
| **II. Multi-Agent Architecture** | ✅ PASS | Model is backend; agents remain unchanged |
| **III. Knowledge-Grounded Responses** | ✅ PASS | RAG system unaffected |
| **IV. Hardware Constraint Compliance** | ✅ PASS | 7.2GB GPU + 8GB RAM ≤ limits |
| **V. Metrics-Driven Quality** | ✅ PASS | GSM8K 90%+ > baseline 75-85% |
| **VI. STEM Domain Coverage** | ✅ PASS | GLM strong on math/coding; other STEM tested |

**Post-Design Re-check**: ✅ All gates pass

## Project Structure

### Documentation (this feature)

```text
specs/002-glm-model-integration/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Research findings
├── data-model.md        # Data models
├── quickstart.md        # Setup guide
├── contracts/           # JSON schemas
│   ├── model-config-schema.json
│   └── inference-metrics-schema.json
└── checklists/
    └── requirements.md  # Validation checklist
```

### Source Code (repository root)

```text
src/
├── config.py                    # UPDATE: Add new model settings
├── models/
│   └── llm_client.py           # UPDATE: Add GLM-specific handling
├── inference/
│   ├── model_manager.py        # UPDATE: Add GLM preset
│   └── metrics.py              # NEW: Performance metrics tracking
└── agents/
    └── [unchanged]              # Agents use model via interface

interface/
└── gradio_app.py               # UPDATE: Add model selector UI

tests/
├── test_glm_integration.py     # NEW: GLM-specific tests
└── test_model_switching.py     # NEW: Model fallback tests

evaluation/
└── benchmark_models.py         # NEW: GSM8K benchmark script
```

**Structure Decision**: Single project, extending existing `src/` structure. New files minimal - mostly updates to existing model management.

## Complexity Tracking

> No constitution violations requiring justification.

| Aspect | Complexity | Justification |
|--------|------------|---------------|
| MoE offloading | Medium | Required for 23B model on 8GB GPU; well-documented in llama.cpp |
| Sampling params | Low | Just configuration changes, no code complexity |
| Model switching | Low | Existing ModelManager supports multiple presets |

## Implementation Phases

### Phase 1: Core Integration
1. Update `src/config.py` with GLM settings
2. Add GLM preset to `MODEL_PRESETS` in model_manager.py
3. Update `LLMClient` for GLM-specific sampling
4. Test basic inference

### Phase 2: Performance & Monitoring
1. Add `InferenceMetrics` tracking
2. Implement performance logging
3. Test partial offload configuration

### Phase 3: UI & Fallback
1. Add model selector to Gradio interface
2. Implement automatic fallback logic
3. Add model info display

### Phase 4: Benchmarking & Validation
1. Create GSM8K benchmark script
2. Run comparative benchmarks
3. Document results
4. Validate Success Criteria

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| GLM repetition issues | Use verified sampling params (temp=0.2, rep_penalty=1.0) |
| VRAM overflow | Conservative 25 layers; fallback to DeepSeek-R1-8B |
| Slow inference | Acceptable 8-12 t/s for tutoring; async streaming |
| Model unavailable in Ollama | Use GGUF via llama.cpp as alternative |

## Next Steps

Run `/speckit.tasks` to generate detailed implementation tasks.
