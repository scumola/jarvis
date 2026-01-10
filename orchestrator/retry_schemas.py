"""
Retry Orchestration Schemas

Defines types and structures for the intelligent retry system.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


class FailureType(str, Enum):
    """
    Primary failure classification types.

    Every failed attempt must be classified into one of these categories.
    """
    MISUNDERSTOOD_INTENT = "misunderstood_intent"          # Task intent not understood
    MISSING_CONSTRAINTS = "missing_constraints"            # Ignored or missed constraints
    INCORRECT_ASSUMPTIONS = "incorrect_assumptions"        # Wrong assumptions made
    PARTIAL_SOLUTION = "partial_solution"                  # Incomplete answer
    TOOL_MISUSE = "tool_misuse"                           # Wrong tool or wrong usage
    HALLUCINATED_FACTS = "hallucinated_facts"             # Unverified information
    INSUFFICIENT_REASONING = "insufficient_reasoning"      # Not deep enough
    UNDERSPECIFIED_SEARCH = "underspecified_search"       # Search too broad/narrow


class RetryStrategy(str, Enum):
    """
    Retry strategy axes.

    Each retry must select exactly one primary strategy.
    Strategies cannot be reused for the same task.
    """
    DECOMPOSITION = "decomposition"                        # Break into substeps
    VERIFICATION_FIRST = "verification_first"              # Validate before solving
    ALTERNATIVE_METHOD = "alternative_method"              # Different approach
    CONSTRAINT_EMPHASIS = "constraint_emphasis"            # Prioritize constraints
    EXAMPLE_DRIVEN = "example_driven"                      # Use concrete example
    REVERSE_REASONING = "reverse_reasoning"                # Work backward
    SIMPLIFICATION = "simplification"                      # Simplest solution


class EscalationReason(str, Enum):
    """Reasons for model escalation."""
    MULTIPLE_STRATEGIES_FAILED = "multiple_strategies_failed"
    INSUFFICIENT_REASONING_DEPTH = "insufficient_reasoning_depth"
    MULTI_HOP_INFERENCE_COLLAPSE = "multi_hop_inference_collapse"
    CONTEXT_OVERLOAD = "context_overload"


@dataclass
class RetryAttempt:
    """
    Record of a single retry attempt.

    Tracks what was tried, why it failed, and the outcome.
    """
    attempt_number: int
    failure_type: Optional[FailureType] = None
    strategy_used: Optional[RetryStrategy] = None
    succeeded: bool = False
    model_used: str = ""
    escalated: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    reasoning: str = ""

    def __repr__(self) -> str:
        status = "✓" if self.succeeded else "✗"
        return (
            f"{status} Attempt {self.attempt_number}: "
            f"{self.strategy_used.value if self.strategy_used else 'initial'} "
            f"({self.failure_type.value if self.failure_type else 'N/A'})"
        )


@dataclass
class RetryHistory:
    """
    Complete retry history for a task.

    Tracks all attempts and provides analysis methods.
    """
    task_query: str
    attempts: List[RetryAttempt] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def add_attempt(self, attempt: RetryAttempt) -> None:
        """Add an attempt to history."""
        self.attempts.append(attempt)

    def get_used_strategies(self) -> List[RetryStrategy]:
        """Get list of strategies already attempted."""
        return [
            a.strategy_used
            for a in self.attempts
            if a.strategy_used is not None
        ]

    def get_unused_strategies(self) -> List[RetryStrategy]:
        """Get strategies not yet tried."""
        used = set(self.get_used_strategies())
        all_strategies = set(RetryStrategy)
        return list(all_strategies - used)

    def get_failure_types(self) -> List[FailureType]:
        """Get all failure types encountered."""
        return [
            a.failure_type
            for a in self.attempts
            if a.failure_type is not None
        ]

    def has_escalated(self) -> bool:
        """Check if any attempt used escalation."""
        return any(a.escalated for a in self.attempts)

    def count_distinct_strategies(self) -> int:
        """Count how many different strategies were tried."""
        return len(set(self.get_used_strategies()))

    def should_allow_escalation(self) -> bool:
        """
        Determine if escalation is justified.

        Criteria:
        - Multiple distinct strategies failed (at least 2)
        - Failure types include reasoning depth or complexity issues
        """
        if self.has_escalated():
            return False  # Already escalated

        distinct_strategies = self.count_distinct_strategies()
        if distinct_strategies < 2:
            return False  # Need more strategy attempts first

        failure_types = self.get_failure_types()
        escalation_worthy = {
            FailureType.INSUFFICIENT_REASONING,
            FailureType.MISUNDERSTOOD_INTENT,  # Complex intent
        }

        return any(ft in escalation_worthy for ft in failure_types)

    def get_summary(self) -> str:
        """Get human-readable summary of retry history."""
        lines = [
            f"Retry History for: {self.task_query[:60]}...",
            f"Total attempts: {len(self.attempts)}",
            f"Strategies tried: {self.count_distinct_strategies()}",
        ]

        for attempt in self.attempts:
            lines.append(f"  {attempt}")

        if self.has_escalated():
            lines.append("  ⬆ Model escalation occurred")

        return "\n".join(lines)


@dataclass
class RetryDecision:
    """
    Output from Retry Strategist LLM.

    Represents the decision about whether and how to retry.
    """
    should_retry: bool
    strategy: Optional[RetryStrategy] = None
    modified_prompt: str = ""
    escalate_model: bool = False
    reasoning: str = ""
    estimated_success_probability: float = 0.0

    def is_valid(self) -> bool:
        """
        Check if decision is valid.

        A retry decision is valid if:
        - If should_retry is True, must have strategy and modified_prompt
        - Strategy must be meaningful (not reusing old approach)
        """
        if not self.should_retry:
            return True  # Giving up is valid

        if not self.strategy:
            return False  # Must have strategy

        if not self.modified_prompt or len(self.modified_prompt) < 10:
            return False  # Must have meaningful prompt modification

        return True


@dataclass
class StrategyPrompt:
    """
    Prompt modification for a specific retry strategy.

    Encapsulates how to transform the original query for a given strategy.
    """
    strategy: RetryStrategy
    original_query: str
    failure_info: str
    modified_query: str

    def get_full_prompt(self) -> str:
        """Generate the complete retry prompt."""
        return f"""[RETRY STRATEGY: {self.strategy.value}]

Original task: {self.original_query}

Previous attempt failed because: {self.failure_info}

Modified approach: {self.modified_query}"""
