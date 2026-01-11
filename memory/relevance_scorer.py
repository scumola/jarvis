"""
Task-Aware Relevance Scoring for Memory Retrieval

Provides enhanced relevance scoring that adapts to different query types:
- TOOL_USE: Tasks requiring tool execution
- RECALL: Explicitly asking about past events/facts
- PROJECT_WORK: Working on a specific project
- CONVERSATION: General chat

Adjusts scoring weights based on task type to prioritize the most relevant memories.
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum
import logging

from memory.schemas import Memory, VerificationStatus

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Classification of user query types."""
    TOOL_USE = "tool_use"           # Query requires tools (find, search, create, etc.)
    CONVERSATION = "conversation"    # General chat/discussion
    PROJECT_WORK = "project_work"   # Working on a specific project
    RECALL = "recall"               # Explicitly asking about past events/facts
    UNKNOWN = "unknown"             # Cannot determine type


class TaskClassifier:
    """
    Classifies user queries into task types for adaptive scoring.

    Uses keyword-based classification. Could be enhanced with LLM in future.
    """

    def __init__(self):
        """Initialize task classifier with keyword patterns."""
        # Keyword patterns for each task type
        self.tool_use_keywords = [
            'find', 'search', 'create', 'read', 'write', 'edit',
            'list', 'fetch', 'get', 'show me', 'display',
            'grep', 'diff', 'backup', 'restore'
        ]

        self.recall_keywords = [
            'remember', 'recall', 'what did', 'when did',
            'do you know', 'tell me about', 'what do you know',
            'have we', 'did i', 'did we', 'last time'
        ]

        self.project_keywords = [
            'project', 'working on', 'building', 'developing',
            'implementing', 'code', 'feature', 'bug', 'issue'
        ]

    def classify(self, query: str) -> TaskType:
        """
        Classify query into a task type.

        Args:
            query: User query string

        Returns:
            TaskType classification

        Priority order:
        1. RECALL (explicit memory requests)
        2. TOOL_USE (action-oriented)
        3. PROJECT_WORK (project context)
        4. CONVERSATION (default)
        """
        query_lower = query.lower()

        # Priority 1: Recall - explicit memory requests
        if any(kw in query_lower for kw in self.recall_keywords):
            return TaskType.RECALL

        # Priority 2: Tool use - action-oriented
        if any(kw in query_lower for kw in self.tool_use_keywords):
            return TaskType.TOOL_USE

        # Priority 3: Project work
        if any(kw in query_lower for kw in self.project_keywords):
            return TaskType.PROJECT_WORK

        # Default: General conversation
        return TaskType.CONVERSATION


