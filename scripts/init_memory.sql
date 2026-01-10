-- Episodic/Semantic Memory Tables for Jarvis
-- Stores long-term memories with RAG (Retrieval-Augmented Generation)

-- Core memories table
CREATE TABLE IF NOT EXISTS memories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    memory_text TEXT NOT NULL,
    memory_type ENUM('identity', 'preference', 'capability', 'project', 'episodic', 'social') NOT NULL,
    embedding_id VARCHAR(64) NOT NULL UNIQUE,
    confidence DECIMAL(3,2) NOT NULL DEFAULT 0.80,
    importance DECIMAL(3,2) NOT NULL DEFAULT 0.50,
    decay_score DECIMAL(5,2) NOT NULL DEFAULT 100.0,
    source_query TEXT,
    source_context TEXT,
    created_by ENUM('curator_llm', 'manual', 'system') DEFAULT 'curator_llm',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP NULL,
    access_count INT DEFAULT 0,
    status ENUM('active', 'archived', 'superseded') DEFAULT 'active',
    superseded_by INT NULL,

    INDEX idx_type (memory_type),
    INDEX idx_status (status),
    INDEX idx_decay (decay_score),
    INDEX idx_embedding (embedding_id),
    INDEX idx_created_at (created_at),
    INDEX idx_accessed (last_accessed_at),

    FOREIGN KEY (superseded_by) REFERENCES memories(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Memory relationships (supersedes/contradicts/supports)
CREATE TABLE IF NOT EXISTS memory_relationships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    memory_id INT NOT NULL,
    related_memory_id INT NOT NULL,
    relationship_type ENUM('supersedes', 'contradicts', 'supports', 'related') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_memory (memory_id),
    INDEX idx_related (related_memory_id),
    INDEX idx_type (relationship_type),

    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (related_memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    UNIQUE KEY unique_relationship (memory_id, related_memory_id, relationship_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Audit log for memory operations
CREATE TABLE IF NOT EXISTS memory_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    memory_id INT,
    operation ENUM('create', 'retrieve', 'update', 'archive', 'decay') NOT NULL,
    details JSON,
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_memory (memory_id),
    INDEX idx_operation (operation),
    INDEX idx_performed_at (performed_at),

    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
