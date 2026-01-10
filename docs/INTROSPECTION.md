# Introspection & Self-Critique System

Deep learning through post-task reflection and qualitative analysis.

## Overview

While the **Procedural Memory** system learns *what worked* (patterns and statistics), the **Introspection System** learns *why things worked or failed* through narrative analysis and reflection.

### Key Difference

| Procedural Memory | Introspection System |
|------------------|---------------------|
| Pattern matching | Root cause analysis |
| Success statistics | Narrative insights |
| "This strategy works 80% of the time" | "This failed because the path didn't exist" |
| Quantitative | Qualitative |
| Applied automatically | Stored for understanding |

## How It Works

### 1. Trigger Condition

Introspection activates **after a successful retry**:

```
User: "Find all Python files in /nonexistent/path"
  ↓
[Initial attempt fails - file not found]
  ↓
[Retry Strategist suggests: "Verify path exists first"]
  ↓
[Retry succeeds - path validation strategy works]
  ↓
🔍 INTROSPECTION TRIGGERED
```

### 2. Analysis Process

The **IntrospectionLLM** analyzes the entire execution:

**Input:**
- Original user request
- Task context (e.g., "file_operations")
- All attempts (success/failure, reasoning)
- Tools used (e.g., `find_files`, `list_directory`)
- Final result

**LLM Reflection:**
```
"Why did the initial approach fail?"
"What was inefficient about the process?"
"What surprised me?"
"What generalizable lesson can I learn?"
```

**Output:** `IntrospectionInsight`
```python
@dataclass
class IntrospectionInsight:
    root_cause: str              # Why it failed initially
    inefficiencies: List[str]    # What was wasteful
    surprises: List[str]         # Unexpected aspects
    generalizable_lesson: str    # Abstract principle
    confidence: float            # How certain (0.0-1.0)
    task_context: str            # Category
```

### 3. Storage

Insights are stored **with the heuristic** in the procedural memory database:

```sql
CREATE TABLE procedural_memory (
    id INT PRIMARY KEY,
    context_type VARCHAR(100),      -- "file_operations"
    failure_type ENUM(...),          -- "FILE_NOT_FOUND"
    strategy ENUM(...),              -- "VERIFY_PRECONDITIONS"
    success_count INT,               -- 5
    failure_count INT,               -- 1
    confidence DECIMAL(3,2),         -- 0.83

    -- Introspection fields (NEW)
    root_cause TEXT,                 -- "Path didn't exist before operation"
    inefficiencies JSON,             -- ["Assumed path existence", "No validation"]
    surprises JSON,                  -- ["Error message was cryptic"]
    generalizable_lesson TEXT,       -- "Always validate filesystem paths before operations"
    insight_confidence DECIMAL(3,2)  -- 0.90
);
```

## Example Introspection

### Scenario: Failed File Search

**User Request:**
```
"Find all JavaScript files in /projects/webapp"
```

**Execution Flow:**

1. **Initial Attempt:**
   - Tool: `find_files(path="/projects/webapp", pattern="*.js")`
   - Result: `Error: No such file or directory`
   - Verification: FAILED (FILE_NOT_FOUND)

2. **Retry:**
   - Strategy: VERIFY_PRECONDITIONS
   - Tool: `list_directory(path="/projects")`
   - Result: Shows "webapp2" but not "webapp"
   - Tool: `find_files(path="/projects/webapp2", pattern="*.js")`
   - Result: Success (found 15 files)
   - Verification: PASSED

3. **Introspection Analysis:**

```json
{
  "root_cause": "User provided incorrect directory name; actual directory was 'webapp2' not 'webapp'",

  "inefficiencies": [
    "Blindly trusted user-provided path without validation",
    "Could have listed /projects directory first to show available options",
    "Error message didn't guide user to correct path"
  ],

  "surprises": [
    "User had a similar directory name (webapp vs webapp2) causing confusion",
    "No suggestion mechanism to show nearby directory names"
  ],

  "generalizable_lesson": "When a filesystem path doesn't exist, list the parent directory to help identify typos or similar names. For user-provided paths, validate existence first and offer corrections for close matches.",

  "confidence": 0.88
}
```

### Recorded Heuristic

**Pattern-based data** (Procedural Memory):
- Context: `file_operations`
- Failure: `FILE_NOT_FOUND`
- Strategy: `VERIFY_PRECONDITIONS`
- Success rate: 100% (1/1)

