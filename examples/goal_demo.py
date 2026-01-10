#!/usr/bin/env python3
"""
Demonstration of Goal Management Integration with Orchestrator.

Shows how to create and execute goals autonomously through Jarvis.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
from goals import GoalProposal, SubtaskProposal, GoalType, Priority
from orchestrator import Orchestrator


def main():
    print("\n" + "="*70)
    print("JARVIS GOAL MANAGEMENT DEMONSTRATION")
    print("="*70)

    # Load configuration
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    # Initialize orchestrator
    print("\n[1] Initializing Jarvis orchestrator...")
    orchestrator = Orchestrator(config)
    print(f"✓ Orchestrator initialized")
    print(f"✓ Goal management enabled: {orchestrator.goal_enabled}")

    # Create a simple goal
    print("\n[2] Creating goal with 3 subtasks...")
    proposal = GoalProposal(
        goal_text="Demonstrate goal execution with file operations",
        goal_type=GoalType.TASK,
        context="Simple demonstration of autonomous task execution",
        priority=Priority.HIGH,
        subtasks=[
            SubtaskProposal(
                task_text="Create directory /tmp/jarvis_demo if it doesn't exist",
                task_order=1,
                prerequisites=[]
            ),
            SubtaskProposal(
                task_text="Create file /tmp/jarvis_demo/step1.txt with content 'Task 1 completed'",
                task_order=2,
                prerequisites=[1]
            ),
            SubtaskProposal(
                task_text="List all files in /tmp/jarvis_demo directory",
                task_order=3,
                prerequisites=[2]
            )
        ]
    )

    goal_id = orchestrator.goal_manager.create_goal(proposal, user_id=3  # Steve (master user))
    print(f"✓ Goal created with ID: {goal_id}")

    # Display goal details
    goal = orchestrator.goal_manager.get_goal(goal_id, include_subtasks=True)
    print(f"\nGoal: {goal.goal_text}")
    print(f"Subtasks:")
    for st in goal.subtasks:
        print(f"  {st.task_order}. {st.task_text}")

    # Execute goal autonomously
    print("\n[3] Executing goal autonomously...")
    print("="*70)
    print("NOTE: This will take a few minutes as the LLM processes each task.")
    print("Set auto_approve=True to run without user approval prompts.")
    print("="*70)

    try:
        result = orchestrator.execute_goal_autonomously(
            goal_id=goal_id,
            user_id=3  # Steve (master user),
            max_iterations=20,
            save_checkpoints=True,
            auto_approve=True  # Enable auto-approval for autonomous execution
        )

        print("\n" + "="*70)
        print("[4] Execution Complete!")
        print("="*70)
        print(result['execution_summary'])
        print()

        # Display results
        print(f"Status: {result['status']}")
        print(f"Progress: {result['final_progress']}%")
        print(f"Tasks completed: {result['tasks_completed']}")
        print(f"Tasks failed: {result['tasks_failed']}")
        print(f"Iterations used: {result['iterations_used']}/{result['max_iterations']}")

        # Check if goal was completed
        if result['status'] == 'completed':
            print("\n✅ Goal completed successfully!")

            # Verify files were created
            if os.path.exists('/tmp/jarvis_demo/step1.txt'):
                with open('/tmp/jarvis_demo/step1.txt') as f:
                    content = f.read()
                print(f"\n✓ File created: /tmp/jarvis_demo/step1.txt")
                print(f"  Content: {content}")

        else:
            print(f"\n⚠ Goal ended with status: {result['status']}")

    except KeyboardInterrupt:
        print("\n\n⚠ Execution interrupted by user")
        goal = orchestrator.goal_manager.get_goal(goal_id)
        print(f"Progress when interrupted: {goal.progress_percentage}%")
        print("You can resume this goal later!")

    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()

    # Show audit log
    print("\n[5] Audit Log (last 10 events):")
    print("="*70)
    audit_entries = orchestrator.goal_manager.get_audit_log(goal_id=goal_id, limit=10)
    for entry in audit_entries:
        print(f"[{entry.created_at}] {entry.event_type.value}")
        if entry.event_details:
            print(f"  {entry.event_details}")

    print("\n" + "="*70)
    print("DEMONSTRATION COMPLETE")
    print("="*70)
    print("\nKey Features Demonstrated:")
    print("  ✓ Goal creation with subtasks and dependencies")
    print("  ✓ Autonomous execution through orchestrator")
    print("  ✓ Auto-approval mode for unattended operation")
    print("  ✓ Progress tracking and status updates")
    print("  ✓ Checkpoint saving for resumability")
    print("  ✓ Comprehensive audit logging")
    print("\nFor more information, see:")
    print("  - docs/GOAL_MANAGEMENT.md - Complete documentation")
    print("  - tests/test_goal_management.py - Unit tests")
    print("  - tests/test_goal_integration.py - Integration tests")
    print()


if __name__ == "__main__":
    main()
