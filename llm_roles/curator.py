"""
Memory Curator LLM - Reviews interactions to propose memory updates.

This is a stateless LLM that:
- Receives conversation segments
- Proposes memories to persist
- Does NOT write to memory directly (orchestrator decides)
"""

import json
import logging
import re
import requests
from typing import List, Dict, Any, Optional

from memory.schemas import MemoryProposal, MemoryType

logger = logging.getLogger(__name__)


class MemoryCuratorLLM:
    """
    The Memory Curator LLM reviews interactions and proposes memory updates.

    This is STATELESS - each curation is independent.
    The orchestrator decides which proposals to actually store.
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
        cleaned = re.sub(r'\n\n\n+', '\n\n', cleaned)
        return cleaned.strip()

    def _build_system_prompt(self) -> str:
        """Build the system prompt for memory curation."""
        return """You are a memory curator for an AI assistant named Jarvis. Your job is to review interactions and decide what should be remembered for future conversations.

MEMORY TYPES:
- identity: Stable facts about the user (name, role, location, background)
  Example: "User's name is Steve"
- preference: User likes/dislikes, communication style, tool preferences
  Example: "User prefers Python over JavaScript"
- capability: What tools and skills the system has or user has
  Example: "Jarvis can use the grep tool to search files"
- project: Current work, goals, ongoing tasks, project context
  Example: "User is building a voice assistant called Jarvis"
- episodic: Past events, conversations, decisions, interactions
  Example: "We discussed adding RAG memory system on Jan 8, 2026"
- social: Communication boundaries, tone preferences, working style
  Example: "User prefers concise responses without excessive praise"

CONFIDENCE LEVELS (how certain are you):
- 1.0: User explicitly stated the fact
- 0.9: Very strongly implied by user's statement
- 0.8: Strongly implied from context
- 0.7: Moderately implied
- 0.6: Inferred from context
- 0.5: Weak inference
- 0.4: Speculative (rarely use this)

IMPORTANCE LEVELS (how critical for future interactions):
- 1.0: Critical identity information or key preferences
- 0.9: Very important (major project goals, core capabilities)
- 0.8: Important (significant preferences, ongoing work)
- 0.7: Moderately important (useful context)
- 0.6: Somewhat important (minor preferences)
- 0.5: Useful but not critical
- 0.4: Nice to know (most episodic events)
- 0.3: Low importance (rarely use)

SOURCE TYPES (where did this fact come from):
- user: Directly stated by the user
  Example: "My name is Steve" -> source_type: user
- tool_output: From a tool execution result
  Example: grep found "version 2.0" in file -> source_type: tool_output, source_identity: grep
- web: From web search or fetch_url
  Example: fetched data from example.com -> source_type: web, source_identity: example.com
- inference: LLM inferred from conversation
  Example: User asked about Python, probably uses Python -> source_type: inference

GUIDELINES:
1. Only propose memories for SIGNIFICANT information
2. Don't remember trivial queries like "hello" or "what's the time"
3. Extract FACTS, not opinions about facts
4. Be specific and concise (one clear statement per memory)
5. Don't remember temporary context or ephemeral details
6. If user corrects previous information, note the NEW fact (old will be superseded)
7. When unsure, err on the side of NOT remembering
8. ALWAYS identify the source_type for fact verification

OUTPUT FORMAT - Respond with a JSON array only:
```json
[
    {
        "memory_text": "Clear, concise statement of what to remember",
        "memory_type": "<ONE OF: identity, preference, capability, project, episodic, social>",
        "confidence": 0.85,
        "importance": 0.7,
        "source_type": "<ONE OF: user, tool_output, web, inference>",
        "source_identity": "<tool name, domain, or 'user' for direct statements>",
        "reasoning": "Why this should be remembered and how confident we are"
    }
]
```

CRITICAL:
- memory_type must be EXACTLY ONE of: identity, preference, capability, project, episodic, social
- source_type must be EXACTLY ONE of: user, tool_output, web, inference
  * Use "user" for direct user statements: "My name is Steve"
  * Use "tool_output" for facts from tool results
  * Use "web" for information from web searches
  * Use "inference" for things you deduce from context
- source_identity: Specific source within the type
  * For user: use "user"
  * For tool_output: use the tool name (e.g., "find_files")
  * For web: use the domain (e.g., "github.com")
  * For inference: use "curator_llm"
- Do NOT use pipes (|) or multiple values - choose the SINGLE best fit
- Use lowercase only for enum values

If NOTHING significant should be remembered, return an empty array: []

Remember: Quality over quantity. Only propose memories that will genuinely help future interactions."""

    def propose_memories(
        self,
        user_query: str,
        conversation_snippet: str,
        tool_results: str,
        assistant_response: str
    ) -> List[MemoryProposal]:
        """
        Analyze interaction and propose 0-N memories to store.

        Args:
            user_query: Original user query
            conversation_snippet: Recent conversation context (last 4 messages)
            tool_results: Summary of tools executed
            assistant_response: Final response to user

        Returns:
            List of MemoryProposal objects (empty if nothing to remember)
        """
        # Build user message with full context
        user_message = f"""Review this interaction and propose any memories worth storing.

USER QUERY:
{user_query}

CONVERSATION CONTEXT:
{conversation_snippet}

TOOLS EXECUTED:
{tool_results}

ASSISTANT RESPONSE:
{assistant_response}

Analyze this interaction and output a JSON array of memories to store. Return [] if nothing significant."""

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

            # Extract JSON array
            proposals_json = self._extract_json_array(clean_message)

            if not proposals_json:
                logger.info("Curator proposed no memories")
                return []

            # Convert to MemoryProposal objects
            proposals = []
            for item in proposals_json:
                try:
                    # Validate required fields
                    if not all(k in item for k in ['memory_text', 'memory_type', 'confidence', 'importance', 'reasoning']):
                        logger.warning(f"Skipping invalid proposal: {item}")
                        continue

                    # Validate memory_type is valid
                    try:
                        mem_type = MemoryType(item['memory_type'])
                    except ValueError:
                        logger.warning(f"Invalid memory_type: {item['memory_type']}")
                        continue

                    # Parse source_type if provided
                    from memory.schemas import MemorySourceType
                    source_type = None
                    if 'source_type' in item:
                        try:
                            source_type = MemorySourceType(item['source_type'])
                        except ValueError:
                            logger.warning(f"Invalid source_type: {item['source_type']}")
                            # Continue anyway with None, will be inferred later

                    # Create proposal
                    proposal = MemoryProposal(
                        memory_text=item['memory_text'],
                        memory_type=mem_type,
                        confidence=float(item['confidence']),
                        importance=float(item['importance']),
                        reasoning=item['reasoning'],
                        source_type=source_type,
                        source_identity=item.get('source_identity')  # Optional
                    )

                    proposals.append(proposal)

                except Exception as e:
                    logger.error(f"Error parsing proposal: {e}")
                    continue

            logger.info(f"Curator proposed {len(proposals)} valid memories")
            return proposals

        except Exception as e:
            logger.error(f"Error in memory curation: {e}")
            return []

    def _extract_json_array(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """
        Extract JSON array from text.

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
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
            elif in_json_block:
                json_content.append(line)

        # Try raw JSON array
        try:
            # Find first [ and last ]
            start = text.find('[')
            end = text.rfind(']') + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                if isinstance(parsed, list):
                    return parsed
        except json.JSONDecodeError:
            pass

        logger.warning("Could not extract JSON array from curator response")
        return None
