"""
MITS - Main Entry Point

Run the tutoring system from command line.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MITS - Mathematics Intelligent Tutoring System"
    )
    
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch Gradio web interface"
    )
    
    parser.add_argument(
        "--api",
        action="store_true", 
        help="Launch FastAPI server"
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port to bind to"
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check system configuration"
    )
    
    args = parser.parse_args()
    
    if args.check:
        check_system()
        return
    
    if args.api:
        launch_api(args.host, args.port)
    else:
        # Default: launch UI
        launch_ui(args.host, args.port)


def check_system():
    """Check system configuration and dependencies."""
    print("🔍 Checking MITS system configuration...\n")
    
    # Check Python version
    import sys
    py_version = sys.version_info
    print(f"Python: {py_version.major}.{py_version.minor}.{py_version.micro}", end=" ")
    if py_version >= (3, 10):
        print("✅")
    else:
        print("❌ (requires 3.10+)")
    
    # Check dependencies
    deps = [
        ("torch", "torch"),
        ("ollama", "ollama"),
        ("gradio", "gradio"),
        ("sympy", "sympy"),
        ("pydantic", "pydantic"),
        ("structlog", "structlog"),
    ]
    
    for name, module in deps:
        try:
            __import__(module)
            print(f"{name}: ✅")
        except ImportError:
            print(f"{name}: ❌ (not installed)")
    
    # Check Ollama connection
    print("\n🔌 Checking Ollama connection...")
    try:
        from src.models.llm_client import LLMClient
        from src.config import settings
        
        client = LLMClient()
        if client.check_connection():
            print(f"Ollama ({settings.OLLAMA_HOST}): ✅")
            
            models = client.list_models()
            print(f"Available models: {len(models)}")
            
            # Check for required model
            model_name = settings.MODEL_NAME.split(':')[0]
            if any(model_name in m for m in models):
                print(f"Model {settings.MODEL_NAME}: ✅")
            else:
                print(f"Model {settings.MODEL_NAME}: ❌ (not found)")
                print(f"  Run: ollama pull {settings.MODEL_NAME}")
        else:
            print(f"Ollama: ❌ (not running)")
            print("  Run: ollama serve")
    except Exception as e:
        print(f"Ollama: ❌ ({e})")
    
    print("\n✨ System check complete!")


def launch_ui(host: str, port: int):
    """Launch Gradio interface."""
    print("🎓 Starting MITS Gradio Interface...")
    
    from interface.gradio_app import create_interface
    
    interface = create_interface()
    interface.launch(
        server_name=host,
        server_port=port,
        share=False,
        show_error=True
    )


def launch_api(host: str, port: int):
    """Launch FastAPI server."""
    print("🚀 Starting MITS API Server...")
    
    import uvicorn
    
    uvicorn.run(
        "interface.api:app",
        host=host,
        port=port,
        reload=True
    )


if __name__ == "__main__":
    main()
