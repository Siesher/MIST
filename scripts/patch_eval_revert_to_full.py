"""Revert subset — empirical test показал steady-state 13 tok/s (after JIT compile).

User's intuition подтвердилась: 16-min "freeze" на problem 1 был JIT compile
overhead Triton kernels (24 GDN layers compile takes ~70s once). Steady state
13.3 tok/s — full 143 eval feasible overnight.

Changes:
1. num_predict 512 → 1024 (back в reasonable territory, less truncation на hard
   problems with long thinking; steady state 13 tok/s × 1024 = ~78s worst case
   per problem, avg ~50-60s due to early termination on </think>)
2. Subset cell — keep diagnostic info (distribution print) но remove
   calc_problems rebinding. Default: full 143 problems used.

Math для overnight:
- 143 problems × ~60s avg + 70s JIT compile = ~9000s = 2.5h per stage
- 3 stages × 2.5h + base model loads = ~7.5-8h overnight ✓
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


# ─── Bump num_predict 512 → 1024 ─────────────────────────────────────
cell3 = nb['cells'][3]
src3 = get_src(cell3)

old_512 = '''    # 512: drop с 2048 для overnight feasibility. На slow path (~2 tok/s без
    # causal-conv1d на Colab) 2048 → 17 min/problem; 512 → 4 min/problem.
    # Truncation risk ~10% на hard problems with long thinking, но IDENTICAL
    # cap для всех 3 моделей → apple-to-apple comparison preserved.
    'num_predict': 512,'''

new_1024 = '''    # 1024: empirical Run 2/3 measured 13.3 tok/s steady state (after Triton
    # JIT compile одноразово ~70s). 1024 / 13 = ~78s worst case per problem,
    # avg ~50-60s с early termination. 143 × 60s × 3 stages = ~7.5h overnight ✓.
    # Truncation risk ~5% на длинных thinking budgets (vs 10% для 512).
    'num_predict': 1024,'''

if old_512 in src3:
    src3 = src3.replace(old_512, new_1024)
    set_src(cell3, src3)
    print('Cell 3: num_predict 512 -> 1024 (steady state 13 tok/s, full 143 viable)')


# ─── Modify subset cell — keep distribution print, remove rebinding ──
cell7 = nb['cells'][7]
src7 = get_src(cell7)

if 'Stratified 30-sample' in src7:
    new_cell7 = '''# Cell 7.5: Distribution diagnostic + optional subset selection.
# UPDATE: Empirical speed test showed steady-state 13.3 tok/s (Run 2/3 после
# Triton JIT compile ~70s одноразово). Full 143 × 3 stages feasible ~7.5h.
# Default: full eval. Uncomment LAST 2 lines чтобы переключиться на 30 stratified.
import random
from collections import defaultdict

random.seed(42)

by_diff = defaultdict(list)
for p in calc_problems:
    by_diff[p.get('difficulty', 'medium')].append(p)

logger.info(f'Calc problems by difficulty: {[(k, len(v)) for k, v in by_diff.items()]}')
logger.info(f'Default: full eval ({len(calc_problems)} problems × 3 stages ≈ 7.5h)')

# ── OPTIONAL: stratified 30 subset (если хочешь quick test ~2.5h) ──
# stratified = []
# for diff in ['easy', 'medium', 'hard']:
#     pool = by_diff.get(diff, [])
#     stratified.extend(random.sample(pool, min(10, len(pool))))
# calc_problems = stratified
# logger.info(f'OVERRIDE: using 30 stratified subset')
'''
    set_src(cell7, new_cell7)
    print('Cell 7.5: subset rebinding commented out, full 143 by default')


NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print()
print('Reverted to full eval:')
print('  - Cell 3: num_predict 512 -> 1024')
print('  - Cell 7.5: subset rebinding commented (full 143 default, uncomment для 30)')
print('  - Estimated overnight: ~7.5-8h на full 143 × 3 stages')
