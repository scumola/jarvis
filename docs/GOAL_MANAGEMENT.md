# Goal & Task Management System

## Overview

The Goal & Task Management System enables Jarvis to track and execute long-running autonomous work with subtasks, dependencies, resumability, and progress tracking.

**Core Capability**: Transform "Set up a development environment" into 5 sequential subtasks with dependency tracking, automatic progress calculation, checkpoint saving, and comprehensive audit logging.

## Architecture

### Database Schema

The system uses 5 tables to track goals, subtasks, dependencies, checkpoints, and audit events.

```
┌─────────────────────────────────────────────────────────────┐
│                    GOAL MANAGEMENT SYSTEM                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐       ┌──────────────┐       ┌────────────┐ │
│  │  goals   │───┬───│  subtasks    │       │ task_      │ │
│  └──────────┘   │   └──────────────┘   ┌──│ dependencies │
│                 │           │           │   └────────────┘ │
│                 │           │           │                   │
│                 │           └───────────┘                   │
│                 │                                           │
│                 ├───► goal_checkpoints                      │
│                 │                                           │
│                 └───► goal_audit_log                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 1. **goals** Table

High-level objectives with status and progress tracking.

| Field | Type | Description |
|-------|------|-------------|
| id | INT | Primary key |
| user_id | INT | Owner of this goal |
| goal_text | TEXT | Natural language description |
| goal_type | ENUM | task, project, learning, research, maintenance |
| context | TEXT | Additional background information |
| status | ENUM | pending, in_progress, completed, blocked, failed, cancelled |
| priority | ENUM | low, medium, high, urgent |
| progress_percentage | INT | 0-100, calculated from subtasks |
| blocking_reason | TEXT | Why this goal is blocked |
| blocking_subtask_id | INT | Which subtask is blocking |
| created_at | TIMESTAMP | When goal was created |
| started_at | TIMESTAMP | When work began |
| completed_at | TIMESTAMP | When goal finished |
| deadline | TIMESTAMP | Optional deadline |
| result_summary | TEXT | Outcome description |
| lessons_learned | TEXT | Post-mortem insights |

#### 2. **subtasks** Table

Individual steps within a goal.

| Field | Type | Description |
|-------|------|-------------|
| id | INT | Primary key |
| goal_id | INT | Parent goal |
| task_text | TEXT | Description of this task |
| task_order | INT | Sequential order (1, 2, 3...) |
| status | ENUM | pending, in_progress, completed, failed, skipped, blocked |
| retries | INT | Number of retry attempts |
| max_retries | INT | Maximum retries before failing |
| started_at | TIMESTAMP | When task started |
| completed_at | TIMESTAMP | When task finished |
| execution_time_seconds | INT | How long it took |
| result | TEXT | Output or result |
| error_message | TEXT | Error details if failed |
| blocking_reason | TEXT | Why task is blocked |
| tools_used | JSON | List of tools invoked |
| verification_passed | BOOLEAN | Did verification pass? |

#### 3. **task_dependencies** Table

Defines prerequisite relationships between subtasks.

| Field | Type | Description |
|-------|------|-------------|
| id | INT | Primary key |
| subtask_id | INT | The dependent task (waits) |
| prerequisite_id | INT | The prerequisite task (must complete first) |
| dependency_type | ENUM | blocking, preferred, optional |

**Example**:
```
Task 3 (Install pip) depends on Task 2 (Install Python)
- subtask_id: 3
- prerequisite_id: 2
- dependency_type: blocking
```

#### 4. **goal_checkpoints** Table

Saved state for resuming work after interruption.

| Field | Type | Description |
|-------|------|-------------|
| id | INT | Primary key |
| goal_id | INT | Parent goal |
| checkpoint_name | VARCHAR | Name for this checkpoint |
| checkpoint_data | JSON | Serialized state data |
| created_at | TIMESTAMP | When saved |

#### 5. **goal_audit_log** Table

Comprehensive event history for all goal activities.

| Field | Type | Description |
|-------|------|-------------|
| id | INT | Primary key |
| goal_id | INT | Related goal |
| subtask_id | INT | Related subtask (if applicable) |
| event_type | ENUM | goal_created, task_started, task_completed, etc. |
| event_details | JSON | Additional event data |
| created_at | TIMESTAMP | When event occurred |

## Automatic Goal Decomposition

**NEW FEATURE**: Jarvis can now automatically analyze user requests and create structured goals with subtasks using the `GoalDecomposerLLM`.

### How It Works

When you give Jarvis a complex request, the `GoalDecomposerLLM`:

1. **Analyzes the request** to determine if it requires multiple steps
2. **Identifies dependencies** between tasks (what must complete first)
3. **Creates a structured goal** with subtasks, priorities, and context
4. **Returns `None`** for simple single-step tasks (no goal needed)

### Decision Criteria

The decomposer creates a goal when the request:
- Requires **2+ discrete steps** that could be tracked independently
- Has **dependencies** (one step must complete before another)
- Spans **multiple tools or operations**
- Would benefit from **progress tracking** and resumability

**Examples of what SHOULD be goals:**
- "Set up a development environment" → 3-5 subtasks
- "Deploy application to server" → 4-6 subtasks
- "Analyze log files and fix errors" → 3-4 subtasks

**Examples of what should NOT be goals (single tasks):**
- "List files in a directory" → Single tool call
- "Read a file" → Single operation
- "Create a file" → Single operation

### Usage with Orchestrator

```python
from orchestrator import Orchestrator
import yaml

