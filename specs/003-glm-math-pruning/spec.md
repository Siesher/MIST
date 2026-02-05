# Feature Specification: GLM STEM Pruning

**Feature Branch**: `003-glm-math-pruning`
**Created**: 2026-01-31
**Status**: Draft
**Input**: Create optimized GLM-4.7-Flash variant for STEM tutoring (code + natural sciences) via REAP pruning with Cerebras-generated multi-domain calibration dataset

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-Domain Optimized Model Generation (Priority: P1)

An ML engineer generates a multi-domain calibration dataset using Cerebras API (Qwen-3-235B) covering code, mathematics, physics, chemistry, biology, and other STEM disciplines. REAP expert pruning is applied to GLM-4.7-Flash on Google Colab A100, producing a smaller model that preserves capabilities across all domains.

**Why this priority**: Core deliverable - without the pruned model, no other features work. Multi-domain calibration ensures no critical expert gets pruned, maintaining quality across code and all natural sciences.

**Independent Test**: Run the complete pruning pipeline on A100 and verify output model passes accuracy thresholds across multiple benchmarks (GSM8K, HumanEval, SciQ).

**Acceptance Scenarios**:

1. **Given** Cerebras API access, **When** engineer runs dataset generation script, **Then** calibration dataset is created with balanced representation across domains:
   - Code: 200 examples (Python, algorithms, debugging)
   - Mathematics: 200 examples (algebra, calculus, linear algebra, statistics, probability)
   - Physics: 150 examples (mechanics, thermodynamics, electromagnetism)
   - Chemistry: 150 examples (organic, inorganic, biochemistry)
   - Biology: 150 examples (molecular, genetics, ecology)
   - Socratic tutoring: 150 examples (multi-domain hint generation)
2. **Given** GLM-4.7-Flash base model and multi-domain calibration dataset, **When** engineer runs REAP pruning script on A100, **Then** pruned model (19-20B params) is produced preserving domain-specific experts
3. **Given** pruned model checkpoint, **When** engineer runs multi-benchmark evaluation, **Then** accuracy is at least 95% of baseline across all domains

---

### User Story 2 - GGUF Conversion for Local Deployment (Priority: P2)

An ML engineer converts the pruned HuggingFace model to GGUF format and registers it with local Ollama installation for use in the MITS STEM tutoring system.

**Why this priority**: Enables local deployment - without GGUF conversion, the pruned model cannot be used on the target hardware (RTX 2080 + 32GB RAM via Ollama).

**Independent Test**: Convert pruned model to GGUF and verify it loads correctly in Ollama with acceptable performance.

**Acceptance Scenarios**:

1. **Given** pruned HuggingFace model checkpoint, **When** engineer runs llama.cpp conversion script, **Then** GGUF file is created with Q4_K_M quantization
2. **Given** GGUF model file, **When** engineer imports to Ollama via Modelfile, **Then** model is accessible via `ollama run glm-stem-pruned`
3. **Given** Ollama-registered model on RTX 2080, **When** inference is run with 4K context, **Then** TTFT < 3s and generation rate >= 5 tokens/sec

---

### User Story 3 - Multi-Domain Quality Validation (Priority: P3)

A developer runs automated benchmarks comparing the pruned model against baseline GLM-4.7-Flash-REAP-23B-A3B across multiple domains to validate quality preservation.

**Why this priority**: Provides evidence that pruning achieved goals across ALL domains - ensures no domain was accidentally degraded by pruning.

**Independent Test**: Run benchmark suite comparing both models on domain-specific benchmarks and measure accuracy delta per domain.

**Acceptance Scenarios**:

1. **Given** pruned model and baseline model, **When** benchmark script runs multi-domain test suite, **Then** accuracy comparison report is generated for each domain:
   - GSM8K (math reasoning)
   - HumanEval (code generation)
   - SciQ/ARC (science knowledge)
   - MMLU-STEM subset (multi-domain)
2. **Given** both models available, **When** performance benchmark runs, **Then** pruned model shows improved memory usage and comparable or better latency
3. **Given** benchmark results, **When** quality delta exceeds 5% degradation in ANY domain, **Then** warning is logged and domain flagged for review

---

### User Story 4 - Reproducible Colab Notebook (Priority: P4)

A developer uses a pre-configured Google Colab notebook to reproduce the entire pruning pipeline, enabling future iterations and model updates.

**Why this priority**: Ensures maintainability - future model updates or different pruning rates can be easily applied without re-learning the process.

**Independent Test**: Open notebook in fresh Colab session with A100, run all cells, and verify pruned model is produced.

**Acceptance Scenarios**:

