"""
Budget Controller for Context-Aware Memory Retrieval

Manages token budget allocation for memory retrieval to prevent context drowning.
Dynamically adjusts the number of memories retrieved based on available tokens.
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

from memory.schemas import Memory
from memory.model_specs import get_context_window, get_recommended_memory_budget

logger = logging.getLogger(__name__)


class BudgetController:
    """
    Controls token budget allocation for memory retrieval.

    Prevents context window overflow by:
    1. Estimating token usage for conversation history
    2. Calculating available budget for memories
    3. Dynamically adjusting k (number of memories)
    4. Filtering memories to fit within budget
    """

    def __init__(self, config: Dict, model_name: Optional[str] = None):
        """
        Initialize BudgetController.

        Args:
            config: Configuration dict with context_budgeting section
            model_name: Name of the LLM model (optional, for auto-detection)
        """
        budgeting_config = config.get('context_budgeting', {})

        # Get model name from config if not provided
        if model_name is None:
            model_name = config.get('ollama', {}).get('model', 'llama3.1:8b')

        # Auto-detect context window from model specifications
        # If max_total_tokens is explicitly set in config, use that (allows override)
        # Otherwise, auto-detect from model name
        if 'max_total_tokens' in budgeting_config:
            self.max_total_budget = budgeting_config['max_total_tokens']
            logger.info(f"Using explicit max_total_tokens from config: {self.max_total_budget:,}")
        else:
            # Auto-detect from model name
            recommended = get_recommended_memory_budget(model_name)
            self.max_total_budget = recommended['max_total_tokens']
            logger.info(
                f"Auto-detected context window for '{model_name}': {self.max_total_budget:,} tokens"
            )

        # Use recommended defaults if not explicitly set, otherwise use config values
        recommended = get_recommended_memory_budget(model_name)

        # Percentage of total budget reserved for memories
        self.memory_budget_percentage = budgeting_config.get(
            'memory_budget_percentage',
            recommended['memory_budget_percentage']
        )

        # Estimated average tokens per memory (default: 50)
        # This includes: memory text (~30-40 tokens) + metadata (~10 tokens)
        self.avg_memory_tokens = budgeting_config.get(
            'avg_memory_tokens',
            recommended['avg_memory_tokens']
        )

        # Hard caps
        self.hard_cap_memories = budgeting_config.get(
            'hard_cap_memories',
            recommended['hard_cap_memories']
        )
        self.min_memories = budgeting_config.get('min_memories', 1)

        logger.info(
            f"BudgetController initialized for '{model_name}': "
            f"total={self.max_total_budget:,}, "
            f"memory_pct={self.memory_budget_percentage:.0%}, "
            f"hard_cap={self.hard_cap_memories}, "
            f"avg_tokens={self.avg_memory_tokens}"
        )

    def calculate_available_budget(self, conversation_tokens: int) -> int:
        """
        Calculate remaining token budget available for memories.

        Args:
            conversation_tokens: Tokens already used by conversation history

        Returns:
            Available token budget for memories

        Formula:
            memory_budget = min(
                total_budget - conversation_tokens,  # Remaining space
                total_budget * memory_pct             # Reserved allocation
            )
        """
        # Calculate remaining space in context window
        remaining_space = self.max_total_budget - conversation_tokens

        # Calculate reserved memory budget (percentage of total)
        reserved_memory_budget = int(self.max_total_budget * self.memory_budget_percentage)

        # Use whichever is smaller (prevents overallocation)
        available_budget = min(remaining_space, reserved_memory_budget)

        # Ensure non-negative
        available_budget = max(0, available_budget)

        logger.debug(
            f"Budget calculation: "
            f"total={self.max_total_budget}, "
            f"conversation={conversation_tokens}, "
            f"remaining={remaining_space}, "
            f"reserved={reserved_memory_budget}, "
            f"available={available_budget}"
        )

        return available_budget

    def calculate_dynamic_k(self, available_budget: int) -> int:
        """
        Calculate how many memories can fit in available budget.

        Args:
            available_budget: Token budget available for memories

        Returns:
            Dynamic k value (number of memories to retrieve)

        Clamped to [min_memories, hard_cap_memories]
        """
        if available_budget <= 0:
            return self.min_memories

        # Calculate max memories that fit in budget
        max_k = available_budget // self.avg_memory_tokens

        # Clamp to configured range
        dynamic_k = max(self.min_memories, min(max_k, self.hard_cap_memories))

        logger.debug(
            f"Dynamic k calculation: "
            f"budget={available_budget}, "
            f"avg_tokens={self.avg_memory_tokens}, "
            f"max_k={max_k}, "
            f"clamped_k={dynamic_k}"
        )

        return int(dynamic_k)

    def estimate_memory_tokens(self, memory: Memory) -> int:
        """
        Estimate token count for a single memory.

        Args:
            memory: Memory object to estimate

        Returns:
            Estimated token count

        Estimation:
            - Text tokens: ~4 characters per token (standard heuristic)
            - Metadata tokens: ~10 (type label, confidence marker, formatting)
        """
        # Estimate text tokens (~4 chars per token)
        text_tokens = len(memory.memory_text) // 4

        # Metadata overhead (type, confidence marker, formatting)
        # Example: "IDENTITY: ✓ My name is Steve\n" → ~10 tokens overhead
        metadata_tokens = 10

        total_tokens = text_tokens + metadata_tokens

        return total_tokens

    def filter_by_budget(
        self,
        memories: List[Memory],
        budget: int
    ) -> Tuple[List[Memory], int]:
        """
        Filter memories to fit within token budget.

        Assumes memories are already sorted by relevance (descending).
        Keeps highest-relevance memories until budget is exhausted.

        Args:
            memories: List of Memory objects (sorted by relevance)
            budget: Token budget limit

        Returns:
            Tuple of:
                - Filtered list of memories that fit in budget
                - Total tokens used by filtered memories
        """
        filtered_memories = []
        tokens_used = 0

        for memory in memories:
            estimated_tokens = self.estimate_memory_tokens(memory)

            # Check if adding this memory would exceed budget
            if tokens_used + estimated_tokens <= budget:
                filtered_memories.append(memory)
                tokens_used += estimated_tokens
            else:
                # Budget exhausted, stop adding memories
                logger.debug(
                    f"Budget exhausted: "
                    f"tokens_used={tokens_used}, "
                    f"next_memory={estimated_tokens}, "
                    f"budget={budget}"
                )
                break

        logger.info(
            f"Budget filtering: "
            f"input={len(memories)} memories, "
            f"output={len(filtered_memories)} memories, "
            f"tokens_used={tokens_used}/{budget}"
        )

        return filtered_memories, tokens_used

    def get_budget_stats(
        self,
        conversation_tokens: int,
        memories_retrieved: int,
        tokens_used: int
    ) -> Dict:
        """
        Generate budget statistics for monitoring/debugging.

        Args:
            conversation_tokens: Tokens in conversation history
            memories_retrieved: Number of memories retrieved
            tokens_used: Tokens used by retrieved memories

        Returns:
            Dict with budget statistics
        """
        available_budget = self.calculate_available_budget(conversation_tokens)
        dynamic_k = self.calculate_dynamic_k(available_budget)

        stats = {
            # Configuration
            'max_total_budget': self.max_total_budget,
            'memory_budget_percentage': self.memory_budget_percentage,
            'avg_memory_tokens': self.avg_memory_tokens,

            # Usage
            'conversation_tokens': conversation_tokens,
            'available_budget': available_budget,
            'calculated_k': dynamic_k,
            'actual_retrieved': memories_retrieved,
            'tokens_used': tokens_used,

            # Utilization
            'budget_utilization': tokens_used / available_budget if available_budget > 0 else 0.0,
            'total_utilization': (conversation_tokens + tokens_used) / self.max_total_budget,

            # Timestamp
            'timestamp': datetime.now().isoformat()
        }

        return stats