# Load configuration
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

# Initialize orchestrator (includes GoalDecomposerLLM)
orchestrator = Orchestrator(config)

# Analyze a user request
result = orchestrator.decompose_and_create_goal(
    user_request="Set up a Python web scraper project with virtual environment and dependencies",
    user_id=1
)

# Check if goal was created
if result['created']:
    goal = result['goal']
    print(f"Created goal: {goal.goal_text}")
    print(f"Subtasks: {len(goal.subtasks)}")

    # Optionally execute the goal autonomously
    exec_result = orchestrator.execute_goal_autonomously(
        goal_id=result['goal_id'],
        user_id=1,
        auto_approve=True
    )
else:
    print(f"No goal needed: {result['reasoning']}")
```

### Auto-Execute Mode

You can analyze AND execute in one call:

```python
# Decompose request and immediately start autonomous execution
result = orchestrator.decompose_and_create_goal(
    user_request="Create a test project structure with directories and README",
    user_id=1,
    auto_execute=True  # Automatically execute after creating goal
)

if result['created']:
    execution = result['execution_result']
    print(f"Status: {execution['status']}")
    print(f"Progress: {execution['final_progress']}%")
    print(f"Tasks completed: {execution['tasks_completed']}")
```

### Decomposition Output

The `GoalDecomposerLLM` returns a `GoalProposal` with:

```python
GoalProposal(
    goal_text="Set up Python web scraper project",
    goal_type=GoalType.TASK,
    context="New project with virtual environment and dependencies",
    priority=Priority.MEDIUM,
    subtasks=[
        SubtaskProposal(
            task_text="Create project directory 'web_scraper'",
            task_order=1,
            prerequisites=[],
            max_retries=3
        ),
        SubtaskProposal(
            task_text="Create virtual environment in project",
            task_order=2,
            prerequisites=[1],  # Depends on directory creation
            max_retries=3
        ),
        SubtaskProposal(
            task_text="Create requirements.txt with requests and beautifulsoup4",
            task_order=3,
            prerequisites=[1],  # Only needs directory, can run parallel with venv
            max_retries=3
        ),
        SubtaskProposal(
            task_text="Create README.md with project description",
            task_order=4,
            prerequisites=[1],
            max_retries=2
        )
    ]
)
```

### Configuration

The decomposer uses the standard Ollama configuration with optional timeout:

```yaml
ollama:
  host: localhost
  port: 11434
  model: qwen2.5-coder:32b
  timeout: 120
  decomposer_timeout: 180  # Optional: timeout for decomposition LLM calls

goals:
  enabled: true  # Must be true for decomposition
