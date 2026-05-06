"""Add truncation-aware metrics to eval_stage (option C from methodology decision).

Changes:
  1. Per-completion: track n_tokens, truncated, has_think_close
  2. Aggregate metrics:
     - truncation_rate: fraction of completions hitting num_predict cap
     - think_close_rate: fraction with </think> emitted (format compliance)
     - accuracy_non_truncated: accuracy ON non-truncated subset only

Diploma narrative двухуровневый:
  "GSPO снижает truncation rate с X% до Y%, AND на completed answers
   accuracy улучшается с A% до B%" — две complementary metrics.
"""
import json
from pathlib import Path

NB = Path('notebooks/honest_eval_full_precision.ipynb')
nb = json.loads(NB.read_text(encoding='utf-8'))


def get_src_list(cell):
    s = cell.get('source', '')
    return s if isinstance(s, list) else s.splitlines(keepends=True)


# ─── Cell 6: eval_stage modifications ─────────────────────────────
target_idx = None
for i, c in enumerate(nb['cells']):
    src = ''.join(get_src_list(c))
    if 'def eval_stage(' in src:
        target_idx = i
        break
assert target_idx is not None
print(f'eval_stage in cell {target_idx}')

cell = nb['cells'][target_idx]
lines = get_src_list(cell)


def find_line_idx(needle: str, start: int = 0) -> int:
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i
    return -1


# Replacement #1: Move n_tokens calc OUT of `if i < 3` AND compute flags
# Old block:
#         t_gen = time.time() - t_start
#         # Per-problem timing для первых 3 — диагностика fast-path vs fallback скорости.
#         if i < 3:
#             n_tokens = len(tokenizer.encode(completion))
#             logger.info(...)
#         extracted = extract_answer(completion)

# New block:
#         t_gen = time.time() - t_start
#         # Always compute n_tokens — нужно для truncation tracking
#         n_tokens = len(tokenizer.encode(completion))
#         truncated = n_tokens >= DECODING_CONFIG['num_predict'] - 5
#         has_think_close = '</think>' in completion
#         # Per-problem timing для первых 3 — диагностика fast-path vs fallback скорости.
#         if i < 3:
#             logger.info(...)
#         extracted = extract_answer(completion)

t_gen_idx = find_line_idx('t_gen = time.time() - t_start')
assert t_gen_idx >= 0, 't_gen line not found'

# Find `if i < 3:` after t_gen line
if_idx = find_line_idx('if i < 3:', t_gen_idx)
# Inside if-block: line `n_tokens = len(tokenizer.encode(completion))`
n_tokens_inside = find_line_idx('n_tokens = len(tokenizer.encode(completion))', if_idx)
assert n_tokens_inside == if_idx + 1, 'Layout assumption broken'

# Insert new lines AFTER t_gen line (8-space indent matches function body)
new_pre_lines = [
    '        # Always compute — нужно для truncation/think_close tracking\n',
    '        n_tokens = len(tokenizer.encode(completion))\n',
    "        truncated = n_tokens >= DECODING_CONFIG['num_predict'] - 5\n",
    "        has_think_close = '</think>' in completion\n",
]

# Remove the old `n_tokens = ...` from inside if-block (now redundant)
# It was at index n_tokens_inside (== if_idx + 1)
del lines[n_tokens_inside]

# Now insert new_pre_lines AFTER t_gen_idx
lines[t_gen_idx + 1:t_gen_idx + 1] = new_pre_lines
print(f'  + truncation/think_close flags inserted after t_gen')

# Replacement #2: Add fields to completions.append dict
old_append = "            'completion_text': visible,  # saved для Phase 0b async judge\n"
new_append = (
    "            'completion_text': visible,  # saved для Phase 0b async judge\n"
    "            'n_tokens': n_tokens,\n"
    "            'truncated': truncated,\n"
    "            'has_think_close': has_think_close,\n"
)
append_idx = find_line_idx("'completion_text': visible")
assert append_idx >= 0
lines[append_idx] = new_append
print(f'  + n_tokens/truncated/has_think_close added to completions dict')

# Replacement #3: Add aggregate metrics to return dict
# Find the return statement and inject new keys before 'mode': ... line
return_idx = find_line_idx('return {')
assert return_idx >= 0
# Find 'mode': line
mode_idx = find_line_idx("'mode': 'fast_programmatic'", return_idx)
assert mode_idx >= 0

new_agg_lines = [
    "        'truncation_rate': sum(1 for c in completions if c.get('truncated')) / max(len(completions), 1),\n",
    "        'think_close_rate': sum(1 for c in completions if c.get('has_think_close')) / max(len(completions), 1),\n",
    "        'accuracy_non_truncated': (\n",
    "            sum(1 for c in completions if c.get('correct') and not c.get('truncated'))\n",
    "            / max(sum(1 for c in completions if c.get('correct') is not None and not c.get('truncated')), 1)\n",
    "        ),\n",
    "        'n_non_truncated': sum(1 for c in completions if not c.get('truncated')),\n",
]
lines[mode_idx:mode_idx] = new_agg_lines
print(f'  + truncation_rate / think_close_rate / accuracy_non_truncated в return dict')

cell['source'] = lines


# ─── Cell 9: print output — surface new metrics ──────────────────
last_idx = None
for i, c in enumerate(nb['cells']):
    src = ''.join(get_src_list(c))
    if 'Phase 0a — Honest accuracy' in src:
        last_idx = i
        break
assert last_idx is not None

cell9 = nb['cells'][last_idx]
lines9 = get_src_list(cell9)


def find_in_cell9(needle: str) -> int:
    for i, ln in enumerate(lines9):
        if needle in ln:
            return i
    return -1


# Replace the print loop в конце с расширенной версией
old_loop_start = find_in_cell9("for stage in ['base', 'gspo', 'kto']:")
old_print_acc = find_in_cell9("acc={r['accuracy']:.3f}")
old_socratic_note = find_in_cell9('socratic_score / leak_rate — Phase 0b')

assert old_loop_start >= 0 and old_print_acc >= 0 and old_socratic_note >= 0

# Build new tail (replace last 4 lines: for-loop + print acc + close + socratic note)
new_tail = [
    "for stage in ['base', 'gspo', 'kto']:\n",
    "    r = results[stage]\n",
    "    print(f\"{stage:5s}  acc={r['accuracy']:.3f} ({r['n_judged']}/{r['n']} judged) | \"\n",
    "          f\"acc_non_trunc={r['accuracy_non_truncated']:.3f} ({r['n_non_truncated']}/{r['n']}) | \"\n",
    "          f\"trunc={r['truncation_rate']:.1%} | think_close={r['think_close_rate']:.1%}\")\n",
    "print('\\nNote: acc_non_trunc — accuracy ON completed answers только (excluded truncated).')\n",
    "print('Note: socratic_score / leak_rate — Phase 0b (run scripts/score_phase0b_async.py later).')\n",
]

# Slice replace from old_loop_start to old_socratic_note inclusive
lines9[old_loop_start:old_socratic_note + 1] = new_tail
cell9['source'] = lines9
print(f'  + Cell 9 print output extended with truncation/think_close metrics')


NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print()
print('Patches applied successfully.')
print()
print('Per-completion now tracks: n_tokens, truncated, has_think_close')
print('Per-stage now reports: accuracy, accuracy_non_truncated, truncation_rate, think_close_rate')
print('Sample diploma table: base trunc=15% acc_nt=0.42 / gspo trunc=4% acc_nt=0.61 / kto trunc=2% acc_nt=0.68')
