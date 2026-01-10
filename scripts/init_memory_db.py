#!/usr/bin/env python3
"""
Initialize memory database schema in MySQL.

Creates the necessary tables for the Jarvis memory system:
- memories: Core memory storage with embeddings
- memory_relationships: Relationships between memories (supersedes, contradicts, etc.)
- memory_audit_log: Audit trail for all memory operations
"""

import mysql.connector
from mysql.connector import Error
import yaml
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_config():
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def create_connection(config):
    """Create MySQL database connection."""
    memory_config = config.get('memory', {})

    try:
        connection = mysql.connector.connect(
            host=memory_config.get('mysql_host', 'tools'),
            database=memory_config.get('mysql_database', 'jarvis'),
            user=memory_config.get('mysql_user', 'steve'),
            password=memory_config.get('mysql_password', ''),
            port=3306
        )
        print(f"✓ Connected to MySQL at {memory_config.get('mysql_host')}:3306")
        return connection
    except Error as e:
        print(f"✗ Error connecting to MySQL: {e}")
        sys.exit(1)


def create_tables(connection):
    """Create all memory system tables."""
    cursor = connection.cursor()

    # Table 1: memories
    print("\nCreating 'memories' table...")
    memories_table = """
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
        FOREIGN KEY (superseded_by) REFERENCES memories(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """

    try:
        cursor.execute(memories_table)
        print("  ✓ Table 'memories' created successfully")
    except Error as e:
        print(f"  ✗ Error creating 'memories' table: {e}")
        return False

    # Table 2: memory_relationships
    print("\nCreating 'memory_relationships' table...")
    relationships_table = """
    CREATE TABLE IF NOT EXISTS memory_relationships (
        id INT AUTO_INCREMENT PRIMARY KEY,
        memory_id INT NOT NULL,
        related_memory_id INT NOT NULL,
        relationship_type ENUM('supersedes', 'contradicts', 'supports', 'related') NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
        FOREIGN KEY (related_memory_id) REFERENCES memories(id) ON DELETE CASCADE,
        UNIQUE KEY unique_relationship (memory_id, related_memory_id, relationship_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """

    try:
        cursor.execute(relationships_table)
        print("  ✓ Table 'memory_relationships' created successfully")
    except Error as e:
        print(f"  ✗ Error creating 'memory_relationships' table: {e}")
        return False

    # Table 3: memory_audit_log
    print("\nCreating 'memory_audit_log' table...")
    audit_table = """
    CREATE TABLE IF NOT EXISTS memory_audit_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        memory_id INT,
        operation ENUM('create', 'retrieve', 'update', 'archive', 'decay') NOT NULL,
        details JSON,
        performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_memory (memory_id),
        INDEX idx_operation (operation),
        INDEX idx_performed_at (performed_at),
        FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """

    try:
        cursor.execute(audit_table)
        print("  ✓ Table 'memory_audit_log' created successfully")
    except Error as e:
        print(f"  ✗ Error creating 'memory_audit_log' table: {e}")
        return False

    connection.commit()
    cursor.close()
    return True


def verify_tables(connection):
    """Verify that all tables were created successfully."""
    cursor = connection.cursor()

    print("\nVerifying tables...")
    tables = ['memories', 'memory_relationships', 'memory_audit_log']

    for table in tables:
        cursor.execute(f"SHOW TABLES LIKE '{table}'")
        result = cursor.fetchone()
        if result:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  ✓ Table '{table}' exists ({count} rows)")
        else:
            print(f"  ✗ Table '{table}' not found")

    cursor.close()


def main():
    """Main execution function."""
    print("="*70)
    print("Jarvis Memory Database Initialization")
    print("="*70)

    # Load configuration
    config = load_config()
    print(f"✓ Configuration loaded")

    # Connect to database
    connection = create_connection(config)

    # Create tables
    if create_tables(connection):
        print("\n" + "="*70)
        print("✓ All tables created successfully!")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("✗ Table creation failed")
        print("="*70)
        connection.close()
        sys.exit(1)

    # Verify tables
    verify_tables(connection)

    # Close connection
    connection.close()
    print("\n✓ Database initialization complete!")
    print("="*70)


if __name__ == "__main__":
    main()
