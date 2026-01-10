"""
API Authentication Module.

Provides API key generation and verification for FastAPI endpoints.
"""

import secrets
import logging
from typing import Optional, Dict
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import mysql.connector
from mysql.connector import pooling
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer()

# Database connection pool (initialized on first use)
_db_pool: Optional[pooling.MySQLConnectionPool] = None


def _get_db_pool() -> pooling.MySQLConnectionPool:
    """
    Get or create database connection pool.

    Returns:
        MySQLConnectionPool instance
    """
    global _db_pool

    if _db_pool is None:
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        memory_config = config.get('memory', {})

        # Create connection pool
        _db_pool = pooling.MySQLConnectionPool(
            pool_name="auth_pool",
            pool_size=5,
            host=memory_config.get('mysql_host', 'tools'),
            database=memory_config.get('mysql_database', 'jarvis'),
            user=memory_config.get('mysql_user', 'steve'),
            password=memory_config.get('mysql_password', '')
        )

        logger.info("Database connection pool initialized for authentication")

    return _db_pool


def generate_api_key() -> str:
    """
    Generate a secure random API key.

    Returns:
        64-character URL-safe API key
    """
    return secrets.token_urlsafe(48)  # 48 bytes = 64 chars in base64


def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict:
    """
    Verify API key and return user information.

    This is used as a FastAPI dependency to protect endpoints.

    Args:
        credentials: HTTP Bearer credentials from request header

    Returns:
        Dict with user information (id, username, display_name, role, etc.)

    Raises:
        HTTPException: 401 if API key is invalid or expired
    """
    api_key = credentials.credentials

    try:
        # Get database connection from pool
        pool = _get_db_pool()
        connection = pool.get_connection()
        cursor = connection.cursor(dictionary=True)

        # Query for user with this API key
        cursor.execute("""
            SELECT
                u.id,
                u.username,
                u.display_name,
                u.role,
                u.is_active,
                ak.id as key_id,
                ak.expires_at
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.id
            WHERE ak.api_key = %s
              AND ak.is_active = TRUE
              AND u.is_active = TRUE
              AND (ak.expires_at IS NULL OR ak.expires_at > NOW())
        """, (api_key,))

        user = cursor.fetchone()

        if not user:
            cursor.close()
            connection.close()
            logger.warning(f"Authentication failed: Invalid or expired API key")
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired API key"
            )

        # Update last_used_at timestamp
        cursor.execute("""
            UPDATE api_keys
            SET last_used_at = NOW()
            WHERE id = %s
        """, (user['key_id'],))
        connection.commit()

        # Update user's last_active_at
        cursor.execute("""
            UPDATE users
            SET last_active_at = NOW()
            WHERE id = %s
        """, (user['id'],))
        connection.commit()

        cursor.close()
        connection.close()

        logger.info(f"User {user['username']} (ID: {user['id']}) authenticated successfully")

        return {
            'id': user['id'],
            'username': user['username'],
            'display_name': user['display_name'],
            'role': user['role']
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error during authentication: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error during authentication"
        )


async def get_current_user(user: Dict = Security(verify_api_key)) -> Dict:
    """
    FastAPI dependency for protected endpoints.

    Usage:
        @app.get("/api/v1/protected")
        async def protected_endpoint(current_user: Dict = Depends(get_current_user)):
            user_id = current_user['id']
            username = current_user['username']
            ...

    Args:
        user: User dict from verify_api_key

    Returns:
        User information dict
    """
    return user


def create_user(username: str, display_name: Optional[str] = None, role: str = 'api_user') -> tuple[int, str]:
    """
    Create a new user with an API key.

    Args:
        username: Unique username
        display_name: Optional display name
        role: User role ('master' or 'api_user')

    Returns:
        Tuple of (user_id, api_key)

    Raises:
        ValueError: If username already exists
        Exception: If database error occurs
    """
    try:
        pool = _get_db_pool()
        connection = pool.get_connection()
        cursor = connection.cursor()

        # Insert user
        cursor.execute("""
            INSERT INTO users (username, display_name, role)
            VALUES (%s, %s, %s)
        """, (username, display_name, role))
        user_id = cursor.lastrowid

        # Generate API key
        api_key = generate_api_key()

        # Insert API key
        cursor.execute("""
            INSERT INTO api_keys (user_id, api_key, name)
            VALUES (%s, %s, %s)
        """, (user_id, api_key, f"{username} default key"))

        connection.commit()
        cursor.close()
        connection.close()

        logger.info(f"Created user {username} (ID: {user_id}) with role {role}")

        return user_id, api_key

    except mysql.connector.IntegrityError as e:
        if "Duplicate entry" in str(e):
            raise ValueError(f"Username '{username}' already exists")
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise


def revoke_user_keys(username: str) -> int:
    """
    Revoke all API keys for a user.

    Args:
        username: Username to revoke keys for

    Returns:
        Number of keys revoked

    Raises:
        ValueError: If user not found
    """
    try:
        pool = _get_db_pool()
        connection = pool.get_connection()
        cursor = connection.cursor()

        # Get user_id
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            connection.close()
            raise ValueError(f"User '{username}' not found")

        user_id = result[0]

        # Revoke all active keys
        cursor.execute("""
            UPDATE api_keys
            SET is_active = FALSE
            WHERE user_id = %s AND is_active = TRUE
        """, (user_id,))

        revoked_count = cursor.rowcount
        connection.commit()
        cursor.close()
        connection.close()

        logger.info(f"Revoked {revoked_count} API keys for user {username}")

        return revoked_count

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error revoking keys: {e}", exc_info=True)
        raise


def regenerate_key(username: str) -> str:
    """
    Revoke old keys and generate a new API key for a user.

    Args:
        username: Username to regenerate key for

    Returns:
        New API key

    Raises:
        ValueError: If user not found
    """
    try:
        pool = _get_db_pool()
        connection = pool.get_connection()
        cursor = connection.cursor()

        # Get user_id
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            connection.close()
            raise ValueError(f"User '{username}' not found")

        user_id = result[0]

        # Revoke old keys
        cursor.execute("""
            UPDATE api_keys
            SET is_active = FALSE
            WHERE user_id = %s AND is_active = TRUE
        """, (user_id,))

        # Generate new key
        api_key = generate_api_key()

        cursor.execute("""
            INSERT INTO api_keys (user_id, api_key, name)
            VALUES (%s, %s, %s)
        """, (user_id, api_key, f"{username} regenerated key"))

        connection.commit()
        cursor.close()
        connection.close()

        logger.info(f"Regenerated API key for user {username}")

        return api_key

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error regenerating key: {e}", exc_info=True)
        raise
