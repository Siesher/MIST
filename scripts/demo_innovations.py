#!/usr/bin/env python3
"""
MITS Groundbreaking Innovations Demo Script

Demonstrates all 6 innovative features implemented in feature 009:
1. Affective State Detection
2. Generative Task Synthesis
3. Counterfactual Explanations
4. Metacognitive Scaffolding
5. Learning Path Optimization
6. Multi-Modal Math Input

Usage:
    python scripts/demo_innovations.py [--feature N]

Options:
    --feature N     Demo specific feature (1-6), or 0 for all
    --interactive   Enable interactive mode with user input
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


def print_header(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def demo_affective_detection():
    """Demo 1: Affective State Detection."""
    print_header("🎭 Feature 1: Affective State Detection")

    try:
        from src.models.affective_detector import AffectiveDetector

        detector = AffectiveDetector()
        print("✅ AffectiveDetector initialized\n")

        # Test messages with different emotional states
        test_cases = [
            ("Отлично, понял! Следующий пример?", 2000, True),
            ("не понмиаю ничего!!!", 500, False),
            ("Ну такое себе...", 15000, None),
            ("Это слишком легко, скучно", 1000, True),
            ("Хм, интересно, а что если...", 5000, None),
        ]

        print("Testing affective detection on various messages:\n")
        for message, response_time_ms, was_correct in test_cases:
            state = detector.analyze_message(
                message=message,
                response_time_ms=response_time_ms,
                context=[],
                was_correct=was_correct
            )

            print(f"Message: \"{message}\"")
            print(f"  → State: {state.state_type.value}")
            print(f"  → Confidence: {state.confidence:.2f}")
            print(f"  → Should simplify: {state.should_simplify}")
            print(f"  → Should encourage: {state.should_encourage}")
            print()

        # Get adaptation prompt
        print("Adaptation prompt example:")
        last_state = detector.analyze_message("не могу решить это!!!!", 500, [], False)
        prompt = detector.get_adaptation_prompt(last_state)
        print(f"  {prompt}\n")

        return True

    except ImportError as e:
        print(f"❌ Failed to import AffectiveDetector: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def demo_task_synthesis():
    """Demo 2: Generative Task Synthesis."""
    print_header("🎲 Feature 2: Generative Task Synthesis")

    try:
        from src.models.task_synthesizer import TaskSynthesizer

        synthesizer = TaskSynthesizer()
        print("✅ TaskSynthesizer initialized\n")

        # Generate tasks for different topics
        topics = [
            ("derivatives", "easy"),
            ("integrals", "medium"),
            ("limits", "hard"),
        ]

        print("Generating verified tasks:\n")
        for topic, difficulty in topics:
            task = synthesizer.generate_task(topic=topic, difficulty=difficulty)

            print(f"Topic: {topic} | Difficulty: {difficulty}")
            print(f"  Problem: {task.problem[:80]}...")
            print(f"  Answer: {task.answer}")
            print(f"  SymPy Verified: {'✅' if task.sympy_verified else '❌'}")
            print(f"  Status: {task.verification_status.value}")
            print()

        # Generate a variation
        print("Generating task variation:")
        base_task = synthesizer.generate_task(topic="derivatives", difficulty="easy")
        variation = synthesizer.generate_variation(base_task, "similar")
        print(f"  Original: {base_task.problem[:50]}...")
        print(f"  Variation: {variation.problem[:50]}...")
        print()

        return True

    except ImportError as e:
        print(f"❌ Failed to import TaskSynthesizer: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def demo_counterfactual():
    """Demo 3: Counterfactual Explanations."""
    print_header("🔍 Feature 3: Counterfactual Explanations")

    try:
        from src.models.counterfactual_engine import CounterfactualEngine
        from src.data.schemas import Task

        engine = CounterfactualEngine()
        print("✅ CounterfactualEngine initialized\n")

        # Create a sample task
        task = Task(
            id="demo_task",
            problem="Найди производную f(x) = x² · sin(x)",
            solution="f'(x) = 2x·sin(x) + x²·cos(x)",
            answer="2x·sin(x) + x²·cos(x)",
            topic="derivatives",
            skills=["product_rule", "derivatives_basic"]
        )

        # Analyze an incorrect answer (common mistake: forgetting product rule)
        student_answer = "2x · cos(x)"  # Wrong: treated as simple derivative
        correct_answer = "2x·sin(x) + x²·cos(x)"

        print("Analyzing student error:")
        print(f"  Task: {task.problem}")
        print(f"  Student answer: {student_answer}")
        print(f"  Correct answer: {correct_answer}")
        print()

        explanation = engine.analyze_error(
            student_answer=student_answer,
            correct_answer=correct_answer,
            task=task
        )

        print("Counterfactual Explanation:")
        print(f"  Missing skill: {explanation.missing_skill}")
        print(f"  Explanation: {explanation.counterfactual_statement_ru}")
        print()

        # Format for display
        display = engine.format_explanation_for_display(explanation)
        print("Formatted display:")
        print(display)
        print()

        return True

    except ImportError as e:
        print(f"❌ Failed to import CounterfactualEngine: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def demo_metacognitive():
    """Demo 4: Metacognitive Scaffolding."""
    print_header("🧠 Feature 4: Metacognitive Scaffolding")

    try:
        from src.models.metacognitive_tracker import MetacognitiveTracker

        tracker = MetacognitiveTracker()
        print("✅ MetacognitiveTracker initialized\n")

        # Simulate a student getting stuck
        stuck_messages = [
            "Не понимаю, что делать дальше",
            "Какой метод тут использовать?",
            "правильно?",
            "Не могу, слишком сложно!",
        ]

        print("Detecting stuck points and generating metacognitive prompts:\n")
        for message in stuck_messages:
            stuck_point = tracker.detect_stuck_point(message)

            if stuck_point:
                prompt = tracker.get_metacognitive_prompt(stuck_point)
                tracker.record_intervention(stuck_point, "metacognitive_prompt", prompt)

                print(f"Student: \"{message}\"")
                print(f"  Stuck type: {stuck_point.type.value}")
                print(f"  Confidence: {stuck_point.confidence:.2f}")
                print(f"  Tutor response: \"{prompt}\"")
                print()

            tracker.increment_message_count()

        # End-of-session reflection
        print("End-of-session reflection:")
        reflection = tracker.get_reflection_prompt(
            session_duration_minutes=45,
            tasks_attempted=10,
            tasks_correct=7,
            topics_covered=["производные", "интегралы"]
        )
        print(reflection[:500] + "...\n")

        # Metacognitive profile
        print("Metacognitive profile:")
        profile = tracker.update_profile()
        print(f"  Overall level: {profile.overall_level.value}")
        print(f"  Awareness: {profile.awareness_level.value}")
        print(f"  Regulation: {profile.regulation_level.value}")
        print(f"  Evaluation: {profile.evaluation_level.value}")
        print()

        return True

    except ImportError as e:
        print(f"❌ Failed to import MetacognitiveTracker: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def demo_learning_path():
    """Demo 5: Learning Path Optimization."""
    print_header("🗺️ Feature 5: Learning Path Optimization")

    try:
        from src.models.learning_path_optimizer import LearningPathOptimizer

        optimizer = LearningPathOptimizer()
        print("✅ LearningPathOptimizer initialized\n")

        # Simulate student mastery
        student_mastery = {
            "arithmetic": 0.95,
            "algebra_basic": 0.85,
            "functions": 0.6,
            "limits_intro": 0.3,
            "limits_techniques": 0.1,
            "derivatives_basic": 0.0,
        }

        print("Student current mastery:")
        for skill, mastery in student_mastery.items():
            bar = "█" * int(mastery * 10) + "░" * (10 - int(mastery * 10))
            print(f"  {skill}: [{bar}] {mastery:.0%}")
        print()

        # Create learning path to definite_integrals
        print("Creating path to: definite_integrals\n")
        path = optimizer.create_path(
            target_skill="definite_integrals",
            student_mastery=student_mastery,
            student_id="demo_student"
        )

        print(f"Path created with {len(path.skills)} skills")
        print(f"Estimated time: {path.estimated_hours:.1f} hours\n")

        # Visualize
        print("Path visualization (ASCII):\n")
        visualization = optimizer.visualize_path(path, format="ascii")
        print(visualization)
        print()

        # Get next skill
        next_skill = optimizer.get_next_skill(path)
        if next_skill:
            print(f"Next skill to study: {next_skill.skill_name_ru}")
            print(f"  Tasks needed: ~{next_skill.estimated_tasks}")
        print()

        # Recommendations
        print("Skill recommendations:")
        recs = optimizer.get_skill_recommendations(student_mastery, count=3)
        for rec in recs:
            print(f"  • {rec['skill_name_ru']}: {rec['rationale']}")
        print()

        return True

    except ImportError as e:
        print(f"❌ Failed to import LearningPathOptimizer: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def demo_vision():
    """Demo 6: Multi-Modal Math Input."""
    print_header("📷 Feature 6: Multi-Modal Math Input (Vision)")

    try:
        from src.models.vision_analyzer import VisionAnalyzer

        analyzer = VisionAnalyzer()
        print("✅ VisionAnalyzer initialized\n")

        # Check if vision model is available
        available = analyzer.is_available()
        print(f"Vision model (minicpm-v) available: {'✅' if available else '❌'}")

        if not available:
            print("\nTo enable vision features, run:")
            print("  ollama pull minicpm-v")
            print()

        # Demonstrate parsing logic with mock response
        print("\nDemonstrating OCR response parsing:")
        mock_response = """
        STEP 1: f(x) = x^2 \\cdot \\sin(x)
        STEP 2: f'(x) = 2x \\cdot \\sin(x) + x^2 \\cdot \\cos(x) | OK
        STEP 3: f'(x) = 2x\\sin(x) + x^2\\cos(x) | OK
        """

        steps = analyzer._parse_extraction_response(mock_response)
        print(f"\nParsed {len(steps)} steps from mock response:")
        for step in steps:
            print(f"  Step {step['step_num']}: {step['latex'][:40]}...")
            print(f"    Status: {step['status']}, Confidence: {step['confidence']:.2f}")
        print()

        # Verify steps
        print("Verifying steps with SymPy:")
        verified = analyzer.verify_steps(steps)
        for v in verified:
            status = "✅" if v.is_correct else "❌" if v.is_correct == False else "❓"
            print(f"  Step {v.step_number}: {status} ({v.confidence.value})")
        print()

        # Generate feedback
        print("Generated feedback:")
        feedback = analyzer._generate_feedback(verified, True)
        print(feedback)
        print()

        return True

    except ImportError as e:
        print(f"❌ Failed to import VisionAnalyzer: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main demo runner."""
    parser = argparse.ArgumentParser(description="MITS Innovations Demo")
    parser.add_argument(
        "--feature",
        type=int,
        default=0,
        help="Feature to demo (1-6), 0 for all"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enable interactive mode"
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  MITS Groundbreaking Innovations Demo")
    print("  Feature 009: Diploma Defense Ready")
    print("=" * 60)

    demos = [
        (1, "Affective State Detection", demo_affective_detection),
        (2, "Generative Task Synthesis", demo_task_synthesis),
        (3, "Counterfactual Explanations", demo_counterfactual),
        (4, "Metacognitive Scaffolding", demo_metacognitive),
        (5, "Learning Path Optimization", demo_learning_path),
        (6, "Multi-Modal Math Input", demo_vision),
    ]

    results = []

    for num, name, func in demos:
        if args.feature == 0 or args.feature == num:
            try:
                success = func()
                results.append((name, success))
            except KeyboardInterrupt:
                print("\n\n⏹️ Demo interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error in {name}: {e}")
                results.append((name, False))

            if args.interactive and args.feature == 0:
                input("\n[Press Enter to continue to next demo...]")

    # Summary
    print_header("📊 Demo Summary")
    print("Results:")
    for name, success in results:
        status = "✅ Success" if success else "❌ Failed"
        print(f"  {name}: {status}")

    total = len(results)
    passed = sum(1 for _, s in results if s)
    print(f"\nTotal: {passed}/{total} features working")

    if passed == total:
        print("\n🎉 All innovations ready for diploma defense!")
    else:
        print("\n⚠️ Some features need attention")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
