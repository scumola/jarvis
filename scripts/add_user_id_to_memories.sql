-- Add user_id column to memories table for multi-user support
--
-- Migration steps:
-- 1. Add user_id column (nullable initially for migration)
-- 2. Create a "system" user for existing memories
-- 3. Update all existing memories to belong to system user
-- 4. Make user_id NOT NULL

-- Step 1: Add user_id column (nullable for now)
ALTER TABLE memories
ADD COLUMN user_id INT NULL AFTER id,
ADD INDEX idx_user_status (user_id, status);

-- Step 2: Create system user for existing memories
INSERT INTO users (username, display_name, role)
VALUES ('system', 'System User', 'master')
ON DUPLICATE KEY UPDATE id=id;

-- Step 3: Update all existing memories to belong to system user
UPDATE memories
SET user_id = (SELECT id FROM users WHERE username = 'system')
WHERE user_id IS NULL;

-- Step 4: Make user_id NOT NULL and add foreign key
ALTER TABLE memories
MODIFY COLUMN user_id INT NOT NULL,
ADD FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
