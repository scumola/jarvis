-- Goal & Task Management System Database Schema
--
-- Purpose: Enable Jarvis to track long-running goals with subtasks,
-- dependencies, and resumability for autonomous work.
--
-- Date: 2026-01-09

-- Goals table: High-level objectives
CREATE TABLE IF NOT EXISTS goals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,

    -- Goal details
    goal_text TEXT NOT NULL COMMENT 'Natural language description of the goal',
    goal_type ENUM('task', 'project', 'learning', 'research', 'maintenance') DEFAULT 'task',
    context TEXT NULL COMMENT 'Additional context or background information',

    -- Status tracking
    status ENUM('pending', 'in_progress', 'completed', 'blocked', 'failed', 'cancelled') DEFAULT 'pending',
    priority ENUM('low', 'medium', 'high', 'urgent') DEFAULT 'medium',
    progress_percentage INT DEFAULT 0 COMMENT 'Calculated from subtask completion (0-100)',

    -- Blocking information
    blocking_reason TEXT NULL COMMENT 'Why this goal is blocked (if status = blocked)',
    blocking_subtask_id INT NULL COMMENT 'Which subtask is blocking progress',

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL COMMENT 'When work began',
    completed_at TIMESTAMP NULL COMMENT 'When goal was completed/failed',
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deadline TIMESTAMP NULL COMMENT 'Optional deadline for completion',

    -- Result tracking
    result_summary TEXT NULL COMMENT 'Summary of outcome when completed/failed',
    lessons_learned TEXT NULL COMMENT 'Post-mortem insights for procedural memory',

    -- Foreign keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    -- Indexes
    INDEX idx_user_status (user_id, status),
    INDEX idx_status_priority (status, priority),
    INDEX idx_deadline (deadline),
    INDEX idx_created (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Subtasks table: Individual steps within a goal
CREATE TABLE IF NOT EXISTS subtasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    goal_id INT NOT NULL,

    -- Task details
    task_text TEXT NOT NULL COMMENT 'Description of this subtask',
    task_order INT NOT NULL COMMENT 'Order within the goal (for sequential execution)',

    -- Status tracking
    status ENUM('pending', 'in_progress', 'completed', 'failed', 'skipped', 'blocked') DEFAULT 'pending',
    retries INT DEFAULT 0 COMMENT 'Number of times this task has been attempted',
    max_retries INT DEFAULT 3 COMMENT 'Maximum retry attempts before failing',

    -- Execution details
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    execution_time_seconds INT NULL COMMENT 'How long it took to complete',

    -- Results
    result TEXT NULL COMMENT 'Output or result of task execution',
    error_message TEXT NULL COMMENT 'Error details if task failed',
    blocking_reason TEXT NULL COMMENT 'Why this task is blocked',

    -- Tool tracking
    tools_used JSON NULL COMMENT 'List of tools invoked for this subtask',
    verification_passed BOOLEAN NULL COMMENT 'Did verification pass?',

    -- Foreign keys
    FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE,

    -- Indexes
    INDEX idx_goal_order (goal_id, task_order),
    INDEX idx_goal_status (goal_id, status),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Task dependencies: Define which tasks must complete before others
CREATE TABLE IF NOT EXISTS task_dependencies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subtask_id INT NOT NULL COMMENT 'The dependent task (waits for prerequisite)',
    prerequisite_id INT NOT NULL COMMENT 'The prerequisite task (must complete first)',
    dependency_type ENUM('blocking', 'preferred', 'optional') DEFAULT 'blocking'
        COMMENT 'blocking=must complete, preferred=should complete, optional=can skip',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (subtask_id) REFERENCES subtasks(id) ON DELETE CASCADE,
    FOREIGN KEY (prerequisite_id) REFERENCES subtasks(id) ON DELETE CASCADE,

    -- Constraints
    UNIQUE KEY unique_dependency (subtask_id, prerequisite_id),
    CHECK (subtask_id != prerequisite_id),

    -- Indexes
    INDEX idx_subtask (subtask_id),
    INDEX idx_prerequisite (prerequisite_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Goal checkpoints: Save state for resumability
CREATE TABLE IF NOT EXISTS goal_checkpoints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    goal_id INT NOT NULL,

    -- Checkpoint details
    checkpoint_name VARCHAR(255) NOT NULL,
    checkpoint_data JSON NOT NULL COMMENT 'Serialized state data for resuming',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE,

    -- Indexes
    INDEX idx_goal_created (goal_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Goal audit log: Track all goal state changes
CREATE TABLE IF NOT EXISTS goal_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    goal_id INT NULL,
    subtask_id INT NULL,

    -- Event details
    event_type ENUM('goal_created', 'goal_started', 'goal_completed', 'goal_failed',
                    'goal_blocked', 'goal_resumed', 'task_started', 'task_completed',
                    'task_failed', 'task_retried', 'checkpoint_saved') NOT NULL,
    event_details JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE,
    FOREIGN KEY (subtask_id) REFERENCES subtasks(id) ON DELETE CASCADE,

    -- Indexes
    INDEX idx_goal (goal_id, created_at),
    INDEX idx_subtask (subtask_id, created_at),
    INDEX idx_event_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add foreign key from goals to subtasks (after both tables exist)
ALTER TABLE goals
ADD CONSTRAINT fk_goals_blocking_subtask
FOREIGN KEY (blocking_subtask_id) REFERENCES subtasks(id) ON DELETE SET NULL;

-- Sample data for testing
-- INSERT INTO goals (user_id, goal_text, goal_type, priority) VALUES
-- (1, 'Set up WireGuard VPN on the home server', 'task', 'high');
