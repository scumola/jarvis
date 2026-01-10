#!/usr/bin/env python3
"""
Enhanced Procedural Memory & Learning Demo

Shows how Jarvis learns from experience and gets smarter over time
through intelligent heuristic management, adaptive thresholds, and
automatic confidence decay.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
from memory.procedural_memory import ProceduralMemoryManager
from orchestrator.retry_schemas import FailureType, RetryStrategy


def display_learning_insights(pm: ProceduralMemoryManager):
    """Display comprehensive learning insights."""
    print(pm.get_learning_insights())


def demo_basic_stats(pm: ProceduralMemoryManager):
    """Show basic statistics."""
    print("\n" + "="*70)
    print("BASIC STATISTICS")
    print("="*70)

    stats = pm.get_statistics()

    print(f"\nTotal Heuristics: {stats['total_heuristics']}")
    print(f"Average Confidence: {stats['average_confidence']:.2%}")

    print(f"\nBy Context Type:")
    for context, count in stats['by_context'].items():
        print(f"  {context}: {count} heuristics")

    print(f"\nSuccess Metrics:")
    metrics = stats['success_metrics']
    print(f"  Total Applications: {metrics['total_applications']}")
    print(f"  Success Rate: {metrics['average_success_rate']:.1%}")


def demo_adaptive_filtering():
    """Demonstrate adaptive confidence thresholds."""
    print("\n" + "="*70)
    print("ADAPTIVE THRESHOLD DEMONSTRATION")
    print("="*70)

    print("\nAdaptive filtering adjusts confidence requirements based on success rate:")
    print("  • High success rate (≥80%) → Lower confidence OK")
    print("  • Medium success rate (50-80%) → Normal confidence")
    print("  • Low success rate (<50%) → Higher confidence required")
    print("\nThis ensures reliable heuristics are used even if confidence drifts down,")
    print("while unreliable ones need high confidence to be applied.")


def demo_pattern_matching():
    """Demonstrate pattern matching."""
    print("\n" + "="*70)
    print("PATTERN MATCHING DEMONSTRATION")
    print("="*70)

    print("\nPattern matching allows heuristics to apply across similar contexts:")
    print("  1. Try exact context match first (e.g., 'filesystem')")
    print("  2. Fall back to 'general' context if no exact match")
    print("\nThis enables cross-domain learning while maintaining specificity.")


def demo_auto_decay():
    """Demonstrate automatic confidence decay."""
    print("\n" + "="*70)
    print("AUTOMATIC CONFIDENCE DECAY")
    print("="*70)

    print("\nConfidence automatically decays for unused heuristics:")
    print(f"  • Threshold: 7 days without use")
    print(f"  • Decay rate: 0.01 per day")
    print("\nThis ensures:")
    print("  ✓ Fresh heuristics are preferred")
    print("  ✓ Outdated strategies fade away")
    print("  ✓ System adapts to changing patterns")


def demo_learning_simulation(pm: ProceduralMemoryManager):
    """Simulate learning over time."""
    print("\n" + "="*70)
    print("LEARNING SIMULATION")
    print("="*70)

    print("\nSimulating how Jarvis learns from retry successes...")

    # Simulate a few successful retries
    scenarios = [
        ("filesystem", FailureType.INCORRECT_ASSUMPTIONS, RetryStrategy.VERIFICATION_FIRST,
         "Verify assumptions before acting on filesystem tasks"),
        ("web_retrieval", FailureType.TOOL_MISUSE, RetryStrategy.ALTERNATIVE_METHOD,
         "Try different retrieval method when initial fails"),
        ("general", FailureType.PARTIAL_SOLUTION, RetryStrategy.DECOMPOSITION,
         "Break complex tasks into smaller steps"),
    ]

    for context, failure, strategy, notes in scenarios:
        print(f"\n✓ Recording success: {context}/{failure.value} → {strategy.value}")
        pm.record_success(context, failure, strategy, notes)

    print("\nLearning recorded! Querying heuristics...")

    # Query what was learned
    for context, failure, _, _ in scenarios:
        heuristics = pm.query_heuristics(context, failure)
        if heuristics:
            h = heuristics[0]
            print(f"\n📚 {context}/{failure.value}:")
            print(f"    Strategy: {h.effective_strategy.value}")
            print(f"    Confidence: {h.confidence_score:.2%}")
            print(f"    Usage: {h.usage_count}x (Success: {h.success_count}, Fail: {h.failure_count})")


def main():
    print("\n" + "="*70)
    print("ENHANCED PROCEDURAL MEMORY & LEARNING DEMO")
    print("="*70)
    print("\nThis demo shows Jarvis's intelligent learning capabilities:")
    print("  🧠 Adaptive confidence thresholds")
    print("  🔄 Automatic confidence decay")
    print("  🎯 Pattern matching across contexts")
    print("  📊 Comprehensive learning analytics")
    print("="*70)

    # Load configuration
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    # Initialize procedural memory
    pm = ProceduralMemoryManager(config['memory'])

    # Show current learning state
    print("\n" + "="*70)
    print("CURRENT LEARNING STATE")
    print("="*70)
    display_learning_insights(pm)

    # Demo features
    demo_adaptive_filtering()
    demo_pattern_matching()
    demo_auto_decay()

    # Optional: Run learning simulation
    print("\n" + "="*70)
    response = input("\nRun learning simulation? (yes/no) [no]: ").strip().lower()

    if response in ['y', 'yes']:
        demo_learning_simulation(pm)
        print("\n" + "="*70)
        print("UPDATED LEARNING STATE")
        print("="*70)
        display_learning_insights(pm)

    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("\nKey Takeaways:")
    print("  ✅ Jarvis learns from every successful retry")
    print("  ✅ High success rate strategies are trusted more")
    print("  ✅ Unused strategies automatically fade away")
    print("  ✅ Cross-context learning through pattern matching")
    print("  ✅ Comprehensive analytics track learning progress")
    print("\nJarvis gets smarter with every interaction! 🚀")
    print()


if __name__ == "__main__":
    main()
