"""
Unit tests for BudgetController.

Tests token budget calculation, dynamic k adjustment, and budget filtering.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from datetime import datetime
from memory.budget_controller import BudgetController
from memory.schemas import Memory, MemoryType, MemoryStatus


class TestBudgetController(unittest.TestCase):
    """Test suite for BudgetController."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'context_budgeting': {
                'max_total_tokens': 8000,
                'memory_budget_percentage': 0.15,
                'avg_memory_tokens': 50,
                'hard_cap_memories': 10,
                'min_memories': 1
            }
        }
        self.controller = BudgetController(self.config)

    def test_initialization(self):
        """Test BudgetController initialization with config."""
        self.assertEqual(self.controller.max_total_budget, 8000)
        self.assertEqual(self.controller.memory_budget_percentage, 0.15)
        self.assertEqual(self.controller.avg_memory_tokens, 50)
        self.assertEqual(self.controller.hard_cap_memories, 10)
        self.assertEqual(self.controller.min_memories, 1)

    def test_initialization_defaults(self):
        """Test BudgetController uses defaults when config missing."""
        controller = BudgetController({})
        self.assertEqual(controller.max_total_budget, 8000)
        self.assertEqual(controller.memory_budget_percentage, 0.15)

    def test_calculate_available_budget_with_space(self):
        """Test budget calculation when plenty of space available."""
        # Conversation uses 1000 tokens, plenty of space
        available = self.controller.calculate_available_budget(conversation_tokens=1000)

        # Should be limited by reserved allocation (15% of 8000 = 1200)
        expected_reserved = int(8000 * 0.15)  # 1200
        remaining_space = 8000 - 1000  # 7000

        expected = min(remaining_space, expected_reserved)  # min(7000, 1200) = 1200
        self.assertEqual(available, expected)

    def test_calculate_available_budget_low_space(self):
        """Test budget calculation when conversation uses most of context."""
        # Conversation uses 7500 tokens, very little space left
        available = self.controller.calculate_available_budget(conversation_tokens=7500)

        # Should be limited by remaining space (8000 - 7500 = 500)
        expected_reserved = int(8000 * 0.15)  # 1200
        remaining_space = 8000 - 7500  # 500

        expected = min(remaining_space, expected_reserved)  # min(500, 1200) = 500
        self.assertEqual(available, expected)

    def test_calculate_available_budget_overflow(self):
        """Test budget calculation when conversation exceeds total budget."""
        # Conversation uses more than total budget
        available = self.controller.calculate_available_budget(conversation_tokens=9000)

        # Should return 0 (no space for memories)
        self.assertEqual(available, 0)

    def test_calculate_dynamic_k_high_budget(self):
        """Test dynamic k calculation with high budget."""
        # 1000 tokens available / 50 avg per memory = 20 memories possible
        k = self.controller.calculate_dynamic_k(available_budget=1000)

        # Should be clamped to hard_cap_memories (10)
        self.assertEqual(k, 10)

    def test_calculate_dynamic_k_medium_budget(self):
        """Test dynamic k calculation with medium budget."""
        # 200 tokens available / 50 avg per memory = 4 memories possible
        k = self.controller.calculate_dynamic_k(available_budget=200)

        # Should return 4 (within range)
        self.assertEqual(k, 4)

    def test_calculate_dynamic_k_low_budget(self):
        """Test dynamic k calculation with low budget."""
        # 30 tokens available / 50 avg per memory = 0.6 → 0 memories possible
        k = self.controller.calculate_dynamic_k(available_budget=30)

        # Should be clamped to min_memories (1)
        self.assertEqual(k, 1)

    def test_calculate_dynamic_k_zero_budget(self):
        """Test dynamic k calculation with zero budget."""
        k = self.controller.calculate_dynamic_k(available_budget=0)

        # Should return min_memories (1)
        self.assertEqual(k, 1)

    def test_estimate_memory_tokens_short(self):
        """Test token estimation for short memory."""
        memory = Memory(
            memory_text="My name is Steve",  # 16 chars → ~4 tokens
            memory_type=MemoryType.IDENTITY,
            embedding_id="test-uuid-1"
        )

        tokens = self.controller.estimate_memory_tokens(memory)

        # ~4 text tokens + 10 metadata = ~14 tokens
        self.assertGreater(tokens, 10)  # At least metadata
        self.assertLess(tokens, 20)  # Reasonable upper bound

    def test_estimate_memory_tokens_long(self):
        """Test token estimation for long memory."""
        memory = Memory(
            memory_text="This is a much longer memory with lots of content that will use many more tokens when passed to the LLM" * 3,  # ~300+ chars
            memory_type=MemoryType.EPISODIC,
            embedding_id="test-uuid-2"
        )

        tokens = self.controller.estimate_memory_tokens(memory)

        # ~75+ text tokens + 10 metadata = ~85+ tokens
        self.assertGreater(tokens, 80)

    def test_filter_by_budget_all_fit(self):
        """Test budget filtering when all memories fit."""
        memories = [
            self._create_test_memory(f"Memory {i}", i) for i in range(5)
        ]

        # Budget of 500 tokens should fit 5 memories (~50 tokens each)
        filtered, tokens_used = self.controller.filter_by_budget(memories, budget=500)

        self.assertEqual(len(filtered), 5)
        self.assertLessEqual(tokens_used, 500)

    def test_filter_by_budget_partial_fit(self):
        """Test budget filtering when only some memories fit."""
        # Create longer memories to ensure they don't all fit
        memories = [
            self._create_test_memory(
                f"This is a longer memory entry number {i} with substantial content to use more tokens",
                i
            ) for i in range(10)
        ]

        # Budget of 200 tokens should fit only some memories
        filtered, tokens_used = self.controller.filter_by_budget(memories, budget=200)

        self.assertLess(len(filtered), 10)  # Not all fit
        self.assertGreater(len(filtered), 0)  # At least some fit
        self.assertLessEqual(tokens_used, 200)  # Within budget

    def test_filter_by_budget_tight_fit(self):
        """Test budget filtering with very tight budget."""
        # Create longer memories
        memories = [
            self._create_test_memory(
                f"This is memory number {i} with enough content to use around 30-40 tokens per memory",
                i
            ) for i in range(10)
        ]

        # Budget of 60 tokens should fit ~1-2 memories max
        filtered, tokens_used = self.controller.filter_by_budget(memories, budget=60)

        self.assertLessEqual(len(filtered), 2)  # At most 2 fit
        self.assertGreater(len(filtered), 0)  # At least 1 fits
        self.assertLessEqual(tokens_used, 60)

    def test_filter_by_budget_zero_budget(self):
        """Test budget filtering with zero budget."""
        memories = [
            self._create_test_memory(f"Memory {i}", i) for i in range(5)
        ]

        # Budget of 0 should return empty list
        filtered, tokens_used = self.controller.filter_by_budget(memories, budget=0)

        self.assertEqual(len(filtered), 0)
        self.assertEqual(tokens_used, 0)

    def test_filter_by_budget_preserves_order(self):
        """Test that budget filtering preserves memory order."""
        memories = [
            self._create_test_memory(f"Memory {i}", i) for i in range(5)
        ]

        filtered, _ = self.controller.filter_by_budget(memories, budget=200)

        # Should preserve order (first memories in list)
        for i, memory in enumerate(filtered):
            self.assertEqual(memory.memory_text, f"Memory {i}")

    def test_get_budget_stats(self):
        """Test budget statistics generation."""
        stats = self.controller.get_budget_stats(
            conversation_tokens=2000,
            memories_retrieved=5,
            tokens_used=250
        )

        # Check all expected fields present
        self.assertIn('max_total_budget', stats)
        self.assertIn('memory_budget_percentage', stats)
        self.assertIn('conversation_tokens', stats)
        self.assertIn('available_budget', stats)
        self.assertIn('calculated_k', stats)
        self.assertIn('actual_retrieved', stats)
        self.assertIn('tokens_used', stats)
        self.assertIn('budget_utilization', stats)
        self.assertIn('total_utilization', stats)
        self.assertIn('timestamp', stats)

        # Check values
        self.assertEqual(stats['conversation_tokens'], 2000)
        self.assertEqual(stats['actual_retrieved'], 5)
        self.assertEqual(stats['tokens_used'], 250)

        # Check calculated utilization
        expected_available = min(8000 - 2000, int(8000 * 0.15))  # min(6000, 1200) = 1200
        expected_budget_util = 250 / expected_available  # ~0.208
        self.assertAlmostEqual(stats['budget_utilization'], expected_budget_util, places=2)

        expected_total_util = (2000 + 250) / 8000  # ~0.281
        self.assertAlmostEqual(stats['total_utilization'], expected_total_util, places=2)

    def test_end_to_end_scenario(self):
        """Test complete budget-aware retrieval scenario."""
        # Scenario: Conversation has used 6000 tokens
        conversation_tokens = 6000

        # Step 1: Calculate available budget
        available = self.controller.calculate_available_budget(conversation_tokens)
        # min(8000 - 6000, 1200) = min(2000, 1200) = 1200
        self.assertEqual(available, 1200)

        # Step 2: Calculate dynamic k
        k = self.controller.calculate_dynamic_k(available)
        # 1200 / 50 = 24, clamped to 10
        self.assertEqual(k, 10)

        # Step 3: Retrieve memories (simulate with 15 memories)
        memories = [
            self._create_test_memory(f"Memory {i}", i) for i in range(15)
        ]

        # Step 4: Filter by budget
        filtered, tokens_used = self.controller.filter_by_budget(memories[:k], available)

        # Should fit 10 memories within 1200 token budget
        self.assertLessEqual(len(filtered), 10)
        self.assertLessEqual(tokens_used, 1200)

        # Step 5: Generate stats
        stats = self.controller.get_budget_stats(conversation_tokens, len(filtered), tokens_used)
        self.assertEqual(stats['conversation_tokens'], 6000)
        self.assertEqual(stats['available_budget'], 1200)

    # Helper methods

    def _create_test_memory(self, text: str, index: int) -> Memory:
        """Create a test memory object."""
        return Memory(
            id=index,
            user_id=1,
            memory_text=text,
            memory_type=MemoryType.IDENTITY,
            embedding_id=f"test-uuid-{index}",
            confidence=0.8,
            importance=0.5,
            decay_score=100.0,
            created_at=datetime.now(),
            status=MemoryStatus.ACTIVE
        )


if __name__ == '__main__':
    unittest.main()
