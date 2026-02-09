#!/bin/bash
# Deploy fine-tuned MITS tutor model to Ollama
#
# Prerequisites:
#   - Ollama installed and running
#   - Base model pulled: ollama pull glm4:9b
#   - LoRA adapter exported to GGUF (via export_lora_gguf.py or Unsloth)
#
# Usage:
#   bash training/scripts/deploy_finetuned.sh [adapter_dir] [model_name]
#
# Examples:
#   bash training/scripts/deploy_finetuned.sh
#   bash training/scripts/deploy_finetuned.sh outputs/mits-tutor-glm/ollama mits-tutor-v2

set -euo pipefail

ADAPTER_DIR="${1:-outputs/mits-tutor-glm/ollama}"
MODEL_NAME="${2:-mits-tutor-ft}"
BASE_MODEL="glm4:9b"

echo "=== MITS Fine-tuned Model Deployment ==="
echo "Adapter dir: ${ADAPTER_DIR}"
echo "Model name:  ${MODEL_NAME}"
echo "Base model:  ${BASE_MODEL}"
echo ""

# Check Ollama is running
if ! ollama list > /dev/null 2>&1; then
    echo "ERROR: Ollama is not running. Start it with: ollama serve"
    exit 1
fi

# Check base model exists
if ! ollama list | grep -q "${BASE_MODEL}"; then
    echo "Base model ${BASE_MODEL} not found. Pulling..."
    ollama pull "${BASE_MODEL}"
fi

# Check Modelfile exists
MODELFILE="${ADAPTER_DIR}/Modelfile"
if [ ! -f "${MODELFILE}" ]; then
    echo "ERROR: Modelfile not found at ${MODELFILE}"
    echo "Run export_lora_gguf.py first to generate it."
    exit 1
fi

# Check adapter file exists
if ! ls "${ADAPTER_DIR}"/*.gguf > /dev/null 2>&1; then
    echo "ERROR: No GGUF adapter found in ${ADAPTER_DIR}"
    echo "Run export_lora_gguf.py first to convert the adapter."
    exit 1
fi

# Delete existing model if present
if ollama list | grep -q "${MODEL_NAME}"; then
    echo "Removing existing model ${MODEL_NAME}..."
    ollama rm "${MODEL_NAME}"
fi

# Create model
echo "Creating model ${MODEL_NAME}..."
cd "${ADAPTER_DIR}"
ollama create "${MODEL_NAME}" -f Modelfile

echo ""
echo "=== Deployment complete! ==="
echo ""
echo "Test the model:"
echo "  ollama run ${MODEL_NAME} 'Помоги разобраться с производными'"
echo ""
echo "Use in MITS (set in .env):"
echo "  MODEL_NAME=${MODEL_NAME}"