**Narrative insights** (Introspection):
- **Root cause:** Path typo (webapp vs webapp2)
- **Inefficiencies:** No upfront validation
- **Surprises:** Similar naming caused confusion
- **Lesson:** Validate paths and suggest corrections
- **Confidence:** 88%

## When Introspection Runs

### Always Analyze

Introspection runs on **every successful retry**, regardless of complexity. The LLM decides whether insights are valuable.

### Returns `has_insights: false`

For straightforward cases where there's nothing to learn:

**Example:**
```
User: "What time is it?"
Initial: Returns current time
Verification: Success
```

No retry occurred → No introspection

**Example:**
```
User: "Read /tmp/test.txt"
Initial: Tool succeeds immediately
Verification: Success
```

No failure → No retry → No introspection

### Returns Deep Insights

For complex scenarios:
- Multiple tool failures
- Unexpected edge cases
- Non-obvious solutions
- User errors (typos, misunderstandings)
- System limitations discovered

## Integration with Procedural Memory

### Heuristic Lifecycle

1. **First Success:**
   ```
   Heuristic created:
   - Pattern: context + failure + strategy
   - Stats: 1 success, 0 failures, 100% confidence
   - Insights: root_cause, lesson, inefficiencies, surprises
   ```

2. **Subsequent Matches:**
   ```
   Heuristic applied (pattern match):
   - Success count incremented
   - Stats updated
   - Original insights retained
   ```

3. **Future Reference:**
   ```
   Developer/User can query:
   "Why does this strategy work?"
   → Read generalizable_lesson and root_cause

   "What are common pitfalls?"
   → Review inefficiencies and surprises
   ```

### Retrieval

**Pattern-based retrieval** (normal operation):
```python
heuristics = procedural_memory.retrieve_relevant_heuristics(
    context="file_operations",
    failure="FILE_NOT_FOUND"
)
# Returns: [Heuristic(strategy=VERIFY_PRECONDITIONS, confidence=0.83, ...)]
```

**Insight-based query** (debugging/understanding):
```python
# Get heuristic with full insights
heuristic = procedural_memory.get_heuristic_by_id(42)

if heuristic.has_insights:
    print(f"Root cause: {heuristic.root_cause}")
    print(f"Lesson: {heuristic.generalizable_lesson}")
    print(f"Inefficiencies: {heuristic.inefficiencies}")
    print(f"Surprises: {heuristic.surprises}")
```

## Configuration

### Enable/Disable Introspection

**In `config/config.yaml`:**

```yaml
memory:
  # Procedural memory must be enabled for introspection
  procedural_enabled: true

ollama:
  # Introspection uses the same model as other LLM roles
  model: "llama3.1:8b"

  # Introspection timeout (can be longer than other roles)
  introspection_timeout: 180  # 3 minutes
```

**Introspection is automatically enabled** when `procedural_enabled: true`.

To disable introspection but keep procedural memory:
- Comment out introspection initialization in `orchestrator/engine.py`
- Or modify code to skip introspection analysis

### Timeout Considerations

Introspection requires deeper reasoning than simple tasks:

- **Verifier:** 60s (quick pass/fail)
- **Curator:** 90s (memory proposals)
- **Introspection:** 180s (deep analysis)

Adjust based on your LLM speed:
```yaml
ollama:
  introspection_timeout: 300  # 5 minutes for slower models
```

## Use Cases

### 1. Debugging Why Strategies Work

```python
from memory.procedural_memory import ProceduralMemoryManager

pm = ProceduralMemoryManager(config['memory'])

# Get all heuristics for a context
heuristics = pm.retrieve_relevant_heuristics(
    context="web_search",
    failure="TIMEOUT"
)

# Review insights
for h in heuristics:
    if h.has_insights:
        print(f"\nStrategy: {h.strategy}")
        print(f"Lesson: {h.generalizable_lesson}")
        print(f"Root cause: {h.root_cause}")
```

### 2. Learning Analytics

```python
# Get learning statistics
insights = pm.get_learning_insights()

print(f"Heuristics with deep insights: {insights['heuristics_with_insights']}")
print(f"Most common inefficiencies: {insights['common_inefficiencies']}")
```

### 3. Training New Models

Export insights for fine-tuning:

