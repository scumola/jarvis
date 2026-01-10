"""
Verifier LLM - Checks if tool results actually answered the user's query.

This is a stateless LLM that:
- Receives the original user query
- Receives the tool results and response
- Determines if the query was adequately answered
- Suggests corrections if needed
"""

import json
import logging
import re
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VerifierLLM:
    """
    The Verifier LLM evaluates whether tool execution results
    adequately answered the user's original question.

    This is STATELESS - each verification is independent.
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

    def verify_results(
        self,
        user_query: str,
        tool_results: str,
        assistant_response: str
    ) -> Dict[str, Any]:
        """
        Verify if the tool results adequately answered the user's query.

        Args:
            user_query: The original user question/request
            tool_results: Summary of what tools executed and what they found
            assistant_response: The assistant's final response to the user

        Returns:
            Dictionary with:
            - verified: bool - Whether the query was adequately answered
            - confidence: str - "high", "medium", or "low"
            - reasoning: str - Why verification passed/failed
            - suggestion: str - If failed, what should be done differently (optional)
        """
        system_prompt = """You are a verification system that checks if a user's query was adequately answered.

CRITICAL: You MUST respond with ONLY a JSON object. No explanatory text before or after. Just the JSON.

Your job is to:
1. Compare the user's original query with the results produced
2. Determine if the query was actually answered
3. Classify the failure type if verification fails
4. Provide reasoning for your decision
5. If the query was NOT adequately answered, suggest what should be done differently

RESPONSE FORMAT - Output ONLY this JSON structure (no other text):
```json
{
  "verified": true or false,
  "confidence": "high" or "medium" or "low",
  "reasoning": "Brief explanation of why verification passed or failed",
  "failure_type": "type of failure if verified=false (see below)",
  "suggestion": "If verification failed, what should be tried instead? (optional)"
}
```

FAILURE TYPES (required when verified=false):
- "misunderstood_intent": The task intent was not understood correctly
- "missing_constraints": Important constraints were ignored or missed
- "incorrect_assumptions": Wrong assumptions were made about the task
- "partial_solution": Answer is incomplete or only partially addresses the query
- "tool_misuse": Wrong tool was used or tool was used incorrectly
- "hallucinated_facts": Response contains unverified or invented information
- "insufficient_reasoning": Not enough depth of reasoning for the task
- "underspecified_search": Search was too broad or too narrow

Examples:

User Query: "Find all Python files"
Tool Results: Found 14 Python files (list provided)
Response: Listed all Python files with paths
Your Verification:
```json
{
  "verified": true,
  "confidence": "high",
  "reasoning": "Query asked for Python files and the tool found and listed them all"
}
```

User Query: "What is the capital of France?"
Tool Results: Found 3 Python files
Response: Here are 3 Python files
Your Verification:
```json
{
  "verified": false,
  "confidence": "high",
  "reasoning": "Query asked about French capital, but tools searched for files instead",
  "failure_type": "misunderstood_intent",
  "suggestion": "The assistant needs tools for web search or knowledge retrieval, not file operations"
}
```

User Query: "Read the README file"
Tool Results: Tried to read 'readme.md' - file not found
Response: The file 'readme.md' does not exist
Your Verification:
```json
{
  "verified": false,
  "confidence": "medium",
  "reasoning": "File not found, but the user asked to read README which typically exists",
  "failure_type": "incorrect_assumptions",
  "suggestion": "Try different capitalization: README.md, Readme.md, or list directory first to find the exact filename"
}
```

IMPORTANT RULES:
- Be strict but fair. Only mark as verified if the user's actual question was answered.
- ALWAYS respond with ONLY valid JSON - no commentary, no explanations outside the JSON
- Do NOT include any text before or after the JSON object
- If you're unsure, still provide valid JSON with "confidence": "low"
"""

        user_message = f"""Original User Query:
{user_query}

Tool Execution Results:
{tool_results}

Assistant's Final Response:
{assistant_response}

Was the user's query adequately answered?

RESPOND WITH ONLY THE JSON OBJECT - NO OTHER TEXT:"""

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

            # Extract JSON from response
            verification = self._extract_json(clean_message)

            if verification:
                return verification
            else:
                # Fallback if we couldn't parse JSON
                logger.warning("Could not parse verification JSON, assuming verified")
                return {
                    'verified': True,
                    'confidence': 'low',
                    'reasoning': 'Could not parse verifier response',
                    'suggestion': None
                }

        except Exception as e:
            logger.error(f"Error in verification: {e}")
            # On error, assume verified (fail open)
            return {
                'verified': True,
                'confidence': 'low',
                'reasoning': f'Verification error: {e}',
                'suggestion': None
            }

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON object from text, looking for ```json blocks first."""
        # Strategy 1: Try to find JSON code block (most reliable)
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
                    json_str = '\n'.join(json_content).strip()
                    if json_str:
                        return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse JSON block: {e}")
            elif in_json_block:
                json_content.append(line)

        # Strategy 2: Try to find raw JSON object in text
        # Look for the outermost { ... } that forms valid JSON
        start_idx = text.find('{')
        if start_idx >= 0:
            # Try increasingly larger substrings until we find valid JSON
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

                # Track string state
                if char == '"':
                    in_string = not in_string
                    continue

                # Only count braces outside strings
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
                                logger.debug(f"Failed to parse JSON object: {e}")
                                break

        # Strategy 3: Log the problematic text for debugging
        logger.warning(f"Could not extract JSON from verifier response. First 200 chars: {text[:200]}")
        return None
