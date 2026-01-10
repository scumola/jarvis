"""
Goal & Task Management System

Enables Jarvis to track long-running goals with subtasks, dependencies,
and resumability for autonomous work.
"""

from .schemas import (
    Goal, Subtask, TaskDependency, GoalCheckpoint, GoalAuditLog,
    GoalType, GoalStatus, Priority, SubtaskStatus, DependencyType, GoalEventType,
    GoalProposal, SubtaskProposal, GoalSummary, SubtaskSummary, GoalWithProgress
)
from .manager import GoalManager

__all__ = [
    'Goal', 'Subtask', 'TaskDependency', 'GoalCheckpoint', 'GoalAuditLog',
    'GoalType', 'GoalStatus', 'Priority', 'SubtaskStatus', 'DependencyType', 'GoalEventType',
    'GoalProposal', 'SubtaskProposal', 'GoalSummary', 'SubtaskSummary', 'GoalWithProgress',
    'GoalManager'
]
