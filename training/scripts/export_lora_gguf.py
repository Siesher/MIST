#!/usr/bin/env python3
"""
Export LoRA adapter weights to GGUF format for Ollama.

Pipeline:
    1. Load LoRA adapter from training output
    2. Convert to GGUF using llama.cpp's convert_lora_to_gguf.py
    3. Generate Ollama Modelfile with ADAPTER instruction

Usage:
    python training/scripts/export_lora_gguf.py \
        --adapter outputs/mits-tutor-glm/lora \
        --output outputs/mits-tutor-glm/ollama \
        --base-model glm4:9b

    # With Unsloth export (if run from Colab):
    python training/scripts/export_lora_gguf.py \
        --gguf-adapter outputs/mits-tutor-glm/lora_gguf/adapter.gguf \
        --output outputs/mits-tutor-glm/ollama \
        --base-model glm4:9b
"""

import argparse
import subprocess
import shutil
from pathlib import Path


MODELFILE_TEMPLATE = """FROM {base_model}
ADAPTER {adapter_path}

PARAMETER temperature 0.7
PARAMETER top_p 0.95
PARAMETER min_p 0.01
PARAMETER num_ctx 4096
PARAMETER stop <|im_end|>
PARAMETER stop <|endoftext|>

SYSTEM \"\"\"Ты — сократический репетитор по математике. Помогай студентам находить решения через наводящие вопросы.
Используй $LaTeX$ для формул. Отвечай на русском.
Формат ответа: {{"move": "тип", "message": "ответ", "reasoning": "обоснование"}}\"\"\"
"""


def find_llama_convert_script() -> Path | None:
    """Find llama.cpp's convert_lora_to_gguf.py."""
    candidates = [
        Path("llama.cpp/convert_lora_to_gguf.py"),
        Path.home() / "llama.cpp" / "convert_lora_to_gguf.py",
        Path("/opt/llama.cpp/convert_lora_to_gguf.py"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def convert_lora_to_gguf(adapter_dir: Path, output_path: Path) -> bool:
    """Convert HuggingFace LoRA adapter to GGUF format."""
    script = find_llama_convert_script()
    if not script:
        print("WARNING: llama.cpp convert_lora_to_gguf.py not found.")
        print("Options:")
        print("  1. Use Unsloth's save_pretrained_gguf() in the notebook")
        print("  2. Clone llama.cpp and run: python convert_lora_to_gguf.py --outfile <output>")
        return False

    cmd = [
        "python", str(script),
        "--outfile", str(output_path),
        str(adapter_dir)
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False

    print(f"GGUF adapter saved: {output_path}")
    return True


def create_modelfile(
    output_dir: Path,
    base_model: str,
    adapter_path: Path,
) -> Path:
    """Generate Ollama Modelfile."""
    modelfile_path = output_dir / "Modelfile"
    content = MODELFILE_TEMPLATE.format(
        base_model=base_model,
        adapter_path=adapter_path.name,
    )
    modelfile_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Modelfile created: {modelfile_path}")
    return modelfile_path


def main():
    parser = argparse.ArgumentParser(description="Export LoRA to GGUF for Ollama")
    parser.add_argument("--adapter", type=str, default=None,
                        help="Path to HuggingFace LoRA adapter directory")
    parser.add_argument("--gguf-adapter", type=str, default=None,
                        help="Path to pre-converted GGUF adapter file")
    parser.add_argument("--output", "-o", type=str, required=True,
                        help="Output directory for Ollama files")
    parser.add_argument("--base-model", type=str, default="glm4:9b",
                        help="Ollama base model name (default: glm4:9b)")
    parser.add_argument("--model-name", type=str, default="mits-tutor-ft",
                        help="Name for the Ollama model (default: mits-tutor-ft)")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine GGUF adapter path
    if args.gguf_adapter:
        gguf_path = Path(args.gguf_adapter)
        if not gguf_path.exists():
            print(f"Error: GGUF adapter not found: {gguf_path}")
            return 1
        # Copy to output dir
        dest = output_dir / gguf_path.name
        if dest != gguf_path:
            shutil.copy2(gguf_path, dest)
        gguf_path = dest
    elif args.adapter:
        adapter_dir = Path(args.adapter)
        if not adapter_dir.exists():
            print(f"Error: Adapter directory not found: {adapter_dir}")
            return 1
        gguf_path = output_dir / "adapter.gguf"
        if not convert_lora_to_gguf(adapter_dir, gguf_path):
            print("Conversion failed. Use Unsloth export or install llama.cpp.")
            # Still create Modelfile for manual use
            gguf_path = output_dir / "adapter.gguf"
    else:
        print("Error: Provide either --adapter or --gguf-adapter")
        return 1

    # Create Modelfile
    create_modelfile(output_dir, args.base_model, gguf_path)

    print(f"\nTo deploy in Ollama:")
    print(f"  cd {output_dir}")
    print(f"  ollama create {args.model_name} -f Modelfile")
    print(f"  ollama run {args.model_name}")

    return 0


if __name__ == "__main__":
    exit(main())
