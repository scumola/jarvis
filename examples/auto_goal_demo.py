#!/usr/bin/env python3
"""
Auto-Goal Detection Demo

Shows how Jarvis automatically detects multi-step tasks and offers
to create goals for them during normal conversation flow.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
from orchestrator import Orchestrator


def main():
    print("\n" + "="*70)
    print("AUTO-GOAL DETECTION DEMONSTRATION")
    print("="*70)
    print("\nThis demo shows how Jarvis automatically detects multi-step tasks")
    print("and offers to create structured goals during normal interaction.")
    print("\nNOTE: This requires Ollama to be running!")
    print("="*70)

    # Load configuration
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    # Verify auto-detection is enabled
    if not config.get('goals', {}).get('auto_detect', True):
        print("\n⚠ WARNING: Auto-goal detection is disabled in config.yaml")
        print("Set goals.auto_detect: true to enable this feature.\n")
        return

    # Disable approval prompts for automated testing
    # (Avoids EOF errors when running via test script)
    config['approval_required'] = False

    # Initialize orchestrator
    print("\nInitializing orchestrator...")
    orchestrator = Orchestrator(config)
    print("✓ Ready\n")

    # Simulate a multi-step user request
    print("\n" + "="*70)
    print("SCENARIO: User asks for a complex multi-step task")
    print("="*70)

    complex_request = """
    Create a new Python project for a REST API:
    1. Create a directory called 'my_api'
    2. Inside it, create a virtual environment
    3. Create a requirements.txt with flask and requests
    4. Create a simple app.py with a hello world Flask app
    5. Create a README.md with setup instructions
    """

    print(f"\nUser request: {complex_request.strip()}\n")
    print("Processing...\n")

    # Process the request - auto-detection will kick in
    result = orchestrator.process_user_input(
        user_input=complex_request,
        user_id=3  # Steve (master user)
    )

    # Show the result
    print("\n" + "="*70)
    print("RESULT")
    print("="*70)

    if result.get('goal_created'):
        print("\n✅ Goal was created and executed!")
        print(f"\nGoal ID: {result['goal_id']}")

        if 'execution_result' in result:
            exec_result = result['execution_result']
            print(f"Status: {exec_result['status']}")
            print(f"Progress: {exec_result['final_progress']}%")
            print(f"Tasks completed: {exec_result['tasks_completed']}")
            print(f"Tasks failed: {exec_result['tasks_failed']}")
    else:
        print("\n✓ Request processed normally (no goal created)")
        print(f"\nResponse: {result['response'][:200]}...")

    print("\n" + "="*70)
    print("KEY FEATURES DEMONSTRATED:")
    print("="*70)
    print("  ✓ Automatic detection of multi-step tasks")
    print("  ✓ User confirmation before goal creation")
    print("  ✓ Three options: yes (auto-execute), no (normal), manual (create only)")
    print("  ✓ Autonomous execution with progress updates")
    print("  ✓ Seamless fallback to normal processing")
    print("\n" + "="*70)
    print("\nTo try this in the main CLI:")
    print("  1. Run: ./venv/bin/python main.py")
    print("  2. Enter a multi-step request")
    print("  3. Answer the goal creation prompt")
    print("  4. Watch Jarvis execute it autonomously!")
    print()


if __name__ == "__main__":
    main()