class RelevanceScorer:
    """
    Enhanced relevance scoring with task-aware weight adjustments.

    Scores memories based on multiple factors with weights adapted to task type.
    """

    def __init__(self, config: Dict):
        """
        Initialize RelevanceScorer.

        Args:
            config: Configuration dict with context_budgeting section
        """
        budgeting_config = config.get('context_budgeting', {})

        self.task_classifier = TaskClassifier()

        # Enable/disable features
        self.task_aware_enabled = budgeting_config.get('task_aware_scoring', True)
        self.recency_boost_enabled = budgeting_config.get('recency_boost_enabled', True)

        # Task-specific weight configurations
        # Format: {factor_name: weight (0.0-1.0)}
        # All weights per task type should sum to ~1.0
        self.task_weights = {
            TaskType.TOOL_USE: {
                'semantic': 0.30,       # Slightly lower - tools need recent context
                'confidence': 0.25,
                'importance': 0.15,
                'decay': 0.10,
                'corroboration': 0.05,
                'recency': 0.15,        # Boost recency for tool context
            },
            TaskType.RECALL: {
                'semantic': 0.40,       # Higher - exact match matters
                'confidence': 0.20,
                'importance': 0.10,
                'decay': 0.05,
                'corroboration': 0.10,  # Trust matters for recall
                'recency': 0.15,        # Recent memories prioritized
            },
            TaskType.PROJECT_WORK: {
                'semantic': 0.35,
                'confidence': 0.25,
                'importance': 0.25,     # Importance matters for projects
                'decay': 0.10,
                'corroboration': 0.05,
                'recency': 0.00,        # Don't prioritize recency
            },
            TaskType.CONVERSATION: {
                'semantic': 0.35,       # Standard weighting
                'confidence': 0.30,
                'importance': 0.20,
                'decay': 0.10,
                'corroboration': 0.05,
                'recency': 0.00,        # No recency bias
            },
            TaskType.UNKNOWN: {
                'semantic': 0.35,       # Default to conversation weights
                'confidence': 0.30,
                'importance': 0.20,
                'decay': 0.10,
                'corroboration': 0.05,
                'recency': 0.00,
            }
        }

        logger.info(
            f"RelevanceScorer initialized: "
            f"task_aware={self.task_aware_enabled}, "
            f"recency_boost={self.recency_boost_enabled}"
        )

    def score_memories(
        self,
        memories: List[Memory],
        query: str,
        distance_map: Dict[str, float]
    ) -> List[Tuple[Memory, float]]:
        """
        Score memories with task-aware weighting.

        Args:
            memories: List of Memory objects to score
            query: User query string
            distance_map: Map of embedding_id -> semantic distance (0.0-1.0)

        Returns:
            List of (memory, relevance_score) tuples
        """
        # Classify task type
        task_type = TaskType.CONVERSATION
        if self.task_aware_enabled:
            task_type = self.task_classifier.classify(query)
            logger.debug(f"Query classified as: {task_type.value}")

        # Get weights for this task type
        weights = self.task_weights[task_type]

        scored = []
        for memory in memories:
            # Calculate individual score components
            distance = distance_map.get(memory.embedding_id, 1.0)
            semantic_score = 1.0 - distance  # Convert distance to similarity

            confidence_score = memory.confidence
            importance_score = memory.importance
            decay_score = memory.decay_score / 100.0  # Normalize to 0-1
            corroboration_score = min(memory.corroboration_count, 5) / 5.0  # Cap at 5

            # Recency score (if enabled)
            recency_score = 0.0
            if self.recency_boost_enabled:
                recency_score = self._calculate_recency_score(memory)

            # Weighted combination
            base_relevance = (
                semantic_score * weights['semantic'] +
                confidence_score * weights['confidence'] +
                importance_score * weights['importance'] +
                decay_score * weights['decay'] +
                corroboration_score * weights['corroboration'] +
                recency_score * weights['recency']
            )

            # Apply verification boost/penalty
            verification_boost = self._get_verification_boost(memory)
            final_relevance = base_relevance * verification_boost

            scored.append((memory, final_relevance))

        logger.debug(
            f"Scored {len(scored)} memories for task type {task_type.value}"
        )

        return scored

    def _calculate_recency_score(self, memory: Memory) -> float:
        """
        Calculate recency score based on last_accessed_at.

        Scoring tiers:
        - Today (0 days): 1.0
        - Last week (1-7 days): 0.8
        - Last 2 weeks (8-14 days): 0.6
        - Last month (15-30 days): 0.4
        - Older (31+ days): 0.2

        Args:
            memory: Memory object to score

        Returns:
            Recency score (0.0-1.0)
        """
        if not memory.last_accessed_at:
            # Never accessed → use created_at
            if not memory.created_at:
                return 0.0
            reference_time = memory.created_at
        else:
            reference_time = memory.last_accessed_at

        days_since = (datetime.now() - reference_time).days

        if days_since == 0:
            return 1.0
        elif days_since <= 7:
            return 0.8
        elif days_since <= 14:
            return 0.6
        elif days_since <= 30:
            return 0.4
        else:
            return 0.2

    def _get_verification_boost(self, memory: Memory) -> float:
        """
        Get verification status boost/penalty multiplier.

        Multipliers:
        - CORROBORATED: 1.0 + (0.05 * corroboration_count) [max 1.25]
        - UNVERIFIED: 1.0 (neutral)
        - DEPRECATED: 0.7 (penalty)
        - CONTRADICTED: 0.3 (strong penalty)

        Args:
            memory: Memory object to evaluate

        Returns:
            Verification boost multiplier
        """
        if memory.verification_status == VerificationStatus.CORROBORATED:
            # Boost by 5% per corroboration, max 25% boost
            boost = 1.0 + (memory.corroboration_count * 0.05)
            return min(boost, 1.25)

        elif memory.verification_status == VerificationStatus.CONTRADICTED:
            return 0.3  # Strong penalty

        elif memory.verification_status == VerificationStatus.DEPRECATED:
            return 0.7  # Moderate penalty

        else:  # UNVERIFIED
            return 1.0  # Neutral
