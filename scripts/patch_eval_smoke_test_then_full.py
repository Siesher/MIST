"""Path B finalization — restore num_predict=2048 + insert smoke test cell.

Rationale: user chose Option B (full 2048 budget, matches training distribution)
ради методологической чистоты. Перед commit'ом 18h+ overnight run — verify
на 3 problems что:
  - Completions reach `</think>` + final answer (no truncation)
  - Quality looks Socratic (not gibberish)
  - is_numeric_correct working
  - Realistic per-problem time estimate

Notebook structure после patch:
  Cell 0: markdown intro
  Cell 1: setup (sentinel-gated install)
  Cell 2: markdown DECODING_CONFIG
  Cell 3: DECODING_CONFIG (num_predict=2048 restored)
  Cell 4: load eval dataset (full 143)
  Cell 5: model loading defs
  Cell 6: eval logic defs
  Cell 7: distribution diagnostic (full set default)
  Cell 8 [NEW]: smoke test — 3 problems (one per difficulty), full timing + completions
  Cell 9: full eval (run только после smoke ✓)
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


# ─── Restore num_predict 1024 → 2048 ────────────────────────────────
cell3 = nb['cells'][3]
src3 = get_src(cell3)

old_1024 = '''    # 1024: empirical Run 2/3 measured 13.3 tok/s steady state (after Triton
    # JIT compile одноразово ~70s). 1024 / 13 = ~78s worst case per problem,
    # avg ~50-60s с early termination. 143 × 60s × 3 stages = ~7.5h overnight ✓.
    # Truncation risk ~5% на длинных thinking budgets (vs 10% для 512).
    'num_predict': 1024,'''

new_2048 = '''    # 2048: matches GSPO/KTO training budget exactly. Avoids truncation на
    # hard problems (training distribution). На steady-state 13 tok/s
    # 2048 / 13 = ~157s worst case per problem; avg ~80-120s due к early
    # termination on </think>. 143 × 100s × 3 stages = ~12h per night, run
    # split across 2 nights если нужно. Methodologically chistyy.
    'num_predict': 2048,'''

if old_1024 in src3:
    src3 = src3.replace(old_1024, new_2048)
    set_src(cell3, src3)
    print('Cell 3: num_predict 1024 -> 2048 (restored к training budget)')


# ─── Insert smoke test cell BEFORE full run cell ────────────────────
# Find current full-run cell (the one с "Cell 8: Run Phase 0a")
run_idx = None
for i, c in enumerate(nb['cells']):
    if c['cell_type'] != 'code':
        continue
    src = get_src(c)
    if 'Run Phase 0a' in src and 'eval_stage(stage_name' in src:
        run_idx = i
        break

assert run_idx is not None, 'Could not find Run Phase 0a cell'

smoke_test_cell = {
    'cell_type': 'code',
    'metadata': {},
    'source': '''# Cell SMOKE: 3-problem dry run — verify quality + measure realistic timing
# BEFORE committing к full 18h overnight eval.
# Picks one problem per difficulty, runs base model, prints completions для sanity check.
import time
import torch

# Load base model fresh (or reuse if already loaded в session)
try:
    _ = model.device
    logger.info(f'Reusing already-loaded model on {model.device}')
except (NameError, AttributeError):
    logger.info('Loading base model для smoke test...')
    model, tokenizer = load_model_with_adapter(None)

# Pick one problem per difficulty для diverse coverage
smoke_problems = []
seen_diffs = set()
for p in calc_problems:
    diff = p.get('difficulty', 'medium')
    if diff not in seen_diffs:
        smoke_problems.append(p)
        seen_diffs.add(diff)
    if len(smoke_problems) >= 3:
        break

logger.info(f'Smoke test: {len(smoke_problems)} problems (difficulties: {[p.get("difficulty") for p in smoke_problems]})')
logger.info(f'num_predict={DECODING_CONFIG["num_predict"]}, enable_thinking={DECODING_CONFIG["enable_thinking"]}')
print()

t_start = time.time()
smoke_results = []
for i, p in enumerate(smoke_problems):
    diff = p.get('difficulty', '?')
    print(f'─── Problem {i+1}/{len(smoke_problems)} [{diff}] ───')
    print(f'Q: {p["prompt"][:200]}{"..." if len(p["prompt"]) > 200 else ""}')
    print(f'Truth: {p["ground_truth"]}')

    t0 = time.time()
    completion = generate_one(model, tokenizer, p['prompt'])
    t_gen = time.time() - t0

    # Per-problem stats
    n_total = len(tokenizer.encode(completion))
    has_think_close = '</think>' in completion
    visible = completion.split('</think>')[-1].strip() if has_think_close else completion
    extracted = extract_answer(completion)
    correct = is_numeric_correct(extracted, p['ground_truth'])
    truncated = n_total >= DECODING_CONFIG['num_predict'] - 5  # within 5 tokens of cap

    print(f'Time: {t_gen:.1f}s | tokens: {n_total} | tok/s: {n_total/max(t_gen, 0.01):.1f}')
    print(f'Has </think>: {has_think_close} | Truncated: {truncated} | Extracted: {extracted!r} | Correct: {correct}')
    print(f'\\n[Visible answer (first 400 chars)]:')
    print(visible[:400] + ('...' if len(visible) > 400 else ''))
    print()

    smoke_results.append({
        'idx': i, 'difficulty': diff, 'time_s': t_gen, 'tokens': n_total,
        'has_think_close': has_think_close, 'truncated': truncated,
        'extracted': extracted, 'truth': p['ground_truth'], 'correct': correct,
    })

t_total = time.time() - t_start
print('═' * 60)
print(f'Smoke test complete: {t_total:.1f}s for {len(smoke_problems)} problems')
print()

# Calculate full eval ETA
avg_time = sum(r['time_s'] for r in smoke_results) / len(smoke_results)
truncation_rate = sum(1 for r in smoke_results if r['truncated']) / len(smoke_results)
correct_count = sum(1 for r in smoke_results if r['correct'])

print(f'Per-problem avg: {avg_time:.1f}s')
print(f'Truncation rate: {truncation_rate:.1%}')
print(f'Quick accuracy: {correct_count}/{len(smoke_results)} (sample size мал, indicative only)')
print()
print(f'ETA for full eval (143 × 3 stages): {143 * avg_time * 3 / 3600:.1f}h overnight')
print()

# Sanity flags
flags = []
if avg_time > 200:
    flags.append('SLOW: avg >200s per problem — full eval >24h')
if truncation_rate > 0.3:
    flags.append('TRUNCATION: >30% hit cap — increase num_predict or accept loss')
if not all(r['has_think_close'] for r in smoke_results):
    flags.append('NO </think>: model не emit'ит close tag — truncation или training issue')

if flags:
    print('⚠ FLAGS:')
    for f in flags:
        print(f'  - {f}')
    print('\\nDecide: continue к full eval (Cell next) OR adjust DECODING_CONFIG and re-run smoke.')
else:
    print('✓ All checks pass. Proceed to full eval (next cell).')
''',
    'outputs': [],
    'execution_count': None,
}

# Idempotency: skip if smoke test cell already exists
existing_sources = [get_src(c) for c in nb['cells']]
already_has_smoke = any('Cell SMOKE: 3-problem dry run' in s for s in existing_sources)

if not already_has_smoke:
    nb['cells'].insert(run_idx, smoke_test_cell)
    print(f'Inserted smoke test cell at position {run_idx} (before full run)')
else:
    print('Smoke test cell already exists, skipping insertion')


NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print()
print('Final notebook structure:')
for i, c in enumerate(nb['cells']):
    src = get_src(c)
    label = src.split(chr(10))[0][:60].replace('#', '').strip()
    print(f'  [{i}] {c["cell_type"]:8s} | {label}')
print()
print('Workflow:')
print('  1. Run Cell 1 (install if fresh runtime, restart, re-run)')
print('  2. Run Cells 2-7 (DECODING_CONFIG, load dataset, defs)')
print('  3. Run smoke test cell — verify 3 problems work с full 2048 budget')
print('  4. Review output: timing, truncation, quality, accuracy')
print('  5. ONLY IF SMOKE PASSES: run final cell для full eval')
