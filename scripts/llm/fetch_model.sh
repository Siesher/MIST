#!/usr/bin/env bash
# fetch_model.sh — восстановление продового GGUF (mits-tutor) из HF-весов.
#
# Источник истины: Siesher/mits-qwen3-9b-kto (public, full bf16 safetensors ~17.9 GB).
# NB (аудит 2026-07-02): Siesher/mits-qwen3-9b-final на HF НЕ существует (404),
#   mits-qwen3-9b-gspo — private (LoRA-формат). KTO — последняя восстановимая стадия.
#
# Pipeline: hf download -> convert_hf_to_gguf.py (bf16) -> llama-quantize Q4_K_M.
# Требования: uv, llama.cpp binaries (LLAMA_BIN) + source tree со скриптом конвертации (LLAMA_SRC).
# Диск: ~18 GB (safetensors) + ~18 GB (bf16 gguf, удаляется) + ~5.3 GB (Q4_K_M).
#
# Usage: bash scripts/llm/fetch_model.sh [--keep-f16]

set -euo pipefail

REPO_ID="${MITS_HF_REPO:-Siesher/mits-qwen3-9b-kto}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODELS_DIR="${MITS_MODELS_DIR:-$ROOT/training/models}"
HF_DIR="$MODELS_DIR/hf-kto"
F16_GGUF="$MODELS_DIR/mits-kto.bf16.gguf"
Q4_GGUF="$MODELS_DIR/mits-kto.q4km.gguf"

LLAMA_BIN="${LLAMA_BIN:-$HOME/.local/opt/llama-b9859}"
LLAMA_SRC="${LLAMA_SRC:-$HOME/.local/opt/llama.cpp-b9859}"

if [[ -f "$Q4_GGUF" ]]; then
    echo "[fetch_model] $Q4_GGUF already exists — nothing to do."
    exit 0
fi

echo "[fetch_model] 1/3 download $REPO_ID -> $HF_DIR"
uvx --from huggingface_hub hf download "$REPO_ID" --local-dir "$HF_DIR"

echo "[fetch_model] 2/3 convert -> $F16_GGUF (bf16)"
if [[ ! -f "$F16_GGUF" ]]; then
    uv run --with gguf --with 'transformers>=5' --with torch --with sentencepiece \
        python "$LLAMA_SRC/convert_hf_to_gguf.py" "$HF_DIR" \
        --outfile "$F16_GGUF" --outtype bf16
fi

echo "[fetch_model] 3/3 quantize -> $Q4_GGUF (Q4_K_M)"
LD_LIBRARY_PATH="$LLAMA_BIN" "$LLAMA_BIN/llama-quantize" "$F16_GGUF" "$Q4_GGUF" Q4_K_M

if [[ "${1:-}" != "--keep-f16" ]]; then
    rm -f "$F16_GGUF"
fi

echo "[fetch_model] done: $(ls -lh "$Q4_GGUF" | awk '{print $5, $9}')"
