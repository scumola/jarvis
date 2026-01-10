# Conversation Summarization

## Overview

Conversation Summarization is a feature that enables Jarvis to handle arbitrarily long conversations without hitting token limits or losing context. As conversations grow, older messages are automatically condensed into an intelligent summary while recent messages remain intact.

## Why It Matters

**Problem**: LLMs have finite context windows (typically 8K-32K tokens). Long conversations eventually exceed this limit, forcing you to either:
- Restart the conversation (losing all context)
- Manually summarize the conversation
- Truncate old messages (losing important information)

**Solution**: Jarvis automatically:
1. Monitors conversation length
2. Triggers summarization at a configurable threshold
3. Condenses older messages into a concise summary
4. Preserves recent messages for immediate context
5. Uses summary + recent messages for future responses

**Result**: Unlimited conversation length with preserved context.

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ PersonaLLM Conversation Flow                                 │
└─────────────────────────────────────────────────────────────┘

Before Summarization:
  [Msg 1] [Msg 2] [Msg 3] ... [Msg 18] [Msg 19] [Msg 20]
  ─────────────────────────────────────────────────────────────
  All messages sent to LLM (approaching token limit)


After Summarization (threshold reached at ~70% of max tokens):
  ┌──────────────────────┐
  │   Summary of         │
  │   Messages 1-14      │  (Condensed, 50-70% size reduction)
  └──────────────────────┘
                           [Msg 15] [Msg 16] ... [Msg 20]
                           ───────────────────────────────
                           Summary + 6 most recent messages

Next Turn:
  ┌──────────────────────┐
  │   Summary of         │
  │   Messages 1-14      │  [Msg 15] [Msg 16] ... [Msg 21]
  └──────────────────────┘  ───────────────────────────────
```

### Process Flow

1. **User sends message** → Added to `conversation_history`

2. **Check tokens** → `_check_and_summarize()` called
   - Estimates current conversation token count
   - If >= threshold (default: 70% of 8000 tokens = 5600 tokens)
   - Proceeds to step 3

3. **Trigger summarization** → `SummarizerLLM.summarize_conversation()`
   - Takes all messages except last N (default: 6)
   - Sends to LLM with special summarization prompt
   - LLM produces structured summary

4. **Update state**
   - Store summary in `conversation_summary`
   - Trim `conversation_history` to last N messages
   - Log the change

5. **Generate response**
   - System prompt (with tools, memory)
   - [Summary] (if present)
   - Recent conversation history
   - → Send to LLM for response

### Components

#### SummarizerLLM

The `SummarizerLLM` class (`llm_roles/summarizer.py`) handles the intelligent condensing of conversation history.

**Key Methods:**

```python
summarize_conversation(conversation_history, preserve_recent=4)
    """
    Create concise summary of older messages.

    Args:
        conversation_history: List of {role, content} dicts
        preserve_recent: Number of recent messages to keep unsummarized

    Returns:
        Summary string (markdown formatted)
    """

should_summarize(conversation_history, max_tokens=8000, threshold=0.7)
    """
    Check if conversation needs summarization.

    Returns:
        True if estimated tokens >= (max_tokens * threshold)
    """

estimate_tokens(text)
    """
    Estimate token count (~4 chars per token).
    Conservative approximation.
    """
```

**Summarization Prompt:**

The system prompt instructs the LLM to:
- **Preserve**: Decisions, facts, user preferences, context, unresolved items
- **Compress**: Verbose explanations, repeated concepts, intermediate steps
- **Format**: Structured markdown with clear sections
- **Target**: 50-70% size reduction

Example summary structure:
```markdown
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

#### PersonaLLM Integration

The `PersonaLLM` class (`llm_roles/persona.py`) is updated with:

**New Fields:**
```python
self.conversation_summary: Optional[str] = None  # Current summary
self.summarizer: SummarizerLLM               # Summarization engine
self.summarization_config: Dict              # Config (thresholds, etc.)
```

**New Method:**
```python
_check_and_summarize():
    """
    Check if summarization needed and trigger if so.
    Called at start of every generate_response().
    """
```

**Modified `generate_response()`:**
```python
def generate_response(self, user_message, available_tools, memory_context):
    # Add user message
    self.conversation_history.append({'role': 'user', 'content': user_message})

    # Check for summarization trigger
    self._check_and_summarize()  # NEW

    # Build context
    messages = [system_prompt]
    if self.conversation_summary:  # NEW
        messages.append({'role': 'system', 'content': f'[Summary]\n{self.conversation_summary}'})

    # Add recent history (not all history)
    preserve_recent = self.summarization_config.get('preserve_recent', 6)
    messages.extend(self.conversation_history[-preserve_recent:])  # CHANGED

    # Call LLM...
```

