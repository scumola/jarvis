"""
Goal & Task Management Schemas

Pydantic models for goals, subtasks, dependencies, and checkpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums

class GoalType(str, Enum):
    """Type of goal."""
    TASK = "task"
    PROJECT = "project"
    LEARNING = "learning"
    RESEARCH = "research"
    MAINTENANCE = "maintenance"


class GoalStatus(str, Enum):
    """Current status of a goal."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Priority(str, Enum):
    """Priority level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SubtaskStatus(str, Enum):
    """Current status of a subtask."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class DependencyType(str, Enum):
    """Type of task dependency."""
    BLOCKING = "blocking"      # Must complete before dependent can start
    PREFERRED = "preferred"    # Should complete first but not required
    OPTIONAL = "optional"      # Can skip if needed


class GoalEventType(str, Enum):
    """Types of goal audit events."""
    GOAL_CREATED = "goal_created"
    GOAL_STARTED = "goal_started"
    GOAL_COMPLETED = "goal_completed"
    GOAL_FAILED = "goal_failed"
    GOAL_BLOCKED = "goal_blocked"
    GOAL_RESUMED = "goal_resumed"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRIED = "task_retried"
    CHECKPOINT_SAVED = "checkpoint_saved"


# Core Models

class Subtask(BaseModel):
    """A single subtask within a goal."""
    id: Optional[int] = None
    goal_id: int

    # Task details
    task_text: str = Field(..., description="Description of this subtask")
    task_order: int = Field(..., description="Order within the goal (for sequential execution)")

    # Status tracking
    status: SubtaskStatus = Field(default=SubtaskStatus.PENDING)
    retries: int = Field(default=0, description="Number of times this task has been attempted")
    max_retries: int = Field(default=3, description="Maximum retry attempts before failing")

    # Execution details
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_seconds: Optional[int] = None

    # Results
    result: Optional[str] = Field(None, description="Output or result of task execution")
    error_message: Optional[str] = Field(None, description="Error details if task failed")
    blocking_reason: Optional[str] = Field(None, description="Why this task is blocked")

    # Tool tracking
    tools_used: Optional[List[str]] = Field(None, description="List of tools invoked")
    verification_passed: Optional[bool] = Field(None, description="Did verification pass?")

    class Config:
        from_attributes = True


class TaskDependency(BaseModel):
    """Defines a dependency between two subtasks."""
    id: Optional[int] = None
    subtask_id: int = Field(..., description="The dependent task (waits for prerequisite)")
    prerequisite_id: int = Field(..., description="The prerequisite task (must complete first)")
    dependency_type: DependencyType = Field(default=DependencyType.BLOCKING)
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Goal(BaseModel):
    """A high-level goal with subtasks."""
    id: Optional[int] = None
    user_id: int

    # Goal details
    goal_text: str = Field(..., description="Natural language description of the goal")
    goal_type: GoalType = Field(default=GoalType.TASK)
    context: Optional[str] = Field(None, description="Additional context or background")

    # Status tracking
    status: GoalStatus = Field(default=GoalStatus.PENDING)
    priority: Priority = Field(default=Priority.MEDIUM)
    progress_percentage: int = Field(default=0, ge=0, le=100, description="Calculated from subtask completion")

    # Blocking information
    blocking_reason: Optional[str] = Field(None, description="Why this goal is blocked")
    blocking_subtask_id: Optional[int] = Field(None, description="Which subtask is blocking progress")

    # Timestamps
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    deadline: Optional[datetime] = None

    # Result tracking
    result_summary: Optional[str] = Field(None, description="Summary of outcome when completed/failed")
    lessons_learned: Optional[str] = Field(None, description="Post-mortem insights for procedural memory")

    # Relationships (loaded separately)
    subtasks: List[Subtask] = Field(default_factory=list, description="List of subtasks")

    class Config:
        from_attributes = True


class GoalCheckpoint(BaseModel):
    """Saved state for resuming a goal."""
    id: Optional[int] = None
    goal_id: int
    checkpoint_name: str
    checkpoint_data: Dict[str, Any] = Field(..., description="Serialized state data")
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GoalAuditLog(BaseModel):
    """Audit log entry for goal events."""
    id: Optional[int] = None
    goal_id: Optional[int] = None
    subtask_id: Optional[int] = None
    event_type: GoalEventType
    event_details: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Proposal Models (for creating new goals)

class SubtaskProposal(BaseModel):
    """Proposal for a new subtask from LLM."""
    task_text: str
    task_order: int
    prerequisites: List[int] = Field(default_factory=list, description="List of task_order values this depends on")
    max_retries: int = Field(default=3)


class GoalProposal(BaseModel):
    """Proposal for a new goal from LLM or user."""
    goal_text: str
    goal_type: GoalType = Field(default=GoalType.TASK)
    context: Optional[str] = None
    priority: Priority = Field(default=Priority.MEDIUM)
    deadline: Optional[datetime] = None
    subtasks: List[SubtaskProposal] = Field(default_factory=list)


# Response Models (for API/UI)

class GoalSummary(BaseModel):
    """Lightweight goal summary for listing."""
    id: int
    goal_text: str
    status: GoalStatus
    priority: Priority
    progress_percentage: int
    created_at: datetime
    deadline: Optional[datetime] = None
    subtask_count: int = 0
    completed_subtask_count: int = 0

    class Config:
        from_attributes = True


class SubtaskSummary(BaseModel):
    """Lightweight subtask summary."""
    id: int
    task_text: str
    status: SubtaskStatus
    task_order: int
    retries: int

    class Config:
        from_attributes = True


class GoalWithProgress(BaseModel):
    """Goal with detailed progress information."""
    goal: Goal
    subtasks: List[Subtask]
    dependencies: List[TaskDependency] = Field(default_factory=list)
    next_task: Optional[Subtask] = Field(None, description="Next task to execute")
    blocked_tasks: List[Subtask] = Field(default_factory=list, description="Tasks waiting on dependencies")
    can_make_progress: bool = Field(..., description="Whether there's work to be done")

    class Config:
        from_attributes = True
