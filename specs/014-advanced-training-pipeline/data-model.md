# Data Model: Advanced STEM Training Pipeline

**Feature**: 014-advanced-training-pipeline
**Date**: 2026-02-12

## Entities

### Training Problem

A STEM problem used across all pipeline stages.

| Field | Type | Description |
|-------|------|-------------|
| prompt | string | Problem statement text |
| answer | string | Verified correct answer |
| domain | enum | math, physics, chemistry, biology, cs |
| difficulty | enum | easy, medium, hard (classified by sort_curriculum.py) |
| type | enum | verifiable, conceptual |
| problem_id | string | Unique identifier (hash of prompt) |

**Source**: HuggingFace dataset `Siesher/mits-stem-training-data` (gspo config)

**Relationships**:
- Used by all pipeline stages
- Classified by sort_curriculum.py into difficulty tiers
- Evaluated by verify_answers.py for correctness checking

### Model Checkpoint

A LoRA adapter representing one pipeline stage's output.

| Field | Type | Description |
|-------|------|-------------|
| adapter_path | path | Directory containing adapter_model.safetensors + adapter_config.json |
| training_config | JSON | Hyperparameters, stage name, metrics |
| stage | enum | sft, gspo, raft, star, dpo |
| base_model | string | HuggingFace model ID (e.g., unsloth/Qwen3-4B) |
| parent_checkpoint | path | Previous stage's checkpoint path |

**Flow**: SFT -> GSPO -> RAFT++ -> AdaSTaR -> DPO

**Storage**: Google Drive (`/content/drive/MyDrive/MITS/checkpoints/{stage}_qwen3_4b/`)

### Staleness Record (AdaSTaR)

Per-problem tracking for adaptive selection in STaR iterations.

| Field | Type | Description |
|-------|------|-------------|
| problem_id | string | References Training Problem |
| last_correct_iter | int | Last iteration where a correct completion was generated |
| difficulty | enum | easy, medium, hard |
| attempt_count | int | Total generation attempts across all iterations |
| correct_count | int | Total correct completions generated |
| priority_score | float | Computed: staleness_weight * staleness + difficulty_weight * difficulty_score |

**Lifecycle**: Created at AdaSTaR start, updated each iteration, used for MinHeap selection.

### Preference Pair (DPO)

A pair of completions for DPO training.

| Field | Type | Description |
|-------|------|-------------|
| prompt | string | Formatted prompt (with system message + chat template) |
| chosen | string | Correct completion with highest format score |
| rejected | string | Incorrect completion or correct with lowest format score |
| domain | string | Problem domain |
| chosen_correctness | float | 1.0 (always correct) |
| chosen_format_score | float | Format reward score [0, 1] |
| rejected_correctness | float | 0.0 or 1.0 |
| rejected_format_score | float | Format reward score [0, 1] |

**Lifecycle**: Generated before DPO training, consumed by TRL DPOTrainer.

### Evaluation Metrics (JSON)

Saved after each pipeline stage.

```json
{
  "stage": "gspo|raft|star|dpo",
  "domain_results": {
    "math": {"avg_reward": 0.75, "accuracy": 0.80, "total": 100},
    "physics": {"avg_reward": 0.60, "accuracy": 0.65, "total": 50}
  },
  "training_log": {
    "steps": 600,
    "final_loss": 0.45,
    "metrics": {}
  },
  "config": {
    "G": 16,
    "learning_rate": 2e-6,
    "hardware": "A100 40GB"
  }
}
```

## State Transitions

```
Training Problem
  ├── [sort_curriculum] → classified (easy/medium/hard)
  ├── [GSPO] → used for RL training (curriculum order)
  ├── [RAFT++] → N completions generated → filtered → SFT data
  ├── [AdaSTaR] → staleness tracked → adaptive selection → SFT data
  └── [DPO] → preference pairs generated → DPO training data

Model Checkpoint
  SFT checkpoint
    → GSPO training → GSPO checkpoint
      → RAFT++ SFT → RAFT checkpoint
        → AdaSTaR iterations → STaR checkpoint
          → DPO training → Final DPO checkpoint
```
