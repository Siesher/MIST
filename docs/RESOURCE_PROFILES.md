# MITS Resource Profiles

MITS supports three hardware profiles to scale from budget laptops to
workstation-class machines. Each profile chooses an appropriate LLM
quantization, context length, and feature set.

## Quick Start

```bash
# Detect recommended profile automatically:
python scripts/detect_resources.py --list

# Override explicitly:
export MITS_PROFILE=lite        # or: standard, max
python scripts/detect_resources.py --verbose
```

## Profile Matrix

| Feature | Lite | Standard | Max |
|---------|:----:|:--------:|:---:|
| **Min RAM (GB)** | 15 | 30 | 60 |
| **Min VRAM (GB)** | 0 (CPU) | 6 | 24 |
| **LLM quantization** | Q4_K_M | Q5_K_M | FP16 |
| **LLM context (tokens)** | 4096 | 8192 | 32768 |
| **Expected speed (tok/s)** | ~12 | ~35 | ~80+ |
| **Knowledge Forge** | yes | yes | yes |
| **Living KG (rule-based)** | yes | yes | yes |
| **LLM-verified proposals** | no | yes | yes |
| **Source Extractor** | slow | fast | batched |
| **Navigator tool calling** | yes | yes | yes |
| **BKT knowledge tracing** | yes | yes | yes |
| **DKT (deep KT)** | no | yes | yes |
| **RuBERT affect detection** | no | yes | yes |
| **Rule-based affect** | yes | yes | yes |
| **Batch inference** | no | yes | yes |
| **Speculative decoding** | no | no | yes |
| **Max concurrent sessions** | 1 | 3 | 16 |

## Profile Rationale

### Lite (16 GB RAM laptop, no GPU)

Budget-friendly setup for an individual student on a mid-range laptop.
The 9B model runs on CPU via `Q4_K_M` GGUF (~5.5 GB), leaving ~10 GB for
the OS, the app, and session data.

**What works fully:**
- Knowledge Forge graph navigation (pure Python, ~100 KB in RAM)
- Living KG self-completion (rule-based verifier only)
- Ollama tool calling (5 navigator tools)
- BKT knowledge tracing
- Rule-based affect detection
- All tutoring agents

**What's disabled to fit:**
- RuBERT affect detector (would add ~500 MB + latency)
- Deep Knowledge Tracing (LSTM adds CPU overhead)
- LLM verifier for graph proposals (extra LLM calls)
- Batch inference and speculative decoding

**Expected user experience:** single-student use, ~12 tokens/sec, graph
operations feel instant.

### Standard (32 GB RAM, mid-range GPU: GTX 1660 Ti / RTX 3060 / 4060)

Recommended setup for a desktop or mid-range laptop with GPU. The 9B
model runs on GPU in `Q5_K_M` (~6.5 GB VRAM). All innovation features
enabled.

**Additional features vs lite:**
- RuBERT-based emotion detection (frustration, confusion)
- Deep Knowledge Tracing (more accurate than pure BKT)
- LLM-verified graph proposals (pedagogical soundness check)
- Small batch inference

### Max (64+ GB RAM, high-end GPU: RTX 4090 / A100 / cloud API)

Full-capability setup for research, evaluation runs, or multi-student
deployments. FP16 model, 32K context, all optimizations on.

**Additional features vs standard:**
- 32K context for long sessions
- Speculative decoding (~2x speedup)
- Up to 16 concurrent students
- Larger navigator frontier results (20 vs 10 vs 5)

## Environment Variable

Override the auto-detected profile:

```bash
# Windows PowerShell
$env:MITS_PROFILE = "lite"

# Bash / macOS
export MITS_PROFILE=lite
```

Valid values: `lite`, `standard`, `max`.

## Profile Detection

The detector at `scripts/detect_resources.py` uses `psutil` for RAM and
`torch.cuda` for VRAM. It picks the largest profile whose minimum
requirements are satisfied.

Thresholds are set slightly below sticker specs to account for OS
overhead:
- 16 GB RAM stick → typically reports ~15.1 GB available → matches Lite
- 32 GB RAM stick → typically reports ~31.1 GB → matches Standard
- 64 GB RAM stick → typically reports ~63 GB → matches Max

## Feature Flags in Code

Components that have resource-sensitive paths check
`src.resource_profiles.feature_enabled()`:

```python
from src.resource_profiles import feature_enabled

if feature_enabled("enable_rubert_affect"):
    # Load the heavy model
    detector = RuBERTAffectDetector()
else:
    # Use lightweight rule-based fallback
    detector = RuleBasedAffectDetector()
```

Relevant flags:
- `enable_rubert_affect`
- `enable_dkt`
- `enable_llm_verifier`
- `enable_source_extractor`
- `enable_batch_inference`
- `enable_speculative_decoding`

Integer tunables:
- `max_tool_rounds` — how many LLM tool rounds per turn
- `max_concurrent_sessions` — how many students at once
- `navigator_max_frontier` — cap on frontier results

## Knowledge Forge on Lite

**Good news: Knowledge Forge and Living KG are effectively free on CPU.**

| Operation | Complexity | Lite latency |
|-----------|-----------|--------------|
| Load forge.json (81 nodes) | O(N) | ~50 ms |
| `explore_concept` | O(degree) | < 1 ms |
| `diagnose_gap` | O(V+E) DFS | < 5 ms |
| `find_optimal_path` | O((V+E) log V) Dijkstra | < 10 ms |
| `get_learning_frontier` | O(V × avg_degree) | < 20 ms |
| Session analysis (1 session) | O(errors × candidates) | < 5 ms |
| Rule-based verifier per proposal | O(V+E) worst case | < 10 ms |

The only LLM-dependent features are **Source Extractor** (offline
document ingestion) and the optional **LLM verifier**. On Lite, the
former is slow but works; the latter is disabled.
