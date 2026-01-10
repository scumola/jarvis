"""
Memory decay calculation logic.

Implements decay scoring system where memories naturally lose vitality
over time based on their type, access patterns, and age.
"""

from datetime import datetime, timedelta
from typing import Dict
import logging

from .schemas import Memory, MemoryType

logger = logging.getLogger(__name__)


# Decay rates by memory type (points per day)
TYPE_DECAY_RATES: Dict[str, float] = {
    MemoryType.IDENTITY.value: 0.5,       # Very slow decay (stable facts)
    MemoryType.PREFERENCE.value: 1.0,     # Slow decay (preferences change slowly)
    MemoryType.CAPABILITY.value: 1.5,     # Medium decay (capabilities evolve)
    MemoryType.PROJECT.value: 2.0,        # Medium-fast decay (projects change)
    MemoryType.EPISODIC.value: 3.0,       # Fast decay (recent events matter most)
    MemoryType.SOCIAL.value: 1.0,         # Slow decay (communication style stable)
}

# Constants for decay calculation
ACCESS_BONUS_PER_ACCESS = 2.0   # Bonus points per access
MAX_ACCESS_BONUS = 20.0         # Cap on access bonus
RECENCY_BONUS = 10.0            # Bonus for recent access (< 7 days)
RECENCY_THRESHOLD_DAYS = 7      # Days to be considered "recent"
MIN_DECAY_SCORE = 0.0           # Minimum decay score
MAX_DECAY_SCORE = 100.0         # Maximum decay score (starting point)


def calculate_decay_score(
    memory: Memory,
    current_time: datetime
) -> float:
    """
    Calculate the current decay score for a memory.

    Decay Formula:
    1. Start with base score (100.0)
    2. Subtract age penalty: days_old * TYPE_DECAY_RATES[type]
    3. Add access bonus: min(access_count * 2, 20)
    4. Add recency bonus: +10 if accessed in last 7 days
    5. Apply confidence/importance modifiers
    6. Clamp to [0, 100]

    Args:
        memory: Memory object with metadata
        current_time: Current datetime for age calculation

    Returns:
        New decay score (0.0 - 100.0)
    """
    # Base score
    score = MAX_DECAY_SCORE

    # 1. Age penalty - how many days since creation
    if memory.created_at:
        days_old = (current_time - memory.created_at).days
    else:
        days_old = 0

    memory_type = memory.memory_type.value if isinstance(memory.memory_type, MemoryType) else memory.memory_type
    decay_rate = TYPE_DECAY_RATES.get(memory_type, 1.0)

    age_penalty = days_old * decay_rate
    score -= age_penalty

    # 2. Access bonus - reward frequently accessed memories
    access_bonus = min(memory.access_count * ACCESS_BONUS_PER_ACCESS, MAX_ACCESS_BONUS)
    score += access_bonus

    # 3. Recency bonus - reward recently accessed memories
    if memory.last_accessed_at:
        days_since_access = (current_time - memory.last_accessed_at).days
        if days_since_access < RECENCY_THRESHOLD_DAYS:
            score += RECENCY_BONUS

    # 4. Importance modifier - slow decay for important memories
    if memory.importance > 0.8:
        score *= 1.2  # 20% boost for high importance

    # 5. Confidence modifier - slow decay for confident memories
    if memory.confidence > 0.8:
        score *= 1.1  # 10% boost for high confidence

    # Clamp to valid range
    score = max(MIN_DECAY_SCORE, min(MAX_DECAY_SCORE, score))

    return round(score, 2)


def should_archive(memory: Memory, threshold: float = 5.0) -> bool:
    """
    Determine if a memory should be archived based on decay score.

    Args:
        memory: Memory to check
        threshold: Decay score threshold for archival (default: 5.0)

    Returns:
        True if memory should be archived
    """
    return memory.decay_score < threshold


def calculate_batch_decay(
    memories: list[Memory],
    current_time: datetime
) -> list[tuple[int, float, float]]:
    """
    Calculate decay scores for multiple memories in batch.

    Useful for scheduled decay updates.

    Args:
        memories: List of Memory objects
        current_time: Current datetime

    Returns:
        List of (memory_id, old_score, new_score) tuples
    """
    updates = []

    for memory in memories:
        old_score = memory.decay_score
        new_score = calculate_decay_score(memory, current_time)

        # Only include if score changed
        if abs(new_score - old_score) > 0.01:
            updates.append((memory.id, old_score, new_score))

    logger.info(f"Calculated decay for {len(memories)} memories, {len(updates)} updates needed")

    return updates


def boost_decay_on_access(current_decay: float, boost_amount: float = 0.5) -> float:
    """
    Boost decay score when a memory is accessed.

    This counteracts natural decay by rewarding usage.

    Args:
        current_decay: Current decay score
        boost_amount: Amount to boost (default: 0.5)

    Returns:
        New decay score (capped at MAX_DECAY_SCORE)
    """
    new_score = current_decay + boost_amount
    return min(new_score, MAX_DECAY_SCORE)


def estimate_days_until_archive(
    memory: Memory,
    current_time: datetime,
    archive_threshold: float = 5.0
) -> int:
    """
    Estimate how many days until a memory will be archived.

    Assumes no further access and linear decay.

    Args:
        memory: Memory to estimate
        current_time: Current datetime
        archive_threshold: Decay threshold for archival

    Returns:
        Estimated days until archive (or -1 if already below threshold)
    """
    current_score = calculate_decay_score(memory, current_time)

    if current_score <= archive_threshold:
        return -1  # Already below threshold

    memory_type = memory.memory_type.value if isinstance(memory.memory_type, MemoryType) else memory.memory_type
    decay_rate = TYPE_DECAY_RATES.get(memory_type, 1.0)

    if decay_rate == 0:
        return 999999  # Effectively never

    # Linear estimation: (current_score - threshold) / decay_rate
    days_remaining = (current_score - archive_threshold) / decay_rate

    return int(days_remaining)


def get_decay_stats(memories: list[Memory]) -> Dict[str, any]:
    """
    Calculate statistics about memory decay scores.

    Useful for monitoring and dashboard display.

    Args:
        memories: List of Memory objects

    Returns:
        Dict with decay statistics
    """
    if not memories:
        return {
            'total': 0,
            'avg_decay_score': 0.0,
            'min_decay_score': 0.0,
            'max_decay_score': 0.0,
            'below_threshold': 0,
            'by_type': {}
        }

    decay_scores = [m.decay_score for m in memories]

    stats = {
        'total': len(memories),
        'avg_decay_score': round(sum(decay_scores) / len(decay_scores), 2),
        'min_decay_score': min(decay_scores),
        'max_decay_score': max(decay_scores),
        'below_threshold': sum(1 for s in decay_scores if s < 5.0),
        'by_type': {}
    }

    # Stats by type
    by_type = {}
    for memory in memories:
        mem_type = memory.memory_type.value if isinstance(memory.memory_type, MemoryType) else memory.memory_type
        if mem_type not in by_type:
            by_type[mem_type] = []
        by_type[mem_type].append(memory.decay_score)

    for mem_type, scores in by_type.items():
        stats['by_type'][mem_type] = {
            'count': len(scores),
            'avg': round(sum(scores) / len(scores), 2),
            'min': min(scores),
            'max': max(scores)
        }

    return stats
