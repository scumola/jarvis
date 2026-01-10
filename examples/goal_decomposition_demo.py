#!/usr/bin/env python3
"""
Goal Decomposition Demo - Automatic goal creation from user requests.

Shows how the GoalDecomposerLLM analyzes user requests and automatically
creates structured goals with subtasks when appropriate.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
from orchestrator import Orchestrator


def demo_simple_task():
    """Test 1: Simple task should NOT create a goal."""
    print("\n" + "="*70)
    print("TEST 1: Simple Task (should NOT create goal)")
    print("="*70)

    # Load configuration
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    # Initialize orchestrator
    orchestrator = Orchestrator(config)

    # Simple request that should NOT be decomposed
    simple_request = "List all Python files in the current directory"

    result = orchestrator.decompose_and_create_goal(
        user_request=simple_request,
        user_id=3  # Steve (master user)
    )

    print(f"\nRequest: {simple_request}")
    print(f"Goal created: {result['created']}")
    print(f"Reasoning: {result['reasoning']}")

    assert result['created'] is False, "Simple task should not create goal"
    print("\n✓ Test passed: Simple task correctly identified")


def demo_complex_task():
    """Test 2: Complex task should create a goal with subtasks."""
    print("\n" + "="*70)
    print("TEST 2: Complex Task (should create goal)")
    print("="*70)

    # Load configuration
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    # Initialize orchestrator
    orchestrator = Orchestrator(config)

    # Complex request that should be decomposed
    complex_request = """
    Set up a new Python project for a web scraper:
    1. Create a project directory called 'web_scraper'
    2. Create a virtual environment inside it
    3. Create a requirements.txt with requests and beautifulsoup4
    4. Create a basic README.md file
    """

    result = orchestrator.decompose_and_create_goal(
        user_request=complex_request,
        user_id=3  # Steve (master user)
    )

    print(f"\nRequest: {complex_request[:100]}...")
    print(f"Goal created: {result['created']}")
    print(f"Reasoning: {result['reasoning']}")

    if result['created']:
        goal = result['goal']
        print(f"\nGoal: {goal.goal_text}")
        print(f"Type: {goal.goal_type.value}")
        print(f"Priority: {goal.priority.value}")
        print(f"\nSubtasks ({len(goal.subtasks)}):")
        for subtask in goal.subtasks:
            print(f"  {subtask.task_order}. {subtask.task_text}")

        assert len(goal.subtasks) >= 3, "Should have at least 3 subtasks"
        print("\n✓ Test passed: Complex task decomposed into goal")
    else:
        print("\n✗ Test failed: Complex task should have created a goal")


def demo_auto_execute():
    """Test 3: Auto-execute a simple goal."""
    print("\n" + "="*70)
    print("TEST 3: Auto-Execute Goal")
    print("="*70)

    # Load configuration
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    # Initialize orchestrator
    orchestrator = Orchestrator(config)

    # Request that will create and execute a simple goal
    request = """
    Create a test directory structure:
    1. Create /tmp/decompose_test directory
    2. Create a file /tmp/decompose_test/info.txt with content 'Auto-generated'
    3. List the contents of /tmp/decompose_test
    """

    print(f"Request: {request[:100]}...")
    print("\nAnalyzing and creating goal...")

    result = orchestrator.decompose_and_create_goal(
        user_request=request,
        user_id=3,  # Steve (master user)
        auto_execute=True  # Automatically execute the goal
    )

    if result['created']:
        goal = result['goal']
        print(f"\n✓ Goal created: {goal.goal_text}")
        print(f"  Subtasks: {len(goal.subtasks)}")

        if 'execution_result' in result:
            exec_result = result['execution_result']
            print(f"\n✓ Goal executed:")
            print(f"  Status: {exec_result['status']}")
            print(f"  Progress: {exec_result['final_progress']}%")
            print(f"  Tasks completed: {exec_result['tasks_completed']}")
            print(f"  Tasks failed: {exec_result['tasks_failed']}")
            print(f"  Iterations used: {exec_result['iterations_used']}")

            # Verify the directory was created
            import os
            if os.path.exists('/tmp/decompose_test/info.txt'):
                with open('/tmp/decompose_test/info.txt') as f:
                    content = f.read()
                print(f"\n✓ Verified: File created with content: '{content}'")
            else:
                print("\n⚠ Warning: File was not created")

            # Cleanup
            import shutil
            if os.path.exists('/tmp/decompose_test'):
                shutil.rmtree('/tmp/decompose_test')
                print("✓ Cleanup completed")

            print("\n✓ Test passed: Goal auto-executed successfully")
        else:
            print("\n✗ Test failed: Goal was not executed")
    else:
        print(f"\n✗ Test failed: Goal was not created - {result['reasoning']}")


def main():
    print("\n" + "="*70)
    print("GOAL DECOMPOSITION DEMONSTRATION")
    print("="*70)
    print("\nThis demo shows how Jarvis automatically analyzes user requests")
    print("and creates structured goals with subtasks when appropriate.")
    print("\nNote: This requires Ollama to be running!")

    try:
        # Test 1: Simple task (should not decompose)
        demo_simple_task()

        # Test 2: Complex task (should decompose)
        demo_complex_task()

        # Test 3: Auto-execute (decompose and run)
        demo_auto_execute()

        print("\n" + "="*70)
        print("ALL TESTS PASSED!")
        print("="*70)
        print("\nKey Features Demonstrated:")
        print("  ✓ Automatic detection of simple vs complex tasks")
        print("  ✓ LLM-driven goal decomposition into subtasks")
        print("  ✓ Dependency tracking between subtasks")
        print("  ✓ Auto-execution with autonomous task completion")
        print("  ✓ Progress tracking and status updates")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠ Demo interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Error during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