#### Orchestrator Integration

The `Orchestrator` (`orchestrator/engine.py`) initializes the summarizer and passes it to PersonaLLM:

```python
# Initialize Conversation Summarizer LLM (if enabled)
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

# Initialize Persona LLM (with summarizer support)
self.persona_llm = PersonaLLM(
    # ... other params ...
    summarizer=self.summarizer_llm,
    summarization_config=summarization_config
)
```

## Configuration

In `config/config.yaml`:

```yaml
# Ollama configuration
ollama:
  summarizer_timeout: 120  # Timeout for summarization LLM calls

# Conversation Summarization
summarization:
  enabled: true              # Enable/disable feature
  max_tokens: 8000           # Maximum conversation token budget
  trigger_threshold: 0.7     # Summarize at 70% of max tokens
  preserve_recent: 6         # Number of recent messages to keep unsummarized
```

### Configuration Parameters

**`enabled`** (boolean, default: `true`)
- Enable or disable automatic summarization
- If disabled, conversations will use truncation or grow unbounded

**`max_tokens`** (integer, default: `8000`)
- Maximum token budget for conversation context
- Includes: system prompt + summary + recent messages
- Set based on your model's context window (typically 8K-32K)

**`trigger_threshold`** (float, default: `0.7`)
- Fraction of `max_tokens` that triggers summarization
- Default: 70% of 8000 = 5600 tokens
- Lower = more frequent summarization (safer, more LLM calls)
- Higher = fewer summarizations (riskier, more tokens per call)

**`preserve_recent`** (integer, default: `6`)
- Number of recent messages to keep unsummarized
- These messages retain full detail
- Represents ~3 conversation turns (user + assistant pairs)
- Higher = more immediate context, less compression
- Lower = more aggressive compression

### Tuning Recommendations

**For short, focused conversations:**
```yaml
max_tokens: 4000
trigger_threshold: 0.8
preserve_recent: 4
```

**For long, exploratory conversations:**
```yaml
max_tokens: 16000
trigger_threshold: 0.6
preserve_recent: 10
```

**For models with large context windows (32K+):**
```yaml
max_tokens: 24000
trigger_threshold: 0.75
preserve_recent: 8
```

## Usage

### Automatic (Default)

Summarization happens transparently:

```
You: I'm working on a Python project called SuperCalculator.
Jarvis: Great! Tell me more about the project.

You: It's a scientific calculator with matrix operations.
Jarvis: Interesting! What features are you planning?

... [10 more exchanges] ...

You: What should I use for the GUI?
Jarvis: Based on our earlier discussion about SuperCalculator...
       [continues with full context]

[Behind the scenes: summarization triggered after message 12,
 condensed first 10 messages into summary, kept last 6 intact]
```

### Manual Control

You can disable summarization in config and use the traditional approach:

```yaml
summarization:
  enabled: false
```

Or adjust thresholds to control when it triggers:

```yaml
summarization:
  enabled: true
  trigger_threshold: 0.9  # Wait until 90% full before summarizing
```

## Benefits

### 1. Unlimited Conversation Length
- No need to restart conversations due to token limits
- Supports multi-hour debugging sessions
- Enables long-term project discussions

### 2. Context Preservation
- Important decisions preserved in summary
- Facts and user preferences retained
- Unresolved items tracked
- Recent messages kept in full detail

### 3. Cost Efficiency
- Reduces token usage for very long conversations
- Summary is much shorter than full history
- Only calls summarization LLM when needed

### 4. Better Response Quality
- Model sees condensed, relevant context instead of truncated messages
- No abrupt cutoffs mid-conversation
- Maintains chronological coherence

## What Gets Preserved vs. Compressed

### Preserved (High Priority)

✅ **Decisions Made**
- "Decided to use Flask-Login for authentication"
- "Chose NumPy for matrix operations"

✅ **Facts Learned**
- "Project name: SuperCalculator"
- "Location: /home/steve/projects/supercalc"

✅ **User Preferences**
- "User prefers tkinter over PyQt for simplicity"
- "Wants dark mode support"

✅ **Context Established**
- File paths, project names, configurations
- Technical details (versions, libraries)

✅ **Unresolved Items**
- "Blog section implementation pending"
- "Need to add error handling for edge cases"

✅ **Recent Messages**
- Last N messages (default 6) kept in full detail
- Ensures immediate context is always available

### Compressed (Lower Priority)