```python
# Get all heuristics with insights
all_heuristics = pm.get_all_heuristics()

training_data = []
for h in all_heuristics:
    if h.has_insights and h.confidence > 0.7:
        training_data.append({
            'scenario': f"{h.context_type} + {h.failure_type}",
            'strategy': h.strategy,
            'lesson': h.generalizable_lesson,
            'success_rate': h.confidence
        })

# Export to JSON for model training
import json
with open('learning_export.json', 'w') as f:
    json.dump(training_data, f, indent=2)
```

### 4. Improving System Prompts

Review common inefficiencies to improve tool usage:

```sql
SELECT
    context_type,
    inefficiencies,
    COUNT(*) as occurrences
FROM procedural_memory
WHERE inefficiencies IS NOT NULL
GROUP BY context_type, inefficiencies
ORDER BY occurrences DESC
LIMIT 10;
```

Use results to update system prompts in `llm_roles/persona.py`.

## Implementation Details

### IntrospectionLLM Class

**Location:** `llm_roles/introspection.py`

**Key Method:**
```python
def analyze_execution(
    self,
    original_task: str,
    task_context: str,
    attempts: List[Dict[str, Any]],
    final_result: Dict[str, Any],
    tools_used: List[str]
) -> Optional[IntrospectionInsight]:
    """
    Perform deep analysis of task execution.

    Returns None if task was too straightforward to yield insights.
    """
```

**System Prompt Highlights:**

```
You are an introspection specialist. Your job is to analyze
task execution and extract qualitative insights.

ANALYSIS FRAMEWORK:

1. Root Cause Analysis
   - Why did the initial approach fail?
   - What assumptions were wrong?
   - What information was missing?

2. Inefficiency Detection
   - What steps were wasteful or redundant?
   - What could have been done earlier/better?
   - What shortcuts were missed?

3. Surprise Identification
   - What was unexpected about this task?
   - What edge cases appeared?
   - What assumptions proved wrong?

4. Generalizable Lessons
   - What ABSTRACT principle can be learned?
   - How does this apply to FUTURE tasks?
   - What pattern should be remembered?

IMPORTANT:
- Don't just record "what worked" - understand WHY
- Focus on lessons applicable to similar future tasks
- Be concise but insightful
- If the task was straightforward, return has_insights: false
```

### Database Schema

**Added fields to `procedural_memory` table:**

```sql
ALTER TABLE procedural_memory
ADD COLUMN root_cause TEXT NULL
    COMMENT 'Why did the task fail initially?';

ADD COLUMN inefficiencies JSON NULL
    COMMENT 'List of inefficiencies identified';

ADD COLUMN surprises JSON NULL
    COMMENT 'Unexpected aspects encountered';

ADD COLUMN generalizable_lesson TEXT NULL
    COMMENT 'Abstract principle for future tasks';

ADD COLUMN insight_confidence DECIMAL(3,2) NULL
    COMMENT 'Confidence in introspection analysis (0.0-1.0)';
```

### Integration Points

**In `orchestrator/engine.py`:**

```python
# After successful retry
if prev_failure and self.introspection_llm:
    introspection_insight = self.introspection_llm.analyze_execution(
        original_task=user_input,
        task_context=task_context,
        attempts=retry_history.attempts,
        final_result=result,
        tools_used=tools_used
    )

    # Store with heuristic
    self.procedural_memory.record_success(
        context_type=task_context,
        failure_type=prev_failure,
        strategy=current_strategy,
        introspection=introspection_insight  # NEW
    )
```

## Testing

### Run Introspection Demo

```bash
source venv/bin/activate
python examples/introspection_demo.py
```

**Demo Flow:**
1. Shows current procedural memory state
2. Triggers a failure scenario (file not found)
3. System retries with better strategy
4. Introspection analyzes the execution
5. Displays the generated insights
6. Shows updated procedural memory with insights

### Manual Testing

**Trigger introspection:**
```python
from orchestrator.engine import Orchestrator

orchestrator = Orchestrator(config)

# Create a scenario that will fail then succeed
result = orchestrator.process_user_input(
    user_input="Find all Python files in /fake/path/that/doesnt/exist",
    user_id=3
)

# Check if introspection was triggered
# Look for log message:
# 🔍 Introspection insight generated: ...
```

