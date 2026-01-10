-- Procedural Memory Table
-- Stores learned heuristics for retry strategy selection

CREATE TABLE IF NOT EXISTS procedural_memory (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Context classification
    context_type ENUM(
        'filesystem',
        'web_retrieval',
        'tool_execution',
        'code_generation',
        'data_processing',
        'general'
    ) NOT NULL,

    -- Pattern identification
    failure_type VARCHAR(50) NOT NULL,  -- From FailureType enum
    effective_strategy VARCHAR(50) NOT NULL,  -- From RetryStrategy enum

    -- Learning metrics
    confidence_score DECIMAL(3,2) NOT NULL DEFAULT 0.5,
    usage_count INT DEFAULT 0,
    success_count INT DEFAULT 0,
    failure_count INT DEFAULT 0,

    -- Temporal tracking
    last_applied_at TIMESTAMP NULL,
    last_success_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Abstract description (NO specifics like filenames, URLs, etc.)
    notes TEXT,

    -- Indexes for fast lookups
    INDEX idx_context_failure (context_type, failure_type),
    INDEX idx_confidence (confidence_score),
    INDEX idx_last_applied (last_applied_at),

    -- Ensure uniqueness of patterns
    UNIQUE KEY unique_pattern (context_type, failure_type, effective_strategy)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
