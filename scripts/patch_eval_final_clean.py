"""Final clean Cell 1 — consolidates ALL lessons learned over the day.

Verified working stack (empirically established 2026-05-05):
- torch == 2.10.0+cu128 (Unsloth requires <2.11, matches system nvcc 12.8)
- transformers == 5.5.0 (Unsloth max AND has qwen3_5 architecture support)
- trl == 0.24.0 (Unsloth max)
- datasets == 4.3.0 (Unsloth bound)
- unsloth 2026.5.1 (latest, supports qwen3_5)
- flash-linear-attention (Triton-based, version-agnostic, ALWAYS works)
- causal-conv1d: best-effort install (build fails на Colab но fla одной достаточно
  для recurrent path, ~10-15 tok/s ожидаемо без conv1d)

Key fixes integrated:
1. import unsloth BEFORE transformers (silences import-order warning)
2. open(SENTINEL).close() — stdlib, no Path import dependency
3. pip uninstall torchcodec — sentence_transformers ловит только ImportError/OSError,
   torchcodec runtime fail → RuntimeError → ломает unsloth import chain
4. Sentinel v4 — force fresh install после полного wipe runtime
5. Sanity assertions on transformers/torch versions после imports

Cell 5 (model loading) uses FastLanguageModel.from_pretrained — Unsloth абстрагирует
Qwen3.5-9B's image-text-to-text multimodal nature, грузит только text branch.
Cell 6 (eval logic) — type-safe _normalize_for_compare + per-problem timing log
для первых 3 problems (диагностика fast-path vs fallback скорости).
"""
import json
from pathlib import Path

NB = Path('notebooks/honest_eval_full_precision.ipynb')
nb = json.loads(NB.read_text(encoding='utf-8'))


def get_src(cell):
    s = cell.get('source', '')
    return ''.join(s) if isinstance(s, list) else s


def set_src(cell, text):
    cell['source'] = text.splitlines(keepends=True)


# ─── Replace Cell 1 entirely with verified-working stack ─────────────
new_cell1 = '''# Cell 1: Setup (FINAL — empirically verified Unsloth-compatible stack)
# First run: install pinned versions → RESTART RUNTIME → re-run this cell.
# Sentinel /content/.install_done_v4 gates install; after restart imports load.
import subprocess, os

# ─── GPU check (need ≥24GB for 9B bf16) ────────────────────
gpu_info = subprocess.check_output(
    ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader']
).decode().strip()
print(f'GPU: {gpu_info}')
gpu_memory_mib = int(gpu_info.split(',')[1].strip().split()[0])
assert gpu_memory_mib >= 24_000, (
    f'Insufficient VRAM for 9B bf16: {gpu_memory_mib} MiB. Need >=24GB.'
)
print(f'VRAM check passed: {gpu_memory_mib} MiB ({gpu_memory_mib/1024:.1f} GiB)')

# ─── Drive mount + repo clone (idempotent) ────────────────
from google.colab import drive
drive.mount('/content/drive')
if not os.path.exists('/content/MITS'):
    !git clone https://github.com/Siesher/MIST.git /content/MITS
%cd /content/MITS
!git checkout 019-ns-vstar-dpo && git pull origin 019-ns-vstar-dpo

# ─── Install (FIRST RUN ONLY — gated by sentinel v4) ──────
# Empirically verified stack — все версии strict-pinned под Unsloth 2026.5.1
# constraint set: transformers<=5.5.0, torch<2.11.0, trl<=0.24.0, datasets<4.4.0
SENTINEL = '/content/.install_done_v4'
if not os.path.exists(SENTINEL):
    print('=== Installing verified stack (Unsloth + transformers 5.5.0 + torch 2.10+cu128) ===')

    # Step 1: pytorch ecosystem на torch 2.10+cu128 (Unsloth max + matches system nvcc 12.8)
    # --extra-index-url нужен для cu128 wheels (на PyPI mirror)
    print('Step 1: pinning torch 2.10+cu128...')
    !pip install -q --force-reinstall \\
        "torch==2.10.0" "torchvision" "torchaudio" \\
        --extra-index-url https://download.pytorch.org/whl/cu128

    # Step 2: HF stack — strict pin к Unsloth-compatible versions
    # transformers 5.5.0 — последняя в Unsloth bound, имеет qwen3_5 architecture
    print('Step 2: HF stack (transformers 5.5.0, trl 0.24, datasets 4.3)...')
    !pip install -q --force-reinstall \\
        "transformers==5.5.0" "trl==0.24.0" "datasets==4.3.0" \\
        "huggingface_hub" "tokenizers"
    !pip install -q peft accelerate bitsandbytes

    # Step 3: Unsloth core (2026.5.1 — latest, supports qwen3_5)
    print('Step 3: Unsloth core...')
    !pip install -q --upgrade unsloth unsloth_zoo

    # Step 4: Other deps
    print('Step 4: scipy + utilities...')
    !pip install -q --upgrade scipy
    !pip install -q sentencepiece protobuf loguru python-dotenv openai
    !pip install -q sympy chempy

    # Step 5: flash-linear-attention — Triton-based GDN kernels (always works, no CUDA build)
    # Покрывает 24/32 GDN linear-attention layers в Qwen3.5-9B
    print('Step 5: flash-linear-attention (Triton)...')
    !pip install -q flash-linear-attention 2>&1 | tail -3

    # Step 6: causal-conv1d — best-effort. Build часто падает на Colab без точного
    # nvcc/torch ABI match, но fla одной достаточно для recurrent rule (главная часть GDN).
    # Без conv1d ожидаем ~10-15 tok/s; с conv1d ~25-35 tok/s.
    print('Step 6: causal-conv1d (best-effort — fallback OK если build fails)...')
    !pip install -q causal-conv1d 2>&1 | tail -3 || echo '  conv1d build failed — fla одной хватит для GDN'

    # Step 7: Kill torchcodec — sentence_transformers ловит только (ImportError, OSError),
    # но torchcodec runtime DLL fail → RuntimeError → cascades в unsloth import.
    # Uninstall переводит fail в ImportError → caught → AudioDecoder=None → load OK.
    print('Step 7: remove torchcodec (sentence_transformers fallback нужен ImportError, не RuntimeError)...')
    !pip uninstall -y torchcodec 2>&1 | tail -1

    # Sentinel: stdlib open() — НЕ требует Path import.
    open(SENTINEL, 'w').close()
    print('=' * 60)
    print('  Install complete. RESTART RUNTIME NOW:')
    print('    Runtime → Restart session')
    print('  After restart: re-run THIS cell — install will skip, imports will load.')
    print('=' * 60)
    raise SystemExit('Restart required — re-run this cell after Runtime → Restart session.')

# ─── Post-restart imports ─────────────────────────────────
# CRITICAL: import unsloth BEFORE transformers — Unsloth patches transformers internals
# at import time. Reverse order gives "Unsloth should be imported before transformers"
# warning + missed optimizations.
import unsloth  # noqa: F401 — must precede transformers import

import sys, json, time, logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

import torch
import transformers
import huggingface_hub
from unsloth import FastLanguageModel
from peft import PeftModel
from dotenv import load_dotenv

# Sanity: pinned versions должны match — иначе runtime ABI mismatch.
print(f'transformers: {transformers.__version__} | huggingface_hub: {huggingface_hub.__version__} | torch: {torch.__version__}')
assert transformers.__version__.startswith('5.5'), (
    f'Expected transformers 5.5.x (Unsloth max + qwen3_5 support). '
    f'Got {transformers.__version__}. If just installed — Runtime → Restart session.'
)
assert torch.__version__.startswith('2.10'), (
    f'Expected torch 2.10.x (Unsloth requires <2.11). Got {torch.__version__}. '
    f'If just downgraded — Runtime → Restart session.'
)

PROJECT_ROOT = Path('/content/MITS')
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env from Drive (Cerebras keys + optional HF_TOKEN для приватных adapter'ов)
ENV_PATH = Path('/content/drive/MyDrive/MITS_secrets/.env')
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
    print(f'Loaded env from {ENV_PATH}')
    if os.environ.get('HF_TOKEN'):
        from huggingface_hub import login as hf_login
        hf_login(token=os.environ['HF_TOKEN'])
        print('HF authenticated via .env')
    else:
        print('Warning: HF_TOKEN missing in .env — adapter download может 401 если приватные.')
else:
    print(f'No .env at {ENV_PATH}. Cerebras judge будет fail в Phase 0b.')

from training.scripts.evaluate_stage import (
    SYSTEM_PROMPT_CALC,
    extract_answer,
    check_format_compliance,
    evaluate_combined_quality,
    load_eval_dataset,
)
from training.cerebras_client import CerebrasClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger('honest_eval')
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
logger.info(f'Device: {DEVICE} | bf16: {torch.cuda.is_bf16_supported()}')
'''