```

### Testing

Run the demo to see it in action:

```bash
./venv/bin/python examples/goal_decomposition_demo.py
```

This demonstrates:
- Simple task detection (no goal created)
- Complex task decomposition (goal with subtasks)
- Auto-execution (decompose and run immediately)

## Automatic Goal Detection in Main Loop

**NEWEST FEATURE**: Jarvis now automatically detects multi-step tasks during normal conversation and offers to create goals for them!

### How It Works

When you interact with Jarvis through `main.py`, the system:

1. **Analyzes every request** using the `GoalDecomposerLLM`
2. **Detects multi-step tasks** that would benefit from goal tracking
3. **Prompts you for confirmation** before creating a goal
4. **Executes autonomously** if you approve (or falls back to normal processing)

### User Experience

```
You: Set up a new Python project with Flask and database support

🎯 MULTI-STEP TASK DETECTED
======================================================================

Goal: Set up Python Flask project with database integration
Type: task
Subtasks: 5

Subtasks:
  1. Create project directory 'flask_project'
  2. Create virtual environment
  3. Create requirements.txt with Flask and SQLAlchemy
  4. Create basic Flask app with database configuration
  5. Create README.md with setup instructions

----------------------------------------------------------------------
Create goal and execute autonomously? (yes/no/manual) [yes]: yes

✓ Goal created (ID: 42)

🚀 Starting autonomous execution...

======================================================================
[Jarvis executes each subtask automatically with progress updates]
======================================================================

✅ GOAL EXECUTION COMPLETE

Status: completed
Progress: 100%
Tasks completed: 5/5
```

### Response Options

When prompted "Create goal and execute autonomously? (yes/no/manual) [yes]":

- **`yes`** (or just press Enter): Create goal and execute it autonomously
- **`no`**: Skip goal creation and process as a normal single task
- **`manual`**: Create the goal but don't execute it (you can run it later)

### Configuration

Control auto-detection behavior in `config.yaml`:

```yaml
goals:
  enabled: true
  auto_detect: true  # Enable automatic goal detection (default: true)
  auto_execute_goals: true  # Auto-execute after creation (default: true)
```

**Options:**
- `auto_detect: false` - Disable automatic detection entirely
- `auto_execute_goals: false` - Always prompt for execution even if user says "yes"

### When Auto-Detection Triggers

The system creates goal suggestions when your request:

✅ Requires **2+ discrete steps**
✅ Has **dependencies** between steps
✅ Spans **multiple tools or operations**
✅ Would benefit from **progress tracking**

**Examples that trigger auto-detection:**
- "Set up a development environment for a React project"
- "Deploy my application to a remote server with SSL"
- "Create a backup system for my database with rotation"
- "Analyze log files, find errors, and create a report"

**Examples that don't (simple tasks):**
- "List all Python files"
- "Read the README.md file"
- "What's the current time?"

### Seamless Fallback

If you decline goal creation:
- Request processes normally as a single task
- No goal tracking or overhead
- Same experience as if auto-detection was disabled

### Demo

Try it yourself:

```bash
# Method 1: Use the interactive demo
./venv/bin/python examples/auto_goal_demo.py

# Method 2: Just run Jarvis normally
./venv/bin/python main.py
# Then enter a multi-step request when prompted
```

### Benefits

🎯 **Zero friction**: Works naturally in conversation
🤖 **Smart detection**: Only suggests goals when beneficial
⚡ **Instant execution**: From request to completion automatically
🔄 **Resumable**: Can pause and resume multi-step work
📊 **Trackable**: Full progress and audit logging
🛡️ **Safe**: User approval required before goal creation

## Python API

### Creating a Goal

```python
from goals import GoalManager, GoalProposal, SubtaskProposal, GoalType, Priority

# Initialize manager
goal_manager = GoalManager(
    host='tools',
    database='jarvis',
    user='steve',
    password='koala1'
)

