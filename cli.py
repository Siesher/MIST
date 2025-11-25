"""
MITS Interactive CLI

Test the tutoring system in command line.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.models.llm_client import LLMClient
from src.agents.tutor_agent import SocraticTutorAgent
from src.agents.task_generator import TaskGeneratorAgent
from src.agents.response_verifier import ResponseVerifierAgent
from src.data.schemas import TutoringSession, Difficulty
from src.config import settings


def print_header():
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " MITS - Socratic Math Tutor (CLI Mode) ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    print()


def print_help():
    print("\nCommands:")
    print("  /hint    - Get a hint")
    print("  /solution - Show solution")
    print("  /new     - New problem")
    print("  /quit    - Exit")
    print()


def main():
    print_header()
    
    # Initialize
    print("Connecting to Ollama...")
    try:
        client = LLMClient()
        if not client.check_connection():
            print("❌ Cannot connect to Ollama. Run: ollama serve")
            return
        print(f"✅ Connected! Using model: {settings.MODEL_NAME}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    tutor = SocraticTutorAgent(client)
    generator = TaskGeneratorAgent(client)
    verifier = ResponseVerifierAgent(client)
    
    print_help()
    
    # Main loop
    while True:
        # Generate task
        print("\n" + "─" * 60)
        topic = input("Topic (derivatives/integrals/limits) [derivatives]: ").strip() or "derivatives"
        diff = input("Difficulty (easy/medium/hard) [medium]: ").strip() or "medium"
        
        print(f"\nGenerating {diff} {topic} problem...")
        try:
            task = generator.generate_task(topic=topic, difficulty=Difficulty(diff))
        except Exception as e:
            print(f"❌ Error generating task: {e}")
            continue
        
        session = TutoringSession(id="cli", student_id="cli_user", task=task)
        
        print("\n" + "═" * 60)
        print("📚 PROBLEM:")
        print(task.problem)
        print("═" * 60)
        print("\nWhat's your approach? (Type your answer or /help)")
        
        # Tutoring loop
        while not session.is_solved:
            user_input = input("\n👤 You: ").strip()
            
            if not user_input:
                continue
            
            # Commands
            if user_input.lower() == "/quit":
                print("\nGoodbye! Keep learning! 🎓")
                return
            
            if user_input.lower() == "/help":
                print_help()
                continue
            
            if user_input.lower() == "/hint":
                if session.hints_used < len(task.hints):
                    hint = task.hints[session.hints_used]
                    session.hints_used += 1
                    print(f"\n💡 Hint {session.hints_used}: {hint}")
                else:
                    print("\n❌ No more hints available!")
                continue
            
            if user_input.lower() == "/solution":
                print(f"\n📖 Solution:\n{task.solution}")
                print(f"\n✅ Answer: {task.answer}")
                session.told_answer = True
                break
            
            if user_input.lower() == "/new":
                break
            
            # Process message
            session.add_student_message(user_input)
            
            # Verify
            result = verifier.verify(task, user_input)
            
            if result.is_correct:
                session.is_solved = True
                print("\n🎉 " + "═" * 56)
                print("   CORRECT! Excellent work!")
                print("   " + "═" * 56)
                print(f"\n   Your answer: {user_input}")
                print(f"   Attempts: {session.attempts}")
                print(f"   Hints used: {session.hints_used}")
                break
            
            # Get tutor response
            response = tutor.generate_response(
                session=session,
                student_message=user_input,
                verification_result=result
            )
            session.add_tutor_response(response)
            
            move_emoji = {
                "scaffolding": "🎯", "problematize": "🤔",
                "rectify": "📝", "encourage": "⭐",
                "hint": "💡", "tell": "📖"
            }
            emoji = move_emoji.get(response.move.value, "")
            
            print(f"\n{emoji} Tutor: {response.message}")
        
        # Ask to continue
        again = input("\nTry another problem? (y/n): ").strip().lower()
        if again != 'y':
            print("\nGoodbye! Keep learning! 🎓")
            break


if __name__ == "__main__":
    main()
