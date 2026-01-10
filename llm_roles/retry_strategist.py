"""
Retry Strategist LLM - Meta-reasoner for intelligent retry orchestration.

This is a stateless LLM that:
- Receives the original task, failed output, and failure classification
- Analyzes retry history to avoid repeating strategies
- Decides whether to retry and how
- Generates modified prompts that change problem-solving approach
- Recommends model escalation when justified
"""

import json
import logging
import re
import requests
from typing import Dict, Any, Optional, List
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.retry_schemas import (
    FailureType,
    RetryStrategy,
    RetryHistory,
    RetryDecision,
    EscalationReason
)

logger = logging.getLogger(__name__)


class RetryStrategistLLM:
    """
    The Retry Strategist is a meta-reasoner that decides retry strategy.

    This is STATELESS - each decision is independent, based on history provided.

    Core principles:
    - Retries must differ in strategy, not wording
    - Each retry explores a new solution path
    - Escalation is a last resort after multiple strategies fail
    """

    def __init__(self, ollama_host: str, ollama_port: int, model: str, timeout: int = 60):
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.model = model
        self.timeout = timeout
        self.base_url = f"http://{ollama_host}:{ollama_port}"

    def _strip_think_tags(self, text: str) -> str:
        """Remove <think>...</think> tags from model output."""
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        cleaned = re.sub(r'\n\n\n+', '\n\n', cleaned)
        return cleaned.strip()

    def decide_retry_strategy(
        self,
        original_query: str,
        failed_response: str,
        failure_type: FailureType,
        failure_reasoning: str,
        retry_history: RetryHistory,
        max_retries: int
    ) -> RetryDecision:
        """
        Decide whether and how to retry a failed attempt.

        Args:
            original_query: The user's original query
            failed_response: The response that failed verification
            failure_type: Classification of why it failed
            failure_reasoning: Verifier's explanation of failure
            retry_history: History of all previous attempts
            max_retries: Maximum number of retries allowed

        Returns:
            RetryDecision with strategy and modified prompt
        """
        # Check if we've exhausted retries
        if len(retry_history.attempts) >= max_retries:
            logger.info("Max retries reached, giving up")
            return RetryDecision(
                should_retry=False,
                reasoning="Maximum retry attempts exhausted"
            )

        # Get available strategies
        used_strategies = retry_history.get_used_strategies()
        unused_strategies = retry_history.get_unused_strategies()

        if not unused_strategies:
            logger.warning("All retry strategies exhausted")
            return RetryDecision(
                should_retry=False,
                reasoning="All retry strategies have been attempted"
            )

        # Build system prompt for strategist
        system_prompt = self._build_strategy_prompt(
            used_strategies=used_strategies,
            unused_strategies=unused_strategies,
            can_escalate=retry_history.should_allow_escalation()
        )

        # Build user message with failure context
        user_message = self._build_user_message(
            original_query=original_query,
            failed_response=failed_response,
            failure_type=failure_type,
            failure_reasoning=failure_reasoning,
            retry_history=retry_history
        )

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_message}
                    ],
                    'stream': False,
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            raw_message = result['message']['content']
            clean_message = self._strip_think_tags(raw_message)

            # Extract decision from response
            decision = self._extract_decision(clean_message, unused_strategies)

            if decision and decision.is_valid():
                return decision
            else:
                # Fallback: try first unused strategy with simple decomposition
                logger.warning("Could not parse strategist decision, using fallback")
                return self._create_fallback_decision(
                    original_query=original_query,
                    unused_strategies=unused_strategies,
                    failure_type=failure_type
                )

        except Exception as e:
            logger.error(f"Error in retry strategist: {e}")
            # On error, give up gracefully
            return RetryDecision(
                should_retry=False,
                reasoning=f"Strategist error: {e}"
            )

    def _build_strategy_prompt(
        self,
        used_strategies: List[RetryStrategy],
        unused_strategies: List[RetryStrategy],
        can_escalate: bool
    ) -> str:
        """Build system prompt for retry strategist."""
        used_str = ", ".join([s.value for s in used_strategies]) if used_strategies else "none"
        unused_str = "\n".join([f"  - {s.value}: {self._get_strategy_description(s)}" for s in unused_strategies])

        escalation_note = ""
        if can_escalate:
            escalation_note = "\n\nNOTE: Model escalation is available if you believe this task requires more reasoning capacity."

        return f"""You are a retry strategist that decides whether and how to retry failed attempts.

CORE PRINCIPLE: Retries must differ in STRATEGY, not wording.
Repeating the same approach with different words is forbidden.

STRATEGIES ALREADY TRIED:
{used_str}

AVAILABLE STRATEGIES:
{unused_str}

Your job:
1. Analyze why the previous attempt failed
2. Select ONE unused strategy that addresses the failure type
3. Generate a modified prompt that implements this strategy
4. Recommend model escalation ONLY if multiple strategies failed and task requires deeper reasoning

You must respond with JSON in this format:
```json
{{
  "should_retry": true or false,
  "strategy": "one of the available strategies above",
  "modified_prompt": "The modified query implementing the chosen strategy",
  "escalate_model": true or false,
  "reasoning": "Why this strategy was chosen and how it differs from previous attempts",
  "estimated_success_probability": 0.0 to 1.0
}}
```

CRITICAL REQUIREMENTS:
- modified_prompt must CHANGE THE APPROACH, not just rephrase
- Do NOT include apologies, encouragement, or "be careful" language
- Focus on problem framing, not tone
- Explain WHY the failure happened and WHAT will be different{escalation_note}

If no good retry strategy exists, set should_retry to false."""

    def _get_strategy_description(self, strategy: RetryStrategy) -> str:
        """Get description of what a strategy does."""
        descriptions = {
            RetryStrategy.DECOMPOSITION: "Break the task into explicit substeps before solving",
            RetryStrategy.VERIFICATION_FIRST: "Validate assumptions, inputs, or facts before attempting solution",
            RetryStrategy.ALTERNATIVE_METHOD: "Use a different reasoning approach than prior attempts",
            RetryStrategy.CONSTRAINT_EMPHASIS: "Re-solve while explicitly prioritizing constraints and edge cases",
            RetryStrategy.EXAMPLE_DRIVEN: "Solve using a concrete example or minimal working case",
            RetryStrategy.REVERSE_REASONING: "Work backward from expected output or success criteria",
            RetryStrategy.SIMPLIFICATION: "Produce the simplest possible correct solution"
        }
        return descriptions.get(strategy, "")

    def _build_user_message(
        self,
        original_query: str,
        failed_response: str,
        failure_type: FailureType,
        failure_reasoning: str,
        retry_history: RetryHistory
    ) -> str:
        """Build user message with failure context."""
        # Format retry history
        history_summary = []
        for attempt in retry_history.attempts:
            if attempt.strategy_used:
                history_summary.append(
                    f"Attempt {attempt.attempt_number}: {attempt.strategy_used.value} "
                    f"- Failed ({attempt.failure_type.value if attempt.failure_type else 'N/A'})"
                )

        history_str = "\n".join(history_summary) if history_summary else "No previous retry attempts"

        return f"""ORIGINAL TASK:
{original_query}

LATEST FAILED RESPONSE:
{failed_response}

FAILURE CLASSIFICATION:
Type: {failure_type.value}
Reasoning: {failure_reasoning}

RETRY HISTORY:
{history_str}

Analyze this failure and decide on a retry strategy. Remember: the retry must use a DIFFERENT APPROACH, not just different wording."""

    def _extract_decision(self, text: str, available_strategies: List[RetryStrategy]) -> Optional[RetryDecision]:
        """Extract retry decision from LLM response."""
        # Try to find JSON code block
        json_data = self._extract_json(text)
        if not json_data:
            return None

        try:
            # Parse strategy enum
            strategy_str = json_data.get('strategy')
            strategy = None
            if strategy_str:
                # Try to match to available strategies
                for s in available_strategies:
                    if s.value == strategy_str:
                        strategy = s
                        break

            return RetryDecision(
                should_retry=json_data.get('should_retry', False),
                strategy=strategy,
                modified_prompt=json_data.get('modified_prompt', ''),
                escalate_model=json_data.get('escalate_model', False),
                reasoning=json_data.get('reasoning', ''),
                estimated_success_probability=json_data.get('estimated_success_probability', 0.0)
            )

        except Exception as e:
            logger.error(f"Error parsing retry decision: {e}")
            return None

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON object from text using multiple strategies.

        Handles cases where LLM outputs text before/after JSON.
        """
        # Strategy 1: Try to find JSON code block first (most reliable)
        lines = text.split('\n')
        in_json_block = False
        json_content = []

        for line in lines:
            if line.strip().startswith('```json'):
                in_json_block = True
                json_content = []
            elif line.strip() == '```' and in_json_block:
                in_json_block = False
                try:
                    return json.loads('\n'.join(json_content))
                except json.JSONDecodeError as e:
                    logger.debug(f"JSON code block parse failed: {e}")
            elif in_json_block:
                json_content.append(line)

        # Strategy 2: Smart brace-matching to find complete JSON object
        # This handles cases where there's text after the JSON
        start_idx = text.find('{')
        if start_idx >= 0:
            brace_count = 0
            in_string = False
            escape_next = False

            for i in range(start_idx, len(text)):
                char = text[i]

                # Handle string escaping
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                # Track if we're inside a string
                if char == '"':
                    in_string = not in_string
                    continue

                # Only count braces outside of strings
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1

                        # Found matching closing brace
                        if brace_count == 0:
                            try:
                                json_str = text[start_idx:i+1].strip()
                                return json.loads(json_str)
                            except json.JSONDecodeError as e:
                                logger.debug(f"Smart brace-matching parse failed: {e}")
                                break

        # Strategy 3: Last resort - try simple first { to last }
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError as e:
            logger.debug(f"Simple extraction failed: {e}")

        return None

    def _create_fallback_decision(
        self,
        original_query: str,
        unused_strategies: List[RetryStrategy],
        failure_type: FailureType
    ) -> RetryDecision:
        """Create a simple fallback retry decision."""
        # Use first available strategy
        strategy = unused_strategies[0] if unused_strategies else None

        if not strategy:
            return RetryDecision(
                should_retry=False,
                reasoning="No strategies available"
            )

        # Generate simple modified prompt based on strategy
        if strategy == RetryStrategy.DECOMPOSITION:
            modified = f"Break this task into steps and solve each step:\n\n{original_query}"
        elif strategy == RetryStrategy.VERIFICATION_FIRST:
            modified = f"First verify all assumptions, then solve:\n\n{original_query}"
        elif strategy == RetryStrategy.SIMPLIFICATION:
            modified = f"Provide the simplest possible solution to:\n\n{original_query}"
        else:
            modified = f"Use a different approach to solve:\n\n{original_query}"

        return RetryDecision(
            should_retry=True,
            strategy=strategy,
            modified_prompt=modified,
            escalate_model=False,
            reasoning=f"Fallback to {strategy.value} strategy",
            estimated_success_probability=0.5
        )
