#!/usr/bin/env python3
"""
Initialize Procedural Memory Database

Creates the procedural_memory table in MySQL.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import mysql.connector
from mysql.connector import Error


def load_config():
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Create procedural_memory table."""
    print("=" * 70)
    print("Procedural Memory Database Initialization")
    print("=" * 70)
    print()

    # Load config
    config = load_config()
    memory_config = config.get('memory', {})

    # Connect to MySQL
    try:
        connection = mysql.connector.connect(
            host=memory_config['mysql_host'],
            database=memory_config['mysql_database'],
            user=memory_config['mysql_user'],
            password=memory_config['mysql_password']
        )

        print(f"✓ Connected to MySQL at {memory_config['mysql_host']}")
        print(f"  Database: {memory_config['mysql_database']}")
        print()

        cursor = connection.cursor()

        # Read SQL file
        sql_file = Path(__file__).parent / 'init_procedural_memory.sql'
        with open(sql_file, 'r') as f:
            sql = f.read()

        # Execute SQL
        print("Creating procedural_memory table...")
        cursor.execute(sql)
        connection.commit()

        print("✓ Table created successfully")
        print()

        # Verify table exists
        cursor.execute("SHOW TABLES LIKE 'procedural_memory'")
        result = cursor.fetchone()

        if result:
            # Show table structure
            cursor.execute("DESCRIBE procedural_memory")
            columns = cursor.fetchall()

            print("Table structure:")
            for col in columns:
                print(f"  - {col[0]:20} {col[1]:30} {col[2]:5}")

            print()
            print("=" * 70)
            print("✓ Procedural memory system initialized successfully!")
            print("=" * 70)
        else:
            print("✗ Table creation failed")
            return 1

        cursor.close()
        connection.close()

        return 0

    except Error as e:
        print(f"✗ MySQL Error: {e}")
        return 1
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
