#!/usr/bin/env python3
"""
Introspection & Self-Critique Demo

Demonstrates how Jarvis learns qualitative insights from task execution,
going beyond simple pattern matching to understand WHY things fail and
extract generalizable lessons.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
import mysql.connector
from orchestrator import Orchestrator


def display_heuristic_with_insights(heuristic_id: int, config: dict):
    """Display a heuristic with its introspection insights."""
    connection = mysql.connector.connect(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, context_type, failure_type, effective_strategy,
                   confidence_score, usage_count, success_count, failure_count,
                   root_cause, inefficiencies, surprises, generalizable_lesson,
                   insight_confidence, notes
            FROM procedural_memory
            WHERE id = %s
        """, (heuristic_id,))

        row = cursor.fetchone()
        if not row:
            print(f"Heuristic {heuristic_id} not found")
            return

        print("\n" + "="*70)
        print(f"HEURISTIC #{row['id']}")
        print("="*70)

        print(f"\nPattern:")
        print(f"  Context: {row['context_type']}")
        print(f"  Failure Type: {row['failure_type']}")
        print(f"  Effective Strategy: {row['effective_strategy']}")

        print(f"\nStatistics:")
        print(f"  Confidence: {float(row['confidence_score']):.2%}")
        print(f"  Usage: {row['usage_count']}x (Success: {row['success_count']}, Fail: {row['failure_count']})")
        success_rate = row['success_count'] / row['usage_count'] if row['usage_count'] > 0 else 0
        print(f"  Success Rate: {success_rate:.1%}")

        if row['notes']:
            print(f"\nNotes: {row['notes']}")

        # Display introspection insights
        has_insights = row['root_cause'] or row['generalizable_lesson']

        if has_insights:
            print("\n" + "-"*70)
            print("INTROSPECTION INSIGHTS")
            print("-"*70)

            if row['root_cause']:
                print(f"\n🔍 Root Cause:")
                print(f"  {row['root_cause']}")

            if row['inefficiencies']:
                import json
                ineffs = json.loads(row['inefficiencies']) if isinstance(row['inefficiencies'], str) else row['inefficiencies']
                if ineffs:
                    print(f"\n⚡ Inefficiencies Identified:")
                    for ineff in ineffs:
                        print(f"  • {ineff}")

            if row['surprises']:
                import json
                surps = json.loads(row['surprises']) if isinstance(row['surprises'], str) else row['surprises']
                if surps:
                    print(f"\n❗ Surprises Encountered:")
                    for surp in surps:
                        print(f"  • {surp}")

            if row['generalizable_lesson']:
                print(f"\n💡 Generalizable Lesson:")
                print(f"  {row['generalizable_lesson']}")

            if row['insight_confidence']:
                print(f"\n📊 Insight Confidence: {float(row['insight_confidence']):.1%}")
        else:
            print("\n(No introspection insights available)")

        print("="*70)

    finally:
        cursor.close()
        connection.close()


def trigger_failure_scenario(orchestrator: Orchestrator, user_id: int):
    """
    Trigger a scenario that will fail and retry, generating introspection insights.

    This tests the full introspection pipeline:
    1. Task fails with incorrect assumptions
    2. Verifier catches failure
    3. Retry strategist suggests verification_first
    4. Retry succeeds
    5. Introspection analyzes why initial approach failed
    6. Insights stored in procedural memory
    """
    print("\n" + "="*70)
    print("TRIGGERING FAILURE SCENARIO")
    print("="*70)
    print("\nScenario: Try to read a file that doesn't exist")
    print("Expected flow:")
    print("  1. Attempt 1: Try to read /tmp/nonexistent_test_file.txt → FAIL")
    print("  2. Verifier: Detects incorrect_assumptions")
    print("  3. Retry strategist: Suggests verification_first or alternative_method")
    print("  4. Attempt 2: Use different approach → SUCCESS")
    print("  5. Introspection: Analyze what went wrong and extract lessons")
    print("="*70)

    # Make sure the file doesn't exist
    import subprocess
    subprocess.run(['rm', '-f', '/tmp/nonexistent_test_file.txt'],
                   capture_output=True)

    # Trigger the scenario
    user_input = "Read the contents of the file /tmp/nonexistent_test_file.txt"

    print(f"\nUser: {user_input}")
    print("\nProcessing... (this may take 2-3 minutes with verification and introspection)")
    print("Watch the logs for introspection insight generation...")

    result = orchestrator.process_user_input(user_input, user_id=user_id)

    print(f"\n{'─'*70}")
    print("RESULT:")
    print(f"{'─'*70}")
    print(f"\nJarvis: {result['response'][:300]}...")

    if result.get('verification'):
        verification = result['verification']
        print(f"\nVerification: {'✓ PASSED' if verification.get('verified') else '✗ FAILED'}")
        if verification.get('failure_type'):
            print(f"  Failure Type: {verification['failure_type']}")

    if result.get('retry_history'):
        history = result['retry_history']
        print(f"\nRetries: {history.get('total_attempts', 1)} attempts")
        if history.get('final_strategy'):
            print(f"  Final Strategy: {history['final_strategy']}")

    return result


