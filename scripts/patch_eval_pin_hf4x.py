"""Pin HF stack to 4.x — transformers 5.x bleeding edge ломает Colab numpy/torch.

Реальный fail на A100 80GB (после run #N):
  - numpy 2.4.4 → scipy/sklearn ABI mismatch → cannot import transformers
  - torch upgraded 2.10+cu128 → 2.11+cu130 → causal-conv1d wheels нет
  - 20+ Colab dependency conflicts (pandas, gradio, numba, bigframes...)

Решение — таргетный install без eager:
  1. transformers >= 4.55, < 5.0 (Qwen3.5 supported, stable, no breaking)
  2. eager только для HF triplet (transformers + hub + tokenizers — tightly coupled)
  3. Остальное — обычный install, не трогает torch/numpy
  4. causal-conv1d skip — pre-built wheel не существует для Colab cu128/cu130
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


cell1 = nb['cells'][1]
src = get_src(cell1)


# ─── 1. Replace eager install block ────────────────────────────────────
old_install = '''# Latest unpinned transformers нужен для qwen3_5 model_type (Qwen3.5 — март 2026).
# `--upgrade-strategy eager` форсирует upgrade всех HF deps вместе, иначе старый
# huggingface_hub сохраняется и ломает import `is_offline_mode`.
!pip install -q -U --upgrade-strategy eager \\
    transformers huggingface_hub tokenizers accelerate peft bitsandbytes \\
    datasets trl openai python-dotenv'''

new_install = '''# Pin HF stack к 4.x — transformers 5.x (bleeding edge) на Colab тянет numpy 2.4
# / torch 2.11+cu130, что ломает scipy/sklearn/numba ABI каскадом. transformers
# 4.55+ имеет полную поддержку Qwen3.5 (model_type=qwen3_5), этого достаточно
# для inference. eager только для HF triplet (tightly coupled) — остальное без
# -U, чтобы не трогать torch/numpy/pandas (Colab default 2.10+cu128 + numpy 2.x).
!pip install -q -U --upgrade-strategy eager "transformers>=4.55,<5.0" "huggingface_hub>=0.25,<1.0" "tokenizers>=0.20,<0.22"
!pip install -q peft accelerate bitsandbytes datasets python-dotenv openai'''

assert old_install in src, 'Anchor "eager install" not found in cell 1'
src = src.replace(old_install, new_install)


# ─── 2. Replace fla + causal-conv1d speedup block ─────────────────────
# (added by previous patch — full block including all comments)
old_speedup = '''# ─── Hybrid-attention speedups for Qwen3.5 ────────────────────
# Qwen3.5 hybrid blocks (GDN linear-attention + causal conv1d) need these libs.
# Без них transformers warn "fast path is not available" → torch fallback ~2-3x slower.
# fla — Triton-based, no CUDA toolkit needed (works в Colab по умолчанию).
# causal-conv1d — native CUDA, pre-built wheel обычно подтянется автоматически.
print('Installing hybrid-attention speedups (Qwen3.5 fast path)...')
!pip install -q flash-linear-attention 2>&1 | tail -3
import subprocess as _sp
_r = _sp.run(['pip', 'install', '-q', 'causal-conv1d>=1.4.0', '--no-build-isolation'],
             capture_output=True, text=True, timeout=600)
if _r.returncode == 0:
    print('  causal-conv1d: installed (CUDA fast path enabled)')
else:
    _tail = (_r.stderr or _r.stdout or '')[-300:]
    print(f'  causal-conv1d: FAILED — falling back to torch (slower).\\n    stderr tail: {_tail}')

'''

new_speedup = '''# ─── Hybrid-attention speedup for Qwen3.5 (Triton-only) ───────
# fla — Triton-based, version-agnostic, works на любом GPU/CUDA combo.
# causal-conv1d — native CUDA, pre-built wheels существуют только для cu118/121/124
# + torch 2.4-2.5. На Colab cu128 (default) или cu130 (eager-upgraded) wheel нет, а
# source build падает (Colab images не имеют nvcc toolkit).
# На A100 sm_80 native torch SDPA path всё равно ~30-50 tok/s — приемлемо даже без
# fla/conv1d. Triton-based fla даёт небольшой bonus если transformers 4.x его юзает.
print('Installing flash-linear-attention (Triton)...')
!pip install -q flash-linear-attention 2>&1 | tail -3 || echo 'fla install failed (continuing)'
print('Note: causal-conv1d skipped — no compat pre-built wheel for Colab torch+CUDA.')

'''

assert old_speedup in src, 'Anchor "Hybrid-attention speedups" not found in cell 1'
src = src.replace(old_speedup, new_speedup)


set_src(cell1, src)
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Cell 1 patched: HF stack pinned to 4.x, causal-conv1d skipped')