# Create proposal
proposal = GoalProposal(
    goal_text="Set up WireGuard VPN on home server",
    goal_type=GoalType.TASK,
    context="Ubuntu 22.04 server, need secure remote access",
    priority=Priority.HIGH,
    subtasks=[
        SubtaskProposal(
            task_text="Install WireGuard packages",
            task_order=1,
            prerequisites=[]
        ),
        SubtaskProposal(
            task_text="Generate server keys",
            task_order=2,
            prerequisites=[1]  # Depends on task 1
        ),
        SubtaskProposal(
            task_text="Configure wg0 interface",
            task_order=3,
            prerequisites=[2]  # Depends on task 2
        ),
        SubtaskProposal(
            task_text="Set up firewall rules",
            task_order=4,
            prerequisites=[3]
        ),
        SubtaskProposal(
            task_text="Test VPN connection",
            task_order=5,
            prerequisites=[4]
        )
    ]
)

# Create goal (returns goal_id)
goal_id = goal_manager.create_goal(proposal, user_id=1)
```

### Executing Tasks

```python
# Get next actionable task (respects dependencies)
next_task = goal_manager.get_next_actionable_task(goal_id)

if next_task:
    print(f"Executing: {next_task.task_text}")

    # Mark as in progress
    goal_manager.update_subtask_status(
        next_task.id,
        SubtaskStatus.IN_PROGRESS
    )

    # Execute task (via orchestrator)
    result = execute_task(next_task.task_text)

    # Mark as completed with result
    goal_manager.update_subtask_status(
        next_task.id,
        SubtaskStatus.COMPLETED,
        result=result,
        tools_used=['bash', 'read_file'],
        verification_passed=True
    )
```

### Handling Failures

```python
# If task fails
goal_manager.update_subtask_status(
    task_id,
    SubtaskStatus.FAILED,
    error_message="Command failed with exit code 1",
    verification_passed=False
)

# Retry the task (if retries remain)
can_retry = goal_manager.retry_subtask(task_id)

if can_retry:
    print("Task queued for retry")
else:
    print("Max retries exceeded, task permanently failed")
    # Mark goal as blocked or failed
    goal_manager.update_goal_status(
        goal_id,
        GoalStatus.BLOCKED,
        blocking_reason="Task 2 failed after 3 retry attempts"
    )
```

### Progress Tracking

```python
# Get detailed progress information
progress = goal_manager.get_goal_with_progress(goal_id)

print(f"Goal: {progress.goal.goal_text}")
print(f"Progress: {progress.goal.progress_percentage}%")
print(f"Status: {progress.goal.status.value}")

if progress.next_task:
    print(f"Next: {progress.next_task.task_text}")

if progress.blocked_tasks:
    print(f"Blocked: {len(progress.blocked_tasks)} tasks waiting")

print(f"Can make progress: {progress.can_make_progress}")
```

### Checkpoints for Resumability

```python
# Save checkpoint after critical steps
goal_manager.save_checkpoint(
    goal_id,
    "after_wireguard_install",
    checkpoint_data={
        'step': 2,
        'server_public_key': 'abc123...',
        'config_path': '/etc/wireguard/wg0.conf'
    }
)

# Later: Resume from checkpoint
checkpoint = goal_manager.get_latest_checkpoint(goal_id)
if checkpoint:
    state = checkpoint.checkpoint_data
    print(f"Resuming from: {checkpoint.checkpoint_name}")
    print(f"State: {state}")
```

### Audit Logging

```python
# Get audit log for goal
log_entries = goal_manager.get_audit_log(goal_id=goal_id, limit=50)

for entry in log_entries:
    print(f"[{entry.created_at}] {entry.event_type.value}")
    if entry.event_details:
        print(f"  Details: {entry.event_details}")
