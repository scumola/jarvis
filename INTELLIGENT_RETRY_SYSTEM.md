# Intelligent Retry Orchestration System

Jarvis implements a sophisticated retry system that explores different problem-solving strategies rather than simply repeating failed attempts.

## Core Principle

**Retries must differ in STRATEGY, not wording.**

Any retry that does not change the problem-solving approach is invalid. The system explores the solution space rather than repeating attempts.

## Architecture

### Three-LLM Separation of Concerns

1. **PersonaLLM (Solver)**
   - Attempts to solve the task
   - Produces candidate output
   - Has no authority over retries or escalation

2. **VerifierLLM (Evaluator)**
   - Determines if output is correct, incomplete, unsafe, or failed
   - Classifies failure type
   - Does not suggest retries

3. **RetryStrategistLLM (Meta-Reasoner)**
   - Stateless
   - Receives original task, failed output, and failure classification
   - Decides whether to retry and how
   - Recommends model escalation when justified

### Design Ethos

- **Repetition is not persistence**
- **Variation is intelligence**
- **Escalation is a last resort**

## Failure Classification

Every failed attempt is classified into one of 8 types:

| Failure Type | Description | Example |
|--------------|-------------|---------|
| `misunderstood_intent` | Task intent not understood | User asks for capital of France, gets file listing |
| `missing_constraints` | Constraints ignored or missed | File search ignores file type requirement |
| `incorrect_assumptions` | Wrong assumptions made | Assumes case-sensitive filename |
| `partial_solution` | Incomplete answer | Returns 3 of 10 requested items |
| `tool_misuse` | Wrong tool or usage | Uses grep instead of find |
| `hallucinated_facts` | Unverified information | Makes up API response format |
| `insufficient_reasoning` | Not deep enough | Surface-level analysis |
| `underspecified_search` | Search too broad/narrow | Searches entire disk when local dir intended |

## Retry Strategies

Each retry must select exactly one primary strategy. Strategies cannot be reused for the same task.

### Available Strategies

| Strategy | Description | When to Use |
|----------|-------------|-------------|
| `decomposition` | Break task into explicit substeps | Complex multi-part queries |
| `verification_first` | Validate assumptions before solving | Uncertain inputs or requirements |
| `alternative_method` | Use different approach | Initial method fundamentally wrong |
| `constraint_emphasis` | Prioritize constraints and edge cases | Missing constraints failure |
| `example_driven` | Solve using concrete example | Abstract requirements unclear |
| `reverse_reasoning` | Work backward from expected output | End goal known but path unclear |
| `simplification` | Simplest possible correct solution | Over-complicated initial attempt |

### Strategy Selection Process

The RetryStrategist:
1. Analyzes failure type
2. Reviews strategies already attempted
3. Selects unused strategy that addresses failure
4. Generates modified prompt implementing strategy
5. Recommends escalation if warranted

## Example Retry Sequence

### Attempt 1: Initial (Failed)
```
Query: "Find all Python files modified in the last week"
Failure: tool_misuse
Reasoning: Used grep instead of find with time filter
```

### Attempt 2: Alternative Method Strategy
```
Modified Query: "Use a different approach to solve:
First use the find command with -mtime filter to locate files by date,
then filter for .py extension."

Strategy: alternative_method
Result: Success
```

## Model Escalation

Escalation to a larger model is permitted only if:

1. Multiple distinct retry strategies have failed (at least 2), AND
2. The failure is classified as:
   - `insufficient_reasoning`
   - `misunderstood_intent` (complex)

### Escalation Process

```python
# In config.yaml
ollama:
  allow_escalation: true
  model: "qwen3:8b"           # Primary model
  escalation_model: "qwen3:14b"  # Larger model for complex tasks
```

When escalation is triggered:
1. RetryStrategist recommends escalation
2. Orchestrator checks escalation policy
3. Model switched for remaining attempts
4. All subsequent retries use larger model
5. Escalation logged in retry history

## Retry History Tracking

The orchestrator tracks per-task:

```python
{
  "total_attempts": 3,
  "strategies_tried": ["alternative_method", "decomposition"],
  "final_strategy": "decomposition",
  "escalated": false,
  "attempts": [
    {
      "number": 1,
      "strategy": "initial",
      "failure_type": "tool_misuse",
      "succeeded": false,
      "model": "qwen3:8b"
    },
    {
      "number": 2,
      "strategy": "alternative_method",
      "failure_type": "partial_solution",
      "succeeded": false,
      "model": "qwen3:8b"
    },
    {
      "number": 3,
      "strategy": "decomposition",
      "failure_type": null,
      "succeeded": true,
      "model": "qwen3:8b"
    }
  ]
}
```

## Configuration

### config.yaml

```yaml
ollama:
  model: "qwen3:8b"
  verifier_timeout: 180
  strategist_timeout: 120
  allow_escalation: false
  escalation_model: "qwen3:14b"

verification:
  enabled: true
  max_retries: 2  # Maximum retry attempts
```

### Retry Limits

- **Default max_retries**: 2 (up to 3 total attempts)
- **Recommended range**: 1-3
- **Not recommended**: > 5 (diminishing returns)

