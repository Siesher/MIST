"""Constrain numpy в HF eager install — eager strategy реверт'ил наш force-reinstall.

Sequence в предыдущем run:
  1. force-reinstall numpy → 2.3.5 ✓
  2. pip install -U --upgrade-strategy eager "transformers>=4.55,<5.0" ...
     ← eager бере "latest compatible" из transitive deps → numpy 2.4.4 (broken) BACK
  3. import transformers → ImportError на GenerationMixin (cascade от broken numpy)

Fix: добавить "numpy>=2.2,<2.4" прямо в HF install constraint. eager уважает
upper bound, не апгрейдит выше нашего pin.
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

old = '!pip install -q -U --upgrade-strategy eager "transformers>=4.55,<5.0" "huggingface_hub>=0.25,<1.0" "tokenizers>=0.20,<0.22"'
new = '!pip install -q -U --upgrade-strategy eager "transformers>=4.55,<5.0" "huggingface_hub>=0.25,<1.0" "tokenizers>=0.20,<0.22" "numpy>=2.2,<2.4"'

assert old in src, 'HF eager install anchor not found'
assert '"numpy>=2.2,<2.4"' not in old, 'Already patched?'
src = src.replace(old, new)

set_src(cell1, src)
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Patched: numpy>=2.2,<2.4 constraint added to HF eager install')
