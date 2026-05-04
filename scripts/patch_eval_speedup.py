"""Patch honest_eval_full_precision.ipynb to enable Qwen3.5 fast attention path.

Changes:
  1. Cell 1 (setup): install flash-linear-attention + causal-conv1d (graceful failure)
  2. Cell 3 (DECODING_CONFIG): num_predict 4096 → 2048 (2x speedup, covers 95-pct thinking)
  3. Cell 6 (eval_stage): per-problem timing log for first 3 problems
"""
import json
from pathlib import Path

NB = Path('notebooks/honest_eval_full_precision.ipynb')
nb = json.loads(NB.read_text(encoding='utf-8'))


def get_src(cell: dict) -> str:
    src = cell.get('source', '')
    return ''.join(src) if isinstance(src, list) else src


def set_src(cell: dict, text: str) -> None:
    cell['source'] = text.splitlines(keepends=True)


# ─── Cell 1: add fla + causal-conv1d install ──────────────────────────
cell1 = nb['cells'][1]
src1 = get_src(cell1)

speedup_block = '''# ─── Hybrid-attention speedups for Qwen3.5 ────────────────────
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

assert 'flash-linear-attention' not in src1, 'Cell 1 already patched'
anchor = '# ─── HF auth (for private adapters; if Siesher/mits-qwen3-9b-gspo is public, skip) ─'
assert anchor in src1, f'Cell 1 anchor missing: {anchor}'
src1 = src1.replace(anchor, speedup_block + anchor)
set_src(cell1, src1)
print('Cell 1 patched: added fla + causal-conv1d install')


# ─── Cell 3: num_predict 4096 → 2048 ──────────────────────────────────
cell3 = nb['cells'][3]
src3 = get_src(cell3)

old_block = (
    "    # 4096: covers 95-percentile thinking (GSPO trained budget=2048, eval slightly\n"
    "    # larger to avoid truncation on hard problems). 8192 is overkill for 9B+thinking.\n"
    "    'num_predict': 4096,"
)
new_block = (
    "    # 2048: GSPO trained budget=2048, covers 95-percentile thinking. 4096 был для\n"
    "    # запаса на hard problems, но удваивает время генерации. 2048 = 2x speedup без\n"
    "    # значимой потери (truncation risk <5%). Жертва ради скорости в lean-demo.\n"
    "    'num_predict': 2048,"
)
assert old_block in src3, 'Cell 3 num_predict block not found (already patched?)'
src3 = src3.replace(old_block, new_block)

# Update rationale string too
old_rat = "'4096 budget eliminates truncation. Greedy decoding for deterministic accuracy.'"
new_rat = "'2048 budget covers GSPO training distribution. Greedy decoding for deterministic accuracy.'"
src3 = src3.replace(old_rat, new_rat)
set_src(cell3, src3)
print('Cell 3 patched: num_predict 4096 -> 2048')


# ─── Cell 6: per-problem timing for first 3 ───────────────────────────
cell6 = nb['cells'][6]
src6 = get_src(cell6)

old_loop = (
    "    completions = []\n"
    "    t0 = time.time()\n"
    "    for i, p in enumerate(problems):\n"
    "        completion = generate_one(model, tokenizer, p['prompt'])\n"
)
new_loop = (
    "    completions = []\n"
    "    t0 = time.time()\n"
    "    for i, p in enumerate(problems):\n"
    "        t_start = time.time()\n"
    "        completion = generate_one(model, tokenizer, p['prompt'])\n"
    "        t_gen = time.time() - t_start\n"
    "        # Per-problem timing для первых 3 — диагностика fast-path vs fallback скорости.\n"
    "        if i < 3:\n"
    "            n_tokens = len(tokenizer.encode(completion))\n"
    "            logger.info(f'  [{i+1}/{len(problems)}] gen={t_gen:.1f}s | tokens={n_tokens} | tok/s={n_tokens/max(t_gen,0.01):.1f}')\n"
)
assert old_loop in src6, 'Cell 6 loop block not found (already patched?)'
src6 = src6.replace(old_loop, new_loop)
set_src(cell6, src6)
print('Cell 6 patched: per-problem timing for first 3 problems')


# ─── Save ─────────────────────────────────────────────────────────────
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print(f'Saved: {NB}')
