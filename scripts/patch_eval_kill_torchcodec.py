"""Kill torchcodec — RuntimeError на dlopen ломает unsloth import chain.

После torch lock attempt (`2c0a364`) Cell 1 imports падают на:
  RuntimeError: Could not load libtorchcodec.
  The PyTorch version (2.11.0+cu130) is not compatible with TorchCodec.

Chain:
  from unsloth → unsloth.models.sentence_transformer
    → from sentence_transformers import ...
      → modality_types.py: try: from torchcodec.decoders import ...
                          except (ImportError, OSError): AudioDecoder = None
      → torchcodec/_core/ops.py raises RuntimeError (NOT caught)

Two issues:
1. torch ended up at 2.11+cu130 несмотря на torch<2.11 constraints — pip
   resolver, видимо, picks transitive `torch>=2.11` от transformers 5.x
   strict, ignoring наш upper bound.
2. sentence_transformers's try/except catches только ImportError/OSError,
   не RuntimeError → torchcodec runtime DLL fail пробрасывается выше.

Fix: pip uninstall -y torchcodec ПОСЛЕ всех installs. Тогда
`from torchcodec.decoders` → ImportError → caught → AudioDecoder=None →
sentence_transformers loads → unsloth loads.

Bump sentinel v2 → v3 чтобы install запустился заново с новой uninstall step.
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


# ─── Bump sentinel v2 → v3 ───────────────────────────────────────────
old_sentinel = "SENTINEL = '/content/.install_done_v2'"
new_sentinel = "SENTINEL = '/content/.install_done_v3'"
assert old_sentinel in src, 'Sentinel v2 anchor not found'
src = src.replace(old_sentinel, new_sentinel)


# ─── Add torchcodec uninstall after Step 5 (FLA) ─────────────────────
old_fla_block = '''    # Step 5: FLA — Triton-based DeltaNet kernels (24/32 layers in Qwen3.5-9B)
    !pip install -q flash-linear-attention 2>&1 | tail -3

    # Sentinel: использует stdlib open() — НЕ требует Path import (он только
    # в post-restart section ниже).
    open(SENTINEL, 'w').close()'''

new_fla_block = '''    # Step 5: FLA — Triton-based DeltaNet kernels (24/32 layers in Qwen3.5-9B)
    !pip install -q flash-linear-attention 2>&1 | tail -3

    # Step 6: KILL torchcodec. Если torch ends up at 2.11+cu130 (Colab default
    # пытается upgrade), torchcodec wheel ABI mismatch → RuntimeError при dlopen
    # libtorchcodec_core{4..8}.so. sentence_transformers/base/modality_types.py
    # ловит только (ImportError, OSError), не RuntimeError → cascade ломает
    # unsloth import. Uninstall переводит fail в ImportError (catchable).
    print('Removing torchcodec (sentence_transformers fallback handles ImportError gracefully)...')
    !pip uninstall -y torchcodec 2>&1 | tail -1

    # Sentinel: использует stdlib open() — НЕ требует Path import (он только
    # в post-restart section ниже).
    open(SENTINEL, 'w').close()'''

assert old_fla_block in src, 'FLA + sentinel anchor not found'
src = src.replace(old_fla_block, new_fla_block)


set_src(cell1, src)
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Cell 1 patched: sentinel v2->v3, torchcodec uninstall added as Step 6')
