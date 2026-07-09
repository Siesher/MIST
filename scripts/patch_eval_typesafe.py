"""Make _normalize_for_compare type-safe for numeric ground_truth.

eval_dataset.jsonl stores ground_truth как int/float (без кавычек) для numeric
problems — JSON не coerce'ит их в string. Старый code предполагал str и падал
на `(s or '').strip()` с AttributeError.
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


cell6 = nb['cells'][6]
src = get_src(cell6)

old_func = (
    'def _normalize_for_compare(s: str) -> str:\n'
    '    """Normalize answer string for numeric/symbolic comparison."""\n'
    "    s = (s or '').strip()\n"
)
new_func = (
    'def _normalize_for_compare(s) -> str:\n'
    '    """Normalize answer string for numeric/symbolic comparison.\n'
    '\n'
    '    Accepts str | int | float | None. eval_dataset.jsonl держит numeric\n'
    '    ground_truth как int/float (JSON не coerce-ит в строки), поэтому\n'
    '    str(s) делается до strip().\n'
    '    """\n'
    "    if s is None:\n"
    "        return ''\n"
    '    s = str(s).strip()\n'
)
assert old_func in src, 'Anchor _normalize_for_compare old signature not found'
src = src.replace(old_func, new_func)

old_sig = 'def is_numeric_correct(extracted: str, ground_truth: str, tolerance: float = 0.02) -> bool | None:'
new_sig = 'def is_numeric_correct(extracted, ground_truth, tolerance: float = 0.02) -> bool | None:'
assert old_sig in src, 'Anchor is_numeric_correct signature not found'
src = src.replace(old_sig, new_sig)

set_src(cell6, src)
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Cell 6 patched: _normalize_for_compare + is_numeric_correct accept any type')
