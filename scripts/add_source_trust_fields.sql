-- Add Source Trust & Fact Confidence Fields to Memories Table
-- This enables tracking the provenance and reliability of each memory

USE jarvis;

-- Add source tracking fields
ALTER TABLE memories
ADD COLUMN source_type ENUM('user', 'tool_output', 'web', 'inference', 'unknown')
    DEFAULT 'unknown'
    AFTER importance,
ADD COLUMN source_identity VARCHAR(500) NULL
    COMMENT 'Domain name, tool name, model name, or other source identifier'
    AFTER source_type,
ADD COLUMN verification_status ENUM('unverified', 'corroborated', 'contradicted', 'deprecated')
    DEFAULT 'unverified'
    AFTER decay_score,
ADD COLUMN corroboration_count INT DEFAULT 0
    COMMENT 'Number of times this fact has been corroborated by other sources'
    AFTER verification_status,
ADD COLUMN last_verified_at TIMESTAMP NULL
    COMMENT 'When this memory was last verified or corroborated'
    AFTER corroboration_count;

-- Add indexes for querying by verification status and source type
ALTER TABLE memories
ADD INDEX idx_verification_status (verification_status, status),
ADD INDEX idx_source_type (source_type);

-- Update existing memories to have reasonable defaults
-- User-provided memories get source_type='user'
UPDATE memories
SET source_type = 'user'
WHERE created_by = 'manual' OR created_by = 'curator_llm';

-- System-generated memories might be inferences
UPDATE memories
SET source_type = 'inference'
WHERE created_by = 'system';