def show_learning_progress(config: dict):
    """Show current state of procedural memory with insights."""
    connection = mysql.connector.connect(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )
    cursor = connection.cursor(dictionary=True)

    try:
        # Count heuristics with insights
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN root_cause IS NOT NULL OR generalizable_lesson IS NOT NULL THEN 1 ELSE 0 END) as with_insights
            FROM procedural_memory
        """)

        stats = cursor.fetchone()

        print("\n" + "="*70)
        print("PROCEDURAL MEMORY STATE")
        print("="*70)
        print(f"\nTotal Heuristics: {stats['total']}")
        print(f"With Introspection Insights: {stats['with_insights']}")

        # Show recent heuristics with insights
        cursor.execute("""
            SELECT id, context_type, failure_type, effective_strategy,
                   generalizable_lesson, insight_confidence
            FROM procedural_memory
            WHERE root_cause IS NOT NULL OR generalizable_lesson IS NOT NULL
            ORDER BY id DESC
            LIMIT 5
        """)

        enriched = cursor.fetchall()

        if enriched:
            print(f"\nRecent Enriched Heuristics:")
            print("-"*70)
            for h in enriched:
                lesson = h['generalizable_lesson']
                lesson_preview = (lesson[:60] + "...") if lesson and len(lesson) > 60 else (lesson or "N/A")
                conf = f"{float(h['insight_confidence']):.0%}" if h['insight_confidence'] else "N/A"
                print(f"\n  #{h['id']}: {h['context_type']}/{h['failure_type']} → {h['effective_strategy']}")
                print(f"    Lesson: {lesson_preview}")
                print(f"    Confidence: {conf}")
        else:
            print("\nNo enriched heuristics yet. Run a failure scenario to generate insights!")

        print("="*70)

    finally:
        cursor.close()
        connection.close()


def main():
    print("\n" + "="*70)
    print("INTROSPECTION & SELF-CRITIQUE DEMO")
    print("="*70)
    print("\nThis demo shows how Jarvis performs post-task reflection to extract")
    print("qualitative insights that go beyond simple pattern matching.")
    print()
    print("Key capabilities:")
    print("  🔍 Root cause analysis - WHY did it fail?")
    print("  ⚡ Inefficiency detection - What could have been better?")
    print("  ❗ Surprise identification - What was unexpected?")
    print("  💡 Generalizable lessons - What principle emerges?")
    print("="*70)

    # Load config
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    # Check if procedural memory is enabled
    if not config.get('memory', {}).get('procedural_enabled', False):
        print("\n⚠️  WARNING: Procedural memory is disabled!")
        print("Enable it in config/config.yaml to use introspection.")
        return

    # User ID for testing
    user_id = 3  # Steve (master user)

    # Show current state
    show_learning_progress(config)

    # Ask if user wants to run failure scenario
    print("\n" + "="*70)
    response = input("\nRun failure scenario to generate introspection insights? (yes/no) [yes]: ").strip().lower()

    if response in ['n', 'no']:
        print("\nDemo cancelled.")
        return

    # Initialize orchestrator
    print("\nInitializing Jarvis with introspection support...")
    orchestrator = Orchestrator(config)

    # Trigger failure scenario
    result = trigger_failure_scenario(orchestrator, user_id)

    # Check if new insights were generated
    print("\n" + "="*70)
    print("Checking for new insights...")

    # Get the most recent heuristic
    connection = mysql.connector.connect(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id
            FROM procedural_memory
            ORDER BY id DESC
            LIMIT 1
        """)
        latest = cursor.fetchone()

        if latest:
            print(f"\nMost recent heuristic: #{latest['id']}")
            display_heuristic_with_insights(latest['id'], config)

    finally:
        cursor.close()
        connection.close()

    # Show updated state
    show_learning_progress(config)

    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("\nKey Takeaways:")
    print("  ✅ Introspection runs automatically after successful retries")
    print("  ✅ Insights are stored alongside pattern statistics")
    print("  ✅ Future queries retrieve enriched heuristics with context")
    print("  ✅ Jarvis learns not just 'what worked' but 'WHY it worked'")
    print("\nJarvis now has deeper understanding through reflection! 🧠✨")
    print()


if __name__ == "__main__":
    main()
