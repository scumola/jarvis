#!/usr/bin/env python3
"""
Initialize API Database

Creates the users, api_keys, and conversation_sessions tables in MySQL.
Also adds user_id column to memories table.
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


def execute_sql_file(cursor, sql_file_path):
    """Execute SQL statements from a file."""
    with open(sql_file_path, 'r') as f:
        sql = f.read()

    # Split by semicolon and execute each statement
    statements = [s.strip() for s in sql.split(';') if s.strip()]

    for statement in statements:
        if statement and not statement.startswith('--'):
            try:
                cursor.execute(statement)
            except Error as e:
                # Check if error is just "table already exists"
                if 'already exists' in str(e).lower() or '1050' in str(e):
                    print(f"  ⚠ Table already exists, skipping...")
                else:
                    raise


def main():
    """Create API database tables."""
    print("=" * 70)
    print("API Database Initialization")
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

        # Execute init_api_users.sql
        print("Creating API users tables...")
        sql_file = Path(__file__).parent / 'init_api_users.sql'
        execute_sql_file(cursor, sql_file)
        connection.commit()
        print("✓ API users tables created")
        print()

        # Execute add_user_id_to_memories.sql
        print("Adding user_id to memories table...")
        sql_file = Path(__file__).parent / 'add_user_id_to_memories.sql'

        try:
            execute_sql_file(cursor, sql_file)
            connection.commit()
            print("✓ user_id column added to memories table")
        except Error as e:
            # Check if column already exists
            if 'Duplicate column' in str(e) or '1060' in str(e):
                print("  ⚠ user_id column already exists, skipping...")
            else:
                raise

        print()

        # Verify tables exist
        tables = ['users', 'api_keys', 'conversation_sessions']
        print("Verifying tables...")
        for table_name in tables:
            cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
            result = cursor.fetchone()

            if result:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  ✓ {table_name}: {count} rows")
            else:
                print(f"  ✗ {table_name}: NOT FOUND")
                return 1

        # Check memories table has user_id
        cursor.execute("DESCRIBE memories")
        columns = cursor.fetchall()
        has_user_id = any('user_id' in str(col) for col in columns)

        if has_user_id:
            print(f"  ✓ memories: user_id column added")
        else:
            print(f"  ✗ memories: user_id column MISSING")
            return 1

        print()
        print("=" * 70)
        print("✓ API database initialized successfully!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  1. Create API users: ./venv/bin/python scripts/manage_users.py create <username>")
        print("  2. Start API server: uvicorn api.server:app --port 8000")
        print("=" * 70)

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
