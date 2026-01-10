"""
Goal Manager - Main interface for goal and task management.

Coordinates goal creation, subtask execution, dependency tracking,
and resumability for long-running autonomous work.
"""

from typing import List, Optional, Dict, Any, Tuple
import logging
import json
from datetime import datetime
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

from .schemas import (
    Goal, Subtask, TaskDependency, GoalCheckpoint, GoalAuditLog,
    GoalProposal, SubtaskProposal, GoalWithProgress,
    GoalStatus, SubtaskStatus, DependencyType, GoalEventType, Priority
)

logger = logging.getLogger(__name__)


class GoalManager:
    """
    Main goal management interface.

    Provides high-level methods for creating and tracking goals,
    managing subtask execution, and handling resumability.
    """

    def __init__(self, host: str, database: str, user: str, password: str, pool_size: int = 5):
        """
        Initialize Goal Manager with database connection.

        Args:
            host: MySQL host
            database: Database name
            user: Database user
            password: Database password
            pool_size: Connection pool size
        """
        self.pool = MySQLConnectionPool(
            pool_name="goal_pool",
            pool_size=pool_size,
            host=host,
            database=database,
            user=user,
            password=password
        )
        logger.info("Goal Manager initialized successfully")

    def _get_connection(self):
        """Get a connection from the pool."""
        return self.pool.get_connection()

    # ==================== Goal CRUD Operations ====================

    def create_goal(self, proposal: GoalProposal, user_id: int) -> int:
        """
        Create a new goal from a proposal.

        Args:
            proposal: GoalProposal with goal details and subtasks
            user_id: ID of the user who owns this goal

        Returns:
            ID of created goal

        Raises:
            Exception if creation fails
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            # Insert goal
            goal_query = """
                INSERT INTO goals (
                    user_id, goal_text, goal_type, context, priority, deadline, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(goal_query, (
                user_id,
                proposal.goal_text,
                proposal.goal_type.value,
                proposal.context,
                proposal.priority.value,
                proposal.deadline,
                GoalStatus.PENDING.value
            ))

            goal_id = cursor.lastrowid

            # Insert subtasks
            if proposal.subtasks:
                subtask_query = """
                    INSERT INTO subtasks (
                        goal_id, task_text, task_order, max_retries, status
                    ) VALUES (%s, %s, %s, %s, %s)
                """

                for subtask in proposal.subtasks:
                    cursor.execute(subtask_query, (
                        goal_id,
                        subtask.task_text,
                        subtask.task_order,
                        subtask.max_retries,
                        SubtaskStatus.PENDING.value
                    ))

                # Insert dependencies
                if any(st.prerequisites for st in proposal.subtasks):
                    # Build task_order -> subtask_id mapping
                    cursor.execute("SELECT id, task_order FROM subtasks WHERE goal_id = %s", (goal_id,))
                    order_to_id = {row[1]: row[0] for row in cursor.fetchall()}

                    dep_query = """
                        INSERT INTO task_dependencies (subtask_id, prerequisite_id, dependency_type)
                        VALUES (%s, %s, %s)
                    """

                    for subtask in proposal.subtasks:
                        if subtask.prerequisites:
                            subtask_id = order_to_id[subtask.task_order]
                            for prereq_order in subtask.prerequisites:
                                prereq_id = order_to_id.get(prereq_order)
                                if prereq_id:
                                    cursor.execute(dep_query, (
                                        subtask_id,
                                        prereq_id,
                                        DependencyType.BLOCKING.value
                                    ))

            connection.commit()

            # Log creation
            self._log_event(
                goal_id=goal_id,
                event_type=GoalEventType.GOAL_CREATED,
                event_details={'goal_text': proposal.goal_text[:100]}
            )

            logger.info(f"Created goal {goal_id} with {len(proposal.subtasks)} subtasks")
            return goal_id

        except Exception as e:
            connection.rollback()
            logger.error(f"Error creating goal: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def get_goal(self, goal_id: int, include_subtasks: bool = True) -> Optional[Goal]:
        """
        Retrieve a goal by ID.

        Args:
            goal_id: Goal ID
            include_subtasks: Whether to load subtasks

        Returns:
            Goal object or None if not found
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            # Get goal
            cursor.execute("SELECT * FROM goals WHERE id = %s", (goal_id,))
            goal_row = cursor.fetchone()

            if not goal_row:
                return None

            goal = Goal(**goal_row)

            # Load subtasks if requested
            if include_subtasks:
                cursor.execute(
                    "SELECT * FROM subtasks WHERE goal_id = %s ORDER BY task_order",
                    (goal_id,)
                )
                subtask_rows = cursor.fetchall()
                # Parse JSON fields
                for row in subtask_rows:
                    if row.get('tools_used') and isinstance(row['tools_used'], str):
                        row['tools_used'] = json.loads(row['tools_used'])
                goal.subtasks = [Subtask(**row) for row in subtask_rows]

            return goal

        finally:
            cursor.close()
            connection.close()

    def list_goals(
        self,
        user_id: int,
        status: Optional[GoalStatus] = None,
        limit: int = 50
    ) -> List[Goal]:
        """
        List goals for a user.

        Args:
            user_id: User ID
            status: Optional status filter
            limit: Maximum results

        Returns:
            List of Goal objects
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            query = "SELECT * FROM goals WHERE user_id = %s"
            params = [user_id]

            if status:
                query += " AND status = %s"
                params.append(status.value)

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [Goal(**row) for row in rows]

        finally:
            cursor.close()
            connection.close()

    def update_goal_status(
        self,
        goal_id: int,
        status: GoalStatus,
        result_summary: Optional[str] = None,
        lessons_learned: Optional[str] = None
    ) -> None:
        """
        Update goal status and optionally add result/lessons.

        Args:
            goal_id: Goal ID
            status: New status
            result_summary: Optional result summary
            lessons_learned: Optional lessons learned
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            updates = ["status = %s"]
            params = [status.value]

            # Set timestamps based on status
            if status == GoalStatus.IN_PROGRESS:
                updates.append("started_at = NOW()")
            elif status in [GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED]:
                updates.append("completed_at = NOW()")

            if result_summary:
                updates.append("result_summary = %s")
                params.append(result_summary)

            if lessons_learned:
                updates.append("lessons_learned = %s")
                params.append(lessons_learned)

            params.append(goal_id)

            query = f"UPDATE goals SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, params)
            connection.commit()

            # Log event
            event_type_map = {
                GoalStatus.IN_PROGRESS: GoalEventType.GOAL_STARTED,
                GoalStatus.COMPLETED: GoalEventType.GOAL_COMPLETED,
                GoalStatus.FAILED: GoalEventType.GOAL_FAILED,
                GoalStatus.BLOCKED: GoalEventType.GOAL_BLOCKED,
            }

            if status in event_type_map:
                self._log_event(goal_id=goal_id, event_type=event_type_map[status])

            logger.info(f"Updated goal {goal_id} status to {status.value}")

        finally:
            cursor.close()
            connection.close()

    # ==================== Subtask Operations ====================

    def get_subtasks(self, goal_id: int) -> List[Subtask]:
        """Get all subtasks for a goal."""
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT * FROM subtasks WHERE goal_id = %s ORDER BY task_order",
                (goal_id,)
            )
            rows = cursor.fetchall()
            # Parse JSON fields
            for row in rows:
                if row.get('tools_used') and isinstance(row['tools_used'], str):
                    row['tools_used'] = json.loads(row['tools_used'])
            return [Subtask(**row) for row in rows]

        finally:
            cursor.close()
            connection.close()

    def update_subtask_status(
        self,
        subtask_id: int,
        status: SubtaskStatus,
        result: Optional[str] = None,
        error_message: Optional[str] = None,
        tools_used: Optional[List[str]] = None,
        verification_passed: Optional[bool] = None
    ) -> None:
        """
        Update subtask status and results.

        Args:
            subtask_id: Subtask ID
            status: New status
            result: Optional result text
            error_message: Optional error message
            tools_used: Optional list of tools invoked
            verification_passed: Optional verification result
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            updates = ["status = %s"]
            params = [status.value]

            # Set timestamps based on status
            if status == SubtaskStatus.IN_PROGRESS:
                updates.append("started_at = NOW()")
            elif status in [SubtaskStatus.COMPLETED, SubtaskStatus.FAILED, SubtaskStatus.SKIPPED]:
                updates.append("completed_at = NOW()")
                updates.append("execution_time_seconds = TIMESTAMPDIFF(SECOND, started_at, NOW())")

            if result:
                updates.append("result = %s")
                params.append(result)

            if error_message:
                updates.append("error_message = %s")
                params.append(error_message)

            if tools_used is not None:
                updates.append("tools_used = %s")
                params.append(json.dumps(tools_used))

            if verification_passed is not None:
                updates.append("verification_passed = %s")
                params.append(verification_passed)

            params.append(subtask_id)

            query = f"UPDATE subtasks SET {', '.join(updates)} WHERE id = %s"
            cursor.execute(query, params)
            connection.commit()

            # Log event
            event_type_map = {
                SubtaskStatus.IN_PROGRESS: GoalEventType.TASK_STARTED,
                SubtaskStatus.COMPLETED: GoalEventType.TASK_COMPLETED,
                SubtaskStatus.FAILED: GoalEventType.TASK_FAILED,
            }

            if status in event_type_map:
                # Get goal_id for logging
                cursor.execute("SELECT goal_id FROM subtasks WHERE id = %s", (subtask_id,))
                goal_id = cursor.fetchone()[0]
                self._log_event(
                    goal_id=goal_id,
                    subtask_id=subtask_id,
                    event_type=event_type_map[status]
                )

            logger.info(f"Updated subtask {subtask_id} status to {status.value}")

            # Update goal progress
            cursor.execute("SELECT goal_id FROM subtasks WHERE id = %s", (subtask_id,))
            goal_id = cursor.fetchone()[0]
            self._update_goal_progress(goal_id)

        finally:
            cursor.close()
            connection.close()

    def retry_subtask(self, subtask_id: int) -> bool:
        """
        Retry a failed subtask if retries remain.

        Args:
            subtask_id: Subtask ID

        Returns:
            True if retry allowed, False if max retries exceeded
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            # Check current retry count
            cursor.execute(
                "SELECT retries, max_retries, goal_id FROM subtasks WHERE id = %s",
                (subtask_id,)
            )
            row = cursor.fetchone()

            if not row:
                return False

            if row['retries'] >= row['max_retries']:
                logger.warning(f"Subtask {subtask_id} has reached max retries")
                return False

            # Increment retry count and reset to pending
            cursor.execute("""
                UPDATE subtasks
                SET status = %s, retries = retries + 1, error_message = NULL
                WHERE id = %s
            """, (SubtaskStatus.PENDING.value, subtask_id))

            connection.commit()

            # Log retry
            self._log_event(
                goal_id=row['goal_id'],
                subtask_id=subtask_id,
                event_type=GoalEventType.TASK_RETRIED,
                event_details={'retry_count': row['retries'] + 1}
            )

            logger.info(f"Subtask {subtask_id} queued for retry (attempt {row['retries'] + 1})")
            return True

        finally:
            cursor.close()
            connection.close()

    # ==================== Dependency Management ====================

    def get_dependencies(self, goal_id: int) -> List[TaskDependency]:
        """Get all task dependencies for a goal."""
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute("""
                SELECT td.*
                FROM task_dependencies td
                JOIN subtasks s ON td.subtask_id = s.id
                WHERE s.goal_id = %s
            """, (goal_id,))
            rows = cursor.fetchall()
            return [TaskDependency(**row) for row in rows]

        finally:
            cursor.close()
            connection.close()

    def get_next_actionable_task(self, goal_id: int) -> Optional[Subtask]:
        """
        Find the next task that can be executed (no blocking dependencies).

        Args:
            goal_id: Goal ID

        Returns:
            Next actionable Subtask or None if no work available
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            # Find pending tasks with no blocking dependencies or all dependencies satisfied
            query = """
                SELECT s.*
                FROM subtasks s
                WHERE s.goal_id = %s
                  AND s.status = 'pending'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM task_dependencies td
                      JOIN subtasks prereq ON td.prerequisite_id = prereq.id
                      WHERE td.subtask_id = s.id
                        AND td.dependency_type = 'blocking'
                        AND prereq.status NOT IN ('completed', 'skipped')
                  )
                ORDER BY s.task_order
                LIMIT 1
            """

            cursor.execute(query, (goal_id,))
            row = cursor.fetchone()

            if row:
                # Parse JSON fields
                if row.get('tools_used') and isinstance(row['tools_used'], str):
                    row['tools_used'] = json.loads(row['tools_used'])
                return Subtask(**row)

            return None

        finally:
            cursor.close()
            connection.close()

    def get_goal_with_progress(self, goal_id: int) -> Optional[GoalWithProgress]:
        """
        Get goal with detailed progress information.

        Args:
            goal_id: Goal ID

        Returns:
            GoalWithProgress object with next task and blocked tasks
        """
        goal = self.get_goal(goal_id, include_subtasks=True)
        if not goal:
            return None

        dependencies = self.get_dependencies(goal_id)
        next_task = self.get_next_actionable_task(goal_id)

        # Find blocked tasks
        blocked_tasks = [
            st for st in goal.subtasks
            if st.status == SubtaskStatus.BLOCKED or (
                st.status == SubtaskStatus.PENDING and
                self._has_unmet_dependencies(st.id, goal.subtasks, dependencies)
            )
        ]

        can_make_progress = next_task is not None or any(
            st.status == SubtaskStatus.IN_PROGRESS for st in goal.subtasks
        )

        return GoalWithProgress(
            goal=goal,
            subtasks=goal.subtasks,
            dependencies=dependencies,
            next_task=next_task,
            blocked_tasks=blocked_tasks,
            can_make_progress=can_make_progress
        )

    def _has_unmet_dependencies(
        self,
        subtask_id: int,
        subtasks: List[Subtask],
        dependencies: List[TaskDependency]
    ) -> bool:
        """Check if a subtask has unmet blocking dependencies."""
        subtask_deps = [d for d in dependencies if d.subtask_id == subtask_id]

        for dep in subtask_deps:
            if dep.dependency_type != DependencyType.BLOCKING:
                continue

            prereq = next((s for s in subtasks if s.id == dep.prerequisite_id), None)
            if prereq and prereq.status not in [SubtaskStatus.COMPLETED, SubtaskStatus.SKIPPED]:
                return True

        return False

    # ==================== Progress Tracking ====================

    def _update_goal_progress(self, goal_id: int) -> None:
        """Recalculate and update goal progress percentage."""
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            # Count completed vs total subtasks
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status IN ('completed', 'skipped') THEN 1 ELSE 0 END) as completed
                FROM subtasks
                WHERE goal_id = %s
            """, (goal_id,))

            row = cursor.fetchone()
            total, completed = row[0], row[1]

            if total > 0:
                progress = int((completed / total) * 100)
            else:
                progress = 0

            cursor.execute(
                "UPDATE goals SET progress_percentage = %s WHERE id = %s",
                (progress, goal_id)
            )
            connection.commit()

        finally:
            cursor.close()
            connection.close()

    # ==================== Checkpoint Management ====================

    def save_checkpoint(
        self,
        goal_id: int,
        checkpoint_name: str,
        checkpoint_data: Dict[str, Any]
    ) -> int:
        """
        Save a checkpoint for resuming later.

        Args:
            goal_id: Goal ID
            checkpoint_name: Name for this checkpoint
            checkpoint_data: State data to save

        Returns:
            Checkpoint ID
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO goal_checkpoints (goal_id, checkpoint_name, checkpoint_data)
                VALUES (%s, %s, %s)
            """, (goal_id, checkpoint_name, json.dumps(checkpoint_data)))

            checkpoint_id = cursor.lastrowid
            connection.commit()

            self._log_event(
                goal_id=goal_id,
                event_type=GoalEventType.CHECKPOINT_SAVED,
                event_details={'checkpoint_name': checkpoint_name}
            )

            logger.info(f"Saved checkpoint '{checkpoint_name}' for goal {goal_id}")
            return checkpoint_id

        finally:
            cursor.close()
            connection.close()

    def get_latest_checkpoint(self, goal_id: int) -> Optional[GoalCheckpoint]:
        """Get the most recent checkpoint for a goal."""
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute("""
                SELECT * FROM goal_checkpoints
                WHERE goal_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (goal_id,))

            row = cursor.fetchone()
            if row:
                # Parse JSON data
                row['checkpoint_data'] = json.loads(row['checkpoint_data'])
                return GoalCheckpoint(**row)

            return None

        finally:
            cursor.close()
            connection.close()

    # ==================== Audit Logging ====================

    def _log_event(
        self,
        goal_id: Optional[int] = None,
        subtask_id: Optional[int] = None,
        event_type: GoalEventType = None,
        event_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an audit event."""
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO goal_audit_log (goal_id, subtask_id, event_type, event_details)
                VALUES (%s, %s, %s, %s)
            """, (
                goal_id,
                subtask_id,
                event_type.value,
                json.dumps(event_details) if event_details else None
            ))
            connection.commit()

        finally:
            cursor.close()
            connection.close()

    def get_audit_log(
        self,
        goal_id: Optional[int] = None,
        subtask_id: Optional[int] = None,
        limit: int = 100
    ) -> List[GoalAuditLog]:
        """Get audit log entries."""
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            query = "SELECT * FROM goal_audit_log WHERE 1=1"
            params = []

            if goal_id:
                query += " AND goal_id = %s"
                params.append(goal_id)

            if subtask_id:
                query += " AND subtask_id = %s"
                params.append(subtask_id)

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Parse JSON fields
            for row in rows:
                if row.get('event_details') and isinstance(row['event_details'], str):
                    row['event_details'] = json.loads(row['event_details'])

            return [GoalAuditLog(**row) for row in rows]

        finally:
            cursor.close()
            connection.close()
