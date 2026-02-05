#!/usr/bin/env python3
"""
ExLlamaV2 Setup Script

Helps with installing and configuring ExLlamaV2 for MITS.

Usage:
    python scripts/setup_exllama.py check      # Check if ExLlamaV2 is available
    python scripts/setup_exllama.py install    # Install ExLlamaV2
    python scripts/setup_exllama.py benchmark  # Run performance benchmark
    python scripts/setup_exllama.py convert    # Convert GGUF to ExLlama format
"""

import sys
import os
import subprocess
import argparse


cuda_path = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8\bin"
if os.path.exists(cuda_path):
    os.add_dll_directory(cuda_path)
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_cuda():
    """Check CUDA availability."""
    print("🔍 Checking CUDA...")

    try:
        import torch
        if torch.cuda.is_available():
            print(f"  ✅ CUDA available: {torch.version.cuda}")
            print(f"  ✅ GPU: {torch.cuda.get_device_name(0)}")
            print(f"  ✅ VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
            return True
        else:
            print("  ❌ CUDA not available")
            return False
    except ImportError:
        print("  ❌ PyTorch not installed")
        return False


def check_exllama():
    """Check if ExLlamaV2 is installed."""
    print("\n🔍 Checking ExLlamaV2...")

    try:
        from exllamav2 import ExLlamaV2, ExLlamaV2Config
        print("  ✅ ExLlamaV2 installed")

        # Check version
        try:
            import exllamav2
            version = getattr(exllamav2, '__version__', 'unknown')
            print(f"  ✅ Version: {version}")
        except:
            pass

        return True
    except ImportError as e:
        print(f"  ❌ ExLlamaV2 not installed: {e}")
        return False


def install_exllama():
    """Install ExLlamaV2."""
    print("\n📦 Installing ExLlamaV2...")

    # Check CUDA first
    if not check_cuda():
        print("\n⚠️  CUDA is required for ExLlamaV2")
        print("   Install PyTorch with CUDA first:")
        print("   pip install torch --index-url https://download.pytorch.org/whl/cu121")
        return False

    # Install ExLlamaV2
    print("\n📥 Installing exllamav2...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "exllamav2"
        ], check=True)
        print("  ✅ ExLlamaV2 installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Installation failed: {e}")
        print("\n   Try manual installation:")
        print("   pip install exllamav2 --no-build-isolation")
        return False


def run_benchmark(model_path: str = None):
    """Run performance benchmark."""
    print("\n⚡ Running benchmark...")

    if not check_exllama():
        print("  ❌ ExLlamaV2 not installed")
        return

    if not model_path:
        print("  ❌ Model path required for benchmark")
        print("     Usage: python setup_exllama.py benchmark --model /path/to/model")
        return

    try:
        from src.models.exllama_client import ExLlamaClient
        import time

        print(f"\n📂 Loading model from: {model_path}")
        start = time.time()
        client = ExLlamaClient(model_path=model_path)
        load_time = time.time() - start
        print(f"  ✅ Model loaded in {load_time:.1f}s")

        # Warmup
        print("\n🔥 Warmup...")
        client.generate("Hello", max_tokens=10)

        # Benchmark
        print("\n📊 Benchmarking...")
        prompts = [
            "What is 2+2?",
            "Explain derivatives in calculus.",
            "Write a Python function to find prime numbers.",
        ]

        total_tokens = 0
        total_time = 0

        for prompt in prompts:
            start = time.time()
            response = client.generate(prompt, max_tokens=100)
            elapsed = time.time() - start

            # Rough token count
            tokens = len(response.split())
            total_tokens += tokens
            total_time += elapsed

            print(f"  • {prompt[:30]}... → {tokens} tokens in {elapsed:.2f}s")

        tps = total_tokens / total_time
        print(f"\n📈 Results:")
        print(f"  • Average speed: {tps:.1f} tokens/sec")
        print(f"  • Total tokens: {total_tokens}")
        print(f"  • Total time: {total_time:.2f}s")

        # Get model info
        info = client.get_model_info()
        if 'num_experts' in info:
            print(f"\n🧠 MoE Info:")
            print(f"  • Total experts: {info['num_experts']}")
            print(f"  • Experts per token: {info['experts_per_token']}")

        client.unload()

    except Exception as e:
        print(f"  ❌ Benchmark failed: {e}")


def show_recommendations():
    """Show hardware recommendations."""
    print("\n📋 ExLlamaV2 Recommendations for MoE Models:")
    print()
    print("┌─────────────────┬───────────────┬─────────────────────────────┐")
    print("│ GPU VRAM        │ Expert Cache  │ Recommendation              │")
    print("├─────────────────┼───────────────┼─────────────────────────────┤")
    print("│ 4GB  (GTX 1650) │ 4 experts     │ Small models only           │")
    print("│ 6GB  (RTX 3060) │ 6-8 experts   │ GLM-4 Q4 with offloading    │")
    print("│ 8GB  (RTX 3070) │ 8-12 experts  │ GLM-4 Q4/Q8 comfortable     │")
    print("│ 12GB (RTX 4070) │ 16 experts    │ Full speed, larger context  │")
    print("│ 24GB (RTX 4090) │ 32+ experts   │ Multiple models, batch      │")
    print("└─────────────────┴───────────────┴─────────────────────────────┘")
    print()
    print("Optimal settings for RTX 2080 (8GB) with GLM-4:")
    print("  EXLLAMA_GPU_SPLIT=7.0")
    print("  EXLLAMA_EXPERT_CACHE=8")
    print("  CONTEXT_LENGTH=4096")


def main():
    parser = argparse.ArgumentParser(description="ExLlamaV2 Setup for MITS")
    parser.add_argument("command", choices=["check", "install", "benchmark", "info"],
                        help="Command to run")
    parser.add_argument("--model", type=str, help="Model path for benchmark")

    args = parser.parse_args()

    print("=" * 60)
    print("🚀 MITS ExLlamaV2 Setup")
    print("=" * 60)

    if args.command == "check":
        cuda_ok = check_cuda()
        exllama_ok = check_exllama()

        print("\n" + "=" * 60)
        if cuda_ok and exllama_ok:
            print("✅ ExLlamaV2 is ready to use!")
            print("\nTo enable in MITS, set in .env:")
            print("  MODEL_BACKEND=exllamav2")
            print("  EXLLAMA_MODEL_PATH=/path/to/your/model")
        else:
            print("❌ Setup incomplete")
            if not cuda_ok:
                print("  → Install CUDA-enabled PyTorch")
            if not exllama_ok:
                print("  → Run: python scripts/setup_exllama.py install")

    elif args.command == "install":
        install_exllama()
        check_exllama()

    elif args.command == "benchmark":
        run_benchmark(args.model)

    elif args.command == "info":
        show_recommendations()


if __name__ == "__main__":
    main()
