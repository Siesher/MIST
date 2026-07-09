"""Fix Colab broken numpy 2.4.4 — ImportError на _center из numpy._core.umath.

Symptom (после pin transformers к 4.x):
  ImportError: cannot import name '_center' from 'numpy._core.umath'
  (через scipy → sklearn → transformers.candidate_generator)

Root cause: Colab Python 3.12 image preinstalled numpy 2.4.4 имеет broken
internal API — `numpy/_core/strings.py` импортирует `_center` из
`numpy._core.umath`, но в installed binary этого symbol нет (внутренний
mismatch installed wheel).

Fix: force-reinstall numpy в stable 2.3.x ветку (последняя до broken 2.4.x).
ДО любого import transformers/scipy/sklearn.
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


# ─── Insert numpy fix right after torchvision uninstall ──────────────
old_anchor = '''# Удаляем torchvision: text-only inference, его не используем.
# Без удаления transformers >=4.55 пытается импортировать torchvision.io в
# processing_utils, и при CUDA-version mismatch (Colab часто имеет torch CUDA13
# vs torchvision CUDA12.8) ломает весь HF stack каскадом.
!pip uninstall -y torchvision 2>/dev/null || true

'''

new_block = '''# Удаляем torchvision: text-only inference, его не используем.
# Без удаления transformers >=4.55 пытается импортировать torchvision.io в
# processing_utils, и при CUDA-version mismatch (Colab часто имеет torch CUDA13
# vs torchvision CUDA12.8) ломает весь HF stack каскадом.
!pip uninstall -y torchvision 2>/dev/null || true

# ─── Fix Colab broken numpy 2.4.4 (cannot import _center) ────
# Current Colab Python 3.12 image ships numpy 2.4.4 с broken internal API:
# numpy._core.strings импортирует _center из numpy._core.umath, но в installed
# binary этого symbol нет. Cascade: scipy → sklearn → transformers
# .candidate_generator → ImportError на AutoModelForCausalLM.
# Fix: rollback на numpy 2.3.x stable до import чего-либо ещё.
print('Fixing numpy ABI (Colab default 2.4.4 has broken _center API)...')
!pip install -q --force-reinstall --no-cache-dir "numpy>=2.2,<2.4" 2>&1 | tail -3
print('Numpy reinstalled to 2.3.x stable.')

'''

assert old_anchor in src, 'Anchor "torchvision uninstall" block not found'
assert 'numpy>=2.2,<2.4' not in src, 'Already patched?'
src = src.replace(old_anchor, new_block)

set_src(cell1, src)
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Cell 1 patched: numpy force-reinstall to 2.3.x stable')
