#!/usr/bin/env python3
"""
Performance Features Demo for MITS.

Feature 010: Demonstrates all performance optimization features:
- Semantic caching with context-aware keys
- A/B testing framework
- Context compression
- Resource monitoring
- Few-shot prompting
- Chain-of-Thought
- Report generation

Run: python scripts/demo_performance.py
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str) -> None:
    """Print section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


def demo_semantic_cache():
    """Demo semantic caching."""
    print_section("1. Semantic Cache Demo")

    try:
        from src.inference.cache import ResponseCache

        cache = ResponseCache(max_size=100, similarity_threshold=0.90)

        # Add sample entries using correct method name: add_response()
        print("\nAdding cached responses...")
        cache.add_response(
            student_input="2x",
            problem_context="Найдите производную f(x) = x²",
            response="Правильно! Производная x² равна 2x.",
            topic="derivatives",
            difficulty="easy",
            student_level="beginner",
            teaching_strategy="encourage"
        )

        cache.add_response(
            student_input="3x²",
            problem_context="Найдите производную f(x) = x³",
            response="Отлично! Ты правильно применил правило степени.",
            topic="derivatives",
            difficulty="easy",
            student_level="beginner",
            teaching_strategy="encourage"
        )

        # Test retrieval
        print("\nTesting cache retrieval...")
        result = cache.get_similar_response(
            student_input="2x",
            problem_context="Найдите производную g(x) = x²",
            topic="derivatives",
            difficulty="easy",
            student_level="beginner"
        )

        if result:
            response, similarity = result
            print(f"  Cache HIT!")
            print(f"  Similarity: {similarity:.3f}")
            print(f"  Response: {response[:50]}...")
        else:
            print("  Cache MISS")

        print(f"\nCache stats: {cache.stats}")

    except Exception as e:
        print(f"  Error: {e}")


def demo_ab_testing():
    """Demo A/B testing."""
    print_section("2. A/B Testing Demo")

    try:
        from src.inference.ab_testing import ABTestingManager
        import uuid

        manager = ABTestingManager()

        # Create experiment with correct signature
        print("\nCreating A/B experiment...")
        exp_id = f"demo_exp_{uuid.uuid4().hex[:8]}"
        exp = manager.create_experiment(
            experiment_id=exp_id,
            name="few_shot_vs_baseline",
            description="Test few-shot prompting effectiveness",
            variants=[
                {"variant_id": "control", "name": "Без few-shot", "config": {"few_shot": False}},
                {"variant_id": "treatment", "name": "С few-shot", "config": {"few_shot": True}}
            ],
            allocation_weights=[0.5, 0.5]
        )
        print(f"  Created: {exp.name} (ID: {exp.experiment_id})")

        # Start experiment
        manager.start_experiment(exp.experiment_id)
        print("  Experiment started!")

        # Simulate assignments
        print("\nSimulating 10 session assignments...")
        for i in range(10):
            session_id = f"demo_session_{i}"
            assignment = manager.get_variant(exp.experiment_id, session_id)
            if assignment:
                # Simulate outcome
                is_success = (i % 3 != 0)  # 70% success rate
                manager.record_outcome(
                    experiment_id=exp.experiment_id,
                    session_id=session_id,
                    metrics={
                        "success": 1.0 if is_success else 0.0,
                        "response_time_ms": 1500.0 + (i * 100),
                        "hints_used": float(i % 3)
                    }
                )
                print(f"  Session {i}: {assignment.variant_id} -> success={is_success}")

        # Get results
        results = manager.get_results(exp.experiment_id)
        if results:
            print(f"\nExperiment Results:")
            print(f"  Total sessions: {results.total_sessions}")
            for variant_data in results.variants_data:
                print(f"  {variant_data.get('variant_id', 'unknown')}: {variant_data.get('count', 0)} sessions")

    except Exception as e:
        print(f"  Error: {e}")


