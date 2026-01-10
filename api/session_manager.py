"""
Session Manager - Per-user Orchestrator instance management.

Manages dedicated Orchestrator instances for each user, handles conversation
persistence, and provides automatic cleanup of inactive sessions.
"""

import threading
import logging
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import mysql.connector
from mysql.connector import pooling
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """
    Represents an active user session.

    Attributes:
        user_id: User ID
        username: Username
        user_role: User role ('master' or 'api_user')
        orchestrator: Dedicated Orchestrator instance
        session_id: Unique session identifier
        created_at: Session creation timestamp
        last_activity_at: Last activity timestamp
    """
    user_id: int
    username: str
    user_role: str
    orchestrator: Any  # Orchestrator type (avoiding circular import)
    session_id: str
    created_at: datetime
    last_activity_at: datetime

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity_at = datetime.now()


class SessionManager:
    """
    Manages per-user Orchestrator instances and conversation persistence.

    For few users with long conversations, we keep instances in memory.
    Inactive sessions are cleaned up after timeout and persisted to database.
    """

    def __init__(self, config: Dict[str, Any], db_config: Dict[str, Any]):
        """
        Initialize Session Manager.

        Args:
            config: Full application config from config.yaml
            db_config: Database configuration for persistence
        """
        self.config = config
        self.db_config = db_config
        self.sessions: Dict[int, UserSession] = {}  # user_id -> UserSession
        self.session_timeout = config.get('api', {}).get('session_timeout', 3600)  # 1 hour default
        self.lock = threading.Lock()

        # Create database connection pool for conversation persistence
        self.db_pool = pooling.MySQLConnectionPool(
            pool_name="session_pool",
            pool_size=5,
            host=db_config.get('mysql_host', 'tools'),
            database=db_config.get('mysql_database', 'jarvis'),
            user=db_config.get('mysql_user', 'steve'),
            password=db_config.get('mysql_password', '')
        )

        logger.info(f"Session Manager initialized (timeout: {self.session_timeout}s)")

    def get_or_create_session(self, user_id: int, username: str, user_role: str) -> UserSession:
        """
        Get existing session or create new one.

        Args:
            user_id: User ID
            username: Username
            user_role: User role ('master' or 'api_user')

        Returns:
            UserSession instance
        """
        with self.lock:
            # Check if session exists and is recent
            if user_id in self.sessions:
                session = self.sessions[user_id]
                if self._is_session_valid(session):
                    session.update_activity()
                    logger.debug(f"Reusing existing session for user {username}")
                    return session
                else:
                    # Session expired, clean up
                    logger.info(f"Session expired for user {username}, creating new session")
                    self._cleanup_session(user_id)

            # Create new session
            session = self._create_session(user_id, username, user_role)
            self.sessions[user_id] = session
            logger.info(f"Created new session {session.session_id} for user {username}")
            return session

    def _create_session(self, user_id: int, username: str, user_role: str) -> UserSession:
        """
        Create a new orchestrator instance for user.

        Args:
            user_id: User ID
            username: Username
            user_role: User role

        Returns:
            UserSession instance
        """
        # Import here to avoid circular dependency
        from orchestrator.engine import Orchestrator

        # Create dedicated Orchestrator instance
        orchestrator = Orchestrator(self.config)

        # SECURITY: Filter tools based on user role
        if user_role != 'master':
            from api.tool_filter import filter_tools_for_user

            # Get all registered tools
            all_tools = [
                {
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': tool.parameters
                }
                for tool in orchestrator.tool_registry.list_tools()
            ]

            # Filter to allowed tools
            allowed_tools = filter_tools_for_user(all_tools, user_role)
            allowed_names = {t['name'] for t in allowed_tools}

            # Store allowed tool names in orchestrator for runtime checks
            orchestrator.allowed_tools = allowed_names
            orchestrator.user_role = user_role

            logger.info(f"API user {username} has access to {len(allowed_names)} tools")
        else:
            orchestrator.allowed_tools = None  # No filtering for master
            orchestrator.user_role = 'master'
            logger.info(f"Master user {username} has access to all tools")

        # Load conversation history from database
        history = self._load_conversation_history(user_id)
        if history:
            orchestrator.persona_llm.conversation_history = history
            logger.info(f"Loaded {len(history)} messages from conversation history for user {username}")

        session_id = str(uuid.uuid4())

        return UserSession(
            user_id=user_id,
            username=username,
            user_role=user_role,
            orchestrator=orchestrator,
            session_id=session_id,
            created_at=datetime.now(),
            last_activity_at=datetime.now()
        )

    def save_session(self, user_id: int):
        """
        Persist conversation history to database.

        Args:
            user_id: User ID to save session for
        """
        if user_id in self.sessions:
            session = self.sessions[user_id]
            try:
                self._save_conversation_history(
                    user_id,
                    session.session_id,
                    session.orchestrator.persona_llm.conversation_history
                )
                logger.debug(f"Saved conversation history for user {session.username}")
            except Exception as e:
                logger.error(f"Error saving session for user {user_id}: {e}", exc_info=True)

    def _is_session_valid(self, session: UserSession) -> bool:
        """
        Check if session is still valid (not expired).

        Args:
            session: UserSession to check

        Returns:
            True if session is valid, False if expired
        """
        now = datetime.now()
        elapsed = (now - session.last_activity_at).total_seconds()
        return elapsed < self.session_timeout

    def _cleanup_session(self, user_id: int):
        """
        Clean up a session (save and remove from memory).

        Args:
            user_id: User ID to cleanup
        """
        if user_id in self.sessions:
            session = self.sessions[user_id]

            # Save conversation history before cleanup
            try:
                self._save_conversation_history(
                    user_id,
                    session.session_id,
                    session.orchestrator.persona_llm.conversation_history
                )
            except Exception as e:
                logger.error(f"Error saving conversation history during cleanup: {e}", exc_info=True)

            # Remove from memory
            del self.sessions[user_id]
            logger.info(f"Cleaned up session for user {session.username}")

    def cleanup_inactive_sessions(self):
        """
        Remove sessions that haven't been used recently.

        This should be called periodically (e.g., every 5 minutes).
        """
        with self.lock:
            now = datetime.now()
            inactive_users = []

            for user_id, session in self.sessions.items():
                elapsed = (now - session.last_activity_at).total_seconds()
                if elapsed > self.session_timeout:
                    inactive_users.append(user_id)

            for user_id in inactive_users:
                self._cleanup_session(user_id)

            if inactive_users:
                logger.info(f"Cleaned up {len(inactive_users)} inactive sessions")

    def _load_conversation_history(self, user_id: int) -> List[Dict]:
        """
        Load latest conversation history from database.

        Args:
            user_id: User ID to load history for

        Returns:
            List of conversation messages (empty if none found)
        """
        try:
            connection = self.db_pool.get_connection()
            cursor = connection.cursor(dictionary=True)

            # Get most recent active session for user
            cursor.execute("""
                SELECT conversation_history
                FROM conversation_sessions
                WHERE user_id = %s
                  AND is_active = TRUE
                ORDER BY last_activity_at DESC
                LIMIT 1
            """, (user_id,))

            result = cursor.fetchone()
            cursor.close()
            connection.close()

            if result and result['conversation_history']:
                # Parse JSON conversation history
                history = json.loads(result['conversation_history'])
                return history

            return []

        except Exception as e:
            logger.error(f"Error loading conversation history: {e}", exc_info=True)
            return []

    def _save_conversation_history(
        self,
        user_id: int,
        session_id: str,
        history: List[Dict]
    ):
        """
        Save conversation history to database.

        Args:
            user_id: User ID
            session_id: Session identifier
            history: List of conversation messages
        """
        try:
            connection = self.db_pool.get_connection()
            cursor = connection.cursor()

            # Serialize conversation history to JSON
            history_json = json.dumps(history)

            # Insert or update conversation session
            cursor.execute("""
                INSERT INTO conversation_sessions
                (user_id, session_id, conversation_history, last_activity_at)
                VALUES (%s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    conversation_history = VALUES(conversation_history),
                    last_activity_at = NOW(),
                    updated_at = NOW()
            """, (user_id, session_id, history_json))

            connection.commit()
            cursor.close()
            connection.close()

        except Exception as e:
            logger.error(f"Error saving conversation history: {e}", exc_info=True)
            raise

    def reset_session(self, user_id: int):
        """
        Reset conversation history for a user.

        Args:
            user_id: User ID to reset
        """
        if user_id in self.sessions:
            session = self.sessions[user_id]

            # Clear conversation history in orchestrator
            session.orchestrator.persona_llm.reset()

            # Save empty history to database
            self._save_conversation_history(user_id, session.session_id, [])

            logger.info(f"Reset conversation history for user {session.username}")

    def get_session_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get information about a user's session.

        Args:
            user_id: User ID

        Returns:
            Dict with session info or None if no active session
        """
        if user_id in self.sessions:
            session = self.sessions[user_id]
            return {
                'session_id': session.session_id,
                'username': session.username,
                'role': session.user_role,
                'message_count': len(session.orchestrator.persona_llm.conversation_history),
                'created_at': session.created_at.isoformat(),
                'last_activity': session.last_activity_at.isoformat()
            }
        return None