📉 **Verbose Explanations**
- Long code snippets → "Set up Flask-Login configuration"
- Detailed explanations → Key points only

📉 **Repeated Concepts**
- Multiple mentions → "Discussed authentication multiple times"

📉 **Intermediate Steps**
- Focus on outcomes, not every step
- "Created user model" vs. detailed implementation

📉 **Tool Outputs**
- Summarize results rather than full outputs
- "Found 15 Python files" vs. listing all files

📉 **Greetings/Pleasantries**
- Omitted unless contextually important

## Monitoring & Debugging

### Log Messages

When summarization triggers, you'll see:

```
INFO - Conversation length threshold reached, triggering summarization
INFO - Conversation summarized. History reduced to 6 recent messages. Summary: 847 chars
```

### Checking Summarization State

In code:

```python
# Check if summary exists
if orchestrator.persona_llm.conversation_summary:
    print("Summary active")
    print(f"Summary length: {len(orchestrator.persona_llm.conversation_summary)} chars")

# Check current history size
history_size = len(orchestrator.persona_llm.conversation_history)
print(f"Current history: {history_size} messages")
```

### Demo Script

Run the interactive demo:

```bash
./venv/bin/python examples/summarization_demo.py
```

This simulates a 20-message conversation and shows:
- When summarization triggers
- What the summary looks like
- That context is preserved after summarization

## Technical Details

### Token Estimation

The system uses a conservative approximation:

```python
estimated_tokens = len(text) // 4
```

This assumes ~4 characters per token, which is typical for English text. It's deliberately conservative (slightly overestimates) to prevent accidental overflow.

**Why not exact counting?**
- Tokenizers are model-specific (GPT vs. Llama vs. Qwen)
- Exact counting requires tokenizer library
- Approximation is fast and good enough for triggering threshold

### Summarization Quality

The `SummarizerLLM` uses the same model as PersonaLLM by default. This means:

**Pros:**
- Consistent behavior across system
- No additional model management
- Understands conversation context well

**Cons:**
- Summarization quality depends on model capability
- Smaller models may produce less concise summaries

**Recommendation**: For production, consider using a larger model specifically for summarization if your main model struggles with condensing conversations.

### Performance Impact

**Summarization cost:**
- 1 LLM call per summarization event
- Processes entire conversation history (up to preserve_recent)
- Typical time: 2-5 seconds for 20 messages

**When does it trigger?**
- Default: every ~15-20 messages (depends on message length)
- Typically 2-3 times in a 60-message conversation

**Optimization:**
- Summarization happens before response generation (user sees delay once)
- Subsequent responses are faster (smaller context)
- Net effect: roughly neutral performance

## Examples

### Example 1: Long Debugging Session

```
User: I'm getting a weird error in my Flask app
Jarvis: What's the error message?

... [30 messages of debugging] ...

User: Wait, what was the original error again?
Jarvis: The original error was: "AttributeError: 'NoneType' object has no attribute 'id'"
       We traced it to the user authentication code where...
```

Even after 30 messages and 2 summarizations, Jarvis remembers the original error because it was preserved in the summary under "Facts & Information".

### Example 2: Multi-Topic Conversation

```
[First 15 messages: discussing Python project setup]
[Summarization triggered]

[Next 15 messages: discussing API design]
[Summarization triggered again - merges with previous summary]

User: What directory structure did we decide on earlier?
Jarvis: We decided on:
        /src - main code
        /tests - unit tests
        /docs - documentation
```

The summary accumulates context from multiple topics, making it available throughout the conversation.

### Example 3: Context Preservation Across Sessions

**Note**: Currently, summaries are **not** persisted across sessions. When you restart Jarvis, the summary is lost.

**Future Enhancement**: Store summaries in database for true session persistence:

```python
# Potential future feature
conversation_sessions table:
  - session_id
  - user_id
  - conversation_history (JSON)
  - conversation_summary (TEXT)
  - last_activity_at
```

This would enable:
- Resuming long conversations after restart
- Multi-day project discussions
- Historical conversation review

## Troubleshooting

### Summarization Not Triggering

**Check 1: Is it enabled?**
```yaml
summarization:
  enabled: true  # Must be true
```

**Check 2: Are conversations long enough?**
- Default threshold: 5600 tokens (~5600 * 4 = 22,400 characters)
- With 6 messages preserved, need ~15-20 messages to trigger
- Try lowering threshold for testing:
  ```yaml
  trigger_threshold: 0.3  # Trigger at 30% (2400 tokens)
  ```

**Check 3: Check logs**
```bash
grep -i "summar" logs/jarvis.log
```