```

## Usage Patterns

### Pattern 1: Simple Sequential Tasks

Goal with tasks that must run in order.

```python
proposal = GoalProposal(
    goal_text="Update system and install Python",
    subtasks=[
        SubtaskProposal(task_text="apt update", task_order=1, prerequisites=[]),
        SubtaskProposal(task_text="apt upgrade", task_order=2, prerequisites=[1]),
        SubtaskProposal(task_text="install python3", task_order=3, prerequisites=[2])
    ]
)
```

**Execution flow:**
1. Task 1 runs
2. Task 2 waits for Task 1 to complete
3. Task 3 waits for Task 2 to complete

### Pattern 2: Parallel Tasks with Final Step

Some tasks can run in parallel, with a final step depending on both.

```python
proposal = GoalProposal(
    goal_text="Set up development environment",
    subtasks=[
        SubtaskProposal(task_text="Install Python", task_order=1, prerequisites=[]),
        SubtaskProposal(task_text="Install Node.js", task_order=2, prerequisites=[]),
        SubtaskProposal(task_text="Install Docker", task_order=3, prerequisites=[]),
        SubtaskProposal(
            task_text="Configure VS Code with all extensions",
            task_order=4,
            prerequisites=[1, 2, 3]  # Waits for all three
        )
    ]
)
```

**Execution flow:**
1. Tasks 1, 2, 3 can run in parallel (no dependencies)
2. Task 4 waits until ALL of 1, 2, 3 are complete

### Pattern 3: Diamond Dependency

```python
proposal = GoalProposal(
    goal_text="Build and deploy application",
    subtasks=[
        SubtaskProposal(task_text="Clone repository", task_order=1, prerequisites=[]),
        SubtaskProposal(task_text="Install dependencies", task_order=2, prerequisites=[1]),
        SubtaskProposal(task_text="Run tests", task_order=3, prerequisites=[2]),
        SubtaskProposal(task_text="Build Docker image", task_order=4, prerequisites=[2]),
        SubtaskProposal(
            task_text="Deploy to production",
            task_order=5,
            prerequisites=[3, 4]  # Both tests AND build must pass
        )
    ]
)
```

**Execution flow:**
```
      1 (Clone)
      |
      2 (Install)
     / \
    3   4  (Tests and Build run in parallel)
     \ /
      5 (Deploy - waits for both)
```

### Pattern 4: Long-Running with Checkpoints

```python
proposal = GoalProposal(
    goal_text="Migrate database to new server",
    subtasks=[
        SubtaskProposal(task_text="Export old database", task_order=1, prerequisites=[]),
        SubtaskProposal(task_text="Transfer dump file", task_order=2, prerequisites=[1]),
        SubtaskProposal(task_text="Import to new server", task_order=3, prerequisites=[2]),
        SubtaskProposal(task_text="Verify data integrity", task_order=4, prerequisites=[3]),
        SubtaskProposal(task_text="Update connection strings", task_order=5, prerequisites=[4])
    ]
)

goal_id = goal_manager.create_goal(proposal, user_id=1)

# After each critical step, save checkpoint
goal_manager.save_checkpoint(goal_id, "export_complete", {'dump_file': '/tmp/backup.sql'})
goal_manager.save_checkpoint(goal_id, "transfer_complete", {'remote_path': '/data/backup.sql'})
goal_manager.save_checkpoint(goal_id, "import_complete", {'new_db': 'postgresql://new_server'})
```

## Integration with Orchestrator

### Autonomous Goal Execution Loop

```python
class Orchestrator:
    def __init__(self, config):
        # ... existing initialization ...
        self.goal_manager = GoalManager(
            host=config['memory']['mysql_host'],
            database=config['memory']['mysql_database'],
            user=config['memory']['mysql_user'],
            password=config['memory']['mysql_password']
        )

    def execute_goal_autonomously(self, goal_id: int, max_iterations: int = 100):
        """
        Autonomously execute a goal until completion or blocking.

        Returns:
            (status, iterations_used)
        """
        iterations = 0

        while iterations < max_iterations:
            # Get current progress
            progress = self.goal_manager.get_goal_with_progress(goal_id)

            # Check if we can make progress
            if not progress.can_make_progress:
                logger.info("No more actionable tasks")
                break

            # Get next task
            next_task = progress.next_task
            if not next_task:
                break

            logger.info(f"Executing task {next_task.task_order}: {next_task.task_text}")

            # Mark as in progress
            self.goal_manager.update_subtask_status(
                next_task.id,
                SubtaskStatus.IN_PROGRESS
            )

            # Execute through normal orchestrator pipeline
            try:
                result = self.process_user_input(
                    user_input=next_task.task_text,
                    user_id=progress.goal.user_id
                )

                # Check if successful
                if result.get('verification', {}).get('success', True):
                    # Mark completed
                    self.goal_manager.update_subtask_status(
                        next_task.id,
                        SubtaskStatus.COMPLETED,
                        result=result['response'],
                        tools_used=[action['tool'] for action in result['actions_taken']],
                        verification_passed=True
                    )
                else:
                    # Mark failed
                    self.goal_manager.update_subtask_status(
                        next_task.id,
                        SubtaskStatus.FAILED,
                        error_message=result.get('verification', {}).get('issues', 'Unknown'),
                        verification_passed=False
                    )

                    # Try to retry
                    can_retry = self.goal_manager.retry_subtask(next_task.id)
                    if not can_retry:
                        logger.error(f"Task {next_task.id} failed permanently")
                        self.goal_manager.update_goal_status(
                            goal_id,
                            GoalStatus.BLOCKED,
                            blocking_reason=f"Task {next_task.task_order} failed after max retries"
                        )
                        break

            except Exception as e:
                logger.error(f"Error executing task: {e}")
                self.goal_manager.update_subtask_status(
                    next_task.id,
                    SubtaskStatus.FAILED,
                    error_message=str(e)
                )
                break

            iterations += 1

        # Check final status
        goal = self.goal_manager.get_goal(goal_id)
        if goal.progress_percentage == 100:
            self.goal_manager.update_goal_status(
                goal_id,
                GoalStatus.COMPLETED,
                result_summary=f"All {len(goal.subtasks)} tasks completed successfully"
            )
            return (GoalStatus.COMPLETED, iterations)
        else:
            return (goal.status, iterations)
