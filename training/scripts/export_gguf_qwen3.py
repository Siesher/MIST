"""
GGUF Export Script for Fine-Tuned Qwen3 Models

Exports trained LoRA adapters to GGUF format for Ollama deployment.
Supports Q4_K_M (primary), Q5_K_M (quality), Q8_0 (high quality).

Usage:
    # On Colab (with Unsloth):
    python training/scripts/export_gguf_qwen3.py \
        --model-size 4b \
        --adapter-path /content/drive/MyDrive/MITS/adapters/qwen3-4b-final \
        --output-dir /content/drive/MyDrive/MITS/gguf/ \
        --quantizations q4_k_m q8_0

    # Verify exported GGUF:
    python training/scripts/export_gguf_qwen3.py \
        --verify /path/to/model.gguf \
        --ollama-host http://localhost:11434
"""

import os
import json
import logging
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Model configurations
MODEL_CONFIGS = {
    "4b": {
        "base_model": "unsloth/Qwen3-4B-Instruct-2507",
        "ollama_name": "mits-tutor-qwen3-4b",
        "hf_repo": "Siesher/mits-qwen3-4b-final",
    },
    "9b": {
        "base_model": "unsloth/Qwen3.5-9B",
        "ollama_name": "mits-tutor-qwen3.5-9b",
        "hf_repo": "Siesher/mits-qwen3-9b-final",
    },
}

# STEM test prompts (5 per domain = 25 total) for GGUF verification
VERIFICATION_PROMPTS = {
    "math": [
        "Реши уравнение x² - 5x + 6 = 0",
        "Найди производную функции f(x) = 3x³ + 2x² - x + 5",
        "Вычисли интеграл ∫(2x + 3)dx",
        "Чему равна сумма углов треугольника? Объясни почему.",
        "Найди площадь круга с радиусом 7 см",
    ],
    "physics": [
        "Тело массой 5 кг движется со скоростью 10 м/с. Найди кинетическую энергию.",
        "Рассчитай силу тока в цепи с напряжением 220В и сопротивлением 110 Ом.",
        "Какой закон Ньютона описывает инерцию? Приведи пример.",
        "Тело падает с высоты 80 м. Найди время падения (g=10 м/с²).",
        "Объясни, почему лёд плавает на поверхности воды.",
    ],
    "chemistry": [
        "Уравняй реакцию: Fe + O₂ → Fe₂O₃",
        "Рассчитай молярную массу H₂SO₄",
        "Какая масса NaCl нужна для приготовления 500 мл 0.1 М раствора?",
        "Чем отличается ковалентная связь от ионной?",
        "Что такое электролиз? Объясни на примере.",
    ],
    "cs": [
        "Напиши функцию на Python для проверки, является ли число простым.",
        "Какова временная сложность бинарного поиска? Объясни почему.",
        "Отсортируй массив [5, 2, 8, 1, 9] методом пузырька. Покажи шаги.",
        "Чем стек отличается от очереди? Приведи примеры использования.",
        "Напиши рекурсивную функцию вычисления факториала на Python.",
    ],
    "biology": [
        "Какие органеллы клетки отвечают за синтез белка?",
        "Объясни первый закон Менделя на примере.",
        "Что такое фотосинтез? Напиши общее уравнение реакции.",
        "Какие уровни организации живой материи ты знаешь?",
        "Чем митоз отличается от мейоза?",
    ],
}


def export_gguf(
    model_size: str,
    adapter_path: str,
    output_dir: str,
    quantizations: List[str],
) -> Dict[str, str]:
    """Export LoRA adapter to GGUF format using Unsloth.

    Args:
        model_size: "4b" or "1.7b"
        adapter_path: Path to trained LoRA adapter directory
        output_dir: Output directory for GGUF files
        quantizations: List of quantization methods (e.g., ["q4_k_m", "q5_k_m", "q8_0"])

    Returns:
        Dict mapping quantization -> output file path
    """
    from unsloth import FastLanguageModel

    config = MODEL_CONFIGS[model_size]
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Loading base model: {config['base_model']}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=adapter_path,
        max_seq_length=4096,
        dtype=None,
        load_in_4bit=True,
    )

    exported = {}
    for quant in quantizations:
        output_name = f"{config['ollama_name']}-{quant}"
        output_path = os.path.join(output_dir, output_name)

        logger.info(f"Exporting {quant} to {output_path}...")
        model.save_pretrained_gguf(
            output_path,
            tokenizer,
            quantization_method=quant,
        )

        # Find the actual GGUF file
        gguf_file = None
        for f in os.listdir(output_path):
            if f.endswith(".gguf"):
                gguf_file = os.path.join(output_path, f)
                break

        if gguf_file:
            exported[quant] = gguf_file
            size_mb = os.path.getsize(gguf_file) / (1024 * 1024)
            logger.info(f"  {quant}: {gguf_file} ({size_mb:.1f} MB)")
        else:
            logger.warning(f"  {quant}: GGUF file not found in {output_path}")

    return exported