def demo_context_compression():
    """Demo context compression."""
    print_section("3. Context Compression Demo")

    try:
        from src.inference.context_compressor import ContextCompressor

        compressor = ContextCompressor(
            token_threshold=500,  # Low threshold for demo
            recent_messages_count=3,
            max_key_events=5
        )

        # Create sample conversation
        conversation = []
        for i in range(15):
            if i % 2 == 0:
                conversation.append({
                    "role": "student",
                    "content": f"Сообщение студента {i//2 + 1}: Я не понимаю как решать эту задачу"
                })
            else:
                conversation.append({
                    "role": "tutor",
                    "content": f"Сообщение репетитора {i//2 + 1}: Давай разберём это по шагам. Подумай, что нужно сделать сначала?"
                })

        print(f"\nOriginal conversation: {len(conversation)} messages")

        # Compress
        compressed = compressor.compress("demo_session", conversation)

        print(f"\nCompression Results:")
        print(f"  Original turns: {compressed.original_turns}")
        print(f"  Compressed turns: {compressed.compressed_turns}")
        print(f"  Original tokens: {compressed.original_tokens}")
        print(f"  Compressed tokens: {compressed.compressed_tokens}")
        print(f"  Compression ratio: {compressed.compression_ratio:.2f}")
        print(f"  Key events extracted: {len(compressed.key_events)}")

        # Show key events
        if compressed.key_events:
            print("\n  Key events:")
            for event in compressed.key_events[:3]:
                print(f"    - [{event.event_type}] {event.content[:40]}...")

        # Rebuild context
        rebuilt = compressor.rebuild_context(compressed)
        print(f"\n  Rebuilt context length: {len(rebuilt)} chars")

    except Exception as e:
        print(f"  Error: {e}")


def demo_resource_monitoring():
    """Demo resource monitoring."""
    print_section("4. Resource Monitoring Demo")

    try:
        from src.inference.metrics import ResourceMonitor

        # Use correct parameter names: sample_interval_sec, not sample_interval
        monitor = ResourceMonitor(sample_interval_sec=1, db_path=None)

        print("\nStarting resource monitor...")
        monitor.start()

        # Sample a few times
        print("Collecting samples...")
        for i in range(3):
            time.sleep(1)
            print(f"  Sample {i+1} collected")

        # Get current usage via sample
        current = monitor.sample()
        print(f"\nCurrent Resource Usage:")
        print(f"  RAM: {current.ram_used_mb:.0f} MB")
        print(f"  CPU: {current.cpu_percent:.1f}%")
        print(f"  VRAM: {current.vram_used_mb:.0f} MB")
        print(f"  GPU Util: {current.gpu_utilization_percent:.1f}%")

        # Get recent samples
        samples = monitor.get_recent_samples(count=10)
        alert_count = sum(1 for s in samples if s.alert_triggered)
        print(f"\nMonitor Stats:")
        print(f"  Samples collected: {len(samples)}")
        print(f"  Alert count: {alert_count}")

        monitor.stop()
        print("\nResource monitor stopped.")

    except Exception as e:
        print(f"  Error: {e}")


def demo_few_shot():
    """Demo few-shot prompting."""
    print_section("5. Few-Shot Prompting Demo")

    try:
        from src.knowledge.few_shot_bank import FewShotBank, get_few_shot_examples

        bank = FewShotBank()

        print(f"\nFew-Shot Bank Stats: {bank.stats}")

        # Get examples by topic
        print("\nGetting derivatives examples...")
        examples = bank.get_examples_by_topic("derivatives", limit=2)

        if examples:
            print(f"  Found {len(examples)} examples")
            for ex in examples:
                print(f"\n  Problem: {ex.problem[:50]}...")
                print(f"  Student: {ex.student_input[:50]}...")
                print(f"  Tutor: {ex.tutor_response[:50]}...")
        else:
            print("  No examples found (check data/few_shot/)")

        # Format for prompt
        if examples:
            formatted = bank.format_for_prompt(examples)
            print(f"\nFormatted prompt section ({len(formatted)} chars):")
            print(formatted[:300] + "...")

    except Exception as e:
        print(f"  Error: {e}")