With max_retries=2:
- Attempt 1: Initial (no strategy)
- Attempt 2: First retry strategy
- Attempt 3: Second retry strategy
- Total: Up to 7 unique strategies available

## Success Feedback Loop

When a retry succeeds, the system records:
- Failure type that triggered retry
- Successful retry strategy
- Task category

This data can be used for:
- Future retry strategy biasing
- Meta-learning without retraining
- Strategy effectiveness analysis

*Note: Currently logged but not yet used for learning*

## Hard Constraints

1. **The same LLM instance may not:**
   - Fail
   - Diagnose its own failure
   - Decide its own retry strategy

2. **The Retry Strategist must be:**
   - Stateless
   - Isolated from execution
   - Based only on history provided

3. **Retries must terminate after max_retries:**
   - Regardless of escalation
   - No infinite loops allowed

## Definition of "Correct Retry Behavior"

A retry is well-orchestrated if:
1. Meaningfully different from prior attempts
2. Justified by explicit failure diagnosis
3. Explores a new reasoning path
4. Either succeeds OR provides new information

## Prompt Mutation Requirements

Modified prompts must:
1. **Explicitly state:**
   - Why the last attempt failed
   - What will be done differently

2. **Alter problem framing, not tone**

3. **Not include:**
   - Apologies
   - Encouragement
   - Generic "be careful" language

### Good Retry Prompt Example

```
[RETRY STRATEGY: decomposition]

Original task: Find all Python files modified in the last week

Previous attempt failed because: Used grep instead of find with time filter

Modified approach:
Break this into steps:
1. Use find command to locate files modified in last 7 days
2. Filter results for .py extension
3. Return the complete list
```

### Bad Retry Prompt Example

```
❌ [SYSTEM FEEDBACK: Previous attempt did not fully answer the query.
Please be more careful and try again.]
```

This is bad because:
- No strategy change
- No analysis of why it failed
- No different approach
- Just encouragement to "try harder"

## Verification Example

### Initial Attempt

**Query**: "Show me the README file"

**Output**: "Error: readme.md not found"

**VerifierLLM Response**:
```json
{
  "verified": false,
  "confidence": "medium",
  "reasoning": "File not found, but README typically exists in projects",
  "failure_type": "incorrect_assumptions",
  "suggestion": "Try different capitalization or list directory first"
}
```

### Retry with Strategy

**RetryStrategistLLM Decision**:
```json
{
  "should_retry": true,
  "strategy": "verification_first",
  "modified_prompt": "First list the directory to find the exact README filename, then read it",
  "escalate_model": false,
  "reasoning": "Verify the file exists and get correct case before attempting to read",
  "estimated_success_probability": 0.85
}
```

**Result**: Success - Found README.md and displayed contents

## Monitoring & Observability

### Log Output

```
2026-01-08 22:00:15 - Attempt 1 - Verification: False (confidence: high)
2026-01-08 22:00:16 - Consulting retry strategist after failure: tool_misuse
2026-01-08 22:00:18 - Retry decision: should_retry=True, strategy=alternative_method, escalate=False
2026-01-08 22:00:19 - Retrying with strategy: alternative_method
2026-01-08 22:00:22 - Attempt 2 - Verification: True (confidence: high)
```

### Metrics to Track

- **Retry success rate by strategy**
- **Average attempts per query**
- **Failure type distribution**
- **Escalation frequency**
- **Strategy effectiveness per failure type**

## Best Practices

### For Users

1. **Allow retries**: Set max_retries >= 2 for complex tasks
2. **Enable verification**: verification.enabled = true
3. **Consider escalation**: For production, keep a larger model available
4. **Monitor logs**: Watch retry patterns to tune max_retries

### For System Tuning

1. **Start conservative**: max_retries = 2
2. **Enable escalation cautiously**: Only if you have larger model
3. **Review retry histories**: Look for patterns in failures
4. **Adjust timeouts**: Give strategist enough time to reason

## Limitations & Future Work

### Current Limitations

1. **No cross-task learning**: Each task starts fresh
2. **No strategy effectiveness tracking**: Could learn which strategies work best
3. **Simple escalation policy**: Could be more nuanced
4. **No parallel strategy exploration**: Tries strategies sequentially

### Potential Enhancements

1. **Strategy effectiveness database**: Learn from successful retries
2. **Parallel strategy attempts**: Try multiple strategies simultaneously
3. **Dynamic max_retries**: Adjust based on task complexity
4. **User-defined strategies**: Allow custom retry approaches
5. **Hybrid strategies**: Combine multiple approaches in one retry

## Comparison to Old System

| Aspect | Old System | New System |
|--------|------------|------------|
| **Retry logic** | Append "[Try again]" | 7 distinct strategies |
| **Failure analysis** | Binary yes/no | 8 classified types |
| **Decision maker** | Human hope | Dedicated strategist LLM |
| **Variation** | None | Required |
| **Escalation** | Manual | Automatic when justified |
| **Tracking** | None | Full history |
| **Success rate** | ~30% | Expected ~70%+ |

---

**Status**: ✅ Fully implemented
**Version**: 1.0
**Last Updated**: 2026-01-08
