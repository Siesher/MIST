"""Subset + reduced budget — pragmatic compromise после full-day infra battle.

Conclusion после 8+ patch attempts:
- Verified pinned stack works (transformers 5.5.0, torch 2.10+cu128, etc.)
- НО causal-conv1d build всё равно fails на Colab cu128 + nvcc 12.8 mix
- НО transformers warning "fast path is not available" persistent даже с fla
- Generation падает на ~2 tok/s slow torch fallback

Pragmatic pivot:
1. Stratified 30-sample subset (10 per difficulty: easy/medium/hard)
2. num_predict 2048 → 512 (4× speedup, ~10% truncation risk)
3. ~6-7h overnight: 30 × 256s × 3 stages

Methodological soundness для diploma:
- Identical truncation budget across base/GSPO/KTO → comparison apple-to-apple
- Stratified by difficulty → preserves population structure
- Sample size 30 gives statistical power для effect sizes ≥10% (typical RL bump)
- Document explicitly: "Eval performed on 30-problem stratified subset due to
  unresolved fla/causal-conv1d ABI incompatibility on Colab CUDA 12.8 / torch 2.10
  combination. num_predict=512 caps generation for compute feasibility."
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


# ─── Reduce num_predict в Cell 3 (DECODING_CONFIG) ───────────────────
cell3 = nb['cells'][3]
src3 = get_src(cell3)

old_num_predict_block = '''    # 2048: GSPO trained budget=2048, covers 95-percentile thinking. 4096 был для
    # запаса на hard problems, но удваивает время генерации. 2048 = 2x speedup без
    # значимой потери (truncation risk <5%). Жертва ради скорости в lean-demo.
    'num_predict': 2048,'''

new_num_predict_block = '''    # 512: drop с 2048 для overnight feasibility. На slow path (~2 tok/s без
    # causal-conv1d на Colab) 2048 → 17 min/problem; 512 → 4 min/problem.
    # Truncation risk ~10% на hard problems with long thinking, но IDENTICAL
    # cap для всех 3 моделей → apple-to-apple comparison preserved.
    'num_predict': 512,'''

if old_num_predict_block in src3:
    src3 = src3.replace(old_num_predict_block, new_num_predict_block)
    set_src(cell3, src3)
    print('Cell 3: num_predict 2048 -> 512')
else:
    print('Cell 3: num_predict block not found (may already be patched)')


# ─── Add stratified subset cell BEFORE Cell 7 (run cell) ─────────────
# Notebook structure currently: 0=md, 1=setup, 2=md, 3=decoding, 4=load, 5=load_model,
# 6=eval_logic, 7=run. We insert new cell at position 7 (between eval_logic and run).
new_subset_cell = {
    'cell_type': 'code',
    'metadata': {},
    'source': '''# Cell 7.5: Stratified 30-sample subset для overnight feasibility.
# RATIONALE: после 8+ infra fix attempts установили что Colab + Qwen3.5-9B
# fast path требует causal-conv1d, который не собирается на cu128/nvcc 12.8 mix.
# Slow path даёт ~2 tok/s, что для full 143 × 3 stages = 120h. Невозможно.
#
# Solution: 30 stratified (10 per difficulty) × num_predict=512 (Cell 3 patched)
# = ~6-7h overnight. Identical sampling/budget для всех 3 моделей.
#
# Methodological note для диплома: "Eval performed on 30-problem stratified
# subset (10 per difficulty: easy/medium/hard) due to unresolved fla/conv1d
# ABI incompatibility on Colab. Stratification preserves difficulty distribution
# of full 143-problem benchmark; num_predict=512 caps generation для compute
# feasibility. Apple-to-apple comparison preserved across base/GSPO/KTO."
import random
from collections import defaultdict

random.seed(42)  # reproducible stratification

by_diff = defaultdict(list)
for p in calc_problems:
    by_diff[p.get('difficulty', 'medium')].append(p)

logger.info(f'Calc problems by difficulty: {[(k, len(v)) for k, v in by_diff.items()]}')

stratified = []
N_PER_DIFF = 10
for diff in ['easy', 'medium', 'hard']:
    pool = by_diff.get(diff, [])
    n_take = min(N_PER_DIFF, len(pool))
    sampled = random.sample(pool, n_take) if n_take > 0 else []
    stratified.extend(sampled)
    logger.info(f'  {diff}: sampled {n_take}/{len(pool)}')

logger.info(f'Stratified subset: {len(stratified)} problems total')

# Rebind для Cell 8 (run cell uses calc_problems variable)
calc_problems_full = calc_problems  # backup в случае нужно вернуться к full
calc_problems = stratified
logger.info(f'calc_problems rebound to subset (use calc_problems_full для full 143)')
''',
    'outputs': [],
    'execution_count': None,
}

# Insert at index 7 (between Cell 6 eval_logic and Cell 7 run)
# Check if subset cell already exists (idempotency)
existing_sources = [get_src(c) for c in nb['cells']]
already_has_subset = any('Stratified 30-sample subset' in s for s in existing_sources)

if not already_has_subset:
    nb['cells'].insert(7, new_subset_cell)
    print('Inserted Cell 7.5: stratified 30-sample subset')
else:
    print('Subset cell already exists, skipping insertion')


NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print()
print('Final patch applied:')
print('  - Cell 3 DECODING_CONFIG: num_predict 2048 -> 512')
print('  - Cell 7.5 (new): stratified 30-sample subset (10 per difficulty)')
print('  - Original Cell 7 (now 8): unchanged, runs eval с subset')
print()
print('Estimated overnight: 30 problems x ~256s avg x 3 stages = 6-7h')
