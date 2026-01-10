"""
Summarizer LLM - Condenses conversation history to maintain context.

This LLM creates concise summaries of long conversations to prevent
token limit issues while preserving essential context.
"""

import json
import logging
import re
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SummarizerLLM:
    """
    The Summarizer LLM condenses conversation history intelligently.

    Key principles:
    - Preserve decisions and conclusions
    - Keep important facts and context
    - Note unresolved items
    - Compress verbose exchanges
    - Maintain chronological coherence
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
        """Build system prompt for conversation summarization."""
        return """You are a conversation summarization expert for Jarvis AI assistant.

Your job is to create a CONCISE summary of conversation history that preserves essential context while reducing token usage.

WHAT TO PRESERVE:
1. **Decisions Made**: What was decided or agreed upon
2. **Facts Learned**: Important information discovered or shared
3. **User Preferences**: User's stated likes, dislikes, requirements
4. **Context Established**: File paths, project names, configurations
5. **Unresolved Items**: Open questions or pending actions
6. **Key Events**: Important actions taken (files created, commands run, etc.)

WHAT TO COMPRESS:
1. **Verbose explanations**: Reduce to key points
2. **Repeated concepts**: Mention once with "discussed multiple times"
3. **Intermediate steps**: Focus on outcomes, not every step
4. **Tool outputs**: Summarize results, not full outputs
5. **Greetings/pleasantries**: Omit unless contextually important

SUMMARY FORMAT:
Create a narrative summary organized chronologically. Use this structure:

```
## Conversation Summary

**Context Established:**
- [Key context items: project name, goals, file paths, etc.]

**Decisions & Conclusions:**
- [Important decisions made]
- [Conclusions reached]

**Actions Taken:**
- [Files created, commands run, configurations changed]

**Facts & Information:**
- [Important facts discovered or shared]

**User Preferences:**
- [User's stated preferences, requirements, constraints]

**Unresolved Items:**
- [Open questions, pending tasks, items to follow up on]

**Technical Details:**
- [Specific paths, versions, configurations that matter]
```

IMPORTANT RULES:
- Be CONCISE: Aim for 50-70% reduction in length
- Stay FACTUAL: Don't add interpretations
- Maintain CHRONOLOGY: Keep the order of events
- Be SPECIFIC: Include exact names, paths, versions when relevant
- Use BULLET POINTS: Easy to scan

Example:

Input (long conversation):
```
User: I'm working on a Flask application for my portfolio site
Assistant: Great! What features do you want?
User: I need user authentication, a blog section, and contact form
Assistant: [Long explanation of Flask authentication...]
User: Let's use Flask-Login
Assistant: Good choice. Here's how to set it up...
[200 lines of code and explanation]
User: Perfect! Now let's add the blog
...
```

Output (summary):
```
## Conversation Summary

**Context Established:**
- Working on Flask application for portfolio site
- Using Flask-Login for authentication

**Decisions & Conclusions:**
- Decided on Flask-Login for user authentication
- Will include: auth, blog section, contact form

**Actions Taken:**
- Set up Flask-Login configuration
- Created user model and login routes

**Unresolved Items:**
- Blog section implementation pending
- Contact form not yet started
```

Remember: The goal is to preserve context while reducing tokens by 50-70%."""

    def summarize_conversation(
        self,
        conversation_history: List[Dict[str, str]],
        preserve_recent: int = 4
    ) -> Optional[str]:
        """
        Summarize a conversation history.

        Args:
            conversation_history: List of message dicts with 'role' and 'content'
            preserve_recent: Number of recent messages to keep unsummarized

        Returns:
            Summary string, or None if summarization fails
        """
        if len(conversation_history) <= preserve_recent:
            logger.debug("Conversation too short to summarize")
            return None

        # Split into messages to summarize and recent messages to preserve
        messages_to_summarize = conversation_history[:-preserve_recent]

        if not messages_to_summarize:
            return None

        # Format conversation for summarization
        conversation_text = self._format_conversation(messages_to_summarize)

        logger.info(f"Summarizing {len(messages_to_summarize)} messages ({len(conversation_text)} chars)")

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': self._build_system_prompt()},
                        {'role': 'user', 'content': f"Summarize this conversation:\n\n{conversation_text}"}
                    ],
                    'stream': False,
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            raw_summary = result['message']['content']

            # Clean up think tags
            summary = self._strip_think_tags(raw_summary)

            logger.info(f"Summary created: {len(summary)} chars (reduction: {len(conversation_text) - len(summary)} chars)")

            return summary

        except Exception as e:
            logger.error(f"Error creating summary: {e}")
            return None

    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """Format conversation messages into a readable text block."""
        formatted = []

        for msg in messages:
            role = msg['role'].capitalize()
            content = msg['content']

            # Truncate very long messages for summary input
            if len(content) > 2000:
                content = content[:2000] + f"\n... [truncated, {len(content) - 2000} more chars]"

            formatted.append(f"{role}: {content}")

        return "\n\n".join(formatted)

    def estimate_tokens(self, text: str) -> int:
        """
        Rough estimate of token count.

        Approximation: ~4 chars per token for English text.
        This is conservative (slightly overestimates).

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return len(text) // 4

    def should_summarize(
        self,
        conversation_history: List[Dict[str, str]],
        max_tokens: int = 8000,
        threshold: float = 0.7
    ) -> bool:
        """
        Check if conversation should be summarized.

        Args:
            conversation_history: Current conversation
            max_tokens: Maximum token budget
            threshold: Trigger summarization at this % of max

        Returns:
            True if summarization is recommended
        """
        # Calculate total conversation length
        total_chars = sum(len(msg['content']) for msg in conversation_history)
        estimated_tokens = total_chars // 4  # ~4 chars per token

        trigger_threshold = max_tokens * threshold

        should_summarize = estimated_tokens >= trigger_threshold

        if should_summarize:
            logger.info(
                f"Summarization recommended: {estimated_tokens} tokens "
                f"(threshold: {trigger_threshold})"
            )

        return should_summarize
