-- Add introspection fields to procedural_memory table
-- These fields store narrative insights from post-task reflection

USE jarvis;

-- Add root cause analysis field
ALTER TABLE procedural_memory
ADD COLUMN root_cause TEXT NULL
COMMENT 'Why did the task fail initially? Root cause analysis from introspection.'
AFTER notes;

-- Add inefficiencies field (JSON array)
ALTER TABLE procedural_memory
ADD COLUMN inefficiencies JSON NULL
COMMENT 'List of inefficiencies identified during task execution.'
AFTER root_cause;

-- Add surprises field (JSON array)
ALTER TABLE procedural_memory
ADD COLUMN surprises JSON NULL
COMMENT 'Unexpected aspects or edge cases encountered.'
AFTER inefficiencies;

-- Add generalizable lesson field
ALTER TABLE procedural_memory
ADD COLUMN generalizable_lesson TEXT NULL
COMMENT 'Abstract principle that applies to future similar tasks.'
AFTER surprises;

-- Add insight confidence field (separate from pattern confidence)
ALTER TABLE procedural_memory
ADD COLUMN insight_confidence DECIMAL(3,2) NULL
COMMENT 'Confidence in the introspection analysis (0.0-1.0).'
AFTER generalizable_lesson;

-- Verify changes
DESCRIBE procedural_memory;

-- Show sample
SELECT id, context_type, failure_type, effective_strategy,
       root_cause, generalizable_lesson, insight_confidence
FROM procedural_memory
LIMIT 3;