Should see:
```
INFO - Conversation Summarizer LLM initialized
INFO - Conversation length threshold reached, triggering summarization
INFO - Conversation summarized. History reduced to 6 recent messages...
```

### Poor Summary Quality

**Symptom**: Summary is too long, misses important info, or is incoherent

**Solution 1**: Use a larger model for summarization
```yaml
# In orchestrator init, add model override for summarizer
self.summarizer_llm = SummarizerLLM(
    model='llama3.1:70b'  # Larger model for better summarization
)
```

**Solution 2**: Adjust preserve_recent
```yaml
preserve_recent: 8  # Keep more messages unsummarized
```

**Solution 3**: Lower trigger threshold (summarize earlier)
```yaml
trigger_threshold: 0.5  # Summarize when conversations are shorter
```

### Context Loss After Summarization

**Symptom**: Jarvis "forgets" important details after summarization

**Diagnosis**: Important information was compressed out of summary

**Solution 1**: Increase preserve_recent
```yaml
preserve_recent: 10  # Keep last 10 messages in full detail
```

**Solution 2**: Use memory system for critical facts
- Memory system stores important facts permanently
- Not affected by conversation summarization
- Retrieved on-demand for future conversations

**Solution 3**: Disable summarization for critical sessions
```yaml
summarization:
  enabled: false  # For this specific session
```

### Unexpected LLM Calls

**Symptom**: Extra LLM API calls happening

**Diagnosis**: Summarization is triggering

**Check**: Look for summarization logs
```bash
grep "summarization" logs/jarvis.log
```

**Solution**: Adjust threshold to reduce frequency
```yaml
trigger_threshold: 0.8  # Summarize less often
max_tokens: 16000       # Allow longer conversations before summarizing
```

## Future Enhancements

### 1. Persistent Summaries
- Store summaries in database
- Resume conversations across sessions
- API endpoint: GET /api/v1/conversation/history

### 2. Incremental Summarization
- Instead of re-summarizing entire history each time
- Append new summary to existing summary
- "Summarize the summary" for very long conversations

### 3. User-Triggered Summarization
- `/summarize` command to manually trigger
- Useful for long code review sessions
- Returns summary to user for review

### 4. Summary Export
- Export conversation summary as markdown file
- Useful for sharing context with team
- `save_summary(conversation_id, output_path)`

### 5. Multi-Level Summaries
- Layer 1: Recent messages (full detail)
- Layer 2: Recent summary (condensed)
- Layer 3: Historical summary (highly condensed)
- Progressive detail levels for very long conversations

### 6. Configurable Summarization Styles
```yaml
summarization:
  style: 'technical'  # technical, conversational, bullet-points
  focus: 'decisions'  # decisions, facts, actions, all
```

### 7. Summary Versioning
- Track summary evolution over time
- Ability to "roll back" if summarization was too aggressive
- Useful for debugging context loss

## Best Practices

### 1. Set Appropriate Thresholds
- Start with defaults (70% of 8000 tokens)
- Adjust based on model context window
- Monitor for context loss and tune accordingly

### 2. Use Memory System for Critical Facts
- Don't rely solely on summarization for important info
- Store user preferences, project details in memory system
- Summarization is for conversation flow, memory is for persistence

### 3. Monitor Summary Quality
- Periodically review summaries (check logs)
- Look for information loss
- Adjust `preserve_recent` if recent context is being lost

### 4. Consider Conversation Patterns
- Short, focused conversations: higher threshold, lower preserve_recent
- Long, exploratory conversations: lower threshold, higher preserve_recent
- Multi-topic conversations: use memory system for cross-topic context

### 5. Plan for Very Long Conversations
- Current system works well up to ~100 messages
- Beyond that, consider manual session breaks
- Future: implement incremental summarization

## Conclusion

Conversation Summarization enables Jarvis to handle extended interactions without losing context or hitting token limits. By automatically condensing older messages while preserving recent detail, the system maintains coherent, contextual conversations of arbitrary length.

Key benefits:
- ✅ Unlimited conversation length
- ✅ Automatic, transparent operation
- ✅ Configurable thresholds and behavior
- ✅ Intelligent context preservation
- ✅ Cost-effective token usage

For most users, the default configuration works well out of the box. Advanced users can tune thresholds based on their specific conversation patterns and model capabilities.

---

**Related Documentation:**
- [Goal Management](GOAL_MANAGEMENT.md) - Long-running task tracking
- [Memory System](MEMORY_SYSTEM.md) - Persistent fact storage
- [Procedural Learning](PROCEDURAL_LEARNING.md) - Learning from experience
