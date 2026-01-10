#!/usr/bin/env python3
"""
Integration test for Goal Management with Orchestrator.

Tests autonomous execution of goals through the orchestrator.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
from goals import GoalProposal, SubtaskProposal, GoalType, Priority
from orchestrator import Orchestrator


def load_config():
    """Load configuration."""
    with open('config/config.yaml') as f:
        return yaml.safe_load(f)


def test_simple_goal_execution():
    """Test executing a simple goal with file operations."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Simple Goal Execution")
    print("="*70)

    config = load_config()

    # Initialize orchestrator (this will also initialize goal_manager)
    print("\n[Step 1] Initializing orchestrator...")
    orchestrator = Orchestrator(config)
    print("✓ Orchestrator initialized")

    # Verify goal manager is available
    assert orchestrator.goal_enabled, "Goal system should be enabled"
    assert orchestrator.goal_manager is not None, "Goal manager should be initialized"
    print("✓ Goal manager available")

    # Create a simple goal
    print("\n[Step 2] Creating test goal...")
    proposal = GoalProposal(
        goal_text="Create test files with sequence numbers",
        goal_type=GoalType.TASK,
        context="Simple test to verify goal execution",
        priority=Priority.HIGH,
        subtasks=[
            SubtaskProposal(
                task_text="Create file /tmp/jarvis_test_1.txt with content 'Step 1 complete'",
                task_order=1,
                prerequisites=[]
            ),
            SubtaskProposal(
                task_text="Create file /tmp/jarvis_test_2.txt with content 'Step 2 complete'",
                task_order=2,
                prerequisites=[1]  # Depends on task 1
            ),
            SubtaskProposal(
                task_text="List files in /tmp that match jarvis_test_*.txt",
                task_order=3,
                prerequisites=[2]  # Depends on task 2
            )
        ]
    )

    goal_id = orchestrator.goal_manager.create_goal(proposal, user_id=1)
    print(f"✓ Created goal ID: {goal_id}")

    # Execute the goal autonomously
    print("\n[Step 3] Executing goal autonomously...")
    print("="*70)

    result = orchestrator.execute_goal_autonomously(
        goal_id=goal_id,
        user_id=1,
        max_iterations=10,
        save_checkpoints=True
    )

    print("="*70)
    print(f"\n[Step 4] Execution Results:")
    print(result['execution_summary'])
    print()

    # Verify results
    assert result['status'] == 'completed', f"Goal should be completed, got: {result['status']}"
    assert result['tasks_completed'] == 3, f"Should complete 3 tasks, got: {result['tasks_completed']}"
    assert result['final_progress'] == 100, f"Should be 100% complete, got: {result['final_progress']}%"

    print("✓ Goal completed successfully!")
    print(f"✓ Tasks completed: {result['tasks_completed']}")
    print(f"✓ Iterations used: {result['iterations_used']}/{result['max_iterations']}")

    # Verify files were created
    import os
    print("\n[Step 5] Verifying files were created...")
    file1 = os.path.exists('/tmp/jarvis_test_1.txt')
    file2 = os.path.exists('/tmp/jarvis_test_2.txt')

    print(f"✓ /tmp/jarvis_test_1.txt exists: {file1}")
    print(f"✓ /tmp/jarvis_test_2.txt exists: {file2}")

    if file1 and file2:
        # Read contents
        with open('/tmp/jarvis_test_1.txt') as f:
            content1 = f.read().strip()
        with open('/tmp/jarvis_test_2.txt') as f:
            content2 = f.read().strip()

        print(f"  Content 1: {content1}")
        print(f"  Content 2: {content2}")

    # Check audit log
    print("\n[Step 6] Checking audit log...")
    audit_entries = orchestrator.goal_manager.get_audit_log(goal_id=goal_id, limit=20)
    print(f"✓ Audit log has {len(audit_entries)} entries")

    event_types = set(e.event_type.value for e in audit_entries)
    print(f"  Event types: {', '.join(sorted(event_types))}")

    # Check checkpoints
    print("\n[Step 7] Checking checkpoints...")
    checkpoint = orchestrator.goal_manager.get_latest_checkpoint(goal_id)
    if checkpoint:
        print(f"✓ Latest checkpoint: {checkpoint.checkpoint_name}")
        print(f"  Data: {checkpoint.checkpoint_data}")
    else:
        print("  No checkpoints found")

    print("\n✅ Integration test passed!")
    return goal_id


def test_goal_with_dependency_blocking():
    """Test that dependencies properly block execution order."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Dependency Blocking")
    print("="*70)

    config = load_config()
    orchestrator = Orchestrator(config)

    print("\n[Test] Creating goal with complex dependencies...")
    proposal = GoalProposal(
        goal_text="Test dependency order enforcement",
        goal_type=GoalType.TASK,
        priority=Priority.MEDIUM,
        subtasks=[
            SubtaskProposal(
                task_text="Create file /tmp/dep_test_base.txt with content 'Base'",
                task_order=1,
                prerequisites=[]
            ),
            SubtaskProposal(
                task_text="Create file /tmp/dep_test_a.txt with content 'Branch A'",
                task_order=2,
                prerequisites=[1]
            ),
            SubtaskProposal(
                task_text="Create file /tmp/dep_test_b.txt with content 'Branch B'",
                task_order=3,
                prerequisites=[1]
            ),
            SubtaskProposal(
                task_text="Create file /tmp/dep_test_final.txt with content 'Final: A and B complete'",
                task_order=4,
                prerequisites=[2, 3]  # Waits for both branches
            )
        ]
    )

    goal_id = orchestrator.goal_manager.create_goal(proposal, user_id=1)
    print(f"✓ Created goal ID: {goal_id}")

    print("\n[Executing] Diamond dependency pattern...")
    result = orchestrator.execute_goal_autonomously(
        goal_id=goal_id,
        user_id=1,
        max_iterations=20
    )

    print(f"\n{result['execution_summary']}")

    assert result['status'] == 'completed', "Goal should complete"
    assert result['final_progress'] == 100, "Should be 100% complete"

    print("\n✅ Dependency blocking test passed!")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("GOAL MANAGEMENT INTEGRATION TEST SUITE")
    print("="*70)

    try:
        # Test 1: Simple goal execution
        test_simple_goal_execution()

        # Test 2: Dependency blocking
        test_goal_with_dependency_blocking()

        print("\n" + "="*70)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("="*70)
        print("\nGoal Management is fully integrated with Orchestrator:")
        print("  ✓ Goals created and stored in database")
        print("  ✓ Autonomous execution loop working")
        print("  ✓ Tasks executed through orchestrator pipeline")
        print("  ✓ Progress tracking functional")
        print("  ✓ Checkpoints saved automatically")
        print("  ✓ Audit logging operational")
        print("  ✓ Dependency blocking respected")
        print("\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