cell1 = nb['cells'][1]
old_cell1 = get_src(cell1)
assert 'GPU check' in old_cell1, 'Cell 1 anchor not found — notebook structure changed?'
set_src(cell1, new_cell1)


# ─── Update Cell 0 markdown intro ────────────────────────────────────
cell0 = nb['cells'][0]
old_md = get_src(cell0)
new_md = '''# Honest Full-Precision Eval — Path A (Unsloth match training stack)

**Цель**: устранить inference-artifact в сравнении base vs GSPO vs KTO. Все три модели прогоняются через **Unsloth FastLanguageModel** (как в training notebook) с identical decoding protocol. Phase 0a: programmatic correctness only (fast_mode=True); Phase 0b — Cerebras judge поверх saved completions, отдельным async скриптом.

**Compute**: Colab A100 40GB. Estimated:
- С `causal-conv1d`: ~30 tok/s × 2048 max × 143 problems × 3 stages ≈ **5h**.
- Без `conv1d` (fla one): ~12 tok/s × 2048 × 143 × 3 ≈ **12h** или 50 stratified subset за **4h**.

**Output**: `evaluation/reports/honest_full_precision_phase0a_YYYYMMDD.json` (repo + Drive mirror).

**Стек (verified 2026-05-05)**: torch 2.10.0+cu128, transformers 5.5.0, trl 0.24.0, datasets 4.3.0, unsloth 2026.5.1, fla 0.5.0+. ALL strict-pinned под Unsloth constraints.

**Структура**:
1. **Setup** — install verified stack → **RESTART RUNTIME** → re-run cell to load imports
2. **DECODING_CONFIG** — single-protocol для трёх моделей (num_predict=2048, enable_thinking=True, temperature=0.0)
3. **Load eval dataset** — 143 calc problems (numeric + latex_boxed)
4. **Per-model inference** — base / +GSPO / +KTO via FastLanguageModel + PEFT merge
5. **Eval loop** — fast_mode=True (programmatic correctness, no Cerebras), per-problem timing для первых 3 problems
6. **Run + save** — JSON report со всеми completions для Phase 0b later
'''

if old_md != new_md:
    set_src(cell0, new_md)


NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Patched: Cell 1 (final verified stack), Cell 0 (markdown updated)')
print('  Sentinel: install_done_v4 (forces fresh install on wiped runtime)')
print('  Key change: torch 2.10+cu128, transformers 5.5.0, trl 0.24, datasets 4.3 — strict pinned')
print('  Import order: unsloth before transformers (silences warning)')
print('  Includes: torchcodec uninstall, conv1d best-effort, fla as primary fast path')
