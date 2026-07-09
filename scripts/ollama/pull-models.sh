#!/bin/bash
# Pull required Ollama models on first start.
# Auto-detects hardware to decide which models to pull.
#
# Usage: docker compose exec ollama sh -c '/app/scripts/pull-models.sh'
#   or run directly: ./scripts/pull-models.sh
#
# Options:
#   --all        Pull all models (GLM + Qwen3-4B + Qwen3-1.7B)
#   --qwen3      Pull only Qwen3 fine-tuned models
#   --glm        Pull only GLM model
#   --auto       Auto-detect hardware and pull appropriate models (default)

set -e

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODE="${1:---auto}"

echo "Waiting for Ollama to be ready..."
for i in $(seq 1 30); do
    if curl -s "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; then
        echo "Ollama is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "Error: Ollama not responding at ${OLLAMA_HOST}"
        exit 1
    fi
    echo "  attempt $i/30..."
    sleep 2
done

# Auto-detect available RAM (GB)
detect_ram() {
    if command -v free &> /dev/null; then
        free -g | awk '/^Mem:/ {print $2}'
    elif [ -f /proc/meminfo ]; then
        awk '/^MemTotal:/ {printf "%.0f", $2/1024/1024}' /proc/meminfo
    elif command -v sysctl &> /dev/null; then
        sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1024/1024/1024}'
    else
        echo "0"
    fi
}

pull_model() {
    local model_name="$1"
    local description="$2"
    echo ""
    echo "Pulling ${description} (${model_name})..."
    if ollama pull "$model_name"; then
        echo "  OK: ${model_name} pulled successfully"
    else
        echo "  Warning: ${model_name} pull failed (may need manual setup)"
    fi
}

# Pull based on mode
case "$MODE" in
    --all)
        echo "Pulling ALL models..."
        pull_model "glm-4.7-flash" "GLM-4.7-Flash (30B MoE, baseline)"
        pull_model "mits-tutor-qwen3-4b" "Qwen3-4B MITS Tutor (fine-tuned)"
        pull_model "mits-tutor-qwen3-1.7b" "Qwen3-1.7B MITS Tutor (lightweight)"
        pull_model "qwen2.5-vl:7b" "Vision model for OCR (optional)"
        ;;
    --qwen3)
        echo "Pulling Qwen3 fine-tuned models..."
        pull_model "mits-tutor-qwen3-4b" "Qwen3-4B MITS Tutor"
        pull_model "mits-tutor-qwen3-1.7b" "Qwen3-1.7B MITS Tutor"
        ;;
    --glm)
        echo "Pulling GLM model..."
        pull_model "glm-4.7-flash" "GLM-4.7-Flash"
        pull_model "qwen2.5-vl:7b" "Vision model for OCR (optional)"
        ;;
    --auto|*)
        RAM_GB=$(detect_ram)
        echo "Detected RAM: ${RAM_GB} GB"

        if [ "$RAM_GB" -ge 16 ] 2>/dev/null; then
            echo "16+ GB RAM: pulling Qwen3-4B (primary) + GLM (fallback)"
            pull_model "mits-tutor-qwen3-4b" "Qwen3-4B MITS Tutor (primary, ~4.5GB)"
            pull_model "glm-4.7-flash" "GLM-4.7-Flash (fallback)"
        elif [ "$RAM_GB" -ge 8 ] 2>/dev/null; then
            echo "8-16 GB RAM: pulling Qwen3-1.7B (primary)"
            pull_model "mits-tutor-qwen3-1.7b" "Qwen3-1.7B MITS Tutor (lightweight, ~3GB)"
            pull_model "mits-tutor-qwen3-4b" "Qwen3-4B MITS Tutor (if fits)"
        else
            echo "< 8 GB RAM: pulling GLM baseline only"
            pull_model "glm-4.7-flash" "GLM-4.7-Flash"
        fi

        # Always try vision model (optional, for OCR)
        pull_model "qwen2.5-vl:7b" "Vision model for OCR (optional)"
        ;;
esac

echo ""
echo "Done. Models available:"
ollama list
