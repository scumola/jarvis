"""
Memory Consolidation System

Detects and merges duplicate, similar, and supporting memories to improve
memory quality and reduce redundancy.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from .schemas import Memory, MemoryType, MemoryStatus, RelationshipType

logger = logging.getLogger(__name__)


# Similarity thresholds for different relationship types
DUPLICATE_THRESHOLD = 0.1  # Almost identical (distance < 0.1)
SIMILAR_THRESHOLD = 0.3    # Similar enough to merge (distance < 0.3)
SUPPORTING_THRESHOLD = 0.5 # Related/supporting (distance < 0.5)


class MemoryConsolidator:
    """
    Analyzes memories to find duplicates, similar memories, and supporting
    evidence. Provides consolidation recommendations and merge capabilities.
    """

    def __init__(self, vector_store, metadata_store):
        """
        Initialize consolidator.

        Args:
            vector_store: VectorStore instance
            metadata_store: MetadataStore instance
        """
        self.vector_store = vector_store
        self.metadata_store = metadata_store

    def analyze_all_memories(self) -> Dict[str, Any]:
        """
        Analyze all active memories for consolidation opportunities.

        Returns:
            Dict with:
            - duplicates: List of duplicate memory groups
            - similar: List of similar memory groups
            - supporting: List of supporting memory pairs
            - statistics: Summary stats
        """
        try:
            logger.info("Starting full memory consolidation analysis...")

            # Get all active memories
            all_memories = self.metadata_store.filter_memories(
                status=MemoryStatus.ACTIVE,
                limit=None
            )

            if not all_memories:
                return {
                    'duplicates': [],
                    'similar': [],
                    'supporting': [],
                    'statistics': {'total_memories': 0}
                }

            logger.info(f"Analyzing {len(all_memories)} active memories")

            # Group by type for more efficient analysis
            by_type = {}
            for mem in all_memories:
                mem_type = str(mem.memory_type)
                if mem_type not in by_type:
                    by_type[mem_type] = []
                by_type[mem_type].append(mem)

            # Analyze each type
            all_duplicates = []
            all_similar = []
            all_supporting = []

            for mem_type, memories in by_type.items():
                if len(memories) < 2:
                    continue  # Need at least 2 to compare

                logger.info(f"Analyzing {len(memories)} {mem_type} memories")

                type_results = self._analyze_memory_group(memories)
                all_duplicates.extend(type_results['duplicates'])
                all_similar.extend(type_results['similar'])
                all_supporting.extend(type_results['supporting'])

            statistics = {
                'total_memories': len(all_memories),
                'duplicate_groups': len(all_duplicates),
                'similar_groups': len(all_similar),
                'supporting_pairs': len(all_supporting),
                'memories_by_type': {k: len(v) for k, v in by_type.items()}
            }

            logger.info(f"Analysis complete: {statistics}")

            return {
                'duplicates': all_duplicates,
                'similar': all_similar,
                'supporting': all_supporting,
                'statistics': statistics
            }

        except Exception as e:
            logger.error(f"Error in consolidation analysis: {e}")
            raise

    def _analyze_memory_group(self, memories: List[Memory]) -> Dict[str, List]:
        """
        Analyze a group of memories (same type) for relationships.

        Args:
            memories: List of Memory objects to analyze

        Returns:
            Dict with duplicates, similar, and supporting lists
        """
        duplicates = []
        similar = []
        supporting = []

        # Compare each memory with others
        for i, mem1 in enumerate(memories):
            for mem2 in memories[i+1:]:
                # Search for similarity
                result = self.vector_store.search(
                    query=mem1.memory_text,
                    k=50  # Get more results for comparison
                )

                # Find mem2 in results
                mem2_distance = None
                for r in result:
                    if r['id'] == mem2.embedding_id:
                        mem2_distance = r['distance']
                        break

                if mem2_distance is None:
                    continue  # Not in results

                # Categorize relationship
                if mem2_distance < DUPLICATE_THRESHOLD:
                    duplicates.append({
                        'memories': [mem1, mem2],
                        'distance': mem2_distance,
                        'relationship': 'duplicate'
                    })
                elif mem2_distance < SIMILAR_THRESHOLD:
                    similar.append({
                        'memories': [mem1, mem2],
                        'distance': mem2_distance,
                        'relationship': 'similar'
                    })
                elif mem2_distance < SUPPORTING_THRESHOLD:
                    supporting.append({
                        'memories': [mem1, mem2],
                        'distance': mem2_distance,
                        'relationship': 'supporting'
                    })

        return {
            'duplicates': duplicates,
            'similar': similar,
            'supporting': supporting
        }

    def merge_duplicates(
        self,
        memories: List[Memory],
        keep_highest_confidence: bool = True
    ) -> int:
        """
        Merge duplicate memories into a single memory.

        Strategy:
        - Keep memory with highest confidence (or first if equal)
        - Archive other memories as superseded
        - Boost confidence of kept memory
        - Update decay score (access boost from merging)

        Args:
            memories: List of duplicate Memory objects to merge
            keep_highest_confidence: If True, keep highest confidence memory

        Returns:
            ID of the kept memory
        """
        if len(memories) < 2:
            raise ValueError("Need at least 2 memories to merge")

        try:
            logger.info(f"Merging {len(memories)} duplicate memories")

            # Sort by confidence (highest first) or ID (oldest first)
            if keep_highest_confidence:
                memories_sorted = sorted(
                    memories,
                    key=lambda m: (m.confidence, m.created_at),
                    reverse=True
                )
            else:
                memories_sorted = sorted(memories, key=lambda m: m.id)

            # Keep first memory
            kept_memory = memories_sorted[0]
            to_archive = memories_sorted[1:]

            # Boost confidence of kept memory (cap at 1.0)
            confidence_boost = min(0.1 * len(to_archive), 0.3)
            new_confidence = min(kept_memory.confidence + confidence_boost, 1.0)

            # Boost decay score (merging = access)
            new_decay = min(kept_memory.decay_score + (5.0 * len(to_archive)), 100.0)

            # Update kept memory
            self.metadata_store.update_confidence(kept_memory.id, new_confidence)
            self.metadata_store.update_decay_score(kept_memory.id, new_decay)

            # Archive duplicates
            for mem in to_archive:
                self.metadata_store.archive_memory(
                    memory_id=mem.id,
                    superseded_by=kept_memory.id
                )

                # Create supersedes relationship
                self.metadata_store.create_relationship(
                    memory_id=kept_memory.id,
                    related_memory_id=mem.id,
                    relationship_type=RelationshipType.SUPERSEDES
                )

                logger.info(f"Archived duplicate memory {mem.id}")

            # Log consolidation (using UPDATE operation type)
            from .schemas import AuditOperation
            self.metadata_store.log_operation(
                operation=AuditOperation.UPDATE,
                memory_id=kept_memory.id,
                details={
                    'action': 'merge_duplicates',
                    'merged_count': len(to_archive),
                    'merged_ids': [m.id for m in to_archive],
                    'new_confidence': new_confidence,
                    'new_decay_score': new_decay
                }
            )

            logger.info(
                f"Merged {len(to_archive)} memories into {kept_memory.id}, "
                f"confidence: {kept_memory.confidence:.2f} → {new_confidence:.2f}"
            )

            return kept_memory.id

        except Exception as e:
            logger.error(f"Error merging memories: {e}")
            raise

    def boost_supporting_memories(
        self,
        memory1: Memory,
        memory2: Memory
    ) -> None:
        """
        Boost confidence of two supporting memories.

        When memories support each other (similar but not duplicates),
        increase their confidence slightly.

        Args:
            memory1: First memory
            memory2: Second memory
        """
        try:
            # Small confidence boost for mutual support
            boost = 0.05

            new_conf1 = min(memory1.confidence + boost, 1.0)
            new_conf2 = min(memory2.confidence + boost, 1.0)

            self.metadata_store.update_confidence(memory1.id, new_conf1)
            self.metadata_store.update_confidence(memory2.id, new_conf2)

            # Create supporting relationship
            self.metadata_store.create_relationship(
                memory_id=memory1.id,
                related_memory_id=memory2.id,
                relationship_type=RelationshipType.SUPPORTS
            )

            logger.info(
                f"Boosted supporting memories {memory1.id} and {memory2.id} "
                f"by {boost:.2f}"
            )

        except Exception as e:
            logger.error(f"Error boosting supporting memories: {e}")
            raise

    def generate_consolidation_report(
        self,
        analysis: Dict[str, Any]
    ) -> str:
        """
        Generate a human-readable consolidation report.

        Args:
            analysis: Output from analyze_all_memories()

        Returns:
            Formatted report string
        """
        stats = analysis['statistics']
        duplicates = analysis['duplicates']
        similar = analysis['similar']
        supporting = analysis['supporting']

        report = []
        report.append("=" * 70)
        report.append("MEMORY CONSOLIDATION REPORT")
        report.append("=" * 70)
        report.append("")

        # Statistics
        report.append("STATISTICS:")
        report.append(f"  Total active memories: {stats['total_memories']}")
        report.append(f"  Duplicate groups: {stats['duplicate_groups']}")
        report.append(f"  Similar groups: {stats['similar_groups']}")
        report.append(f"  Supporting pairs: {stats['supporting_pairs']}")
        report.append("")

        report.append("By type:")
        for mem_type, count in stats.get('memories_by_type', {}).items():
            report.append(f"  - {mem_type}: {count}")
        report.append("")

        # Duplicates (highest priority)
        if duplicates:
            report.append("DUPLICATES (should merge):")
            report.append(f"  Found {len(duplicates)} duplicate groups")
            for i, dup in enumerate(duplicates[:5], 1):  # Show top 5
                mems = dup['memories']
                dist = dup['distance']
                report.append(f"\n  {i}. Distance: {dist:.4f}")
                for mem in mems:
                    report.append(f"     [{mem.id}] {mem.memory_text[:60]}...")
                    report.append(f"             Confidence: {mem.confidence:.2f}, "
                                  f"Decay: {mem.decay_score:.1f}")
            if len(duplicates) > 5:
                report.append(f"\n  ... and {len(duplicates) - 5} more")
            report.append("")

        # Similar
        if similar:
            report.append("SIMILAR MEMORIES (consider merging):")
            report.append(f"  Found {len(similar)} similar groups")
            for i, sim in enumerate(similar[:3], 1):  # Show top 3
                mems = sim['memories']
                dist = sim['distance']
                report.append(f"\n  {i}. Distance: {dist:.4f}")
                for mem in mems:
                    report.append(f"     [{mem.id}] {mem.memory_text[:60]}...")
            if len(similar) > 3:
                report.append(f"\n  ... and {len(similar) - 3} more")
            report.append("")

        # Supporting
        if supporting:
            report.append("SUPPORTING MEMORIES (can boost confidence):")
            report.append(f"  Found {len(supporting)} supporting pairs")
            report.append("")

        # Recommendations
        report.append("RECOMMENDATIONS:")
        if duplicates:
            report.append(f"  1. Merge {len(duplicates)} duplicate groups")
        if similar:
            report.append(f"  2. Review {len(similar)} similar groups for merging")
        if supporting:
            report.append(f"  3. Boost confidence for {len(supporting)} supporting pairs")
        if not duplicates and not similar and not supporting:
            report.append("  No consolidation needed - memories are well-organized!")
        report.append("")

        report.append("=" * 70)

        return "\n".join(report)


def auto_consolidate(
    vector_store,
    metadata_store,
    merge_duplicates: bool = True,
    boost_supporting: bool = True
) -> Dict[str, Any]:
    """
    Automatically consolidate memories.

    Args:
        vector_store: VectorStore instance
        metadata_store: MetadataStore instance
        merge_duplicates: If True, automatically merge duplicates
        boost_supporting: If True, boost supporting memories

    Returns:
        Dict with consolidation results
    """
    consolidator = MemoryConsolidator(vector_store, metadata_store)

    # Analyze
    analysis = consolidator.analyze_all_memories()

    results = {
        'analysis': analysis,
        'merged_groups': 0,
        'boosted_pairs': 0,
        'errors': []
    }

    # Merge duplicates
    if merge_duplicates and analysis['duplicates']:
        logger.info(f"Auto-merging {len(analysis['duplicates'])} duplicate groups")
        for dup in analysis['duplicates']:
            try:
                consolidator.merge_duplicates(dup['memories'])
                results['merged_groups'] += 1
            except Exception as e:
                logger.error(f"Error merging group: {e}")
                results['errors'].append(str(e))

    # Boost supporting
    if boost_supporting and analysis['supporting']:
        logger.info(f"Boosting {len(analysis['supporting'])} supporting pairs")
        for sup in analysis['supporting']:
            try:
                mems = sup['memories']
                consolidator.boost_supporting_memories(mems[0], mems[1])
                results['boosted_pairs'] += 1
            except Exception as e:
                logger.error(f"Error boosting pair: {e}")
                results['errors'].append(str(e))

    logger.info(
        f"Auto-consolidation complete: merged {results['merged_groups']} groups, "
        f"boosted {results['boosted_pairs']} pairs"
    )

    return results
