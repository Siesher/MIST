#!/bin/bash
# =============================================================================
# GLM-STEM Model Installation Script
# Installs REAP-pruned GLM model (42 experts) for MITS
# =============================================================================

set -e

# Configuration
MODEL_NAME="glm-stem-42exp"
HF_REPO="Siesher/glm-stem-42exp-gguf"
DEFAULT_VARIANT="q4km"
MODELS_DIR="${HOME}/models"
MIN_DISK_GB=20

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
VARIANT="${DEFAULT_VARIANT}"
REINSTALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --variant)
            VARIANT="$2"
            shift 2
            ;;
        --reinstall)
            REINSTALL=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--variant q4km|q8] [--reinstall]"
            echo ""
            echo "Options:"
            echo "  --variant   GGUF variant: q4km (~13GB) or q8 (~21GB). Default: q4km"
            echo "  --reinstall Force reinstallation even if model exists"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Validate variant
if [[ "$VARIANT" != "q4km" && "$VARIANT" != "q8" ]]; then
    echo -e "${RED}Invalid variant: $VARIANT. Use 'q4km' or 'q8'${NC}"
    exit 1
fi

GGUF_FILE="glm-stem-42exp-${VARIANT}.gguf"
GGUF_URL="https://huggingface.co/${HF_REPO}/resolve/main/${GGUF_FILE}"

echo "=============================================="
echo "  GLM-STEM Model Installation"
echo "=============================================="
echo "Model: ${MODEL_NAME}"
echo "Variant: ${VARIANT}"
echo "Target: ${MODELS_DIR}/${GGUF_FILE}"
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}ERROR: Ollama is not installed${NC}"
    echo "Install Ollama first: https://ollama.ai/download"
    exit 1
fi
echo -e "${GREEN}✓ Ollama found${NC}"

# Check if Ollama is running
if ! ollama list &> /dev/null; then
    echo -e "${YELLOW}Starting Ollama server...${NC}"
    ollama serve &> /dev/null &
    sleep 3
fi
echo -e "${GREEN}✓ Ollama is running${NC}"

# Check if model already exists
if ollama list 2>/dev/null | grep -q "${MODEL_NAME}"; then
    if [[ "$REINSTALL" == "true" ]]; then
        echo -e "${YELLOW}Removing existing model for reinstall...${NC}"
        ollama rm "${MODEL_NAME}" || true
    else
        echo -e "${GREEN}✓ Model '${MODEL_NAME}' already installed${NC}"
        echo ""
        echo "To reinstall, run: $0 --reinstall"
        exit 0
    fi
fi

# Check disk space
AVAILABLE_GB=$(df -BG "${HOME}" | awk 'NR==2 {print $4}' | tr -d 'G')
if [[ "$AVAILABLE_GB" -lt "$MIN_DISK_GB" ]]; then
    echo -e "${RED}ERROR: Insufficient disk space${NC}"
    echo "Available: ${AVAILABLE_GB}GB, Required: ${MIN_DISK_GB}GB"
    exit 1
fi
echo -e "${GREEN}✓ Disk space OK (${AVAILABLE_GB}GB available)${NC}"

# Create models directory
mkdir -p "${MODELS_DIR}"
cd "${MODELS_DIR}"

# Download GGUF file
GGUF_PATH="${MODELS_DIR}/${GGUF_FILE}"
if [[ -f "${GGUF_PATH}" ]]; then
    echo -e "${YELLOW}GGUF file exists, skipping download${NC}"
else
    echo ""
    echo "Downloading ${GGUF_FILE}..."
    echo "This may take 10-30 minutes depending on your connection."
    echo ""

    # Try huggingface_hub first (supports resume)
    if command -v python3 &> /dev/null; then
        python3 -c "
from huggingface_hub import hf_hub_download
import os
print('Using huggingface_hub for download with resume support...')
path = hf_hub_download(
    repo_id='${HF_REPO}',
    filename='${GGUF_FILE}',
    local_dir='${MODELS_DIR}',
    local_dir_use_symlinks=False
)
print(f'Downloaded to: {path}')
" 2>/dev/null || {
            echo "huggingface_hub not available, falling back to curl..."
            curl -L -C - -o "${GGUF_PATH}" "${GGUF_URL}"
        }
    else
        # Fallback to curl with resume
        curl -L -C - -o "${GGUF_PATH}" "${GGUF_URL}"
    fi
fi
echo -e "${GREEN}✓ GGUF downloaded${NC}"

# Create Modelfile (simple, same as glm-4.7-flash)
MODELFILE_PATH="${MODELS_DIR}/Modelfile.glm-stem"
cat > "${MODELFILE_PATH}" << 'EOF'
FROM ./glm-stem-42exp-VARIANT.gguf

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER top_k 2
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx 4096
PARAMETER num_predict 512
EOF

# Replace VARIANT placeholder
sed -i "s/VARIANT/${VARIANT}/g" "${MODELFILE_PATH}"
echo -e "${GREEN}✓ Modelfile created${NC}"

# Create model in Ollama
echo ""
echo "Creating Ollama model..."
ollama create "${MODEL_NAME}" -f "${MODELFILE_PATH}"
echo -e "${GREEN}✓ Model registered in Ollama${NC}"

# Verification test
echo ""
echo "Running verification test..."
RESPONSE=$(ollama run "${MODEL_NAME}" "What is 2 + 2?" 2>&1 | head -5)
if [[ -n "$RESPONSE" ]]; then
    echo -e "${GREEN}✓ Model responds correctly${NC}"
    echo "Sample response: ${RESPONSE:0:100}..."
else
    echo -e "${RED}WARNING: Model may not be working correctly${NC}"
fi

echo ""
echo "=============================================="
echo -e "${GREEN}  Installation Complete!${NC}"
echo "=============================================="
echo ""
echo "Usage:"
echo "  ollama run ${MODEL_NAME} \"Solve: 2x + 5 = 13\""
echo ""
echo "In MITS:"
echo "  The model will be used automatically as the default."
echo ""
