"""Match training stack: Unsloth + transformers 5.x + torchvision 0.23.

Root cause discovered after run #N с pinned transformers 4.55:
  ValueError: model type `qwen3_5` not recognized
  → 4.55.4 вышла ДО релиза Qwen3.5 (март 2026).
  → Qwen3.5-9B = image-text-to-text (multimodal), Model Class
    AutoModelForImageTextToText, NOT AutoModelForCausalLM.

Training notebook (grpo_qwen3.5_9b.ipynb cell 1) использует:
  - transformers >= 5.0.0 (qwen3_5 architecture support)
  - Unsloth FastLanguageModel (multimodal-as-text abstraction)
  - torchvision >= 0.23 (matches torch 2.11)

For honest re-eval Path A: replicate training stack EXACTLY. Это даёт:
  1. Identical inference path для всех трёх (base, GSPO, KTO)
  2. Adapter saved by Unsloth → loaded by Unsloth = canonical path
  3. Cell 1 training proven to work on Colab (training was successful)

Trade-off vs pure-HF: heavier install (Unsloth), требуется RESTART RUNTIME
после Cell 1. Sentinel /content/.install_done_v2 предотвращает повторный
install после restart — user re-runs Cell 1, install skipped, imports run.

Cell 5 model loading: AutoModelForCausalLM → FastLanguageModel.from_pretrained
с FastLanguageModel.for_inference() после adapter merge.
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


# ─── 1. Replace Cell 1 entirely ──────────────────────────────────────
new_cell1 = '''# Cell 1: Setup (Path A — replicate training stack exactly)
# First run: install training-matched stack → RESTART RUNTIME → re-run this cell.
# Sentinel /content/.install_done_v2 gates install; after restart imports load.
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

# ─── Install (FIRST RUN ONLY — gated by sentinel) ─────────
# Stack matches grpo_qwen3.5_9b.ipynb cell 1 (proven working on Colab).
SENTINEL = '/content/.install_done_v2'
if not os.path.exists(SENTINEL):
    print('=== Installing training-matched stack ===')
    print('  (transformers 5.x for qwen3_5 + Unsloth for multimodal-as-text)')
    # Step 1: Unsloth core
    !pip install -q --upgrade --force-reinstall --no-cache-dir unsloth unsloth_zoo
    # Step 2: transformers v5 (Qwen3.5 hybrid arch support)
    !pip install -q "transformers>=5.0.0" trl peft datasets
    # Step 3: torchvision matching torch 2.11 (PIL._typing._Ink fix)
    !pip install -q --upgrade scipy "torchvision>=0.23.0"
    # Step 4: Other deps (eval needs python-dotenv + openai for Cerebras client)
    !pip install -q accelerate bitsandbytes sentencepiece protobuf loguru python-dotenv openai
    !pip install -q sympy chempy
    # Step 5: FLA — Triton-based DeltaNet kernels (24/32 layers in Qwen3.5-9B)
    !pip install -q flash-linear-attention 2>&1 | tail -3

    Path(SENTINEL).touch()
    print('=' * 60)
    print('  Install complete. RESTART RUNTIME NOW:')
    print('    Runtime → Restart session')
    print('  After restart: re-run THIS cell — install will skip.')
    print('=' * 60)
    raise SystemExit('Restart required — re-run this cell after Runtime → Restart session.')

# ─── Post-restart imports ─────────────────────────────────
# HOTFIX for PIL._typing._Ink (Pillow 12 + torchvision pre-0.23 incompatibility)
try:
    from PIL import _typing
    if not hasattr(_typing, '_Ink'):
        import sys
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '--upgrade',
                              'torchvision>=0.23.0', 'pillow<12.0.0'])
except ImportError:
    pass

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

# Sanity: transformers 5.x required for qwen3_5
print(f'transformers: {transformers.__version__} | huggingface_hub: {huggingface_hub.__version__} | torch: {torch.__version__}')
assert transformers.__version__.startswith('5.'), (
    f'transformers must be 5.x for Qwen3.5 (model_type=qwen3_5). '
    f'Current: {transformers.__version__}. Restart runtime if just installed.'
)

PROJECT_ROOT = Path('/content/MITS')
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env from Drive (Cerebras keys + optional HF_TOKEN)
ENV_PATH = Path('/content/drive/MyDrive/MITS_secrets/.env')
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
    print(f'Loaded env from {ENV_PATH}')
    if os.environ.get('HF_TOKEN'):
        from huggingface_hub import login as hf_login
        hf_login(token=os.environ['HF_TOKEN'])
        print('HF authenticated via .env')
    else:
        print('Warning: HF_TOKEN missing in .env — adapter download may 401 if private.')
else:
    print(f'No .env at {ENV_PATH}. Cerebras judge will fail in Phase 0b.')

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


# ─── 2. Replace Cell 5 (model loading) — Unsloth path ────────────────
new_cell5 = '''# Cell 5: Model loading via Unsloth (matches training stack from grpo_qwen3.5_9b.ipynb)
BASE_MODEL_ID = 'Qwen/Qwen3.5-9B'  # matches BASE_MODEL in training notebook
MAX_SEQ_LENGTH = 4096  # covers thinking budget 2048 + completion + headroom

ADAPTERS = {
    'base': None,
    'gspo': 'Siesher/mits-qwen3-9b-gspo',
    'kto':  'Siesher/mits-qwen3-9b-kto',
}


def load_model_with_adapter(adapter_id: str | None):
    """Load Qwen3.5-9B via Unsloth FastLanguageModel, optionally apply LoRA + merge.

    Why Unsloth: Qwen3.5-9B is image-text-to-text (multimodal) с Model Class
    AutoModelForImageTextToText. AutoModelForCausalLM не работает напрямую.
    FastLanguageModel.from_pretrained абстрагирует text-only branch loading,
    skipping vision tower (saves ~2GB VRAM + matches training stack exactly).

    Adapter merge_and_unload даёт plain HF model для inference path,
    FastLanguageModel.for_inference активирует Unsloth fast kernels.
    """
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL_ID,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=False,
        dtype=torch.bfloat16,
    )
    # Unsloth wraps tokenizer in some versions — unwrap if needed.
    if not hasattr(tokenizer, 'vocab_size') and hasattr(tokenizer, 'tokenizer'):
        tokenizer = tokenizer.tokenizer

    if adapter_id:
        model = PeftModel.from_pretrained(model, adapter_id)
        model = model.merge_and_unload()
        logger.info(f'Merged adapter {adapter_id}')

    FastLanguageModel.for_inference(model)
    return model, tokenizer


def generate_one(model, tokenizer, prompt: str) -> str:
    messages = [
        {'role': 'system', 'content': DECODING_CONFIG['system_prompt']},
        {'role': 'user', 'content': prompt},
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
        enable_thinking=DECODING_CONFIG['enable_thinking'],
    )
    inputs = tokenizer(text, return_tensors='pt').to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=DECODING_CONFIG['num_predict'],
            do_sample=DECODING_CONFIG['temperature'] > 0,
            temperature=max(DECODING_CONFIG['temperature'], 1e-5),
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    completion = tokenizer.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
    return completion
'''

cell5 = nb['cells'][5]
old_cell5 = get_src(cell5)
assert 'BASE_MODEL_ID' in old_cell5 and 'AutoModelForCausalLM' in old_cell5, (
    'Cell 5 anchor not found'
)
set_src(cell5, new_cell5)


# ─── 3. Update Cell 0 markdown intro ─────────────────────────────────
cell0 = nb['cells'][0]
old_md = get_src(cell0)
new_md = old_md.replace(
    '**Структура**:\n1. Setup (paths, imports, .env)\n',
    '**Структура**:\n1. Setup (install training stack → **RESTART RUNTIME** → imports/.env)\n',
)
if new_md != old_md:
    set_src(cell0, new_md)


NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Patched: Cell 1 (Unsloth + transformers 5.x install + post-restart imports)')
print('         Cell 5 (FastLanguageModel.from_pretrained loading)')
print('         Cell 0 (markdown updated with restart note)')
