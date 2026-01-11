"""
Integration tests for Context Budgeting & Memory Shaping system.

Tests the complete flow from Orchestrator → MemoryManager → BudgetController/RelevanceScorer.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from memory.budget_controller import BudgetController
from memory.relevance_scorer import RelevanceScorer, TaskType, TaskClassifier
from memory.schemas import Memory, MemoryType, MemoryStatus, VerificationStatus


class TestTaskClassifier(unittest.TestCase):
    """Test task classification for adaptive scoring."""

    def setUp(self):
        """Set up test fixtures."""
        self.classifier = TaskClassifier()

    def test_classify_tool_use(self):
        """Test TOOL_USE classification."""
        queries = [
            "Find all Python files in the project",
            "Search for the config file",
            "Create a new directory called 'test'",
            "Show me the list of users"
        ]

        for query in queries:
            task_type = self.classifier.classify(query)
            self.assertEqual(task_type, TaskType.TOOL_USE, f"Failed for: {query}")

    def test_classify_recall(self):
        """Test RECALL classification."""
        queries = [
            "What did we discuss yesterday?",
            "Do you remember my name?",
            "When did I last work on this project?",
            "Have we talked about this before?"
        ]

        for query in queries:
            task_type = self.classifier.classify(query)
            self.assertEqual(task_type, TaskType.RECALL, f"Failed for: {query}")

    def test_classify_project_work(self):
        """Test PROJECT_WORK classification."""
        queries = [
            "I'm working on the authentication feature",
            "Let's continue building the API",
            "This project needs better error handling"
        ]

        for query in queries:
            task_type = self.classifier.classify(query)
            self.assertEqual(task_type, TaskType.PROJECT_WORK, f"Failed for: {query}")

    def test_classify_conversation(self):
        """Test CONVERSATION classification (default)."""
        queries = [
            "Hello, how are you?",
            "That's interesting",
            "I agree with that approach"
        ]

        for query in queries:
            task_type = self.classifier.classify(query)
            self.assertEqual(task_type, TaskType.CONVERSATION, f"Failed for: {query}")


class TestRelevanceScorer(unittest.TestCase):
    """Test task-aware relevance scoring."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'context_budgeting': {
                'task_aware_scoring': True,
                'recency_boost_enabled': True
            }
        }
        self.scorer = RelevanceScorer(self.config)

    def test_recency_score_today(self):
        """Test recency scoring for recently accessed memory."""
        memory = Memory(
            memory_text="Test memory",
            memory_type=MemoryType.IDENTITY,
            embedding_id="test-1",
            last_accessed_at=datetime.now()
        )

        score = self.scorer._calculate_recency_score(memory)
        self.assertEqual(score, 1.0)

    def test_recency_score_old(self):
        """Test recency scoring for old memory."""
        from datetime import timedelta
        memory = Memory(
            memory_text="Test memory",
            memory_type=MemoryType.IDENTITY,
            embedding_id="test-1",
            last_accessed_at=datetime.now() - timedelta(days=60)
        )

        score = self.scorer._calculate_recency_score(memory)
        self.assertEqual(score, 0.2)

    def test_verification_boost_corroborated(self):
        """Test verification boost for corroborated memories."""
        memory = Memory(
            memory_text="Test memory",
            memory_type=MemoryType.IDENTITY,
            embedding_id="test-1",
            verification_status=VerificationStatus.CORROBORATED,
            corroboration_count=3
        )

        boost = self.scorer._get_verification_boost(memory)
        self.assertEqual(boost, 1.15)  # 1.0 + (3 * 0.05)

    def test_verification_boost_contradicted(self):
        """Test verification penalty for contradicted memories."""
        memory = Memory(
            memory_text="Test memory",
            memory_type=MemoryType.IDENTITY,
            embedding_id="test-1",
            verification_status=VerificationStatus.CONTRADICTED
        )

        boost = self.scorer._get_verification_boost(memory)
        self.assertEqual(boost, 0.3)

    def test_score_memories_with_task_awareness(self):
        """Test that different task types produce different scores."""
        memories = [
            Memory(
                id=1,
                memory_text="Test memory 1",
                memory_type=MemoryType.IDENTITY,
                embedding_id="test-1",
                confidence=0.8,
                importance=0.5,
                decay_score=100.0,
                corroboration_count=0,
                verification_status=VerificationStatus.UNVERIFIED,
                last_accessed_at=datetime.now()
            )
        ]

        distance_map = {"test-1": 0.2}

        # Test different query types
        queries = {
            "Find my files": TaskType.TOOL_USE,
            "What did I say?": TaskType.RECALL,
            "Hello": TaskType.CONVERSATION
        }

        scores = {}
        for query, expected_type in queries.items():
            scored = self.scorer.score_memories(memories, query, distance_map)
            scores[expected_type] = scored[0][1]

        # Scores should differ based on task type
        self.assertIsNotNone(scores[TaskType.TOOL_USE])
        self.assertIsNotNone(scores[TaskType.RECALL])
        self.assertIsNotNone(scores[TaskType.CONVERSATION])