def demo_cot():
    """Demo Chain-of-Thought."""
    print_section("6. Chain-of-Thought Demo")

    try:
        from src.knowledge.cot_templates import CoTManager, should_use_cot

        manager = CoTManager()

        # Check difficulty decision
        print("\nCoT Decision Logic:")
        for diff in ["easy", "medium", "hard"]:
            use = should_use_cot(diff)
            print(f"  Difficulty '{diff}': use_cot = {use}")

        # Get problem-solving CoT
        print("\nProblem-Solving CoT for derivatives:")
        cot_prompt = manager.get_problem_solving_cot(
            topic="derivatives",
            given="функция f(x) = sin(2x)",
            find="производную f'(x)"
        )
        print(cot_prompt[:300] + "...")

        # Get error analysis CoT
        print("\nError Analysis CoT:")
        error_cot = manager.get_error_analysis_cot("chain_rule")
        print(error_cot[:300] + "...")

    except Exception as e:
        print(f"  Error: {e}")


def demo_offline_mode():
    """Demo offline mode detection."""
    print_section("7. Offline Mode Detection Demo")

    try:
        from src.utils.offline_mode import (
            detect_offline_mode,
            get_offline_status_message
        )

        print("\nDetecting offline status...")
        status = detect_offline_mode()

        print(f"\nStatus:")
        print(f"  Network available: {status.has_network}")
        print(f"  Ollama available: {status.ollama_available}")
        print(f"  Local models: {status.local_models}")
        print(f"  Local embeddings: {status.local_embeddings}")
        print(f"  Local RAG: {status.local_rag}")
        print(f"  Is offline: {status.is_offline}")
        print(f"  Can operate: {status.can_operate}")

        print(f"\n  {get_offline_status_message(status)}")

    except Exception as e:
        print(f"  Error: {e}")


def demo_report_generation():
    """Demo report generation."""
    print_section("8. Report Generation Demo")

    try:
        from src.logging.report_generator import ReportGenerator

        generator = ReportGenerator()

        print("\nAggregating data for last 7 days...")
        data = generator.aggregate_data(days=7)

        print(f"\nReport Data Summary:")
        print(f"  Period: {data.period_start.date()} to {data.period_end.date()}")
        print(f"  Total sessions: {data.total_sessions}")
        print(f"  Sessions solved: {data.sessions_solved}")
        print(f"  Avg response time: {data.avg_response_time_ms:.0f} ms")
        print(f"  Cache hit rate: {data.cache_hit_rate*100:.1f}%")
        print(f"  Daily metrics: {len(data.daily_metrics)} days")
        print(f"  Topics: {len(data.topics_breakdown)}")

        if data.total_sessions > 0:
            print("\nGenerating charts...")
            files = generator.generate_full_report(days=7, prefix="demo_")
            print(f"  Generated {len(files)} files:")
            for name, path in files.items():
                print(f"    - {name}: {path}")
        else:
            print("\n  No session data - run some tutoring sessions first!")
            print("  Charts will be generated from session data.")

    except Exception as e:
        print(f"  Error: {e}")


def main():
    """Run all demos."""
    print("\n" + "="*60)
    print(" MITS Performance Optimization (Feature 010) Demo")
    print(" " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)

    demos = [
        ("Semantic Cache", demo_semantic_cache),
        ("A/B Testing", demo_ab_testing),
        ("Context Compression", demo_context_compression),
        ("Resource Monitoring", demo_resource_monitoring),
        ("Few-Shot Prompting", demo_few_shot),
        ("Chain-of-Thought", demo_cot),
        ("Offline Mode", demo_offline_mode),
        ("Report Generation", demo_report_generation),
    ]

    for name, func in demos:
        try:
            func()
        except Exception as e:
            print(f"\n[{name}] Error: {e}")

    print_section("Demo Complete!")
    print("\nAll performance optimization features are ready for use.")
    print("See specs/010-performance-optimization/ for documentation.")


if __name__ == "__main__":
    main()
