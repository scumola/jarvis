"""
Core orchestrator engine.

This is the TRUSTED COMPUTING BASE.
The orchestrator:
- Owns all permissions and execution
- Mediates between LLMs and the system
- Enforces safety policies
- Is deterministic, strict, and paranoid
"""

import logging
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from tools import ToolRegistry, ToolInvocation, BUILTIN_TOOLS
from llm_roles import PersonaLLM, VerifierLLM, MemoryCuratorLLM, RetryStrategistLLM, GoalDecomposerLLM, SummarizerLLM, IntrospectionLLM
from .retry_schemas import (
    FailureType,
    RetryStrategy,
    RetryHistory,
    RetryAttempt,
    RetryDecision
)
from .context_classifier import classify_context

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    The orchestrator is the central control system.

    It:
    - Parses only structured outputs (JSON) from LLMs
    - Ignores LLM prose for execution decisions
    - Enforces permissions
    - Executes tools in controlled environments
    - Maintains audit logs
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Initialize tool registry
        registry_path = config['tools']['registry_path']
        self.tool_registry = ToolRegistry(registry_path)

        # Register built-in tools
        for tool_name, (schema, impl) in BUILTIN_TOOLS.items():
            self.tool_registry.register_tool(schema, impl)

        # Initialize Conversation Summarizer LLM (if enabled)
        ollama_config = config['ollama']
        summarization_config = config.get('summarization', {})
        if summarization_config.get('enabled', True):
            self.summarizer_llm = SummarizerLLM(
                ollama_host=ollama_config['host'],
                ollama_port=ollama_config['port'],
                model=ollama_config['model'],
                timeout=ollama_config.get('summarizer_timeout', 120)
            )
            logger.info("Conversation Summarizer LLM initialized")
        else:
            self.summarizer_llm = None
            logger.info("Conversation summarization disabled")

        # Initialize Persona LLM (with summarizer support)
        self.persona_llm = PersonaLLM(
            ollama_host=ollama_config['host'],
            ollama_port=ollama_config['port'],
            model=ollama_config['model'],
            timeout=ollama_config['timeout'],
            summarizer=self.summarizer_llm,
            summarization_config=summarization_config
        )

        # Initialize Verifier LLM (for result verification)
        self.verifier_llm = VerifierLLM(
            ollama_host=ollama_config['host'],
            ollama_port=ollama_config['port'],
            model=ollama_config['model'],
            timeout=ollama_config.get('verifier_timeout', 180)
        )

        # Initialize Retry Strategist LLM (for intelligent retries)
        self.retry_strategist = RetryStrategistLLM(
            ollama_host=ollama_config['host'],
            ollama_port=ollama_config['port'],
            model=ollama_config['model'],
            timeout=ollama_config.get('strategist_timeout', 120)
        )

        # Execution settings
        self.require_approval = config['tools']['require_approval']
        self.enable_verification = config.get('verification', {}).get('enabled', True)
        self.max_retries = config.get('verification', {}).get('max_retries', 2)

        # Model escalation settings
        self.escalation_model = ollama_config.get('escalation_model', None)
        self.allow_escalation = ollama_config.get('allow_escalation', False)

        # Initialize Memory Manager (if enabled)
        self.memory_enabled = config.get('memory', {}).get('enabled', False)
        if self.memory_enabled:
            from memory import MemoryManager
            self.memory_manager = MemoryManager(config['memory'])
            logger.info("Memory system initialized")
        else:
            self.memory_manager = None
            logger.info("Memory system disabled")

        # Initialize Goal Manager (if enabled)
        self.goal_enabled = config.get('goals', {}).get('enabled', True)
        if self.goal_enabled:
            from goals import GoalManager
            self.goal_manager = GoalManager(
                host=config['memory']['mysql_host'],
                database=config['memory']['mysql_database'],
                user=config['memory']['mysql_user'],
                password=config['memory']['mysql_password']
            )

            # Initialize Goal Decomposer LLM (for auto-decomposing user requests)
            self.goal_decomposer = GoalDecomposerLLM(
                ollama_host=ollama_config['host'],
                ollama_port=ollama_config['port'],
                model=ollama_config['model'],
                timeout=ollama_config.get('decomposer_timeout', 180)
            )
            logger.info("Goal Management system initialized with auto-decomposition")
        else:
            self.goal_manager = None
            self.goal_decomposer = None
            logger.info("Goal Management system disabled")

        # Initialize Procedural Memory (if enabled)
        self.procedural_enabled = config.get('memory', {}).get('procedural_enabled', False)
        if self.procedural_enabled:
            from memory.procedural_memory import ProceduralMemoryManager
            self.procedural_memory = ProceduralMemoryManager(config['memory'])
            logger.info("Procedural memory system initialized")
        else:
            self.procedural_memory = None
            logger.info("Procedural memory disabled")

        # Initialize Memory Curator LLM (if memory enabled)
        if self.memory_enabled:
            self.curator_llm = MemoryCuratorLLM(
                ollama_host=ollama_config['host'],
                ollama_port=ollama_config['port'],
                model=ollama_config['model'],
                timeout=ollama_config.get('curator_timeout', 180)
            )
            logger.info("Memory Curator LLM initialized")
        else:
            self.curator_llm = None

        # Initialize Introspection LLM (if procedural memory enabled)
        if self.procedural_enabled:
            self.introspection_llm = IntrospectionLLM(
                ollama_host=ollama_config['host'],
                ollama_port=ollama_config['port'],
                model=ollama_config['model'],
                timeout=ollama_config.get('introspection_timeout', 180)
            )
            logger.info("Introspection LLM initialized")
        else:
            self.introspection_llm = None

        logger.info("Orchestrator initialized")

    def process_user_input(self, user_input: str, user_id: Optional[int] = None, disable_auto_goal: bool = False) -> Dict[str, Any]:
        """
        Process a single user input through the full cycle with verification.

        1. [NEW] Check if request should be auto-converted to a goal
        2. Pass to Persona LLM
        3. Parse proposed actions
        4. Validate actions
        5. Execute approved actions
        6. Verify results match query intent
        7. Retry with corrections if needed (up to max_retries)

        Args:
            user_input: User's query/command
            user_id: Optional user ID for multi-user memory isolation (API mode)
            disable_auto_goal: If True, skip auto-goal detection (used during autonomous execution)

        Returns:
            Dictionary with response text and execution results
        """
        logger.info(f"Processing user input for user_id={user_id}: {user_input[:100]}...")

        # AUTO-GOAL DETECTION: Check if this request should become a goal
        # Skip if we're already executing a goal autonomously (prevents infinite recursion)
        if (not disable_auto_goal and
            self.goal_enabled and
            self.config.get('goals', {}).get('auto_detect', True)):
            goal_result = self._check_auto_goal_creation(user_input, user_id)
            if goal_result:
                # Request was converted to a goal and handled
                return goal_result

        # Classify task context for procedural memory
        task_context = classify_context(user_input)
        logger.debug(f"Task context classified as: {task_context}")

        # Initialize retry history
        retry_history = RetryHistory(task_query=user_input)

        # Track current model (for escalation)
        current_model = self.persona_llm.model

        # Track current strategy across loop iterations
        current_strategy = None  # None for initial attempt

        # Track which heuristic was applied (for feedback)
        applied_heuristic_id = None

        # Initial attempt (not a retry yet)
        attempt_number = 0
        input_message = user_input

        while True:
            attempt_number += 1

            # Execute one attempt
            result = self._execute_single_attempt(
                input_message=input_message,
                model=current_model,
                user_id=user_id
            )

            # If verification is disabled, return immediately
            if not self.enable_verification:
                return result

            # Verify the results
            verification = self._verify_result(
                original_query=user_input,
                action_results=result['actions_taken'],
                final_response=result['response']
            )

            logger.info(
                f"Attempt {attempt_number} - Verification: {verification['verified']} "
                f"(confidence: {verification['confidence']})"
            )

            # Parse failure type if verification failed
            failure_type = None
            if not verification['verified'] and verification.get('failure_type'):
                try:
                    failure_type = FailureType(verification['failure_type'])
                except ValueError:
                    logger.warning(f"Unknown failure type: {verification.get('failure_type')}")
                    failure_type = FailureType.PARTIAL_SOLUTION  # Default

            # Record this attempt
            attempt = RetryAttempt(
                attempt_number=attempt_number,
                failure_type=failure_type,
                strategy_used=current_strategy,  # Will be None for first attempt, strategy for retries
                succeeded=verification['verified'],
                model_used=current_model,
                escalated=(current_model != self.persona_llm.model),
                reasoning=verification.get('reasoning', '')
            )
            retry_history.add_attempt(attempt)

            # If verified, we're done!
            if verification['verified']:
                result['verification'] = verification
                result['retry_history'] = self._format_retry_history(retry_history)

                # If this was a successful retry (not first attempt), record to procedural memory
                if attempt_number > 1 and current_strategy and self.procedural_enabled:
                    try:
                        # Get the failure type from previous attempt
                        prev_failure = retry_history.attempts[-2].failure_type if len(retry_history.attempts) >= 2 else None

                        if prev_failure:
                            # INTROSPECTION: Analyze execution to extract qualitative insights
                            introspection_insight = None
                            if self.introspection_llm:
                                try:
                                    # Build attempt dicts for introspection
                                    attempt_dicts = [
                                        {
                                            'success': att.succeeded,
                                            'verification': {
                                                'failure_type': att.failure_type.value if att.failure_type else None,
                                                'reasoning': att.reasoning
                                            },
                                            'actions_taken': []  # Would need to track this per attempt
                                        }
                                        for att in retry_history.attempts
                                    ]

                                    # Extract all tools used across attempts
                                    tools_used = list(set([
                                        action.get('tool_name')
                                        for action in result.get('actions_taken', [])
                                        if action.get('tool_name')
                                    ]))

                                    introspection_insight = self.introspection_llm.analyze_execution(
                                        original_task=user_input,
                                        task_context=task_context,
                                        attempts=attempt_dicts,
                                        final_result=result,
                                        tools_used=tools_used
                                    )

                                    if introspection_insight:
                                        logger.info(
                                            f"🔍 Introspection insight generated: "
                                            f"{introspection_insight.generalizable_lesson[:60] if introspection_insight.generalizable_lesson else 'N/A'}..."
                                        )

                                except Exception as e:
                                    logger.error(f"Error during introspection: {e}")

                            # Record success to procedural memory (with optional insights)
                            self.procedural_memory.record_success(
                                context_type=task_context,
                                failure_type=prev_failure,
                                strategy=current_strategy,
                                notes=f"Successful retry for: {user_input[:50]}...",
                                introspection=introspection_insight
                            )
                            logger.info(
                                f"Recorded successful retry to procedural memory: "
                                f"{task_context}/{prev_failure.value} → {current_strategy.value}"
                            )

                        # If we used a heuristic and it succeeded, give it positive feedback
                        if applied_heuristic_id:
                            # Heuristic success is already recorded in record_success above
                            logger.info(f"Heuristic {applied_heuristic_id} succeeded")

                    except Exception as e:
                        logger.error(f"Error recording to procedural memory: {e}")

                # Store memories after successful verification
                if self.memory_enabled:
                    try:
                        self._curate_and_store_memories(
                            user_query=user_input,
                            action_results=result['actions_taken'],
                            final_response=result['response'],
                            user_id=user_id
                        )
                    except Exception as e:
                        logger.error(f"Memory storage error: {e}")

                return result

            # Not verified - decide whether and how to retry
            if attempt_number > self.max_retries:
                logger.warning(f"Max retries ({self.max_retries}) reached")
                result['verification'] = verification
                result['verification']['max_retries_reached'] = True
                result['retry_history'] = self._format_retry_history(retry_history)
                return result

            # Check procedural memory for learned heuristics FIRST
            retry_decision = None
            if self.procedural_enabled and failure_type:
                try:
                    heuristics = self.procedural_memory.query_heuristics(
                        context_type=task_context,
                        failure_type=failure_type
                    )

                    # Check if we have a heuristic that hasn't been tried yet
                    used_strategies = retry_history.get_used_strategies()
                    for heuristic in heuristics:
                        if heuristic.effective_strategy not in used_strategies:
                            # Found an applicable heuristic!
                            logger.info(
                                f"Applying learned heuristic: {task_context}/"
                                f"{failure_type.value} → {heuristic.effective_strategy.value} "
                                f"(confidence={heuristic.confidence_score:.2f})"
                            )

                            # Create retry decision from heuristic
                            retry_decision = RetryDecision(
                                should_retry=True,
                                strategy=heuristic.effective_strategy,
                                modified_prompt=self._apply_heuristic_to_prompt(
                                    user_input,
                                    heuristic
                                ),
                                escalate_model=False,  # Heuristics don't trigger escalation
                                reasoning=f"Applied learned heuristic (confidence={heuristic.confidence_score:.2f})",
                                estimated_success_probability=heuristic.confidence_score
                            )

                            applied_heuristic_id = heuristic.id
                            break  # Use first matching heuristic

                except Exception as e:
                    logger.error(f"Error querying procedural memory: {e}")

            # If no heuristic found, ask Retry Strategist for decision
            if not retry_decision:
                logger.info(f"Consulting retry strategist after failure: {failure_type.value if failure_type else 'unknown'}")

                retry_decision = self.retry_strategist.decide_retry_strategy(
                    original_query=user_input,
                    failed_response=result['response'],
                    failure_type=failure_type or FailureType.PARTIAL_SOLUTION,
                    failure_reasoning=verification.get('reasoning', ''),
                    retry_history=retry_history,
                    max_retries=self.max_retries
                )

            logger.info(
                f"Retry decision: should_retry={retry_decision.should_retry}, "
                f"strategy={retry_decision.strategy}, "
                f"escalate={retry_decision.escalate_model}"
            )

            # If strategist says don't retry, give up
            if not retry_decision.should_retry:
                logger.info(f"Retry strategist recommends giving up: {retry_decision.reasoning}")
                result['verification'] = verification
                result['verification']['strategist_gave_up'] = True
                result['retry_history'] = self._format_retry_history(retry_history)
                return result

            # Store strategy for next attempt
            current_strategy = retry_decision.strategy

            # Handle model escalation
            if retry_decision.escalate_model and self.allow_escalation and self.escalation_model:
                if current_model != self.escalation_model:
                    logger.info(f"Escalating model: {current_model} → {self.escalation_model}")
                    current_model = self.escalation_model

            # Prepare for retry with modified prompt
            input_message = retry_decision.modified_prompt
            logger.info(
                f"Retrying with strategy: {retry_decision.strategy.value}\n"
                f"Modified prompt: {input_message[:100]}..."
            )

        # Should never reach here
        return result

    def _execute_single_attempt(
        self,
        input_message: str,
        model: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute a single attempt to answer the user's query.

        Args:
            input_message: The query/prompt to process (may be modified for retries)
            model: Optional model override for escalation
            user_id: Optional user ID for multi-user memory isolation

        Returns:
            Result dictionary with response and actions
        """
        # Step 1: Retrieve relevant memories (if enabled)
        memory_context = None
        if self.memory_enabled and user_id is not None:
            try:
                memories = self.memory_manager.retrieve_memories(
                    user_id=user_id,
                    query=input_message,
                    k=10,
                    min_confidence=0.5,
                    min_decay_score=20.0
                )
                memory_context = {
                    'memories': memories,
                    'query': input_message,
                    'count': len(memories)
                }
                logger.info(f"Retrieved {len(memories)} relevant memories")
            except Exception as e:
                logger.error(f"Memory retrieval error: {e}")
                memory_context = None

        # Step 2: Get LLM response (with memory context and optional model override)
        available_tools = self.tool_registry.get_tools_for_llm()

        # Temporarily override model if escalated
        original_model = None
        if model and model != self.persona_llm.model:
            original_model = self.persona_llm.model
            self.persona_llm.model = model
            logger.info(f"Using escalated model: {model}")

        try:
            llm_response = self.persona_llm.generate_response(
                input_message,
                available_tools,
                memory_context
            )
        finally:
            # Restore original model
            if original_model:
                self.persona_llm.model = original_model

        response_text = llm_response['response_text']
        proposed_actions = llm_response['proposed_actions']

        logger.info(f"LLM proposed {len(proposed_actions)} actions")

        # Step 2: Process any proposed actions
        action_results = []
        for action in proposed_actions:
            result = self._execute_action(action)
            action_results.append(result)

            # Feed result back to LLM
            self.persona_llm.add_tool_result(action['tool_name'], result)

        # If there were actions, get a final response from the LLM
        final_response = response_text
        if action_results:
            # Let the LLM see the results and respond
            summary_prompt = (
                "The tools have finished executing. Please look at the results above "
                "and provide a clear, helpful summary for the user. "
                "Tell them what you found or what was accomplished."
            )
            final_llm = self.persona_llm.generate_response(
                summary_prompt,
                available_tools,
                memory_context
            )
            final_response = final_llm['response_text']

        return {
            'response': final_response,
            'actions_taken': action_results
        }

    def _verify_result(
        self,
        original_query: str,
        action_results: List[Dict[str, Any]],
        final_response: str
    ) -> Dict[str, Any]:
        """
        Verify if the action results adequately answered the user's query.

        Returns verification dict from VerifierLLM.
        """
        # Build a summary of tool results
        if not action_results:
            tool_summary = "No tools were executed."
        else:
            tool_summary = "Tools executed:\n"
            for action in action_results:
                tool_name = action.get('tool_name', 'unknown')
                success = action.get('success', False)
                if success:
                    tool_summary += f"- {tool_name}: SUCCESS\n"
                else:
                    error = action.get('error', 'Unknown error')
                    tool_summary += f"- {tool_name}: FAILED ({error})\n"

        return self.verifier_llm.verify_results(
            user_query=original_query,
            tool_results=tool_summary,
            assistant_response=final_response
        )

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single action (tool invocation).

        This is where all safety checks happen, including role-based access control.
        """
        tool_name = action['tool_name']
        parameters = action['parameters']
        reasoning = action.get('reasoning', '')

        logger.info(f"Executing action: {tool_name} - {reasoning}")

        # SECURITY: Check if tool is allowed for this user (API access control)
        if hasattr(self, 'allowed_tools') and self.allowed_tools is not None:
            if tool_name not in self.allowed_tools:
                user_role = getattr(self, 'user_role', 'unknown')
                logger.warning(
                    f"Tool '{tool_name}' blocked for user role '{user_role}'"
                )
                return {
                    'tool_name': tool_name,
                    'success': False,
                    'error': (
                        f"Access denied: Tool '{tool_name}' is not available for API users. "
                        f"This tool performs local file modifications or destructive operations. "
                        f"Please use the CLI interface for write operations."
                    ),
                    'blocked_by_security': True
                }

        # Create invocation object
        invocation = ToolInvocation(
            tool_name=tool_name,
            parameters=parameters,
            reasoning=reasoning
        )

        # Step 1: Validate the invocation
        is_valid, error = self.tool_registry.validate_invocation(invocation)
        if not is_valid:
            logger.warning(f"Invalid tool invocation: {error}")
            return {
                'tool_name': tool_name,
                'success': False,
                'error': f'Validation failed: {error}'
            }

        # Step 2: Check if approval is needed
        tool_schema = self.tool_registry.get_tool_schema(tool_name)
        if tool_schema.requires_approval and self.require_approval:
            # For now, we'll implement simple approval
            # In a real system, this would prompt the user
            approved = self._request_approval(tool_name, parameters, reasoning)
            if not approved:
                logger.info(f"Action not approved: {tool_name}")
                return {
                    'tool_name': tool_name,
                    'success': False,
                    'error': 'Action requires approval and was not approved'
                }

        # Step 3: Execute the tool
        implementation = self.tool_registry.get_implementation(tool_name)
        if not implementation:
            return {
                'tool_name': tool_name,
                'success': False,
                'error': 'Tool implementation not found'
            }

        try:
            result = implementation(**parameters)
            logger.info(f"Tool {tool_name} executed successfully")
            return {
                'tool_name': tool_name,
                **result
            }
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                'tool_name': tool_name,
                'success': False,
                'error': f'Execution error: {str(e)}'
            }

    def _request_approval(self, tool_name: str, parameters: Dict, reasoning: str) -> bool:
        """
        Request human approval for a dangerous action.

        For the MVP, we'll implement simple console approval.
        Later, this can be more sophisticated.
        """
        print("\n" + "="*60)
        print("APPROVAL REQUIRED")
        print("="*60)
        print(f"Tool: {tool_name}")
        print(f"Parameters: {json.dumps(parameters, indent=2)}")
        print(f"Reasoning: {reasoning}")
        print("="*60)

        while True:
            response = input("Approve this action? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            else:
                print("Please enter 'yes' or 'no'")

    def reset_conversation(self):
        """Reset the persona LLM conversation history."""
        self.persona_llm.reset()
        logger.info("Conversation reset")

    def _curate_and_store_memories(
        self,
        user_query: str,
        action_results: List[Dict],
        final_response: str,
        user_id: Optional[int] = None
    ) -> None:
        """
        Use MemoryCuratorLLM to propose memories, then store them.

        This is called AFTER successful verification.

        Args:
            user_query: Original user query
            action_results: Results from tool executions
            final_response: Final response to user
            user_id: Optional user ID for multi-user memory isolation
        """
        # Build conversation context
        conversation_snippet = self._build_conversation_snippet()

        # Build tool results summary
        tool_summary = self._build_tool_summary(action_results)

        # Ask Curator LLM for memory proposals
        proposals = self.curator_llm.propose_memories(
            user_query=user_query,
            conversation_snippet=conversation_snippet,
            tool_results=tool_summary,
            assistant_response=final_response
        )

        if not proposals:
            logger.info("No memories proposed by curator")
            return

        logger.info(f"Curator proposed {len(proposals)} memories")

        # Orchestrator validates and stores each proposal
        for proposal in proposals:
            try:
                # Validation checks
                if proposal.confidence < 0.3:
                    logger.info(f"Rejecting low-confidence memory: {proposal.reasoning}")
                    continue

                if len(proposal.memory_text) < 5:
                    logger.warning(f"Rejecting too-short memory: {proposal.memory_text}")
                    continue

                # Store the memory
                if user_id is not None:
                    memory_id = self.memory_manager.store_memory(proposal, user_id)
                    logger.info(f"Stored memory {memory_id} for user {user_id}: {proposal.memory_text[:50]}...")
                else:
                    logger.warning("Cannot store memory: user_id is None")

            except Exception as e:
                logger.error(f"Failed to store memory: {e}")
                # Continue with other proposals

    def _apply_heuristic_to_prompt(self, original_query: str, heuristic) -> str:
        """
        Apply a learned heuristic to modify the query prompt.

        Args:
            original_query: Original user query
            heuristic: Heuristic object with strategy to apply

        Returns:
            Modified prompt implementing the strategy
        """
        strategy = heuristic.effective_strategy

        # Generate strategy-specific prompt modification
        if strategy == RetryStrategy.DECOMPOSITION:
            return f"Break this task into explicit steps and solve each:\n\n{original_query}"

        elif strategy == RetryStrategy.VERIFICATION_FIRST:
            return f"First verify assumptions and inputs, then solve:\n\n{original_query}"

        elif strategy == RetryStrategy.ALTERNATIVE_METHOD:
            return f"Use a different approach than before to solve:\n\n{original_query}"

        elif strategy == RetryStrategy.CONSTRAINT_EMPHASIS:
            return f"Pay careful attention to all constraints and edge cases:\n\n{original_query}"

        elif strategy == RetryStrategy.EXAMPLE_DRIVEN:
            return f"Solve using a concrete example first:\n\n{original_query}"

        elif strategy == RetryStrategy.REVERSE_REASONING:
            return f"Work backward from the expected result:\n\n{original_query}"

        elif strategy == RetryStrategy.SIMPLIFICATION:
            return f"Provide the simplest possible correct solution:\n\n{original_query}"

        else:
            # Fallback
            return original_query

    def _build_conversation_snippet(self) -> str:
        """Build a snippet of recent conversation for curator context."""
        # Get last 4 messages from persona_llm history
        history = self.persona_llm.conversation_history[-4:]

        snippet = ""
        for msg in history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            # Truncate long messages
            if len(content) > 200:
                content = content[:200] + "..."
            snippet += f"{role}: {content}\n\n"

        return snippet

    def _format_retry_history(self, retry_history: RetryHistory) -> Dict[str, Any]:
        """
        Format retry history for output.

        Args:
            retry_history: RetryHistory object

        Returns:
            Dictionary with formatted retry information
        """
        return {
            'total_attempts': len(retry_history.attempts),
            'strategies_tried': [s.value for s in retry_history.get_used_strategies()],
            'final_strategy': (
                retry_history.attempts[-1].strategy_used.value
                if retry_history.attempts and retry_history.attempts[-1].strategy_used
                else None
            ),
            'escalated': retry_history.has_escalated(),
            'attempts': [
                {
                    'number': a.attempt_number,
                    'strategy': a.strategy_used.value if a.strategy_used else 'initial',
                    'failure_type': a.failure_type.value if a.failure_type else None,
                    'succeeded': a.succeeded,
                    'model': a.model_used
                }
                for a in retry_history.attempts
            ]
        }

    def _build_tool_summary(self, action_results: List[Dict]) -> str:
        """Format tool results for curator."""
        if not action_results:
            return "No tools executed."

        summary = ""
        for action in action_results:
            tool_name = action.get('tool_name', 'unknown')
            success = action.get('success', False)
            summary += f"- {tool_name}: {'SUCCESS' if success else 'FAILED'}\n"
        return summary

    # ==================== Goal Management Integration ====================

    def execute_goal_autonomously(
        self,
        goal_id: int,
        user_id: int,
        max_iterations: int = 100,
        save_checkpoints: bool = True,
        auto_approve: bool = True
    ) -> Dict[str, Any]:
        """
        Autonomously execute a goal until completion, blocking, or max iterations.

        Args:
            goal_id: ID of the goal to execute
            user_id: User ID who owns this goal
            max_iterations: Maximum task execution attempts (safety limit)
            save_checkpoints: Whether to save checkpoints after each task
            auto_approve: Whether to auto-approve tool executions (default: True for autonomy)

        Returns:
            Dict with:
                - status: Final goal status
                - tasks_completed: Number of tasks completed
                - tasks_failed: Number of tasks failed
                - iterations_used: Number of iterations
                - final_progress: Progress percentage
                - execution_summary: Human-readable summary
        """
        if not self.goal_enabled:
            raise RuntimeError("Goal management system is not enabled")

        logger.info(f"Starting autonomous execution of goal {goal_id}")

        from goals import GoalStatus, SubtaskStatus

        iterations = 0
        tasks_completed = 0
        tasks_failed = 0

        # Save original approval setting and temporarily disable if auto_approve
        original_require_approval = self.require_approval
        if auto_approve:
            self.require_approval = False
            logger.info("Auto-approval enabled for autonomous execution")

        try:
            # Mark goal as in progress
            self.goal_manager.update_goal_status(goal_id, GoalStatus.IN_PROGRESS)

            while iterations < max_iterations:
                # Get current progress
                progress = self.goal_manager.get_goal_with_progress(goal_id)

                # Check if we can make progress
                if not progress.can_make_progress:
                    logger.info("No more actionable tasks available")
                    break

                # Get next task
                next_task = progress.next_task
                if not next_task:
                    logger.info("No next task found")
                    break

                logger.info(f"[Goal {goal_id}] Executing task {next_task.task_order}/{len(progress.subtasks)}: {next_task.task_text}")

                # Mark task as in progress
                self.goal_manager.update_subtask_status(
                    next_task.id,
                    SubtaskStatus.IN_PROGRESS
                )

                # Execute task through normal orchestrator pipeline
                # CRITICAL: Disable auto-goal detection to prevent infinite recursion
                try:
                    result = self.process_user_input(
                        user_input=next_task.task_text,
                        user_id=user_id,
                        disable_auto_goal=True  # Prevent nested goal creation
                    )

                    # Extract tools used
                    tools_used = [action.get('tool_name') for action in result.get('actions_taken', [])]

                    # Check if verification passed (if enabled)
                    verification = result.get('verification', {})
                    verification_passed = verification.get('success', True) if self.enable_verification else True

                    if verification_passed:
                        # Mark task as completed
                        self.goal_manager.update_subtask_status(
                            next_task.id,
                            SubtaskStatus.COMPLETED,
                            result=result.get('response', '')[:1000],  # Limit result size
                            tools_used=tools_used,
                            verification_passed=True
                        )
                        tasks_completed += 1
                        logger.info(f"✓ Task {next_task.task_order} completed successfully")

                        # Save checkpoint if enabled
                        if save_checkpoints:
                            self.goal_manager.save_checkpoint(
                                goal_id,
                                f"after_task_{next_task.task_order}",
                                {
                                    'task_order': next_task.task_order,
                                    'tasks_completed': tasks_completed,
                                    'iteration': iterations
                                }
                            )

                    else:
                        # Task failed verification
                        issues = verification.get('issues', 'Verification failed')
                        logger.warning(f"✗ Task {next_task.task_order} failed verification: {issues}")

                        self.goal_manager.update_subtask_status(
                            next_task.id,
                            SubtaskStatus.FAILED,
                            error_message=issues[:500],
                            tools_used=tools_used,
                            verification_passed=False
                        )
                        tasks_failed += 1

                        # Try to retry
                        can_retry = self.goal_manager.retry_subtask(next_task.id)
                        if not can_retry:
                            logger.error(f"Task {next_task.id} failed permanently after max retries")
                            self.goal_manager.update_goal_status(
                                goal_id,
                                GoalStatus.BLOCKED,
                                result_summary=f"Task {next_task.task_order} failed after {next_task.max_retries} attempts"
                            )
                            break

                except Exception as e:
                    logger.error(f"Error executing task {next_task.id}: {e}", exc_info=True)
                    self.goal_manager.update_subtask_status(
                        next_task.id,
                        SubtaskStatus.FAILED,
                        error_message=str(e)[:500]
                    )
                    tasks_failed += 1

                    # Try to retry
                    can_retry = self.goal_manager.retry_subtask(next_task.id)
                    if not can_retry:
                        self.goal_manager.update_goal_status(
                            goal_id,
                            GoalStatus.BLOCKED,
                            result_summary=f"Task {next_task.task_order} encountered fatal error"
                        )
                        break

                iterations += 1

            # Get final status
            goal = self.goal_manager.get_goal(goal_id)

            # Update goal status based on completion
            if goal.progress_percentage == 100:
                self.goal_manager.update_goal_status(
                    goal_id,
                    GoalStatus.COMPLETED,
                    result_summary=f"Successfully completed all {len(goal.subtasks)} tasks in {iterations} iterations",
                    lessons_learned=f"Completed {tasks_completed} tasks, {tasks_failed} failed/retried"
                )
                final_status = GoalStatus.COMPLETED
            elif iterations >= max_iterations:
                self.goal_manager.update_goal_status(
                    goal_id,
                    GoalStatus.BLOCKED,
                    result_summary=f"Reached maximum iterations ({max_iterations}) with {goal.progress_percentage}% complete"
                )
                final_status = GoalStatus.BLOCKED
            else:
                final_status = goal.status

            execution_summary = (
                f"Goal {goal_id}: {final_status.value}\n"
                f"Progress: {goal.progress_percentage}%\n"
                f"Tasks completed: {tasks_completed}\n"
                f"Tasks failed: {tasks_failed}\n"
                f"Iterations: {iterations}/{max_iterations}"
            )

            logger.info(f"Goal execution complete:\n{execution_summary}")

            return {
                'goal_id': goal_id,
                'status': final_status.value,
                'tasks_completed': tasks_completed,
                'tasks_failed': tasks_failed,
                'iterations_used': iterations,
                'max_iterations': max_iterations,
                'final_progress': goal.progress_percentage,
                'execution_summary': execution_summary,
                'goal': goal
            }

        finally:
            # Restore original approval setting
            self.require_approval = original_require_approval
            if auto_approve:
                logger.info("Auto-approval disabled, approval setting restored")

    def decompose_and_create_goal(
        self,
        user_request: str,
        user_id: int,
        conversation_context: Optional[str] = None,
        auto_execute: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a user request and automatically create a goal if appropriate.

        This method uses the GoalDecomposerLLM to determine if a request should
        be broken down into a structured goal with subtasks. If so, it creates
        the goal and optionally starts autonomous execution.

        Args:
            user_request: The user's request to analyze
            user_id: ID of the user making the request
            conversation_context: Optional recent conversation for context
            auto_execute: If True, automatically start executing the goal

        Returns:
            Dictionary with:
            - created: bool - Whether a goal was created
            - goal_id: int - ID of created goal (if created)
            - goal: Goal object (if created)
            - reasoning: str - Why goal was/wasn't created
            - execution_result: dict - Result of autonomous execution (if auto_execute)
            Returns None if decomposition fails.
        """
        if not self.goal_enabled:
            logger.warning("Goal management is disabled, cannot decompose request")
            return {
                'created': False,
                'reasoning': 'Goal management system is disabled'
            }

        logger.info(f"Analyzing request for goal decomposition: {user_request[:100]}...")

        try:
            # Use GoalDecomposerLLM to analyze the request
            proposal = self.goal_decomposer.decompose_request(
                user_request=user_request,
                conversation_context=conversation_context
            )

            if proposal is None:
                logger.info("Request is a simple task, not creating goal")
                return {
                    'created': False,
                    'reasoning': 'Request does not require goal tracking (single task)'
                }

            # Create the goal
            goal_id = self.goal_manager.create_goal(proposal, user_id=user_id)
            goal = self.goal_manager.get_goal(goal_id, include_subtasks=True)

            logger.info(
                f"Created goal {goal_id}: {goal.goal_text} "
                f"with {len(goal.subtasks)} subtasks"
            )

            result = {
                'created': True,
                'goal_id': goal_id,
                'goal': goal,
                'reasoning': f'Request decomposed into {len(goal.subtasks)} subtasks'
            }

            # Auto-execute if requested
            if auto_execute:
                logger.info(f"Auto-executing goal {goal_id}")
                execution_result = self.execute_goal_autonomously(
                    goal_id=goal_id,
                    user_id=user_id,
                    auto_approve=True
                )
                result['execution_result'] = execution_result

            return result

        except Exception as e:
            logger.error(f"Error in goal decomposition: {e}", exc_info=True)
            return {
                'created': False,
                'reasoning': f'Decomposition failed: {str(e)}'
            }

    def _check_auto_goal_creation(
        self,
        user_input: str,
        user_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Check if user input should be automatically converted to a goal.

        This is called at the beginning of process_user_input to detect
        multi-step tasks and offer to create a goal for them.

        Args:
            user_input: The user's request
            user_id: User ID for goal creation

        Returns:
            Result dict if goal was created and executed, None if normal processing should continue
        """
        try:
            # Get recent conversation context for the decomposer
            conversation_context = None
            if hasattr(self.persona_llm, 'conversation_history'):
                # Get last 3 messages for context
                recent = self.persona_llm.conversation_history[-6:]  # 3 exchanges
                conversation_context = "\n".join([
                    f"{msg['role']}: {msg['content'][:200]}"
                    for msg in recent
                ])

            logger.info("Checking if request should become a goal...")

            # Ask the decomposer
            proposal = self.goal_decomposer.decompose_request(
                user_request=user_input,
                conversation_context=conversation_context
            )

            # If decomposer says this is a simple task, continue normally
            if proposal is None:
                logger.debug("Request is a simple task, continuing with normal processing")
                return None

            # Decomposer suggests this should be a goal!
            logger.info(
                f"Auto-detected goal opportunity: {proposal.goal_text} "
                f"({len(proposal.subtasks)} subtasks)"
            )

            # Ask user for confirmation
            print("\n" + "="*70)
            print("🎯 MULTI-STEP TASK DETECTED")
            print("="*70)
            print(f"\nGoal: {proposal.goal_text}")
            print(f"Type: {proposal.goal_type.value}")
            print(f"Subtasks: {len(proposal.subtasks)}")
            print("\nSubtasks:")
            for i, subtask in enumerate(proposal.subtasks[:5], 1):  # Show first 5
                print(f"  {i}. {subtask.task_text}")
            if len(proposal.subtasks) > 5:
                print(f"  ... and {len(proposal.subtasks) - 5} more")

            print("\n" + "-"*70)

            # Get user confirmation
            response = input("Create goal and execute autonomously? (yes/no/manual) [yes]: ").strip().lower()

            if response in ['n', 'no']:
                print("Continuing with normal single-task processing...\n")
                return None

            # User wants to create the goal
            goal_id = self.goal_manager.create_goal(proposal, user_id=user_id)
            goal = self.goal_manager.get_goal(goal_id, include_subtasks=True)

            print(f"\n✓ Goal created (ID: {goal_id})")

            # Check if we should auto-execute
            auto_execute = self.config.get('goals', {}).get('auto_execute_goals', True)

            if response == 'manual':
                # User wants manual execution
                print("Goal created but not executing. Use goal execution commands to run it.\n")
                return {
                    'response': f"Goal created: {goal.goal_text} (ID: {goal_id}, {len(goal.subtasks)} subtasks)",
                    'actions_taken': [],
                    'goal_created': True,
                    'goal_id': goal_id,
                    'goal': goal
                }

            if auto_execute or response in ['y', 'yes', '']:
                # Execute the goal autonomously
                print("\n🚀 Starting autonomous execution...\n")
                print("="*70)

                exec_result = self.execute_goal_autonomously(
                    goal_id=goal_id,
                    user_id=user_id,
                    auto_approve=True,  # Auto-approve tool executions during goal execution
                    save_checkpoints=True
                )

                print("="*70)
                print("\n✅ GOAL EXECUTION COMPLETE\n")
                print(f"Status: {exec_result['status']}")
                print(f"Progress: {exec_result['final_progress']}%")
                print(f"Tasks completed: {exec_result['tasks_completed']}/{len(goal.subtasks)}")
                if exec_result['tasks_failed'] > 0:
                    print(f"Tasks failed: {exec_result['tasks_failed']}")
                print()

                # Return formatted result
                return {
                    'response': exec_result['execution_summary'],
                    'actions_taken': [{
                        'goal_id': goal_id,
                        'goal_text': goal.goal_text,
                        'subtasks_completed': exec_result['tasks_completed'],
                        'status': exec_result['status']
                    }],
                    'goal_created': True,
                    'goal_id': goal_id,
                    'goal': goal,
                    'execution_result': exec_result
                }

        except KeyboardInterrupt:
            # User interrupted, continue with normal processing
            print("\n\nGoal creation cancelled, continuing with normal processing...\n")
            return None

        except Exception as e:
            logger.error(f"Error in auto-goal detection: {e}", exc_info=True)
            print(f"\n⚠ Error during goal detection: {e}")
            print("Continuing with normal processing...\n")
            return None