**Query stored insights:**
```sql
SELECT
    id,
    context_type,
    failure_type,
    strategy,
    success_count,
    confidence,
    generalizable_lesson,
    insight_confidence
FROM procedural_memory
WHERE generalizable_lesson IS NOT NULL
ORDER BY created_at DESC
LIMIT 5;
```

## Limitations

### Current Limitations

1. **No Cross-Heuristic Analysis:**
   - Each introspection is isolated to one retry event
   - Doesn't identify patterns across multiple heuristics
   - Future: Meta-introspection to find themes

2. **Depends on Successful Retry:**
   - Only analyzes when retry eventually succeeds
   - Failed retries don't get introspection
   - Future: Analyze repeated failures too

3. **No User Feedback Loop:**
   - User can't confirm/reject insights
   - No way to rate insight quality
   - Future: User feedback mechanism

4. **Storage Only:**
   - Insights are stored but not actively used
   - Doesn't modify system prompts based on lessons
   - Future: Auto-improve prompts from insights

### Performance Considerations

- **LLM Call:** Each successful retry triggers one introspection call
- **Latency:** Adds 30-180s to retry flow (asynchronous potential)
- **Cost:** Additional LLM inference per retry
- **Database:** JSON fields may grow large

**Optimization:**
- Skip introspection for high-confidence heuristics (>0.9)
- Run introspection asynchronously after response sent
- Limit introspection to first N instances of a pattern

## Future Enhancements

### Planned Features

1. **Async Introspection:**
   ```python
   # Don't block user response
   asyncio.create_task(introspection_llm.analyze_execution(...))
   ```

2. **Meta-Learning:**
   ```python
   # Periodically analyze ALL insights to find patterns
   meta_insights = analyze_insight_patterns(all_heuristics)
   # "File operations often fail due to path validation - update system prompt"
   ```

3. **Insight-Based Prompting:**
   ```python
   # When suggesting retry strategy, include relevant lesson
   lesson = heuristic.generalizable_lesson
   prompt += f"\nRemember: {lesson}"
   ```

4. **User Feedback:**
   ```python
   # After showing result
   "Was this helpful? (y/n)"
   if not helpful:
       heuristic.downvote()
       # Request new introspection
   ```

5. **Insight Search:**
   ```python
   # Query insights by natural language
   search_insights("How to handle file not found errors?")
   # Returns: relevant generalizable_lessons
   ```

## Best Practices

### 1. Review Insights Periodically

```bash
# Weekly review
mysql -u jarvis_user -p jarvis -e "
SELECT generalizable_lesson, insight_confidence
FROM procedural_memory
WHERE created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
  AND generalizable_lesson IS NOT NULL
ORDER BY insight_confidence DESC;
"
```

### 2. Use Insights for Documentation

Export high-confidence lessons:
```python
high_conf_insights = [
    h for h in pm.get_all_heuristics()
    if h.has_insights and h.insight_confidence > 0.85
]

# Add to user documentation
with open('docs/LESSONS_LEARNED.md', 'w') as f:
    f.write("# System Lessons Learned\n\n")
    for h in high_conf_insights:
        f.write(f"## {h.context_type} - {h.failure_type}\n")
        f.write(f"{h.generalizable_lesson}\n\n")
```

### 3. Fine-Tune Prompts

If introspection reveals common inefficiencies:
```
Inefficiency: "Assumed file exists without checking"
Lesson: "Always validate filesystem paths first"

→ Update llm_roles/persona.py:
  "Before file operations, always verify paths exist."
```

### 4. Monitor Insight Quality

```sql
-- Check distribution of confidence
SELECT
    ROUND(insight_confidence, 1) as conf_bucket,
    COUNT(*) as count
FROM procedural_memory
WHERE insight_confidence IS NOT NULL
GROUP BY conf_bucket
ORDER BY conf_bucket;
```

If most insights have low confidence (<0.6), the introspection timeout may be too short.

---

## Summary

**Introspection System** = Deep learning through narrative reflection

- **What:** Post-task analysis extracting qualitative insights
- **When:** After every successful retry
- **Why:** Understand WHY strategies work, not just THAT they work
- **How:** IntrospectionLLM analyzes execution → Stores insights with heuristic
- **Value:** Debugging, system improvement, knowledge extraction

**Procedural Memory** learns patterns. **Introspection** learns wisdom.
