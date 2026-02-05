# Data Model: GLM STEM Pruning

**Feature**: 003-glm-math-pruning
**Date**: 2026-01-31

## Entities

### CalibrationExample

A single training example for REAP calibration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| instruction | string | Yes | The task description or question |
| input | string | No | Additional context (empty for most examples) |
| output | string | Yes | Expected response with step-by-step reasoning |
| domain | string | Yes | One of: code, math, physics, chemistry, biology, socratic |
| subtopic | string | Yes | Specific subtopic within domain |
| difficulty | string | Yes | One of: basic, intermediate, advanced |

**Example**:
```json
{
  "instruction": "Solve the differential equation: dy/dx = 2xy",
  "input": "",
  "output": "This is a separable differential equation. Let me solve it step by step:\n\nStep 1: Separate variables\ndy/y = 2x dx\n\nStep 2: Integrate both sides\n∫(1/y)dy = ∫2x dx\nln|y| = x² + C\n\nStep 3: Solve for y\ny = e^(x² + C) = Ae^(x²)\n\nwhere A = e^C is an arbitrary constant.\n\nFinal answer: y = Ae^(x²)",
  "domain": "math",
  "subtopic": "differential_equations",
  "difficulty": "intermediate"
}
```

### CalibrationDataset

Collection of examples for REAP pruning.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| version | string | Yes | Dataset version (semver) |
| created_at | datetime | Yes | Generation timestamp |
| generator_model | string | Yes | Model used to generate examples |
| total_examples | integer | Yes | Total count of examples |
| domain_distribution | object | Yes | Count per domain |
| examples | array[CalibrationExample] | Yes | The calibration examples |

### DomainDistribution

Balance of examples across STEM domains.

| Domain | Target Count | Target % | Subtopics |
|--------|--------------|----------|-----------|
| code | 200 | 20% | python, algorithms, debugging, data_structures, oop |
| math | 200 | 20% | algebra, calculus, statistics, probability, linear_algebra, trigonometry |
| physics | 150 | 15% | mechanics, thermodynamics, electromagnetism, waves, quantum |
| chemistry | 150 | 15% | organic, inorganic, biochemistry, stoichiometry, reactions |
| biology | 150 | 15% | molecular, genetics, ecology, anatomy, evolution |
| socratic | 150 | 15% | hints, questions, misconceptions, scaffolding |

### PruningConfig

Configuration for REAP pruning run.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| base_model | string | Yes | HuggingFace model ID |
| pruning_method | string | Yes | "reap" (fixed) |
| pruning_rate | float | Yes | Fraction of experts to prune (0.0-0.5) |
| calibration_dataset | string | Yes | Path to calibration JSONL |
| seed | integer | Yes | Random seed for reproducibility |
| num_samples | integer | Yes | Number of calibration samples |
| max_seq_length | integer | Yes | Maximum sequence length (2048) |

### PrunedModelMetadata

Metadata for the output pruned model.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| base_model | string | Yes | Original model ID |
| pruned_model_name | string | Yes | Name for pruned model |
| total_params_before | integer | Yes | Parameters before pruning |
| total_params_after | integer | Yes | Parameters after pruning |
| active_params | integer | Yes | Active parameters per forward pass |
| experts_removed | integer | Yes | Number of experts pruned |
| experts_remaining | integer | Yes | Number of experts kept |
| pruning_rate_actual | float | Yes | Actual pruning rate achieved |
| calibration_dataset_hash | string | Yes | SHA256 of calibration data |

### BenchmarkResult

Results from multi-domain validation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| model_name | string | Yes | Model being evaluated |
| benchmark_name | string | Yes | Name of benchmark |
| domain | string | Yes | Primary domain tested |
| score | float | Yes | Accuracy or pass rate |
| baseline_score | float | Yes | Baseline model score |
| retention_rate | float | Yes | score / baseline_score |
| samples_tested | integer | Yes | Number of samples |
| timestamp | datetime | Yes | Evaluation timestamp |

### GGUFArtifact

Metadata for converted GGUF file.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| filename | string | Yes | GGUF filename |
| source_model | string | Yes | HuggingFace model used |
| quantization | string | Yes | Quantization type (Q4_K_M) |
| file_size_bytes | integer | Yes | Size of GGUF file |
| sha256 | string | Yes | File hash for integrity |
| ollama_model_name | string | Yes | Name in Ollama registry |

## Relationships

```
CalibrationDataset
    └── contains many → CalibrationExample

PruningConfig
    └── references → CalibrationDataset
    └── produces → PrunedModelMetadata

PrunedModelMetadata
    └── converts to → GGUFArtifact
    └── validated by → BenchmarkResult (many)
```

## Validation Rules

### CalibrationExample
- `instruction` must be non-empty and < 1000 characters
- `output` must be non-empty and contain step-by-step reasoning
- `domain` must be one of the 6 defined domains
- `difficulty` must be one of: basic, intermediate, advanced

### CalibrationDataset
- `total_examples` must equal len(examples)
- Domain distribution must match ±5% of targets
- No duplicate instructions within dataset

### BenchmarkResult
- `retention_rate` must be >= 0.95 for all domains
- If any domain fails, flag for review
