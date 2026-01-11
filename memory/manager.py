"""
Memory Manager - Main interface for all memory operations.

Coordinates between ChromaDB (vector store) and MySQL (metadata store)
to provide semantic search with metadata filtering.
"""

from typing import List, Optional, Dict, Any, Tuple
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
from .budget_controller import BudgetController
from .relevance_scorer import RelevanceScorer

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

        # Context budgeting components (NEW)
        budgeting_config = config.get('context_budgeting', {})
        if budgeting_config.get('enabled', False):
            self.budget_controller = BudgetController(config)
            self.relevance_scorer = RelevanceScorer(config)
            logger.info("Context budgeting enabled")
        else:
            self.budget_controller = None
            self.relevance_scorer = None
            logger.info("Context budgeting disabled")

        logger.info("Memory Manager initialized successfully")

    def retrieve_memories(
        self,
        user_id: int,
        query: str,
        k: int = 10,
        token_budget: Optional[int] = None,
        memory_types: Optional[List[MemoryType]] = None,
        min_confidence: Optional[float] = None,
        min_decay_score: Optional[float] = None
    ) -> List[Memory]:
        """
        Retrieve relevant memories for a query using RAG with context budgeting.

        Process:
        0. [NEW] Calculate dynamic k based on token budget (if enabled)
        1. Embed query and search vector store (semantic similarity)
        2. Get top-k candidates from ChromaDB (filtered by user_id)
        3. Enrich with MySQL metadata
        4. Filter by confidence, decay_score, type
        4.5. [NEW] Score with task-aware relevance (if enabled)
        4.7. [NEW] Apply type quotas and budget filtering (if enabled)
        5. Update access counts
        6. Return sorted by relevance

        Args:
            user_id: User ID to retrieve memories for (required for multi-user isolation)
            query: Query text to search for
            k: Number of results to retrieve (default from config)
            token_budget: [NEW] Optional token budget for memories (enables dynamic k)
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

            # Step 0: Budget-aware k calculation (NEW)
            original_k = k
            if token_budget and self.budget_controller:
                dynamic_k = self.budget_controller.calculate_dynamic_k(token_budget)
                k = min(k, dynamic_k)
                logger.info(f"Budget-aware k: {k} (original: {original_k}, budget: {token_budget} tokens)")

            # Apply hard cap from config
            budgeting_config = self.config.get('context_budgeting', {})
            hard_cap = budgeting_config.get('hard_cap_memories', 10)
            k = min(k, hard_cap)

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
                    # Normalize to strings for comparison to handle both enum and string inputs
                    mem_type_str = memory.memory_type.value if hasattr(memory.memory_type, 'value') else str(memory.memory_type)
                    types_str = [t.value if hasattr(t, 'value') else str(t) for t in memory_types]
                    if mem_type_str not in types_str:
                        continue

                # Filter by status (only active)
                if memory.status != MemoryStatus.ACTIVE:
                    continue

                filtered_memories.append(memory)

            # Step 4: Sort by relevance with task-aware scoring (ENHANCED)
            # Find original distance scores
            distance_map = {r['id']: r['distance'] for r in vector_results}

            # Use RelevanceScorer if available, otherwise fallback to legacy scoring
            if self.relevance_scorer:
                scored_memories = self.relevance_scorer.score_memories(
                    filtered_memories,
                    query,
                    distance_map
                )
            else:
                # Legacy scoring (backward compatibility)
                scored_memories = []
                for memory in filtered_memories:
                    distance = distance_map.get(memory.embedding_id, 1.0)

                    # Calculate verification trust multiplier
                    from memory.schemas import VerificationStatus
                    verification_boost = 1.0  # Default: no boost
                    if memory.verification_status == VerificationStatus.CORROBORATED:
                        verification_boost = 1.0 + (memory.corroboration_count * 0.05)
                    elif memory.verification_status == VerificationStatus.CONTRADICTED:
                        verification_boost = 0.3
                    elif memory.verification_status == VerificationStatus.DEPRECATED:
                        verification_boost = 0.7

                    # Calculate base relevance score
                    base_relevance = (
                        (1.0 - distance) * 0.35 +  # Semantic similarity (35%)
                        memory.confidence * 0.30 +  # Confidence (30%)
                        memory.importance * 0.20 +  # Importance (20%)
                        (memory.decay_score / 100.0) * 0.10 +  # Vitality (10%)
                        (min(memory.corroboration_count, 5) / 5.0) * 0.05  # Corroboration (5%)
                    )

                    relevance = base_relevance * verification_boost
                    scored_memories.append((memory, relevance))

            # Sort by relevance (descending)
            scored_memories.sort(key=lambda x: x[1], reverse=True)

            # Step 4.5: Apply type quotas (NEW)
            type_quotas = budgeting_config.get('type_quotas', {})
            if type_quotas:
                top_memories_with_quotas = self._apply_type_quotas(
                    [m for m, score in scored_memories],
                    type_quotas
                )
            else:
                top_memories_with_quotas = [m for m, score in scored_memories[:k]]

            # Step 4.7: Budget filtering (NEW)
            if token_budget and self.budget_controller:
                top_memories, tokens_used = self.budget_controller.filter_by_budget(
                    top_memories_with_quotas[:k],
                    token_budget
                )
                logger.info(f"Budget filtering: {len(top_memories)} memories, {tokens_used} tokens used")
            else:
                top_memories = top_memories_with_quotas[:k]

            # Step 4.8: Check for consolidation opportunities (NEW)
            if budgeting_config.get('consolidation_enabled', False):
                duplicate_pairs = self._check_consolidation_needed(top_memories)
                if duplicate_pairs:
                    logger.info(
                        f"Found {len(duplicate_pairs)} potential duplicate pairs for consolidation"
                    )
                    # Note: Actual consolidation would happen asynchronously
                    # For now, just log for manual review

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
                        'types': [t.value if hasattr(t, 'value') else str(t) for t in memory_types] if memory_types else None
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
                # Same type - normalize to strings for comparison
                mem_type_str = memory.memory_type.value if hasattr(memory.memory_type, 'value') else str(memory.memory_type)
                arg_type_str = memory_type.value if hasattr(memory_type, 'value') else str(memory_type)
                if mem_type_str != arg_type_str:
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

    def _apply_type_quotas(
        self,
        memories: List[Memory],
        quotas: Dict[str, int]
    ) -> List[Memory]:
        """
        Apply per-type quotas to memory list.

        Ensures no single memory type dominates the results by limiting
        each type to a configured maximum.

        Args:
            memories: List of Memory objects (sorted by relevance)
            quotas: Dict mapping memory type to max count
                   Example: {"identity": 2, "capability": 3}

        Returns:
            Filtered list of memories respecting type quotas
        """
        type_counts = {}
        filtered = []

        for memory in memories:
            mem_type = memory.memory_type.value if hasattr(memory.memory_type, 'value') else str(memory.memory_type)
            current_count = type_counts.get(mem_type, 0)
            quota = quotas.get(mem_type, 999)  # No limit if not specified

            if current_count < quota:
                filtered.append(memory)
                type_counts[mem_type] = current_count + 1

        logger.debug(f"Type quota filtering: {len(memories)} → {len(filtered)}, counts: {type_counts}")
        return filtered

    def _check_consolidation_needed(self, memories: List[Memory]) -> List[Tuple[int, int]]:
        """
        Detect potential duplicates in retrieved memories.

        Uses text similarity to find memories that might be duplicates.
        This is lightweight detection - actual consolidation happens separately.

        Args:
            memories: List of Memory objects to check

        Returns:
            List of (memory1_id, memory2_id) pairs that might be duplicates
        """
        duplicates = []
        consolidation_threshold = self.config.get('context_budgeting', {}).get(
            'consolidation_similarity_threshold',
            0.85
        )

        for i, mem1 in enumerate(memories):
            for j, mem2 in enumerate(memories[i+1:], start=i+1):
                # Only check same type - normalize to strings for comparison
                mem1_type_str = mem1.memory_type.value if hasattr(mem1.memory_type, 'value') else str(mem1.memory_type)
                mem2_type_str = mem2.memory_type.value if hasattr(mem2.memory_type, 'value') else str(mem2.memory_type)
                if mem1_type_str == mem2_type_str:
                    similarity = self._text_similarity(mem1.memory_text, mem2.memory_text)
                    if similarity > consolidation_threshold:
                        duplicates.append((mem1.id, mem2.id))
                        logger.debug(
                            f"Potential duplicate: {mem1.id} & {mem2.id} "
                            f"(similarity: {similarity:.2f})"
                        )

        return duplicates

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using Jaccard index on words.

        Simple implementation for duplicate detection.
        For production: Could use embedding distance instead.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0.0-1.0)
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def consolidate_duplicates(
        self,
        mem1_id: int,
        mem2_id: int,
        strategy: str = "keep_highest_confidence"
    ) -> Optional[int]:
        """
        Consolidate two duplicate memories.

        Strategies:
        - keep_highest_confidence: Keep memory with higher confidence
        - keep_most_recent: Keep more recently created memory

        The kept memory receives a confidence boost from learning from both.
        The discarded memory is marked as SUPERSEDED.

        Args:
            mem1_id: ID of first memory
            mem2_id: ID of second memory
            strategy: Consolidation strategy to use

        Returns:
            ID of kept memory, or None if consolidation failed
        """
        mem1 = self.metadata_store.get_memory_by_id(mem1_id)
        mem2 = self.metadata_store.get_memory_by_id(mem2_id)

        if not mem1 or not mem2:
            logger.error(f"Cannot consolidate: memory {mem1_id} or {mem2_id} not found")
            return None

        # Determine which to keep based on strategy
        if strategy == "keep_highest_confidence":
            if mem1.confidence >= mem2.confidence:
                keep, discard = mem1, mem2
            else:
                keep, discard = mem2, mem1
        elif strategy == "keep_most_recent":
            if mem1.created_at >= mem2.created_at:
                keep, discard = mem1, mem2
            else:
                keep, discard = mem2, mem1
        else:
            logger.error(f"Unknown consolidation strategy: {strategy}")
            return None

        # Mark discarded memory as superseded
        self.metadata_store.update_memory(
            discard.id,
            status=MemoryStatus.SUPERSEDED,
            superseded_by=keep.id
        )

        # Boost confidence of kept memory (learned from both)
        new_confidence = min(keep.confidence + 0.05, 1.0)
        self.metadata_store.update_memory(
            keep.id,
            confidence=new_confidence,
            corroboration_count=keep.corroboration_count + 1
        )

        logger.info(
            f"Consolidated memories {discard.id} → {keep.id} "
            f"(strategy: {strategy}, new confidence: {new_confidence:.2f})"
        )

        return keep.id
