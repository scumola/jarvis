"""
MySQL metadata store for memory metadata and relationships.

Handles all structured data storage for the memory system including
memory metadata, relationships, and audit logs.
"""

import mysql.connector
from mysql.connector import pooling, Error
from typing import List, Dict, Any, Optional, Tuple
import logging
import json
from datetime import datetime

from .schemas import (
    Memory, MemoryType, MemoryStatus, MemoryCreatedBy,
    MemoryRelationship, RelationshipType,
    MemoryAuditLog, AuditOperation
)

logger = logging.getLogger(__name__)


class MetadataStore:
    """
    MySQL wrapper for memory metadata operations.

    Uses connection pooling for better performance and handles all
    CRUD operations for memories, relationships, and audit logs.
    """

    def __init__(self, host: str, database: str, user: str, password: str, pool_size: int = 5):
        """
        Initialize MySQL connection pool.

        Args:
            host: MySQL host
            database: Database name
            user: MySQL user
            password: MySQL password
            pool_size: Number of connections in pool
        """
        try:
            self.connection_pool = pooling.MySQLConnectionPool(
                pool_name="memory_pool",
                pool_size=pool_size,
                host=host,
                database=database,
                user=user,
                password=password,
                port=3306,
                autocommit=False
            )
            logger.info(f"MySQL connection pool initialized (host={host}, db={database})")

        except Error as e:
            logger.error(f"Error creating MySQL connection pool: {e}")
            raise

    def _get_connection(self):
        """Get a connection from the pool."""
        return self.connection_pool.get_connection()

    def insert_memory(self, memory: Memory, user_id: int) -> int:
        """
        Insert a new memory into the database.

        Args:
            memory: Memory object to insert
            user_id: ID of the user who owns this memory

        Returns:
            ID of inserted memory

        Raises:
            Exception if insert fails
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            INSERT INTO memories (
                user_id, memory_text, memory_type, embedding_id,
                confidence, importance, decay_score,
                source_type, source_identity,
                source_query, source_context, created_by,
                verification_status, corroboration_count,
                status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            # Import source trust enums
            from memory.schemas import MemorySourceType, VerificationStatus

            values = (
                user_id,  # NEW: user_id for multi-user support
                memory.memory_text,
                memory.memory_type.value if isinstance(memory.memory_type, MemoryType) else memory.memory_type,
                memory.embedding_id,
                memory.confidence,
                memory.importance,
                memory.decay_score,
                # Source Trust fields
                memory.source_type.value if isinstance(memory.source_type, MemorySourceType) else memory.source_type,
                memory.source_identity,
                memory.source_query,
                memory.source_context,
                memory.created_by.value if isinstance(memory.created_by, MemoryCreatedBy) else memory.created_by,
                # Verification fields
                memory.verification_status.value if isinstance(memory.verification_status, VerificationStatus) else memory.verification_status,
                memory.corroboration_count,
                memory.status.value if isinstance(memory.status, MemoryStatus) else memory.status
            )

            cursor.execute(query, values)
            connection.commit()

            memory_id = cursor.lastrowid
            logger.debug(f"Inserted memory {memory_id} for user {user_id}")

            return memory_id

        except Error as e:
            connection.rollback()
            logger.error(f"Error inserting memory: {e}")
            raise

        finally:
            cursor.close()
            connection.close()

    def get_memory(self, memory_id: int) -> Optional[Memory]:
        """
        Retrieve a memory by ID.

        Args:
            memory_id: ID of memory to retrieve

        Returns:
            Memory object or None if not found
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            query = """
            SELECT * FROM memories WHERE id = %s
            """

            cursor.execute(query, (memory_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_memory(row)
            return None

        except Error as e:
            logger.error(f"Error retrieving memory {memory_id}: {e}")
            return None

        finally:
            cursor.close()
            connection.close()

    def get_memories_by_ids(self, memory_ids: List[str], user_id: int) -> List[Memory]:
        """
        Retrieve multiple memories by their embedding IDs.

        Args:
            memory_ids: List of embedding IDs (UUIDs from ChromaDB)
            user_id: User ID to verify ownership (security)

        Returns:
            List of Memory objects belonging to the user
        """
        if not memory_ids:
            return []

        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            placeholders = ','.join(['%s'] * len(memory_ids))
            query = f"""
            SELECT * FROM memories
            WHERE user_id = %s
            AND embedding_id IN ({placeholders})
            AND status = 'active'
            """

            params = [user_id] + list(memory_ids)
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            memories = [self._row_to_memory(row) for row in rows]
            return memories

        except Error as e:
            logger.error(f"Error retrieving memories by IDs: {e}")
            return []

        finally:
            cursor.close()
            connection.close()

    def filter_memories(
        self,
        user_id: int,
        memory_ids: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
        min_decay_score: Optional[float] = None,
        memory_types: Optional[List[MemoryType]] = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        limit: Optional[int] = None
    ) -> List[Memory]:
        """
        Filter memories based on metadata criteria.

        Args:
            user_id: User ID to filter memories for (required for multi-user support)
            memory_ids: Optional list of embedding IDs to filter
            min_confidence: Minimum confidence threshold
            min_decay_score: Minimum decay score threshold
            memory_types: List of memory types to include
            status: Memory status (default: active)
            limit: Maximum number of results

        Returns:
            List of Memory objects matching criteria
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            query = "SELECT * FROM memories WHERE user_id = %s"
            params = [user_id]  # NEW: Filter by user_id for isolation

            if memory_ids:
                placeholders = ','.join(['%s'] * len(memory_ids))
                query += f" AND embedding_id IN ({placeholders})"
                params.extend(memory_ids)

            if min_confidence is not None:
                query += " AND confidence >= %s"
                params.append(min_confidence)

            if min_decay_score is not None:
                query += " AND decay_score >= %s"
                params.append(min_decay_score)

            if memory_types:
                type_values = [t.value if isinstance(t, MemoryType) else t for t in memory_types]
                placeholders = ','.join(['%s'] * len(type_values))
                query += f" AND memory_type IN ({placeholders})"
                params.extend(type_values)

            query += " AND status = %s"
            params.append(status.value if isinstance(status, MemoryStatus) else status)

            query += " ORDER BY decay_score DESC, confidence DESC"

            if limit:
                query += " LIMIT %s"
                params.append(limit)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            memories = [self._row_to_memory(row) for row in rows]
            logger.debug(f"Filtered {len(memories)} memories")

            return memories

        except Error as e:
            logger.error(f"Error filtering memories: {e}")
            return []

        finally:
            cursor.close()
            connection.close()

    def update_access(self, memory_id: int) -> None:
        """
        Update last_accessed_at and increment access_count.

        Args:
            memory_id: ID of memory to update
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            UPDATE memories
            SET last_accessed_at = NOW(),
                access_count = access_count + 1
            WHERE id = %s
            """

            cursor.execute(query, (memory_id,))
            connection.commit()

            logger.debug(f"Updated access for memory {memory_id}")

        except Error as e:
            connection.rollback()
            logger.error(f"Error updating access for memory {memory_id}: {e}")

        finally:
            cursor.close()
            connection.close()

    def update_decay_scores(self, updates: List[Tuple[int, float]]) -> None:
        """
        Batch update decay scores for multiple memories.

        Args:
            updates: List of (memory_id, new_decay_score) tuples
        """
        if not updates:
            return

        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            UPDATE memories
            SET decay_score = %s
            WHERE id = %s
            """

            # Reverse tuple order for query (score, id)
            values = [(score, mem_id) for mem_id, score in updates]

            cursor.executemany(query, values)
            connection.commit()

            logger.info(f"Updated decay scores for {len(updates)} memories")

        except Error as e:
            connection.rollback()
            logger.error(f"Error batch updating decay scores: {e}")
            raise

        finally:
            cursor.close()
            connection.close()

    def update_decay_score(self, memory_id: int, new_score: float) -> None:
        """
        Update decay score for a single memory.

        Args:
            memory_id: ID of memory to update
            new_score: New decay score (0.0 - 100.0)
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            UPDATE memories
            SET decay_score = %s
            WHERE id = %s
            """

            cursor.execute(query, (new_score, memory_id))
            connection.commit()

            logger.debug(f"Updated decay score for memory {memory_id} to {new_score:.2f}")

        except Error as e:
            connection.rollback()
            logger.error(f"Error updating decay score for memory {memory_id}: {e}")
            raise

        finally:
            cursor.close()
            connection.close()

    def update_confidence(self, memory_id: int, new_confidence: float) -> None:
        """
        Update confidence for a single memory.

        Args:
            memory_id: ID of memory to update
            new_confidence: New confidence (0.0 - 1.0)
        """
        if not 0.0 <= new_confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {new_confidence}")

        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            UPDATE memories
            SET confidence = %s
            WHERE id = %s
            """

            cursor.execute(query, (new_confidence, memory_id))
            connection.commit()

            logger.debug(f"Updated confidence for memory {memory_id} to {new_confidence:.2f}")

        except Error as e:
            connection.rollback()
            logger.error(f"Error updating confidence for memory {memory_id}: {e}")
            raise

        finally:
            cursor.close()
            connection.close()

    def archive_memory(
        self,
        memory_id: int,
        superseded_by: Optional[int] = None
    ) -> None:
        """
        Mark a memory as archived or superseded.

        Args:
            memory_id: ID of memory to archive
            superseded_by: Optional ID of memory that supersedes this one
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            status = MemoryStatus.SUPERSEDED if superseded_by else MemoryStatus.ARCHIVED

            query = """
            UPDATE memories
            SET status = %s, superseded_by = %s
            WHERE id = %s
            """

            cursor.execute(query, (status.value, superseded_by, memory_id))
            connection.commit()

            logger.info(f"Archived memory {memory_id} (status={status.value})")

        except Error as e:
            connection.rollback()
            logger.error(f"Error archiving memory {memory_id}: {e}")
            raise

        finally:
            cursor.close()
            connection.close()

    def update_verification_status(
        self,
        memory_id: int,
        verification_status: str,
        increment_corroboration: bool = False
    ) -> None:
        """
        Update the verification status of a memory.

        Args:
            memory_id: ID of memory to update
            verification_status: New verification status (unverified, corroborated, contradicted, deprecated)
            increment_corroboration: If True, increment the corroboration_count
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            if increment_corroboration:
                query = """
                UPDATE memories
                SET verification_status = %s,
                    corroboration_count = corroboration_count + 1,
                    last_verified_at = NOW()
                WHERE id = %s
                """
            else:
                query = """
                UPDATE memories
                SET verification_status = %s,
                    last_verified_at = NOW()
                WHERE id = %s
                """

            cursor.execute(query, (verification_status, memory_id))
            connection.commit()

            logger.info(f"Updated verification status for memory {memory_id} to {verification_status}")

        except Error as e:
            connection.rollback()
            logger.error(f"Error updating verification status for memory {memory_id}: {e}")
            raise

        finally:
            cursor.close()
            connection.close()

    def create_relationship(
        self,
        memory_id: int,
        related_memory_id: int,
        relationship_type: RelationshipType
    ) -> int:
        """
        Create a relationship between two memories.

        Args:
            memory_id: Primary memory ID
            related_memory_id: Related memory ID
            relationship_type: Type of relationship

        Returns:
            Relationship ID
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            INSERT INTO memory_relationships (memory_id, related_memory_id, relationship_type)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE created_at = NOW()
            """

            cursor.execute(query, (
                memory_id,
                related_memory_id,
                relationship_type.value if isinstance(relationship_type, RelationshipType) else relationship_type
            ))
            connection.commit()

            relationship_id = cursor.lastrowid
            logger.debug(f"Created relationship {relationship_id}")

            return relationship_id

        except Error as e:
            connection.rollback()
            logger.error(f"Error creating relationship: {e}")
            raise

        finally:
            cursor.close()
            connection.close()

    def log_operation(
        self,
        operation: AuditOperation,
        memory_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a memory operation to the audit log.

        Args:
            operation: Type of operation performed
            memory_id: Optional memory ID affected
            details: Optional operation details
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            query = """
            INSERT INTO memory_audit_log (memory_id, operation, details)
            VALUES (%s, %s, %s)
            """

            details_json = json.dumps(details) if details else None

            cursor.execute(query, (
                memory_id,
                operation.value if isinstance(operation, AuditOperation) else operation,
                details_json
            ))
            connection.commit()

            logger.debug(f"Logged {operation.value} operation")

        except Error as e:
            connection.rollback()
            logger.error(f"Error logging operation: {e}")

        finally:
            cursor.close()
            connection.close()

    def _row_to_memory(self, row: Dict[str, Any]) -> Memory:
        """
        Convert database row to Memory object.

        Args:
            row: Dictionary from cursor.fetchone(dictionary=True)

        Returns:
            Memory object
        """
        from memory.schemas import MemorySourceType, VerificationStatus

        return Memory(
            id=row['id'],
            user_id=row.get('user_id'),  # NEW: user_id for multi-user support
            memory_text=row['memory_text'],
            memory_type=MemoryType(row['memory_type']),
            embedding_id=row['embedding_id'],
            confidence=float(row['confidence']),
            importance=float(row['importance']),
            decay_score=float(row['decay_score']),
            # Source Trust fields
            source_type=MemorySourceType(row.get('source_type', 'unknown')),
            source_identity=row.get('source_identity'),
            source_query=row.get('source_query'),
            source_context=row.get('source_context'),
            created_by=MemoryCreatedBy(row['created_by']),
            # Verification fields
            verification_status=VerificationStatus(row.get('verification_status', 'unverified')),
            corroboration_count=row.get('corroboration_count', 0),
            last_verified_at=row.get('last_verified_at'),
            # Temporal metadata
            created_at=row.get('created_at'),
            last_accessed_at=row.get('last_accessed_at'),
            access_count=row.get('access_count', 0),
            status=MemoryStatus(row['status']),
            superseded_by=row.get('superseded_by')
        )

    def get_memory_by_embedding_id(self, embedding_id: str) -> Optional[Memory]:
        """
        Get a memory by its embedding ID.

        Args:
            embedding_id: Embedding ID to search for

        Returns:
            Memory object or None if not found
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            query = """
            SELECT * FROM memories
            WHERE embedding_id = %s
            LIMIT 1
            """

            cursor.execute(query, (embedding_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_memory(row)
            return None

        except Error as e:
            logger.error(f"Error getting memory by embedding_id: {e}")
            return None

        finally:
            cursor.close()
            connection.close()

    def get_all_relationships(self) -> List[Any]:
        """
        Get all memory relationships.

        Returns:
            List of relationship objects (simple dicts)
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            query = """
            SELECT * FROM memory_relationships
            ORDER BY created_at DESC
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            # Convert to simple objects
            from collections import namedtuple
            Relationship = namedtuple('Relationship', [
                'id', 'memory_id', 'related_memory_id',
                'relationship_type', 'created_at'
            ])

            relationships = []
            for row in rows:
                relationships.append(Relationship(
                    id=row['id'],
                    memory_id=row['memory_id'],
                    related_memory_id=row['related_memory_id'],
                    relationship_type=RelationshipType(row['relationship_type']),
                    created_at=row.get('created_at')
                ))

            logger.debug(f"Retrieved {len(relationships)} relationships")
            return relationships

        except Error as e:
            logger.error(f"Error getting all relationships: {e}")
            return []

        finally:
            cursor.close()
            connection.close()

    def get_all_audit_logs(self, limit: Optional[int] = 1000) -> List[Any]:
        """
        Get all audit log entries.

        Args:
            limit: Maximum number of entries to return (default: 1000)

        Returns:
            List of audit log objects
        """
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            if limit:
                query = """
                SELECT * FROM memory_audit_log
                ORDER BY performed_at DESC
                LIMIT %s
                """
                cursor.execute(query, (limit,))
            else:
                query = """
                SELECT * FROM memory_audit_log
                ORDER BY performed_at DESC
                """
                cursor.execute(query)

            rows = cursor.fetchall()

            # Convert to simple objects
            from collections import namedtuple
            AuditLog = namedtuple('AuditLog', [
                'id', 'memory_id', 'operation', 'details', 'performed_at'
            ])

            logs = []
            for row in rows:
                # Parse JSON details if present
                details = None
                if row.get('details'):
                    try:
                        details = json.loads(row['details'])
                    except:
                        details = row['details']

                logs.append(AuditLog(
                    id=row['id'],
                    memory_id=row.get('memory_id'),
                    operation=AuditOperation(row['operation']),
                    details=details,
                    performed_at=row.get('performed_at')
                ))

            logger.debug(f"Retrieved {len(logs)} audit log entries")
            return logs

        except Error as e:
            logger.error(f"Error getting all audit logs: {e}")
            return []

        finally:
            cursor.close()
            connection.close()
