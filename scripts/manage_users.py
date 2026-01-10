#!/usr/bin/env python3
"""
User Management CLI for Jarvis API.

Commands:
  create <username> [display_name] [--role master|api_user]
                                      - Create user and API key
  list                                - List all users
  revoke <username>                   - Revoke user's API keys
  regenerate <username>               - Generate new API key for user
  delete <username>                   - Deactivate a user account

Examples:
  ./manage_users.py create alice "Alice Smith"
  ./manage_users.py create bob "Bob Jones" --role master
  ./manage_users.py list
  ./manage_users.py revoke alice
  ./manage_users.py regenerate alice
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.auth import create_user, revoke_user_keys, regenerate_key, _get_db_pool
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def cmd_create(args):
    """Create a new user with API key."""
    username = args.username
    display_name = args.display_name
    role = args.role

    try:
        user_id, api_key = create_user(username, display_name, role)

        print("\n" + "="*70)
        print("USER CREATED SUCCESSFULLY")
        print("="*70)
        print(f"User ID:      {user_id}")
        print(f"Username:     {username}")
        print(f"Display Name: {display_name or '(none)'}")
        print(f"Role:         {role}")
        print(f"API Key:      {api_key}")
        print("="*70)
        print("\nIMPORTANT: Save this API key - it will not be shown again!")
        print(f"\nExample usage:")
        print(f'  curl -H "Authorization: Bearer {api_key}" http://localhost:8000/api/v1/me')
        print()

        return 0

    except ValueError as e:
        logger.error(f"Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        return 1


def cmd_list(args):
    """List all users."""
    try:
        pool = _get_db_pool()
        connection = pool.get_connection()
        cursor = connection.cursor(dictionary=True)

        # Get all users with their API key counts
        cursor.execute("""
            SELECT
                u.id,
                u.username,
                u.display_name,
                u.role,
                u.is_active,
                u.created_at,
                u.last_active_at,
                COUNT(ak.id) as key_count,
                SUM(CASE WHEN ak.is_active = TRUE THEN 1 ELSE 0 END) as active_key_count
            FROM users u
            LEFT JOIN api_keys ak ON u.id = ak.user_id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """)

        users = cursor.fetchall()
        cursor.close()
        connection.close()

        if not users:
            print("\nNo users found.")
            return 0

        print("\n" + "="*100)
        print(f"{'ID':<5} {'Username':<20} {'Display Name':<25} {'Role':<10} {'Active':<8} {'Keys':<8} {'Last Active'}")
        print("="*100)

        for user in users:
            user_id = user['id']
            username = user['username']
            display_name = user['display_name'] or '(none)'
            role = user['role']
            is_active = 'Yes' if user['is_active'] else 'No'
            key_info = f"{user['active_key_count']}/{user['key_count']}"
            last_active = user['last_active_at'].strftime('%Y-%m-%d %H:%M') if user['last_active_at'] else 'Never'

            print(f"{user_id:<5} {username:<20} {display_name:<25} {role:<10} {is_active:<8} {key_info:<8} {last_active}")

        print("="*100)
        print(f"\nTotal users: {len(users)}\n")

        return 0

    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        return 1


def cmd_revoke(args):
    """Revoke all API keys for a user."""
    username = args.username

    try:
        revoked_count = revoke_user_keys(username)

        print(f"\nRevoked {revoked_count} API key(s) for user '{username}'")
        print("User will not be able to authenticate until a new key is generated.\n")

        return 0

    except ValueError as e:
        logger.error(f"Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Failed to revoke keys: {e}")
        return 1


def cmd_regenerate(args):
    """Regenerate API key for a user."""
    username = args.username

    try:
        new_key = regenerate_key(username)

        print("\n" + "="*70)
        print("NEW API KEY GENERATED")
        print("="*70)
        print(f"Username: {username}")
        print(f"New Key:  {new_key}")
        print("="*70)
        print("\nAll previous keys for this user have been revoked.")
        print("IMPORTANT: Save this API key - it will not be shown again!\n")

        return 0

    except ValueError as e:
        logger.error(f"Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Failed to regenerate key: {e}")
        return 1


def cmd_delete(args):
    """Deactivate a user account."""
    username = args.username

    try:
        pool = _get_db_pool()
        connection = pool.get_connection()
        cursor = connection.cursor()

        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            connection.close()
            logger.error(f"User '{username}' not found")
            return 1

        user_id = result[0]

        # Deactivate user
        cursor.execute("""
            UPDATE users
            SET is_active = FALSE
            WHERE id = %s
        """, (user_id,))

        # Revoke all API keys
        cursor.execute("""
            UPDATE api_keys
            SET is_active = FALSE
            WHERE user_id = %s
        """, (user_id,))

        connection.commit()
        cursor.close()
        connection.close()

        print(f"\nUser '{username}' has been deactivated.")
        print("Their API keys have been revoked and they can no longer access the system.\n")

        return 0

    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Jarvis User Management CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new user')
    create_parser.add_argument('username', help='Username (unique)')
    create_parser.add_argument('display_name', nargs='?', help='Display name (optional)')
    create_parser.add_argument('--role', choices=['master', 'api_user'], default='api_user',
                               help='User role (default: api_user)')
    create_parser.set_defaults(func=cmd_create)

    # List command
    list_parser = subparsers.add_parser('list', help='List all users')
    list_parser.set_defaults(func=cmd_list)

    # Revoke command
    revoke_parser = subparsers.add_parser('revoke', help='Revoke user API keys')
    revoke_parser.add_argument('username', help='Username')
    revoke_parser.set_defaults(func=cmd_revoke)

    # Regenerate command
    regen_parser = subparsers.add_parser('regenerate', help='Regenerate API key')
    regen_parser.add_argument('username', help='Username')
    regen_parser.set_defaults(func=cmd_regenerate)

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Deactivate user account')
    delete_parser.add_argument('username', help='Username')
    delete_parser.set_defaults(func=cmd_delete)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
