"""
Goal Decomposer LLM - Breaks down user requests into goals with subtasks.

This LLM analyzes user requests and proposes structured goals with:
- Sequential subtasks
- Dependency relationships
- Appropriate priority and context
"""

import json
import logging
import re
import requests
from typing import Optional

from goals.schemas import GoalProposal, SubtaskProposal, GoalType, Priority

logger = logging.getLogger(__name__)


class GoalDecomposerLLM:
    """
    The Goal Decomposer LLM analyzes user requests and proposes structured goals.

    This is STATELESS - each decomposition is independent.
    """

    def __init__(self, ollama_host: str, ollama_port: int, model: str, timeout: int = 180):
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.model = model
        self.timeout = timeout
        self.base_url = f"http://{ollama_host}:{ollama_port}"

    def _strip_think_tags(self, text: str) -> str:
        """Remove <think>...</think> tags from model output."""
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

        # Handle orphaned closing tags
        if '</think>' in cleaned:
            closing_tag_pos = cleaned.rfind('</think>')
            if closing_tag_pos != -1:
                cleaned = cleaned[closing_tag_pos + len('</think>'):]

        cleaned = re.sub(r'\n\n\n+', '\n\n', cleaned)
        return cleaned.strip()

    def _build_system_prompt(self) -> str:
        """Build the system prompt for goal decomposition."""
        return """You are a goal decomposition expert for Jarvis AI assistant. Your job is to analyze user requests and break them down into structured goals with subtasks.

GOAL TYPES:
- task: Single-session work (can complete in one sitting)
- project: Multi-session work spanning days/weeks
- learning: Educational goals with practice steps
- research: Investigation and information gathering
- maintenance: Ongoing upkeep and monitoring

PRIORITY LEVELS:
- urgent: Time-sensitive, do immediately
- high: Important, do soon
- medium: Normal priority (default)
- low: Nice to have, do when time permits

DECOMPOSITION GUIDELINES:

1. WHEN TO CREATE A GOAL:

   MUST BE ALL OF:
   - An IMPERATIVE request (command, question requiring action)
   - Requires 2+ discrete, actionable steps
   - Steps have clear dependencies or sequence
   - Work spans multiple tools or operations

   Examples of VALID goals:
   ✓ "Set up a development environment" → 3-5 subtasks
   ✓ "Deploy application to server" → 4-6 subtasks
   ✓ "Analyze log files and fix errors" → 3-4 subtasks
   ✓ "Create a web scraper for news articles" → 4-6 subtasks

   NOT goals (single tasks):
   ✗ "List files in a directory" → Single tool call
   ✗ "Read a file" → Single operation
   ✗ "Create a file" → Single operation

   NOT goals (informational/conversational):
   ✗ "The project is located at /home/steve/projects" → Just providing info
   ✗ "I like coffee" → Stating preference (store in memory)
   ✗ "My name is Steve" → Declarative statement
   ✗ "Thanks for the help" → Conversational
   ✗ "I'm working on a Python project" → Background info

   EDGE CASES - Be conservative:
   ~ "I need to add feature X" → Vague, ask for clarification instead
   ~ "Can you help with Y?" → Too broad, not specific enough
   ~ Single-sentence requests → Usually NOT goals unless clearly multi-step

2. SUBTASK BREAKDOWN:
   - Each subtask should be concrete and actionable
   - Use imperative verbs: "Install X", "Create Y", "Configure Z"
   - Each subtask should be verifiable (can check if done)
   - Keep subtasks focused (one clear objective each)

   Good subtasks:
   ✓ "Install Python 3.11 from deadsnakes PPA"
   ✓ "Create virtual environment in project directory"
   ✓ "Install dependencies from requirements.txt"

   Bad subtasks:
   ✗ "Do Python stuff" (too vague)
   ✗ "Install Python and set up environment" (multiple steps)
   ✗ "Make it work" (not actionable)

3. DEPENDENCY IDENTIFICATION:
   - task_order: Sequential number (1, 2, 3...)
   - prerequisites: List of task_order numbers this depends on

   Dependency patterns:

   Sequential (each depends on previous):
   - Task 1: prerequisites = []
   - Task 2: prerequisites = [1]
   - Task 3: prerequisites = [2]

   Parallel (independent tasks):
   - Task 1: prerequisites = []
   - Task 2: prerequisites = []
   - Task 3: prerequisites = []

   Diamond (parallel then merge):
   - Task 1: prerequisites = []
   - Task 2: prerequisites = [1]
   - Task 3: prerequisites = [1]
   - Task 4: prerequisites = [2, 3]  # Waits for both

4. CONTEXT:
   - Provide helpful background information
   - Mention constraints or requirements
   - Include relevant environment details

   Example: "Ubuntu 22.04 server, need secure remote access, existing firewall rules in place"

5. REASONABLE SCOPE:
   - 2-10 subtasks typical
   - Too few (1): Not a goal, just a task
   - Too many (15+): Break into multiple goals
   - Complex projects can have 10-15 subtasks max

OUTPUT FORMAT - Respond with JSON only:
```json
{
    "should_create_goal": true,
    "reasoning": "Why this should be a goal vs single task",
    "goal_text": "Clear description of the overall objective",
    "goal_type": "task|project|learning|research|maintenance",
    "context": "Relevant background and constraints",
    "priority": "low|medium|high|urgent",
    "subtasks": [
        {
            "task_text": "Concrete, actionable task description",
            "task_order": 1,
            "prerequisites": [],
            "max_retries": 3
        },
        {
            "task_text": "Next task",
            "task_order": 2,
            "prerequisites": [1],
            "max_retries": 3
        }
    ]
}
```

If should_create_goal is false (simple single task), return:
```json
{
    "should_create_goal": false,
    "reasoning": "This is a single operation that doesn't need goal tracking",
    "suggested_action": "Direct user message for simple execution"
}
```

CRITICAL RULES:
- Be VERY conservative: When in doubt, return should_create_goal=false
- ONLY create goals for clear, multi-step REQUESTS (not statements or questions)
- Declarative statements (facts, preferences) are NEVER goals
- Conversational messages are NEVER goals
- Vague requests should be clarified, NOT turned into goals
- Single operations are NEVER goals
- All subtasks must be concrete and actionable
- Dependencies must be logical (no circular dependencies)
- task_order must be sequential (1, 2, 3...)

DEFAULT ASSUMPTION: Most user messages are NOT goals. Only create when clearly multi-step.
"""

    def decompose_request(
        self,
        user_request: str,
        conversation_context: Optional[str] = None
    ) -> Optional[GoalProposal]:
        """
        Analyze a user request and propose a goal if appropriate.

        Args:
            user_request: The user's request to analyze
            conversation_context: Optional recent conversation for context

        Returns:
            GoalProposal if request should be a goal, None if single task
        """
        # Build user message
        user_message = f"""Analyze this user request and determine if it should be a goal with subtasks.

USER REQUEST:
{user_request}"""

        if conversation_context:
            user_message += f"""

RECENT CONVERSATION CONTEXT:
{conversation_context}"""

        user_message += "\n\nRespond with JSON only."

        try:
            # Call Ollama
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': self._build_system_prompt()},
                        {'role': 'user', 'content': user_message}
                    ],
                    'stream': False,
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            raw_message = result['message']['content']

            # Strip think tags
            clean_message = self._strip_think_tags(raw_message)

            # Extract JSON
            decomposition = self._extract_json(clean_message)

            if not decomposition:
                logger.warning("Could not extract JSON from decomposer response")
                return None

            # Check if should create goal
            if not decomposition.get('should_create_goal', False):
                logger.info(f"Request is single task: {decomposition.get('reasoning')}")
                return None

            # Validate required fields
            required = ['goal_text', 'goal_type', 'subtasks']
            if not all(k in decomposition for k in required):
                logger.warning(f"Missing required fields in decomposition: {decomposition}")
                return None

            # Parse goal type
            try:
                goal_type = GoalType(decomposition['goal_type'])
            except ValueError:
                logger.warning(f"Invalid goal_type: {decomposition['goal_type']}, defaulting to TASK")
                goal_type = GoalType.TASK

            # Parse priority
            priority_str = decomposition.get('priority', 'medium')
            try:
                priority = Priority(priority_str)
            except ValueError:
                logger.warning(f"Invalid priority: {priority_str}, defaulting to MEDIUM")
                priority = Priority.MEDIUM

            # Parse subtasks
            subtasks = []
            for st_data in decomposition['subtasks']:
                try:
                    subtask = SubtaskProposal(
                        task_text=st_data['task_text'],
                        task_order=st_data['task_order'],
                        prerequisites=st_data.get('prerequisites', []),
                        max_retries=st_data.get('max_retries', 3)
                    )
                    subtasks.append(subtask)
                except Exception as e:
                    logger.error(f"Error parsing subtask: {e}")
                    continue

            if not subtasks:
                logger.warning("No valid subtasks parsed")
                return None

            # Create proposal
            proposal = GoalProposal(
                goal_text=decomposition['goal_text'],
                goal_type=goal_type,
                context=decomposition.get('context'),
                priority=priority,
                subtasks=subtasks
            )

            logger.info(f"Decomposed request into goal with {len(subtasks)} subtasks")
            return proposal

        except Exception as e:
            logger.error(f"Error in goal decomposition: {e}")
            return None

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Extract JSON object from text.

        Handles both code blocks and raw JSON.
        """
        # Try code blocks first
        lines = text.split('\n')
        in_json_block = False
        json_content = []

        for line in lines:
            if line.strip().startswith('```json'):
                in_json_block = True
                json_content = []
            elif line.strip() == '```' and in_json_block:
                in_json_block = False
                # Try to parse
                try:
                    parsed = json.loads('\n'.join(json_content))
                    return parsed
                except json.JSONDecodeError:
                    pass
            elif in_json_block:
                json_content.append(line)

        # Try raw JSON object
        try:
            # Find first { and last }
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                return parsed
        except json.JSONDecodeError:
            pass

        logger.warning("Could not extract JSON from decomposer response")
        return None