def verify_gguf(
    gguf_path: str,
    ollama_host: str = "http://localhost:11434",
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify GGUF model by running test prompts through Ollama.

    Tests 5 prompts per STEM domain (25 total).
    """
    import requests

    if model_name is None:
        model_name = Path(gguf_path).stem

    results = {"model": model_name, "domains": {}, "total": 0, "responded": 0}

    for domain, prompts in VERIFICATION_PROMPTS.items():
        domain_results = []

        for prompt in prompts:
            results["total"] += 1
            try:
                resp = requests.post(
                    f"{ollama_host}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 512,
                        },
                    },
                    timeout=120,
                )

                if resp.status_code == 200:
                    response_text = resp.json().get("response", "")
                    results["responded"] += 1
                    domain_results.append({
                        "prompt": prompt,
                        "response": response_text[:200] + "..." if len(response_text) > 200 else response_text,
                        "tokens": len(response_text.split()),
                        "has_thinking": "<think>" in response_text,
                        "has_question": "?" in response_text.split("</think>")[-1] if "</think>" in response_text else "?" in response_text,
                        "status": "ok",
                    })
                else:
                    domain_results.append({
                        "prompt": prompt,
                        "status": f"error_{resp.status_code}",
                    })

            except Exception as e:
                domain_results.append({
                    "prompt": prompt,
                    "status": f"error: {e}",
                })

        results["domains"][domain] = domain_results

    results["response_rate"] = results["responded"] / results["total"] if results["total"] else 0
    return results


def upload_to_huggingface(
    model_size: str,
    adapter_path: str,
    gguf_dir: str,
    token: Optional[str] = None,
) -> str:
    """Upload LoRA adapter + GGUF files to HuggingFace.

    Returns: HuggingFace repo URL
    """
    from huggingface_hub import HfApi

    config = MODEL_CONFIGS[model_size]
    api = HfApi(token=token)

    repo_id = config["hf_repo"]

    # Create repo if needed
    api.create_repo(repo_id, exist_ok=True, repo_type="model")

    # Upload adapter files
    logger.info(f"Uploading adapter from {adapter_path}...")
    api.upload_folder(
        folder_path=adapter_path,
        repo_id=repo_id,
        path_in_repo="adapter",
    )

    # Upload GGUF files
    gguf_path = Path(gguf_dir)
    for gguf_file in gguf_path.rglob("*.gguf"):
        logger.info(f"Uploading {gguf_file.name}...")
        api.upload_file(
            path_or_fileobj=str(gguf_file),
            path_in_repo=f"gguf/{gguf_file.name}",
            repo_id=repo_id,
        )

    url = f"https://huggingface.co/{repo_id}"
    logger.info(f"Upload complete: {url}")
    return url


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GGUF Export for Qwen3 MITS models")
    subparsers = parser.add_subparsers(dest="command")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export LoRA to GGUF")
    export_parser.add_argument("--model-size", choices=["4b", "9b", "1.7b"], required=True)
    export_parser.add_argument("--adapter-path", required=True)
    export_parser.add_argument("--output-dir", required=True)
    export_parser.add_argument("--quantizations", nargs="+",
                               default=["q4_k_m", "q5_k_m", "q8_0"])

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify GGUF via Ollama")
    verify_parser.add_argument("--model-name", required=True)
    verify_parser.add_argument("--ollama-host", default="http://localhost:11434")
    verify_parser.add_argument("--output", default="evaluation/reports/gguf_verification.json")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload to HuggingFace")
    upload_parser.add_argument("--model-size", choices=["4b", "9b", "1.7b"], required=True)
    upload_parser.add_argument("--adapter-path", required=True)
    upload_parser.add_argument("--gguf-dir", required=True)
    upload_parser.add_argument("--token", help="HuggingFace token")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.command == "export":
        exported = export_gguf(
            args.model_size, args.adapter_path,
            args.output_dir, args.quantizations,
        )
        print(json.dumps(exported, indent=2))

    elif args.command == "verify":
        results = verify_gguf(
            gguf_path="",
            model_name=args.model_name,
            ollama_host=args.ollama_host,
        )
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif args.command == "upload":
        url = upload_to_huggingface(
            args.model_size, args.adapter_path,
            args.gguf_dir, args.token,
        )
        print(f"Uploaded: {url}")