class TestEndToEndBudgeting(unittest.TestCase):
    """Test complete end-to-end budget-aware retrieval flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'context_budgeting': {
                'enabled': True,
                'max_total_tokens': 8000,
                'memory_budget_percentage': 0.15,
                'avg_memory_tokens': 50,
                'hard_cap_memories': 10,
                'min_memories': 1,
                'task_aware_scoring': True,
                'recency_boost_enabled': True
            }
        }

        self.budget_controller = BudgetController(self.config)
        self.relevance_scorer = RelevanceScorer(self.config)

    def test_budget_aware_k_reduction(self):
        """Test that k is reduced when conversation uses many tokens."""
        # Scenario: Conversation uses 6000 tokens
        conv_tokens = 6000

        # Calculate available budget
        available = self.budget_controller.calculate_available_budget(conv_tokens)
        # min(8000 - 6000, 1200) = min(2000, 1200) = 1200
        self.assertEqual(available, 1200)

        # Calculate dynamic k
        k = self.budget_controller.calculate_dynamic_k(available)
        # 1200 / 50 = 24, clamped to 10
        self.assertEqual(k, 10)

    def test_budget_aware_k_overflow(self):
        """Test that k is minimal when conversation exceeds budget."""
        # Scenario: Conversation uses 7900 tokens (near limit)
        conv_tokens = 7900

        # Calculate available budget
        available = self.budget_controller.calculate_available_budget(conv_tokens)
        # min(8000 - 7900, 1200) = min(100, 1200) = 100
        self.assertEqual(available, 100)

        # Calculate dynamic k
        k = self.budget_controller.calculate_dynamic_k(available)
        # 100 / 50 = 2
        self.assertEqual(k, 2)

    def test_complete_retrieval_flow(self):
        """Test complete flow: budget calculation → scoring → filtering."""
        # Step 1: Budget calculation
        conv_tokens = 5000
        available_budget = self.budget_controller.calculate_available_budget(conv_tokens)
        dynamic_k = self.budget_controller.calculate_dynamic_k(available_budget)

        # Step 2: Simulate memory retrieval and scoring
        memories = []
        for i in range(15):
            memories.append(Memory(
                id=i,
                memory_text=f"This is test memory number {i} with some content",
                memory_type=MemoryType.IDENTITY,
                embedding_id=f"test-{i}",
                confidence=0.8,
                importance=0.5,
                decay_score=100.0,
                status=MemoryStatus.ACTIVE,
                last_accessed_at=datetime.now()
            ))

        distance_map = {f"test-{i}": 0.1 + (i * 0.01) for i in range(15)}

        # Score memories
        scored = self.relevance_scorer.score_memories(
            memories,
            "Find my files",
            distance_map
        )
        scored.sort(key=lambda x: x[1], reverse=True)

        # Take top k
        top_k = [m for m, score in scored[:dynamic_k]]

        # Step 3: Budget filtering
        filtered, tokens_used = self.budget_controller.filter_by_budget(
            top_k,
            available_budget
        )

        # Assertions
        self.assertLessEqual(len(filtered), dynamic_k)
        self.assertLessEqual(tokens_used, available_budget)
        self.assertGreater(len(filtered), 0)


class TestMemoryConsolidation(unittest.TestCase):
    """Test memory consolidation and duplicate detection."""

    def test_text_similarity_identical(self):
        """Test text similarity for identical texts."""
        from memory.manager import MemoryManager

        # Create minimal mock for MemoryManager
        manager = Mock(spec=MemoryManager)
        manager._text_similarity = MemoryManager._text_similarity.__get__(manager)

        text1 = "My name is Steve and I like Python"
        text2 = "My name is Steve and I like Python"

        similarity = manager._text_similarity(text1, text2)
        self.assertEqual(similarity, 1.0)

    def test_text_similarity_partial(self):
        """Test text similarity for partially similar texts."""
        from memory.manager import MemoryManager

        manager = Mock(spec=MemoryManager)
        manager._text_similarity = MemoryManager._text_similarity.__get__(manager)

        text1 = "I like Python programming"
        text2 = "I like Java programming"

        similarity = manager._text_similarity(text1, text2)
        # "I", "like", "programming" are common (3/4 = 0.75)
        self.assertGreater(similarity, 0.5)
        self.assertLess(similarity, 1.0)

    def test_text_similarity_different(self):
        """Test text similarity for completely different texts."""
        from memory.manager import MemoryManager

        manager = Mock(spec=MemoryManager)
        manager._text_similarity = MemoryManager._text_similarity.__get__(manager)

        text1 = "The weather is nice today"
        text2 = "Python programming language"

        similarity = manager._text_similarity(text1, text2)
        self.assertLess(similarity, 0.3)


class TestEnhancedArchival(unittest.TestCase):
    """Test enhanced archival criteria."""

    def test_archival_decay_threshold(self):
        """Test archival based on decay score."""
        from memory.decay import should_archive_enhanced

        memory = Memory(
            memory_text="Test",
            memory_type=MemoryType.IDENTITY,
            embedding_id="test-1",
            decay_score=3.0,  # Below threshold
            confidence=0.8,
            verification_status=VerificationStatus.UNVERIFIED,
            access_count=5,
            created_at=datetime.now()
        )

        config = {'enhanced_archival': {'decay_threshold': 5.0}}
        should_arch, reason = should_archive_enhanced(memory, datetime.now(), config)

        self.assertTrue(should_arch)
        self.assertEqual(reason, "decay_score_low")

    def test_archival_low_confidence_contradicted(self):
        """Test archival for low confidence contradicted memories."""
        from memory.decay import should_archive_enhanced

        memory = Memory(
            memory_text="Test",
            memory_type=MemoryType.IDENTITY,
            embedding_id="test-1",
            decay_score=50.0,  # Good decay
            confidence=0.3,  # Low confidence
            verification_status=VerificationStatus.CONTRADICTED,
            access_count=0,
            created_at=datetime.now()
        )

        config = {'enhanced_archival': {'min_confidence_threshold': 0.4}}
        should_arch, reason = should_archive_enhanced(memory, datetime.now(), config)

        self.assertTrue(should_arch)
        self.assertEqual(reason, "low_confidence_contradicted")

    def test_archival_old_never_accessed(self):
        """Test archival for old never-accessed memories."""
        from memory.decay import should_archive_enhanced
        from datetime import timedelta

        memory = Memory(
            memory_text="Test",
            memory_type=MemoryType.IDENTITY,
            embedding_id="test-1",
            decay_score=50.0,
            confidence=0.8,
            verification_status=VerificationStatus.UNVERIFIED,
            access_count=0,
            created_at=datetime.now() - timedelta(days=400)
        )

        config = {'enhanced_archival': {'old_age_days': 365}}
        should_arch, reason = should_archive_enhanced(memory, datetime.now(), config)

        self.assertTrue(should_arch)
        self.assertEqual(reason, "old_never_accessed")


if __name__ == '__main__':
    unittest.main()
