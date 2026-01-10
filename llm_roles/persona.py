"""
Persona LLM - The primary conversational agent.

This is the "face" of Jarvis - the long-running conversational context
that the user interacts with.
"""

import json
import logging
import re
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class PersonaLLM:
    """
    The Persona LLM handles:
    - Natural language conversation
    - Proposing structured actions (tool calls)
    - Maintaining conversational context

    It NEVER executes actions directly.
    """

    def __init__(self, ollama_host: str, ollama_port: int, model: str, timeout: int = 120, summarizer=None, summarization_config: Optional[Dict] = None):
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.model = model
        self.timeout = timeout
        self.base_url = f"http://{ollama_host}:{ollama_port}"

        # Conversation history with summarization support
        self.conversation_history: List[Dict[str, str]] = []
        self.conversation_summary: Optional[str] = None

        # Summarization support
        self.summarizer = summarizer
        self.summarization_config = summarization_config or {}

    def _strip_think_tags(self, text: str) -> str:
        """
        Remove <think>...</think> tags from model output.
        Some models use these for internal reasoning that shouldn't be shown to users.

        Handles cases where:
        1. Both tags present: <think>...</think>
        2. Only closing tag present (qwen bug): ...content...</think>
        """
        # First, remove properly formatted think tags
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

        # Handle case where opening tag is missing but closing tag exists
        # Strip everything up to and including the closing tag
        if '</think>' in cleaned:
            # Find the last occurrence of </think> and remove everything before it
            closing_tag_pos = cleaned.rfind('</think>')
            if closing_tag_pos != -1:
                cleaned = cleaned[closing_tag_pos + len('</think>'):]

        # Clean up any extra whitespace left behind
        cleaned = re.sub(r'\n\n\n+', '\n\n', cleaned)
        return cleaned.strip()

    def _build_system_prompt(self, available_tools: List[Dict], memory_context: Optional[Dict] = None) -> str:
        """Build the system prompt for the Persona LLM."""
        tools_description = "\n".join([
            f"- {tool['name']}: {tool['description']}\n  Parameters: {json.dumps(tool['parameters'], indent=2)}"
            for tool in available_tools
        ])

        # Build memory context section if memories are available
        memory_section = ""
        if memory_context and memory_context.get('memories'):
            memories = memory_context['memories']
            memory_section = "\n\nRELEVANT MEMORIES:\n"
            memory_section += "Here are relevant facts from past interactions:\n\n"

            # Group by type for better organization
            by_type = {}
            for mem in memories:
                mem_type = mem.memory_type.value if hasattr(mem.memory_type, 'value') else str(mem.memory_type)
                if mem_type not in by_type:
                    by_type[mem_type] = []
                by_type[mem_type].append(mem)

            # Format memories by type
            for mem_type, mems in sorted(by_type.items()):
                memory_section += f"{mem_type.upper()}:\n"
                for mem in mems:
                    # Include confidence as a cue to the LLM
                    conf_marker = "✓" if mem.confidence > 0.8 else "~"
                    memory_section += f"  {conf_marker} {mem.memory_text}\n"
                memory_section += "\n"

            memory_section += "Use these memories to provide personalized, context-aware responses.\n"

        return f"""You are Jarvis, a helpful AI assistant with access to tools.

You can help the user by:
1. Having natural conversations
2. Using tools to perform actions

{memory_section}

AVAILABLE TOOLS:
{tools_description}

CRITICAL RULES:
1. You CANNOT execute actions directly - you can only PROPOSE tool calls
2. When you want to use a tool, output a JSON block with this exact format:
   ```json
   {{
     "action": "tool_call",
     "tool_name": "name_of_tool",
     "parameters": {{"param1": "value1", "param2": "value2"}},
     "reasoning": "why you want to use this tool"
   }}
   ```
3. You can propose multiple tool calls in sequence
4. Always explain to the user what you're doing
5. Be helpful, concise, and honest
6. If you don't know something, say so
7. Never pretend to have capabilities you don't have

WHEN TO USE TOOLS:
- Use tools for ACTIONS: reading files, searching, fetching data, creating files
- For simple questions, calculations, or explanations: respond directly (no tools needed)

WHEN NOT TO USE TOOLS:
- User is just chatting or providing information ("My name is X", "I like Y")
  → Just respond conversationally. Facts are automatically remembered.
- User asks a general question you can answer without tools
  → Respond directly with your knowledge
- User is thanking you or making small talk
  → Respond conversationally, no tools needed

When responding:
- For conversational messages: Just talk naturally, NO tool calls
- For action requests: Explain what you'll do, THEN propose tool calls
- After receiving tool results: Explain what happened to the user
"""

    def _check_and_summarize(self):
        """
        Check if conversation should be summarized and trigger summarization if needed.

        This prevents token limit issues by condensing older conversation history
        while preserving recent messages.
        """
        if not self.summarizer:
            return  # Summarization disabled

        # Check if summarization is needed
        max_tokens = self.summarization_config.get('max_tokens', 8000)
        threshold = self.summarization_config.get('trigger_threshold', 0.7)
        preserve_recent = self.summarization_config.get('preserve_recent', 6)

        if self.summarizer.should_summarize(
            self.conversation_history,
            max_tokens=max_tokens,
            threshold=threshold
        ):
            logger.info("Conversation length threshold reached, triggering summarization")

            # Create summary
            summary = self.summarizer.summarize_conversation(
                self.conversation_history,
                preserve_recent=preserve_recent
            )

            if summary:
                # Store the summary
                self.conversation_summary = summary

                # Trim old conversation history, keeping only recent messages
                self.conversation_history = self.conversation_history[-preserve_recent:]

                logger.info(
                    f"Conversation summarized. History reduced to {len(self.conversation_history)} "
                    f"recent messages. Summary: {len(summary)} chars"
                )
            else:
                logger.warning("Summarization failed, keeping full history")

    def generate_response(self, user_message: str, available_tools: List[Dict], memory_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Generate a response to the user's message.

        Args:
            user_message: The user's input
            available_tools: List of tool schemas available to this LLM
            memory_context: Optional dict with retrieved memories

        Returns:
            Dictionary with:
            - response_text: Natural language response
            - proposed_actions: List of tool invocations (if any)
        """
        # Add user message to history
        self.conversation_history.append({
            'role': 'user',
            'content': user_message
        })

        # Check if summarization is needed
        self._check_and_summarize()

        # Build messages for Ollama (now with memory context)
        messages = [
            {'role': 'system', 'content': self._build_system_prompt(available_tools, memory_context)}
        ]

        # Add conversation summary if present
        if self.conversation_summary:
            messages.append({
                'role': 'system',
                'content': f"[Previous conversation summary]\n{self.conversation_summary}\n[End summary]"
            })

        # Add recent conversation history (preserve_recent messages from config, default 6)
        preserve_recent = self.summarization_config.get('preserve_recent', 6)
        messages.extend(self.conversation_history[-preserve_recent:])

        try:
            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    'model': self.model,
                    'messages': messages,
                    'stream': False,
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            raw_message = result['message']['content']

            # Keep the raw message in history (with think tags for context continuity)
            self.conversation_history.append({
                'role': 'assistant',
                'content': raw_message
            })

            # Parse out any tool calls from the response
            proposed_actions = self._extract_tool_calls(raw_message)

            # Clean the message for user display (remove think tags)
            display_message = self._strip_think_tags(raw_message)

            return {
                'response_text': display_message,
                'proposed_actions': proposed_actions
            }

        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return {
                'response_text': f"[Error communicating with LLM: {e}]",
                'proposed_actions': []
            }

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract tool call JSON blocks from the LLM's response.

        Looks for ```json ... ``` blocks containing action definitions.
        """
        actions = []

        # Simple extraction - look for ```json blocks
        lines = text.split('\n')
        in_json_block = False
        json_content = []

        for line in lines:
            if line.strip().startswith('```json'):
                in_json_block = True
                json_content = []
            elif line.strip() == '```' and in_json_block:
                in_json_block = False
                # Try to parse the JSON
                try:
                    action = json.loads('\n'.join(json_content))
                    if action.get('action') == 'tool_call':
                        actions.append({
                            'tool_name': action.get('tool_name'),
                            'parameters': action.get('parameters', {}),
                            'reasoning': action.get('reasoning', '')
                        })
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON block: {e}")
            elif in_json_block:
                json_content.append(line)

        return actions

    def add_tool_result(self, tool_name: str, result: Dict[str, Any]):
        """
        Add a tool execution result to the conversation history.
        This lets the LLM see what happened when a tool was executed.

        Formats results in a human-readable way rather than raw JSON.
        """
        if not result.get('success'):
            # Error case - show the error
            result_message = f"[Tool '{tool_name}' failed: {result.get('error', 'Unknown error')}]"
        else:
            # Success - format based on tool type
            output = result.get('output', {})

            if tool_name == 'find_files':
                # Format find_files results concisely
                matches = output.get('matches', [])
                count = output.get('count', 0)
                pattern = output.get('pattern', '')

                result_message = f"[Tool 'find_files' found {count} files matching '{pattern}':\n"
                # Show up to 20 matches, then summarize
                for match in matches[:20]:
                    result_message += f"  - {match['path']} ({match['type']})\n"
                if count > 20:
                    result_message += f"  ... and {count - 20} more files]\n"
                else:
                    result_message += "]"

            elif tool_name == 'list_directory':
                # Format directory listing concisely
                entries = output.get('entries', [])
                count = output.get('count', 0)
                result_message = f"[Tool 'list_directory' found {count} items:\n"
                for entry in entries[:20]:
                    result_message += f"  - {entry['name']} ({entry['type']})\n"
                if count > 20:
                    result_message += f"  ... and {count - 20} more items]\n"
                else:
                    result_message += "]"

            elif tool_name == 'read_file':
                # Format file read - truncate very long files
                content = output.get('content', '')
                path = output.get('path', '')
                truncated = output.get('truncated', False)

                if len(content) > 2000:
                    content = content[:2000] + f"\n... (truncated, {len(content)} total chars)"

                result_message = f"[Tool 'read_file' read {path}:\n{content}\n"
                if truncated:
                    result_message += "(File was truncated)\n"
                result_message += "]"

            elif tool_name == 'fetch_url':
                # Format URL fetch results
                url = output.get('url', '')
                content = output.get('content', '')
                content_type = output.get('content_type', 'unknown')
                size = output.get('size_bytes', 0)

                # Truncate very long content
                if len(content) > 2000:
                    content = content[:2000] + f"\n... (truncated, {len(content)} total chars)"

                result_message = f"[Tool 'fetch_url' fetched {url}:\n"
                result_message += f"Content-Type: {content_type}, Size: {size} bytes\n\n"
                result_message += f"{content}\n]"

            elif tool_name == 'edit_file':
                # Format file edit results with diff
                path = output.get('path', '')
                backup = output.get('backup_path', '')
                diff = output.get('diff', '')

                result_message = f"[Tool 'edit_file' edited {path}:\n"
                result_message += f"Backup created: {backup}\n\n"
                result_message += f"Diff:\n{diff}\n]"

            elif tool_name == 'list_backups':
                # Format backup list
                backups = output.get('backups', [])
                count = output.get('count', 0)
                result_message = f"[Tool 'list_backups' found {count} backup(s):\n"
                for backup in backups[:10]:  # Show max 10
                    result_message += f"  - {backup['original_name']} @ {backup['timestamp']} ({backup['backup_file']})\n"
                if count > 10:
                    result_message += f"  ... and {count - 10} more\n"
                result_message += "]"

            elif tool_name == 'restore_backup':
                # Format restore results with diff
                restored_to = output.get('restored_to', '')
                backup_used = output.get('backup_used', '')
                diff = output.get('diff', '')

                result_message = f"[Tool 'restore_backup' restored {restored_to}:\n"
                result_message += f"From backup: {backup_used}\n\n"
                result_message += f"Diff:\n{diff}\n]"

            elif tool_name == 'get_news_headlines':
                # Format news headlines
                headlines = output.get('headlines', [])
                count = output.get('count', 0)
                query = output.get('query', '')

                result_message = f"[Tool 'get_news_headlines' found {count} headlines for '{query}':\n\n"
                for i, headline in enumerate(headlines, 1):
                    result_message += f"{i}. {headline['title']}\n"
                    if headline.get('snippet'):
                        result_message += f"   {headline['snippet']}\n"
                    result_message += f"   URL: {headline['url']}\n"
                    if headline.get('published'):
                        result_message += f"   Published: {headline['published']}\n"
                    result_message += "\n"
                result_message += "]"

            else:
                # Default: use compact JSON for other tools
                result_message = f"[Tool '{tool_name}' executed successfully. Output: {json.dumps(output)}]"

        self.conversation_history.append({
            'role': 'user',  # Tool results come from the system/user perspective
            'content': result_message
        })

    def reset(self):
        """Reset conversation history."""
        self.conversation_history = []
        logger.info("Persona LLM conversation history reset")
