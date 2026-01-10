"""
Introspection LLM - Reflective analysis of task execution.

This LLM performs qualitative analysis after task completion to extract
deeper insights beyond simple pattern matching.

Key questions it answers:
- What went wrong and why?
- What was inefficient?
- What surprised me?
- What generalizable lessons can I learn?
"""

import json
import logging
import re
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IntrospectionInsight:
    """
    A reflective insight from task execution analysis.

    This captures qualitative learning that goes beyond simple
    "this strategy worked" pattern matching.
    """
    root_cause: Optional[str]           # Why did it fail initially?
    inefficiencies: List[str]            # What could have been done better?
    surprises: List[str]                 # What was unexpected?
    generalizable_lesson: Optional[str]  # Abstract lesson applicable to future tasks
    confidence: float                     # How confident are we in this analysis?
    task_context: str                    # What type of task was this?

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'root_cause': self.root_cause,
            'inefficiencies': self.inefficiencies,
            'surprises': self.surprises,
            'generalizable_lesson': self.generalizable_lesson,
            'confidence': self.confidence,
            'task_context': self.task_context
        }


class IntrospectionLLM:
    """
    The Introspection LLM performs post-task reflection.

    Unlike procedural memory which records "what worked",
    introspection asks "why did it work/fail" and "what can I learn".

    This generates narrative insights that enrich our understanding
    of problem-solving patterns.
    """

    def __init__(self, ollama_host: str, ollama_port: int, model: str, timeout: int = 120):
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
        """Build system prompt for introspection analysis."""
        return """You are an introspection expert for Jarvis AI assistant. Your job is to analyze task execution and extract deep, qualitative insights that go beyond simple pattern matching.

CORE PRINCIPLE:
Don't just record "what worked" - understand WHY it worked or failed, and extract generalizable lessons.

YOUR ANALYSIS PROCESS:

1. **Root Cause Analysis**
   - If the task failed initially, why?
   - What assumptions were incorrect?
   - What information was missing?
   - What environmental factors contributed?

   Examples:
   ✓ "Assumed file path existed without verification"
   ✓ "Misunderstood user intent - they wanted X but we did Y"
   ✓ "Tool required parameter we didn't have access to"
   ✗ "It just didn't work" (too vague)

2. **Inefficiency Detection**
   - Were unnecessary steps taken?
   - Could we have used fewer tools?
   - Did we gather information we already had?
   - Were there redundant operations?

   Examples:
   ✓ "Used write_file before checking if directory exists"
   ✓ "Listed entire directory when we only needed to check one file"
   ✓ "Made 3 web requests when 1 would suffice"
   ✗ "Could have been faster" (not actionable)

3. **Surprise Identification**
   - What was unexpected about this task?
   - What edge cases did we encounter?
   - What worked differently than anticipated?
   - What new constraints did we discover?

   Examples:
   ✓ "Directory permissions were more restrictive than expected"
   ✓ "File format was different from typical examples"
   ✓ "Tool output included unexpected metadata"
   ✗ "Something weird happened" (too vague)

4. **Generalizable Lessons**
   - What abstract principle can we extract?
   - How does this apply to similar tasks?
   - What pattern should we remember?
   - What heuristic emerges?

   Examples:
   ✓ "For file operations, always verify path existence before writing"
   ✓ "When user request is ambiguous, ask clarifying questions first"
   ✓ "Complex tasks benefit from decomposition before execution"
   ✗ "Be more careful" (not actionable)

WHEN TO GENERATE INSIGHTS:

Generate insights when:
✓ Task required retries (failure → success journey has learning value)
✓ Task succeeded but took inefficient path
✓ Task revealed unexpected edge cases
✓ Task exposed gaps in our understanding

Skip insights when:
✗ Task succeeded on first try with expected approach
✗ Task was too simple to yield generalizable lessons
✗ No clear learning opportunity present

OUTPUT FORMAT - Respond with JSON only:
```json
{
    "has_insights": true,
    "root_cause": "Clear explanation of why initial approach failed (null if task succeeded first try)",
    "inefficiencies": [
        "Specific inefficiency 1",
        "Specific inefficiency 2"
    ],
    "surprises": [
        "Unexpected aspect 1",
        "Unexpected aspect 2"
    ],
    "generalizable_lesson": "Abstract principle that applies to future similar tasks",
    "confidence": 0.85,
    "reasoning": "Why we extracted these insights and how confident we are"
}
```

If no meaningful insights can be extracted:
```json
{
    "has_insights": false,
    "reasoning": "Task was straightforward with no learning opportunities"
}
```

CRITICAL RULES:
- Be specific and actionable, not vague
- Focus on "why" and "how", not just "what"
- Extract principles that generalize beyond this specific task
- Empty arrays are fine if no inefficiencies/surprises found
- Confidence should reflect certainty of the analysis (0.0-1.0)
- If task succeeded first try and was straightforward, return has_insights=false

Remember: The goal is to make Jarvis smarter through reflection, not just record statistics."""

    def analyze_execution(
        self,
        original_task: str,
        task_context: str,
        attempts: List[Dict[str, Any]],
        final_result: Dict[str, Any],
        tools_used: List[str]
    ) -> Optional[IntrospectionInsight]:
        """
        Analyze task execution and generate introspective insights.

        Args:
            original_task: The user's original request
            task_context: Classified context (filesystem, web_retrieval, etc.)
            attempts: List of attempt dicts with success/failure info
            final_result: Final result dict from orchestrator
            tools_used: List of tool names that were used

        Returns:
            IntrospectionInsight if meaningful insights extracted, None otherwise
        """
        # Build analysis prompt
        analysis_prompt = self._build_analysis_prompt(
            original_task,
            task_context,
            attempts,
            final_result,
            tools_used
        )

        try:
            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': self._build_system_prompt()},
                        {'role': 'user', 'content': analysis_prompt}
                    ],
                    'stream': False,
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            raw_message = result['message']['content']

            # Clean think tags
            clean_message = self._strip_think_tags(raw_message)

            # Extract JSON
            insight_data = self._extract_json(clean_message)

            if not insight_data:
                logger.warning("Could not parse introspection response")
                return None

            # Check if insights were found
            if not insight_data.get('has_insights', False):
                logger.debug(f"No insights for task: {insight_data.get('reasoning', 'No reason given')}")
                return None

            # Build IntrospectionInsight
            insight = IntrospectionInsight(
                root_cause=insight_data.get('root_cause'),
                inefficiencies=insight_data.get('inefficiencies', []),
                surprises=insight_data.get('surprises', []),
                generalizable_lesson=insight_data.get('generalizable_lesson'),
                confidence=float(insight_data.get('confidence', 0.7)),
                task_context=task_context
            )

            logger.info(
                f"Generated introspection insight: {insight.generalizable_lesson[:80] if insight.generalizable_lesson else 'N/A'}"
            )

            return insight

        except Exception as e:
            logger.error(f"Error during introspection: {e}")
            return None

    def _build_analysis_prompt(
        self,
        original_task: str,
        task_context: str,
        attempts: List[Dict[str, Any]],
        final_result: Dict[str, Any],
        tools_used: List[str]
    ) -> str:
        """Build the analysis prompt with execution details."""
        prompt = f"""Analyze this task execution and extract qualitative insights.

ORIGINAL TASK:
{original_task}

TASK CONTEXT: {task_context}

EXECUTION ATTEMPTS:
"""

        # Format attempts
        for i, attempt in enumerate(attempts, 1):
            success = attempt.get('success', False)
            status = "✓ SUCCESS" if success else "✗ FAILED"
            prompt += f"\nAttempt {i}: {status}\n"

            if not success:
                verification = attempt.get('verification', {})
                failure_type = verification.get('failure_type', 'unknown')
                reasoning = verification.get('reasoning', 'No details')
                prompt += f"  Failure Type: {failure_type}\n"
                prompt += f"  Reasoning: {reasoning}\n"

            actions = attempt.get('actions_taken', [])
            if actions:
                prompt += f"  Tools Used: {', '.join([a.get('tool_name', 'unknown') for a in actions])}\n"

        # Final result
        prompt += f"\nFINAL RESULT:\n"
        prompt += f"Success: {final_result.get('verification', {}).get('verified', True)}\n"
        prompt += f"Response: {final_result.get('response', '')[:200]}...\n"

        # Summary stats
        prompt += f"\nEXECUTION SUMMARY:\n"
        prompt += f"- Total attempts: {len(attempts)}\n"
        prompt += f"- Tools involved: {', '.join(set(tools_used))}\n"
        prompt += f"- Required retries: {len(attempts) > 1}\n"

        prompt += "\n\nBased on this execution, what insights can you extract? Focus on root causes, inefficiencies, surprises, and generalizable lessons."

        return prompt

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