```

## Benefits

### Before Goal Management

```
User: "Set up a development environment"
System: Executes as single monolithic task
        - No progress tracking
        - Can't resume if interrupted
        - No retry logic
        - No audit trail
```

### After Goal Management

```
User: "Set up a development environment"
System:
  1. Creates goal with 5 subtasks
  2. Executes tasks in dependency order
  3. Tracks progress (0% → 20% → 40% → 60% → 80% → 100%)
  4. Saves checkpoints after critical steps
  5. Retries failed tasks automatically
  6. Logs all events to audit trail
  7. Can resume from interruption
  8. Provides detailed status updates
```

## Testing

Run the comprehensive test suite:

```bash
./venv/bin/python tests/test_goal_management.py
```

**Tests cover:**
- ✅ Goal creation with subtasks and dependencies
- ✅ Next actionable task selection (respects dependencies)
- ✅ Progress tracking and calculation
- ✅ Checkpoint save/load for resumability
- ✅ Comprehensive audit logging
- ✅ Task failure and retry handling

## Database Queries

### Active Goals for User

```sql
SELECT id, goal_text, status, priority, progress_percentage, created_at
FROM goals
WHERE user_id = 1
  AND status IN ('pending', 'in_progress', 'blocked')
ORDER BY priority DESC, created_at ASC;
```

### Blocked Goals

```sql
SELECT g.id, g.goal_text, g.blocking_reason, s.task_text as blocking_task
FROM goals g
LEFT JOIN subtasks s ON g.blocking_subtask_id = s.id
WHERE g.status = 'blocked';
```

### Goal Progress Report

```sql
SELECT
    g.id,
    g.goal_text,
    g.progress_percentage,
    COUNT(s.id) as total_tasks,
    SUM(CASE WHEN s.status IN ('completed', 'skipped') THEN 1 ELSE 0 END) as completed_tasks,
    SUM(CASE WHEN s.status = 'failed' THEN 1 ELSE 0 END) as failed_tasks
FROM goals g
LEFT JOIN subtasks s ON g.id = s.goal_id
WHERE g.user_id = 1
GROUP BY g.id;
```

## Future Enhancements

1. **LLM Goal Decomposition**: Automatically break down user requests into goals and subtasks
2. **Dynamic Task Addition**: Add new subtasks mid-execution based on findings
3. **Parallel Execution**: Run independent tasks concurrently (thread pool)
4. **Resource Estimation**: Predict time/cost before starting
5. **Smart Retry Strategies**: Different retry logic based on error type
6. **Goal Templates**: Pre-defined goal structures for common tasks
7. **Cross-Goal Dependencies**: Goals that depend on other goals

---

**Status**: ✅ Fully Implemented and Tested
**Date**: 2026-01-09
**Next**: Integrate with orchestrator for autonomous execution
