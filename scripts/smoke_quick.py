"""
MITS Quick Test Script

Test the tutoring system without UI.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.response_verifier import ResponseVerifierAgent
from src.agents.task_generator import TaskGeneratorAgent
from src.agents.tutor_agent import SocraticTutorAgent
from src.config import settings
from src.data.schemas import Difficulty, TutoringSession
from src.models.llm_client import LLMClient


def main():
    print("=" * 60)
    print("  MITS Quick Test")
    print("=" * 60)
    print()

    # 1. Test LLM Connection
    print("[1/4] Testing LLM connection...")
    try:
        client = LLMClient()
        if client.check_connection():
            print(f"  ✅ Connected to Ollama at {settings.OLLAMA_HOST}")
            models = client.list_models()
            print(f"  ✅ Available models: {len(models)}")
        else:
            print("  ❌ Cannot connect to Ollama")
            print("     Run: ollama serve")
            return
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return

    # 2. Test Task Generator
    print("\n[2/4] Testing Task Generator...")
    try:
        generator = TaskGeneratorAgent(client)
        task = generator.generate_task(
            topic="derivatives",
            difficulty=Difficulty.EASY
        )
        print(f"  ✅ Generated task: {task.problem[:50]}...")
        print(f"  ✅ Answer: {task.answer}")
        print(f"  ✅ Hints: {len(task.hints)}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return

    # 3. Test Tutor Agent
    print("\n[3/4] Testing Tutor Agent...")
    try:
        tutor = SocraticTutorAgent(client)
        session = TutoringSession(
            id="test",
            student_id="test_user",
            task=task
        )

        response = tutor.generate_response(
            session=session,
            student_message="I don't know how to start"
        )
        print(f"  ✅ Tutor move: {response.move.value}")
        print(f"  ✅ Response: {response.message[:80]}...")
        print(f"  ✅ Is telling: {response.is_telling}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return

    # 4. Test Verifier
    print("\n[4/4] Testing Response Verifier...")
    try:
        verifier = ResponseVerifierAgent(client)
        result = verifier.verify(task, "2x")
        print("  ✅ Verification works")
        print(f"  ✅ Is correct: {result.is_correct}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return

    print("\n" + "=" * 60)
    print("  ✅ All tests passed! MITS is ready.")
    print("=" * 60)
    print("\nTo start the UI, run:")
    print("  python -m interface.gradio_app")
    print("\nOr double-click: launch.bat")


if __name__ == "__main__":
    main()
