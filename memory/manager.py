"""
Memory Manager - Main interface for all memory operations.

Coordinates between ChromaDB (vector store) and MySQL (metadata store)
to provide semantic search with metadata filtering.
"""

from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from .vector_store import VectorStore
from .metadata_store import MetadataStore
from .decay import (
    calculate_decay_score,
    calculate_batch_decay,
    boost_decay_on_access,
    should_archive
)
from .schemas import (
    Memory, MemoryProposal, MemoryType, MemoryStatus,
    MemoryCreatedBy, AuditOperation, RelationshipType
)

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Main memory system interface.

    Provides high-level methods for storing and retrieving memories,
    coordinating between vector similarity search (ChromaDB) and
    structured metadata filtering (MySQL).
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Memory Manager with vector and metadata stores.

        Args:
            config: Memory configuration dict from config.yaml
        """
        self.config = config

        # Initialize vector store (ChromaDB)
        vector_db_path = config.get('vector_db_path', 'data/vector_store')
        self.vector_store = VectorStore(vector_db_path)

        # Initialize metadata store (MySQL)
        self.metadata_store = MetadataStore(
            host=config.get('mysql_host', 'tools'),
            database=config.get('mysql_database', 'jarvis'),
            user=config.get('mysql_user', 'steve'),
            password=config.get('mysql_password', ''),
            pool_size=5
        )

        # Retrieval settings
        self.default_k = config.get('default_k', 10)
        self.min_confidence = config.get('min_confidence', 0.5)
        self.min_decay_score = config.get('min_decay_score', 20.0)

        logger.info("Memory Manager initialized successfully")

    def retrieve_memories(
        self,
        user_id: int,
        query: str,
        k: int = 10,
        memory_types: Optional[List[MemoryType]] = None,
        min_confidence: Optional[float] = None,
        min_decay_score: Optional[float] = None
    ) -> List[Memory]:
        """
        Retrieve relevant memories for a query using RAG.

        Process:
        1. Embed query and search vector store (semantic similarity)
        2. Get top-k candidates from ChromaDB (filtered by user_id)
        3. Enrich with MySQL metadata
        4. Filter by confidence, decay_score, type
        5. Update access counts
        6. Return sorted by relevance

        Args:
            user_id: User ID to retrieve memories for (required for multi-user isolation)
            query: Query text to search for
            k: Number of results to retrieve (default from config)
            memory_types: Optional filter by memory types
            min_confidence: Minimum confidence threshold
            min_decay_score: Minimum decay score threshold

        Returns:
            List of Memory objects, sorted by relevance
        """
        try:
            # Use config defaults if not specified
            if min_confidence is None:
                min_confidence = self.min_confidence
            if min_decay_score is None:
                min_decay_score = self.min_decay_score

            logger.info(f"Retrieving memories for user {user_id}, query: '{query[:50]}...'")

            # Step 1: Semantic search in vector store (filtered by user_id)
            # Fetch more candidates than needed for filtering
            vector_results = self.vector_store.search(
                query=query,
                k=k * 2,  # Fetch 2x to account for filtering
                where={"user_id": str(user_id)}  # NEW: Filter by user_id for isolation
            )

            if not vector_results:
                logger.info("No semantic matches found")
                return []

            # Extract embedding IDs
            embedding_ids = [r['id'] for r in vector_results]

            # Step 2: Get full memory objects from metadata store
            memories = self.metadata_store.get_memories_by_ids(embedding_ids, user_id)

            if not memories:
                logger.info("No memories found in metadata store")
                return []

            # Step 3: Apply metadata filters
            filtered_memories = []
            for memory in memories:
                # Filter by confidence
                if memory.confidence < min_confidence:
                    continue

                # Filter by decay score
                if memory.decay_score < min_decay_score:
                    continue

                # Filter by type (if specified)
                if memory_types:
                    if memory.memory_type not in memory_types:
                        continue

                # Filter by status (only active)
                if memory.status != MemoryStatus.ACTIVE:
                    continue

                filtered_memories.append(memory)

            # Step 4: Sort by relevance (combine semantic distance + metadata)
            # Find original distance scores
            distance_map = {r['id']: r['distance'] for r in vector_results}

            scored_memories = []
            for memory in filtered_memories:
                distance = distance_map.get(memory.embedding_id, 1.0)

                # Calculate verification trust multiplier
                from memory.schemas import VerificationStatus
                verification_boost = 1.0  # Default: no boost
                if memory.verification_status == VerificationStatus.CORROBORATED:
                    # Corroborated facts get a significant boost
                    verification_boost = 1.0 + (memory.corroboration_count * 0.05)  # +5% per corroboration
                elif memory.verification_status == VerificationStatus.CONTRADICTED:
                    # Contradicted facts are heavily penalized
                    verification_boost = 0.3  # 70% penalty
                elif memory.verification_status == VerificationStatus.DEPRECATED:
                    # Deprecated facts are slightly penalized
                    verification_boost = 0.7  # 30% penalty

                # Calculate base relevance score (lower distance = higher relevance)
                # Combine semantic similarity with metadata quality
                base_relevance = (
                    (1.0 - distance) * 0.35 +  # Semantic similarity (35%)
                    memory.confidence * 0.30 +  # Confidence (30%)
                    memory.importance * 0.20 +  # Importance (20%)
                    (memory.decay_score / 100.0) * 0.10 +  # Vitality (10%)
                    (min(memory.corroboration_count, 5) / 5.0) * 0.05  # Corroboration (5%, capped at 5)
                )

                # Apply verification trust multiplier
                relevance = base_relevance * verification_boost

                scored_memories.append((memory, relevance))

            # Sort by relevance (descending)
            scored_memories.sort(key=lambda x: x[1], reverse=True)

            # Limit to k results
            top_memories = [m for m, score in scored_memories[:k]]

            # Step 5: Update access counts and boost decay
            for memory in top_memories:
                self.metadata_store.update_access(memory.id)
                # Note: Decay boost will be applied in next decay update cycle

            # Step 6: Log retrieval
            self.metadata_store.log_operation(
                operation=AuditOperation.RETRIEVE,
                details={
                    'query': query[:100],
                    'retrieved_count': len(top_memories),
                    'filters': {
                        'min_confidence': min_confidence,
                        'min_decay': min_decay_score,
                        'types': [t.value for t in memory_types] if memory_types else None
                    }
                }
            )

            logger.info(f"Retrieved {len(top_memories)} relevant memories")
            return top_memories

        except Exception as e:
            logger.error(f"Error retrieving memories: {e}")
            return []

    def store_memory(self, proposal: MemoryProposal, user_id: int) -> int:
        """
        Store a new memory from a curator proposal.

        Process:
        1. Check for duplicates/contradictions
        2. Generate embedding ID
        3. Store in vector store (ChromaDB)
        4. Store metadata in MySQL
        5. Handle any contradictions (archive old memories)
        6. Log to audit trail

        Args:
            proposal: MemoryProposal from curator LLM
            user_id: ID of the user who owns this memory

        Returns:
            ID of stored memory

        Raises:
            Exception if storage fails
        """
        try:
            logger.info(f"Storing memory for user {user_id}: {proposal.memory_text[:50]}...")

            # Step 1: Check for duplicates and contradictions
            contradictions = self.check_contradictions(
                user_id=user_id,
                memory_text=proposal.memory_text,
                memory_type=proposal.memory_type
            )

            # Step 2: Generate unique embedding ID
            embedding_id = VectorStore.generate_embedding_id()

            # Step 3: Create Memory object
            from memory.schemas import MemorySourceType, VerificationStatus

            # Determine source_type: use proposal if provided, else infer from memory_type
            if proposal.source_type:
                source_type = proposal.source_type
            else:
                # Infer source type based on memory category
                if proposal.memory_type in [MemoryType.IDENTITY, MemoryType.PREFERENCE]:
                    # User directly stated their name, preferences, etc.
                    source_type = MemorySourceType.USER
                else:
                    # System inferred this from conversation context
                    source_type = MemorySourceType.INFERENCE

            memory = Memory(
                user_id=user_id,  # NEW: Set user_id for multi-user support
                memory_text=proposal.memory_text,
                memory_type=proposal.memory_type,
                embedding_id=embedding_id,
                confidence=proposal.confidence,
                importance=proposal.importance,
                decay_score=100.0,  # Start at max
                # Source Trust fields
                source_type=source_type,
                source_identity=proposal.source_identity or 'curator_llm',
                source_query=None,  # Will be set by orchestrator
                source_context=None,  # Will be set by orchestrator
                created_by=MemoryCreatedBy.CURATOR_LLM,
                # Verification (starts unverified)
                verification_status=VerificationStatus.UNVERIFIED,
                corroboration_count=0,
                status=MemoryStatus.ACTIVE
            )

            # Step 4: Store in MySQL first (to get ID)
            memory_id = self.metadata_store.insert_memory(memory, user_id)
            memory.id = memory_id

            # Step 5: Store embedding in ChromaDB
            # Handle both enum and string values for memory_type
            mem_type = memory.memory_type.value if hasattr(memory.memory_type, 'value') else str(memory.memory_type)
            self.vector_store.add_memory(
                memory_id=embedding_id,
                text=memory.memory_text,
                metadata={
                    'user_id': str(user_id),  # NEW: Include user_id for isolation
                    'memory_id': str(memory_id),
                    'memory_type': mem_type,
                    'confidence': str(memory.confidence),
                    'importance': str(memory.importance)
                }
            )

            # Step 6: Handle contradictions
            if contradictions:
                logger.info(f"Found {len(contradictions)} potential contradictions")
                for old_memory in contradictions:
                    # Archive the old memory
                    self.metadata_store.archive_memory(
                        memory_id=old_memory.id,
                        superseded_by=memory_id
                    )

                    # Create relationship
                    self.metadata_store.create_relationship(
                        memory_id=memory_id,
                        related_memory_id=old_memory.id,
                        relationship_type=RelationshipType.SUPERSEDES
                    )

                    logger.info(f"Archived contradicting memory {old_memory.id}")

            # Step 7: Log creation
            self.metadata_store.log_operation(
                operation=AuditOperation.CREATE,
                memory_id=memory_id,
                details={
                    'memory_text': memory.memory_text[:100],
                    'memory_type': str(memory.memory_type),
                    'confidence': memory.confidence,
                    'importance': memory.importance,
                    'reasoning': proposal.reasoning
                }
            )

            logger.info(f"Memory {memory_id} stored successfully")
            return memory_id

        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            raise

    def check_contradictions(
        self,
        user_id: int,
        memory_text: str,
        memory_type: MemoryType
    ) -> List[Memory]:
        """
        Find memories that might contradict a new memory.

        Uses semantic similarity to find related memories of the same type.

        Args:
            user_id: User ID to check contradictions for (only within user's memories)
            memory_text: Text of new memory to check
            memory_type: Type of memory

        Returns:
            List of potentially contradicting Memory objects
        """
        try:
            # Search for semantically similar memories (scoped to user)
            similar = self.vector_store.search(
                query=memory_text,
                k=5,  # Check top 5 similar
                where={"user_id": str(user_id)}  # NEW: Filter by user_id
            )

            if not similar:
                return []

            # Get memory objects
            embedding_ids = [r['id'] for r in similar]
            memories = self.metadata_store.get_memories_by_ids(embedding_ids, user_id)

            # Filter for same type and high similarity (distance < 0.3)
            contradictions = []
            distance_map = {r['id']: r['distance'] for r in similar}

            for memory in memories:
                # Same type
                if memory.memory_type != memory_type:
                    continue

                # High similarity (potential duplicate/contradiction)
                distance = distance_map.get(memory.embedding_id, 1.0)
                if distance < 0.3:  # Very similar
                    contradictions.append(memory)

            logger.debug(f"Found {len(contradictions)} potential contradictions")
            return contradictions

        except Exception as e:
            logger.error(f"Error checking contradictions: {e}")
            return []

    def decay_memories(self) -> int:
        """
        Run decay calculation on all active memories.

        This should be called periodically (e.g., daily cron job) to update
        decay scores based on age and access patterns.

        Returns:
            Number of memories updated
        """
        try:
            logger.info("Running memory decay update...")

            # Get all active memories
            all_memories = self.metadata_store.filter_memories(
                status=MemoryStatus.ACTIVE,
                limit=None
            )

            if not all_memories:
                logger.info("No active memories to decay")
                return 0

            # Calculate new decay scores
            current_time = datetime.now()
            updates = calculate_batch_decay(all_memories, current_time)

            if not updates:
                logger.info("No decay updates needed")
                return 0

            # Prepare batch update
            score_updates = [(mem_id, new_score) for mem_id, old_score, new_score in updates]

            # Apply updates to database
            self.metadata_store.update_decay_scores(score_updates)

            # Check for memories to archive (decay < 5.0)
            archived_count = 0
            for mem_id, old_score, new_score in updates:
                if new_score < 5.0:
                    memory = next((m for m in all_memories if m.id == mem_id), None)
                    if memory and should_archive(memory):
                        self.metadata_store.archive_memory(mem_id)
                        archived_count += 1

            # Log decay operation
            self.metadata_store.log_operation(
                operation=AuditOperation.DECAY,
                details={
                    'updated_count': len(updates),
                    'archived_count': archived_count,
                    'timestamp': current_time.isoformat()
                }
            )

            logger.info(f"Decay complete: {len(updates)} updated, {archived_count} archived")
            return len(updates)

        except Exception as e:
            logger.error(f"Error during decay update: {e}")
            raise

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get memory system statistics.

        Returns:
            Dict with counts, averages, and breakdowns
        """
        try:
            all_memories = self.metadata_store.filter_memories(
                status=MemoryStatus.ACTIVE,
                limit=None
            )

            total_count = len(all_memories)

            if total_count == 0:
                return {
                    'total_memories': 0,
                    'by_type': {},
                    'avg_confidence': 0.0,
                    'avg_decay_score': 0.0
                }

            # Aggregate stats
            by_type = {}
            total_confidence = 0.0
            total_decay = 0.0

            for memory in all_memories:
                mem_type = str(memory.memory_type)
                if mem_type not in by_type:
                    by_type[mem_type] = 0
                by_type[mem_type] += 1

                total_confidence += memory.confidence
                total_decay += memory.decay_score

            stats = {
                'total_memories': total_count,
                'by_type': by_type,
                'avg_confidence': round(total_confidence / total_count, 2),
                'avg_decay_score': round(total_decay / total_count, 2),
                'vector_store_count': self.vector_store.count()
            }

            logger.debug(f"Memory stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {'error': str(e)}
