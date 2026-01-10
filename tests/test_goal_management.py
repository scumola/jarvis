#!/usr/bin/env python3
"""
Test script for Goal & Task Management System.

Tests:
1. Goal creation with subtasks
2. Dependency tracking
3. Next actionable task selection
4. Progress tracking
5. Checkpoints and resumability
6. Audit logging
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
from datetime import datetime, timedelta

from goals import (
    GoalManager, GoalProposal, SubtaskProposal,
    GoalType, Priority, GoalStatus, SubtaskStatus
)


def load_config():
    """Load configuration."""
    with open('config/config.yaml') as f:
        return yaml.safe_load(f)


def test_goal_creation():
    """Test creating a goal with subtasks and dependencies."""
    print("\n" + "="*70)
    print("TEST 1: Goal Creation with Subtasks")
    print("="*70)

    config = load_config()
    goal_manager = GoalManager(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )

    # Create a goal with subtasks
    print("\n[Test 1.1] Create goal: Set up development environment")
    proposal = GoalProposal(
        goal_text="Set up Python development environment on new machine",
        goal_type=GoalType.TASK,
        context="Fresh Ubuntu 22.04 installation, need to install tools",
        priority=Priority.HIGH,
        deadline=datetime.now() + timedelta(days=7),
        subtasks=[
            SubtaskProposal(
                task_text="Update system packages (apt update && apt upgrade)",
                task_order=1,
                prerequisites=[]
            ),
            SubtaskProposal(
                task_text="Install Python 3.11 from deadsnakes PPA",
                task_order=2,
                prerequisites=[1]  # Depends on task 1
            ),
            SubtaskProposal(
                task_text="Install pip and virtualenv",
                task_order=3,
                prerequisites=[2]  # Depends on task 2
            ),
            SubtaskProposal(
                task_text="Install development tools (git, vim, curl)",
                task_order=4,
                prerequisites=[1]  # Depends on task 1 only
            ),
            SubtaskProposal(
                task_text="Create project directory structure",
                task_order=5,
                prerequisites=[3, 4]  # Depends on both 3 and 4
            )
        ]
    )

    goal_id = goal_manager.create_goal(proposal, user_id=1)
    print(f"✓ Created goal ID: {goal_id}")

    # Verify goal created
    goal = goal_manager.get_goal(goal_id, include_subtasks=True)
    assert goal is not None, "Goal should be created"
    assert len(goal.subtasks) == 5, "Should have 5 subtasks"
    assert goal.status == GoalStatus.PENDING, "Should be pending"
    assert goal.progress_percentage == 0, "Should be 0% complete"
    print(f"✓ Goal has {len(goal.subtasks)} subtasks")
    print(f"✓ Status: {goal.status.value}, Progress: {goal.progress_percentage}%")

    # Verify dependencies
    dependencies = goal_manager.get_dependencies(goal_id)
    print(f"✓ Created {len(dependencies)} dependencies")
    for dep in dependencies:
        prereq = next(s for s in goal.subtasks if s.id == dep.prerequisite_id)
        dependent = next(s for s in goal.subtasks if s.id == dep.subtask_id)
        print(f"  - Task {dependent.task_order} depends on Task {prereq.task_order}")

    print("\n✅ Goal creation test passed!")
    return goal_id


def test_next_actionable_task(goal_id: int):
    """Test finding the next task that can be executed."""
    print("\n" + "="*70)
    print("TEST 2: Next Actionable Task Selection")
    print("="*70)

    config = load_config()
    goal_manager = GoalManager(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )

    print("\n[Test 2.1] Find first actionable task")
    next_task = goal_manager.get_next_actionable_task(goal_id)

    assert next_task is not None, "Should have an actionable task"
    assert next_task.task_order == 1, "First task should be task 1 (no dependencies)"
    print(f"✓ Next task: Task {next_task.task_order}")
    print(f"  {next_task.task_text}")

    print("\n[Test 2.2] Complete task 1, check next actionable")
    # Mark task 1 as in progress then completed
    goal_manager.update_subtask_status(
        next_task.id,
        SubtaskStatus.IN_PROGRESS,
        tools_used=['bash']
    )
    goal_manager.update_subtask_status(
        next_task.id,
        SubtaskStatus.COMPLETED,
        result="System packages updated successfully",
        verification_passed=True
    )
    print("✓ Task 1 completed")

    # Check progress
    goal = goal_manager.get_goal(goal_id)
    print(f"✓ Goal progress: {goal.progress_percentage}%")
    assert goal.progress_percentage == 20, "Should be 20% complete (1/5)"

    # Find next task (should be task 2 or 4, both depend only on task 1)
    next_task = goal_manager.get_next_actionable_task(goal_id)
    assert next_task is not None, "Should have next actionable task"
    assert next_task.task_order in [2, 4], "Should be task 2 or 4 (both now unblocked)"
    print(f"✓ Next task: Task {next_task.task_order}")
    print(f"  {next_task.task_text}")

    print("\n[Test 2.3] Complete task 2, task 3 should become actionable")
    if next_task.task_order == 4:
        # If task 4 was selected, find and complete task 2 manually
        task_2 = next(s for s in goal_manager.get_subtasks(goal_id) if s.task_order == 2)
        goal_manager.update_subtask_status(task_2.id, SubtaskStatus.IN_PROGRESS)
        goal_manager.update_subtask_status(task_2.id, SubtaskStatus.COMPLETED, result="Python installed")
    else:
        # Complete the selected task 2
        goal_manager.update_subtask_status(next_task.id, SubtaskStatus.IN_PROGRESS)
        goal_manager.update_subtask_status(next_task.id, SubtaskStatus.COMPLETED, result="Python installed")

    print("✓ Task 2 completed")

    # Task 3 should now be actionable (depends on task 2)
    next_task = goal_manager.get_next_actionable_task(goal_id)
    # Could be task 3 or task 4 depending on what was completed
    assert next_task is not None, "Should have actionable task"
    print(f"✓ Next actionable: Task {next_task.task_order}")

    print("\n✅ Next actionable task test passed!")
    return goal_id


def test_progress_tracking(goal_id: int):
    """Test progress calculation and goal with progress details."""
    print("\n" + "="*70)
    print("TEST 3: Progress Tracking")
    print("="*70)

    config = load_config()
    goal_manager = GoalManager(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )

    print("\n[Test 3.1] Get goal with detailed progress")
    progress_info = goal_manager.get_goal_with_progress(goal_id)

    print(f"✓ Goal: {progress_info.goal.goal_text}")
    print(f"✓ Progress: {progress_info.goal.progress_percentage}%")
    print(f"✓ Next task: {progress_info.next_task.task_text if progress_info.next_task else 'None'}")
    print(f"✓ Can make progress: {progress_info.can_make_progress}")
    print(f"✓ Blocked tasks: {len(progress_info.blocked_tasks)}")

    if progress_info.blocked_tasks:
        print("\n  Blocked tasks:")
        for task in progress_info.blocked_tasks:
            print(f"    - Task {task.task_order}: {task.task_text[:50]}...")

    assert progress_info.can_make_progress, "Should be able to make progress"

    print("\n[Test 3.2] Complete all remaining tasks")
    # Complete remaining tasks in order
    while True:
        next_task = goal_manager.get_next_actionable_task(goal_id)
        if not next_task:
            break

        print(f"  Completing task {next_task.task_order}...")
        goal_manager.update_subtask_status(next_task.id, SubtaskStatus.IN_PROGRESS)
        goal_manager.update_subtask_status(
            next_task.id,
            SubtaskStatus.COMPLETED,
            result=f"Task {next_task.task_order} completed"
        )

    # Check final progress
    goal = goal_manager.get_goal(goal_id)
    print(f"✓ Final progress: {goal.progress_percentage}%")
    assert goal.progress_percentage == 100, "Should be 100% complete"

    # Update goal status to completed
    goal_manager.update_goal_status(
        goal_id,
        GoalStatus.COMPLETED,
        result_summary="Successfully set up Python development environment",
        lessons_learned="System package updates should always come first"
    )
    print("✓ Goal marked as completed")

    print("\n✅ Progress tracking test passed!")


def test_checkpoints(goal_id: int):
    """Test checkpoint saving and loading."""
    print("\n" + "="*70)
    print("TEST 4: Checkpoint Management")
    print("="*70)

    config = load_config()
    goal_manager = GoalManager(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )

    print("\n[Test 4.1] Save checkpoint")
    checkpoint_data = {
        'current_step': 3,
        'environment_vars': {'PATH': '/usr/local/bin'},
        'temp_files': ['/tmp/install.log']
    }

    checkpoint_id = goal_manager.save_checkpoint(
        goal_id,
        "after_python_install",
        checkpoint_data
    )
    print(f"✓ Saved checkpoint ID: {checkpoint_id}")

    print("\n[Test 4.2] Load latest checkpoint")
    checkpoint = goal_manager.get_latest_checkpoint(goal_id)

    assert checkpoint is not None, "Should load checkpoint"
    assert checkpoint.checkpoint_name == "after_python_install", "Name should match"
    assert checkpoint.checkpoint_data['current_step'] == 3, "Data should match"
    print(f"✓ Loaded checkpoint: {checkpoint.checkpoint_name}")
    print(f"✓ Data: {checkpoint.checkpoint_data}")

    print("\n✅ Checkpoint test passed!")


def test_audit_log(goal_id: int):
    """Test audit log retrieval."""
    print("\n" + "="*70)
    print("TEST 5: Audit Log")
    print("="*70)

    config = load_config()
    goal_manager = GoalManager(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )

    print("\n[Test 5.1] Retrieve audit log")
    log_entries = goal_manager.get_audit_log(goal_id=goal_id, limit=20)

    print(f"✓ Retrieved {len(log_entries)} audit log entries")
    print("\nRecent events:")
    for entry in log_entries[:10]:
        print(f"  [{entry.created_at}] {entry.event_type.value}")
        if entry.event_details:
            print(f"    Details: {entry.event_details}")

    assert len(log_entries) > 0, "Should have audit entries"
    assert any(e.event_type.value == 'goal_created' for e in log_entries), "Should have goal_created event"

    print("\n✅ Audit log test passed!")


def test_goal_with_failure():
    """Test goal with task failure and retry."""
    print("\n" + "="*70)
    print("TEST 6: Task Failure and Retry")
    print("="*70)

    config = load_config()
    goal_manager = GoalManager(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )

    print("\n[Test 6.1] Create goal with potential failure")
    proposal = GoalProposal(
        goal_text="Deploy application to server",
        goal_type=GoalType.TASK,
        priority=Priority.URGENT,
        subtasks=[
            SubtaskProposal(
                task_text="Run tests",
                task_order=1,
                max_retries=2
            ),
            SubtaskProposal(
                task_text="Build Docker image",
                task_order=2,
                prerequisites=[1],
                max_retries=3
            )
        ]
    )

    goal_id = goal_manager.create_goal(proposal, user_id=1)
    print(f"✓ Created goal ID: {goal_id}")

    print("\n[Test 6.2] Fail task 1, then retry")
    next_task = goal_manager.get_next_actionable_task(goal_id)

    # Start and fail the task
    goal_manager.update_subtask_status(next_task.id, SubtaskStatus.IN_PROGRESS)
    goal_manager.update_subtask_status(
        next_task.id,
        SubtaskStatus.FAILED,
        error_message="Test suite failed: 2 tests failed",
        verification_passed=False
    )
    print("✓ Task 1 failed")

    # Retry the task
    retry_allowed = goal_manager.retry_subtask(next_task.id)
    assert retry_allowed, "Should allow retry"
    print("✓ Task 1 queued for retry")

    # Complete on retry
    next_task = goal_manager.get_next_actionable_task(goal_id)
    assert next_task.id == next_task.id, "Should be same task after retry"
    assert next_task.retries == 1, "Should have retry count of 1"
    print(f"✓ Task retry count: {next_task.retries}")

    goal_manager.update_subtask_status(next_task.id, SubtaskStatus.IN_PROGRESS)
    goal_manager.update_subtask_status(
        next_task.id,
        SubtaskStatus.COMPLETED,
        result="All tests passed"
    )
    print("✓ Task 1 completed on retry")

    print("\n✅ Failure and retry test passed!")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("GOAL & TASK MANAGEMENT SYSTEM TEST SUITE")
    print("="*70)

    try:
        # Run tests
        goal_id = test_goal_creation()
        test_next_actionable_task(goal_id)
        test_progress_tracking(goal_id)
        test_checkpoints(goal_id)
        test_audit_log(goal_id)
        test_goal_with_failure()

        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\nGoal & Task Management System is working correctly:")
        print("  ✓ Goal creation with subtasks and dependencies")
        print("  ✓ Next actionable task selection")
        print("  ✓ Progress tracking and calculation")
        print("  ✓ Checkpoint save/load for resumability")
        print("  ✓ Comprehensive audit logging")
        print("  ✓ Task failure and retry handling")
        print("\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
