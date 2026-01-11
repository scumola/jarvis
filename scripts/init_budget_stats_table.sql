-- Budget Statistics Tracking Table
--
-- Tracks token budget usage for memory retrieval to enable monitoring
-- and optimization of context budgeting system.
--
-- Usage: mysql -u your_user -p your_database < scripts/init_budget_stats_table.sql

CREATE TABLE IF NOT EXISTS memory_budget_stats (
    -- Primary key
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- User context
    user_id INT NOT NULL,

    -- Query that triggered memory retrieval
    query TEXT,

    -- Budget calculations
    available_budget INT COMMENT 'Token budget available for memories after conversation usage',
    calculated_k INT COMMENT 'Dynamic k value calculated based on budget',

    -- Actual retrieval results
    actual_retrieved INT COMMENT 'Number of memories actually retrieved',
    tokens_used INT COMMENT 'Actual tokens consumed by retrieved memories',

    -- Timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes for efficient queries
    INDEX idx_user_time (user_id, created_at),
    INDEX idx_created_at (created_at),

    -- Foreign key constraint
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tracks token budget usage and memory retrieval statistics for context budgeting optimization';
