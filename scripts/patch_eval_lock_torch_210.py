"""Lock torch <2.11 — Unsloth 2026.5.1 регрессировала compat с torch 2.11.

Two bugs from previous run:

1. NameError на Path(SENTINEL).touch() — Path не был импортирован к моменту
   touch(); from pathlib import Path лежал в post-restart imports section.
   Fix: open(SENTINEL, 'w').close() — использует stdlib open() прямо.

2. Unsloth 2026.5.1 explicitly требует torch<2.11.0:
     unsloth-zoo 2026.5.1 requires torch<2.11.0,>=2.4.0, but you have torch 2.11.0
     torchaudio 2.10.0+cu128 requires torch==2.10.0, but you have torch 2.11.0
   transformers>=5.0.0 install тянет torch 2.11 как transitive. Это recent
   Unsloth regression — training notebook писался при torch 2.11 support,
   теперь поддержка узкая (2.4-2.10).

Fix: pin torch в каждой pip install line через "torch<2.11". Pip респектит
user constraint выше transitive deps.

Side benefit: Colab default torch == 2.10.0+cu128 — locking <2.11 матчит
эту pre-installed binary, скорее install идёт быстрее (no torch redownload).
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


# ─── Fix 1: Replace install block with torch-locked version ──────────
old_install_block = '''SENTINEL = '/content/.install_done_v2'
if not os.path.exists(SENTINEL):
    print('=== Installing training-matched stack ===')
    print('  (transformers 5.x for qwen3_5 + Unsloth for multimodal-as-text)')
    # Step 1: Unsloth core
    !pip install -q --upgrade --force-reinstall --no-cache-dir unsloth unsloth_zoo
    # Step 2: transformers v5 (Qwen3.5 hybrid arch support)
    !pip install -q "transformers>=5.0.0" trl peft datasets
    # Step 3: torchvision matching torch 2.11 (PIL._typing._Ink fix)
    !pip install -q --upgrade scipy "torchvision>=0.23.0"
    # Step 4: Other deps (eval needs python-dotenv + openai for Cerebras client)
    !pip install -q accelerate bitsandbytes sentencepiece protobuf loguru python-dotenv openai
    !pip install -q sympy chempy
    # Step 5: FLA — Triton-based DeltaNet kernels (24/32 layers in Qwen3.5-9B)
    !pip install -q flash-linear-attention 2>&1 | tail -3

    Path(SENTINEL).touch()'''

new_install_block = '''SENTINEL = '/content/.install_done_v2'
if not os.path.exists(SENTINEL):
    print('=== Installing training-matched stack (torch 2.10 locked) ===')
    print('  Unsloth 2026.5.1 requires torch<2.11; Colab default 2.10 уже OK.')

    # Step 0: Lock pytorch ecosystem to torch 2.10 — Colab default. Это
    # предотвращает upgrade-to-2.11 от transitive deps трансформеров.
    !pip install -q --upgrade "torch>=2.10,<2.11" "torchvision" "torchaudio>=2.10,<2.11"

    # Step 1: Unsloth core (без force-reinstall — fresh runtime, deps clean)
    !pip install -q --upgrade unsloth unsloth_zoo "torch<2.11"

    # Step 2: transformers v5 — torch upper bound prevents re-upgrade
    !pip install -q --upgrade "transformers>=5.0.0,<6.0" "torch<2.11" trl peft datasets

    # Step 3: scipy + torchvision compat already locked в Step 0
    !pip install -q --upgrade scipy

    # Step 4: Other deps (Cerebras client requires python-dotenv + openai)
    !pip install -q accelerate bitsandbytes sentencepiece protobuf loguru python-dotenv openai
    !pip install -q sympy chempy

    # Step 5: FLA — Triton-based DeltaNet kernels (24/32 layers in Qwen3.5-9B)
    !pip install -q flash-linear-attention 2>&1 | tail -3

    # Sentinel: использует stdlib open() — НЕ требует Path import (он только
    # в post-restart section ниже).
    open(SENTINEL, 'w').close()'''

assert old_install_block in src, 'Install block anchor not found — has Cell 1 changed?'
assert 'Path(SENTINEL).touch()' in old_install_block, 'Bug Path import не найден в исходнике'
src = src.replace(old_install_block, new_install_block)


set_src(cell1, src)
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('Cell 1 patched:')
print('  - Path(SENTINEL).touch() → open(SENTINEL, "w").close() (stdlib, no Path import)')
print('  - Added Step 0: lock torch>=2.10,<2.11 (Unsloth 2026.5.1 regression fix)')
print('  - All transformers/unsloth lines explicitly carry "torch<2.11" constraint')