1. **Given** Colab Pro+ account with A100 runtime, **When** user opens notebook and sets Cerebras API key, **Then** all dependencies install successfully
2. **Given** configured notebook, **When** user runs dataset generation cells, **Then** calibration dataset is created and saved to Drive
3. **Given** calibration dataset, **When** user runs pruning cells, **Then** pruned model checkpoint is saved to Drive with training logs

---

### Edge Cases

- What happens when Cerebras API rate limit is reached during dataset generation?
- How does system handle A100 OOM during pruning of full GLM-4.7-Flash model?
- What happens when llama.cpp conversion fails due to unsupported architecture changes?
- How does system handle partial dataset generation (interrupted session)?

## Requirements *(mandatory)*

### Functional Requirements

**Dataset Generation**
- **FR-001**: System MUST generate multi-domain calibration dataset using Cerebras API (Qwen-3-235B) with at least 1000 examples
- **FR-002**: Dataset MUST include balanced representation across domains:
  - Code: algorithms, debugging, code explanation (20%)
  - Mathematics: algebra, calculus, statistics, probability (20%)
  - Physics: mechanics, thermodynamics, electromagnetism, quantum (15%)
  - Chemistry: organic, inorganic, biochemistry (15%)
  - Biology: molecular, genetics, ecology, anatomy (15%)
  - Socratic tutoring: multi-domain hint generation (15%)
- **FR-003**: Each domain example MUST include step-by-step reasoning or solution
- **FR-004**: Dataset format MUST be compatible with REAP calibration requirements

**Pruning Process**
- **FR-005**: System MUST apply REAP expert pruning algorithm to GLM-4.7-Flash base model
- **FR-006**: Pruning MUST target 30-40% expert reduction (from 23B to 19-20B total parameters)
- **FR-007**: System MUST preserve at least 95% of baseline accuracy across ALL domains after pruning
- **FR-008**: System MUST run on Google Colab Pro+ with A100 40GB or 80GB GPU
- **FR-009**: Total compute time MUST fit within 100 compute unit budget (A100 40GB) or 75 compute unit budget (A100 80GB)
- **FR-010**: System MUST checkpoint progress to Google Drive for resumability

**Model Conversion**
- **FR-011**: System MUST convert pruned model to GGUF format compatible with Ollama
- **FR-012**: GGUF conversion MUST use Q4_K_M quantization for optimal quality/size balance
- **FR-013**: System MUST provide Modelfile template for Ollama registration

**Validation**
- **FR-014**: System MUST validate pruned model on multi-domain benchmark suite before conversion
- **FR-015**: Validation MUST include: GSM8K (math), HumanEval (code), SciQ (science), MMLU-STEM

### Key Entities

- **CalibrationDataset**: Collection of multi-domain STEM examples for REAP saliency calculation. Attributes: examples (list), format (REAP-compatible JSON), domains (code, math, physics, chemistry, biology), task_types (problem_solving, code_generation, socratic_hints)
- **DomainDistribution**: Balance of examples across domains. Attributes: domain_name, example_count, percentage, subtopics
- **PrunedModel**: GLM-4.7-Flash with reduced experts. Attributes: base_model, pruning_rate, preserved_experts, total_params, active_params
- **GGUFArtifact**: Quantized model file for Ollama. Attributes: quantization_type, file_size, compatible_backends
- **BenchmarkResult**: Multi-domain quality validation output. Attributes: model_name, domain_scores (dict), overall_accuracy, latency_metrics, comparison_delta_per_domain

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Quality Preservation (per domain)**
- **SC-001**: Pruned model achieves at least 95% of baseline accuracy on GSM8K (math reasoning)
- **SC-002**: Pruned model achieves at least 95% of baseline accuracy on HumanEval (code generation)
- **SC-003**: Pruned model achieves at least 95% of baseline accuracy on SciQ/ARC (science knowledge)
- **SC-004**: Pruned model achieves at least 95% of baseline accuracy on MMLU-STEM subset

**Size Reduction**
- **SC-005**: Total model size reduced by at least 15% (from 23B to 19-20B parameters)
- **SC-006**: GGUF file size under 12GB with Q4_K_M quantization

**Performance**
- **SC-007**: First token latency under 3 seconds on RTX 2080 with partial offload
- **SC-008**: Generation speed at least 5 tokens per second on target hardware

**Process Efficiency**
- **SC-009**: Complete pipeline runs within 8 hours of A100 compute time
- **SC-010**: Calibration dataset generation completes within 30 minutes using Cerebras API with key rotation
- **SC-011**: Model loads successfully in Ollama and responds to queries across all STEM domains
