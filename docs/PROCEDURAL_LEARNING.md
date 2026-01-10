# Enhanced Procedural Memory & Learning

## Overview

Jarvis's procedural memory system enables **continuous learning from experience**. Every time a retry strategy succeeds, the system records it as a heuristic and uses it to solve similar problems faster in the future.

**Key Capability**: Transform trial-and-error into permanent knowledge that improves system performance over time.

---

## Core Features

### 1. **Automatic Confidence Decay** 🕐

Heuristics that haven't been used recently automatically lose confidence over time.

**How it works:**
- Every time heuristics are queried, stale ones are decayed
- Default: Heuristics unused for 7+ days decay by 0.01 per day
- Prevents outdated strategies from being applied

**Benefits:**
- ✅ Fresh knowledge is preferred
- ✅ Outdated patterns fade away naturally
- ✅ System adapts to changing environments
- ✅ No manual maintenance required

**Configuration:**
```yaml
memory:
  procedural_auto_decay: true  # Enable automatic decay
  procedural_decay_days: 7  # Start decaying after N days
  procedural_decay_amount: 0.01  # Decay per day
```

---

### 2. **Adaptive Confidence Thresholds** 📊

Confidence requirements adapt based on success rate - reliable heuristics get more leeway.

**How it works:**
- High success rate (≥80%) → Accept with 70% of base confidence
- Medium success rate (50-80%) → Require base confidence
- Low success rate (<50%) → Require 120% of base confidence
- New heuristics (<3 uses) → Use base threshold

**Example:**
```
Base confidence threshold: 0.4

Heuristic A: 90% success rate, confidence 0.30 → ACCEPTED (0.30 ≥ 0.28)
Heuristic B: 45% success rate, confidence 0.45 → REJECTED (0.45 < 0.48)
Heuristic C: 70% success rate, confidence 0.40 → ACCEPTED (meets base)
```

**Benefits:**
- ✅ Proven strategies are trusted more
- ✅ Unreliable strategies need higher confidence
- ✅ Balances exploration and exploitation
- ✅ Self-correcting system

**Configuration:**
```yaml
memory:
  procedural_adaptive: true  # Enable adaptive thresholds
  procedural_min_confidence: 0.4  # Base threshold
```

---

### 3. **Intelligent Pattern Matching** 🎯

Heuristics can apply across similar contexts through fallback matching.

**Matching Strategy:**
1. **Exact match**: Try specific context first (e.g., `filesystem`)
2. **General fallback**: If no exact match, check `general` context
3. **Sorted by confidence**: Best matches returned first

**Example:**
```
Query: filesystem/incorrect_assumptions

Search order:
  1. filesystem/incorrect_assumptions → Found 2 heuristics
  2. Return filesystem-specific strategies

Query: code_generation/incorrect_assumptions

Search order:
  1. code_generation/incorrect_assumptions → No matches
  2. general/incorrect_assumptions → Found 1 heuristic
  3. Return general strategy as fallback
```

**Benefits:**
- ✅ Specific knowledge takes precedence
- ✅ General patterns provide backup
- ✅ Cross-domain learning
- ✅ Graceful degradation

**Configuration:**
```yaml
memory:
  procedural_pattern_matching: true  # Enable fuzzy matching
```

---

### 4. **Comprehensive Learning Analytics** 📈

Track what Jarvis is learning with detailed insights and statistics.

**Metrics Tracked:**
- Total heuristics and confidence distribution
- Success rate and application counts
- Top performing strategies
- Learning velocity (new heuristics per week/month)
- System maturity assessment

**Usage:**
```python
from memory.procedural_memory import ProceduralMemoryManager

# Get statistics
stats = pm.get_statistics()
print(f"Total heuristics: {stats['total_heuristics']}")
print(f"Average success rate: {stats['success_metrics']['average_success_rate']}")

# Get human-readable insights
insights = pm.get_learning_insights()
print(insights)
```

**Example Output:**
```
📊 PROCEDURAL MEMORY INSIGHTS
==================================================

🧠 Total Heuristics: 12
📈 Average Confidence: 58%

Confidence Distribution:
  🌟 Very High: 3 heuristics
  ⭐ High: 5 heuristics
  ⚡ Medium: 3 heuristics
  ⚠️  Low: 1 heuristics

✅ Success Metrics:
  Applied: 45 times
  Succeeded: 38 times
  Failed: 7 times
  Success Rate: 84.4%

🏆 Top Performing Strategies:
  1. filesystem/incorrect_assumptions → verification_first (100% success)
  2. general/partial_solution → decomposition (91% success)
  3. web_retrieval/tool_misuse → alternative_approach (85% success)

📚 Learning Activity:
  Last 7 days: 3 new heuristics
  Last 30 days: 8 new heuristics

🎓 System Maturity: DEVELOPING
  Jarvis is actively learning from experience.
```

---

## How Learning Works

### Recording Success

When a retry strategy succeeds, it's automatically recorded:

```python
# In orchestrator/engine.py (automatic)
if attempt_number > 1 and current_strategy and self.procedural_enabled:
    self.procedural_memory.record_success(
        context_type=task_context,
        failure_type=prev_failure,
        strategy=current_strategy,
        notes="Abstract pattern description"
    )
```

**What happens:**
1. Check if heuristic already exists for this pattern
2. If exists: Boost confidence by +0.1, increment success count
3. If new: Create with confidence 0.5, success_count=1
4. Update last_applied_at and last_success_at timestamps

### Recording Failure

If a heuristic fails when applied:

```python
pm.record_failure(heuristic_id)
```

**What happens:**
1. Decrease confidence by -0.2
2. Increment failure_count and usage_count
3. Update last_applied_at
4. Confidence never goes below 0.0

### Querying Heuristics

Heuristics are queried before retry attempts:

```python
heuristics = pm.query_heuristics(
    context_type='filesystem',
    failure_type=FailureType.INCORRECT_ASSUMPTIONS
)

if heuristics:
    # Apply the best matching strategy
    best_strategy = heuristics[0].effective_strategy
```

**Process:**
1. Auto-decay stale heuristics
2. Query exact context match
3. If none, try general fallback (if pattern matching enabled)
4. Apply adaptive filtering based on success rates
5. Return sorted by confidence and success count

---

## Configuration

Full configuration options in `config.yaml`:

```yaml
memory:
  # Basic procedural memory
  procedural_enabled: true  # Master switch
  procedural_min_confidence: 0.4  # Base confidence threshold

  # Automatic decay (NEW)
  procedural_auto_decay: true  # Auto-decay stale heuristics
  procedural_decay_days: 7  # Start decaying after this many days
  procedural_decay_amount: 0.01  # Decay amount per day

  # Adaptive learning (NEW)
  procedural_adaptive: true  # Use success-rate-based thresholds
  procedural_pattern_matching: true  # Enable context fallback matching
```

---

## Database Schema

The `procedural_memory` table stores all learned heuristics:

```sql
CREATE TABLE procedural_memory (
    id INT PRIMARY KEY AUTO_INCREMENT,
    context_type ENUM(...),  -- Task context
    failure_type VARCHAR(50),  -- How it failed
    effective_strategy VARCHAR(50),  -- What worked
    confidence_score DECIMAL(3,2),  -- 0.0 to 1.0
    usage_count INT,  -- Times applied
    success_count INT,  -- Times succeeded
    failure_count INT,  -- Times failed
    last_applied_at TIMESTAMP,  -- Last use
    last_success_at TIMESTAMP,  -- Last success
    created_at TIMESTAMP,  -- When learned
    updated_at TIMESTAMP,  -- Last modified
    notes TEXT  -- Abstract pattern description
);
```

**Indexes:**
- `context_type` + `failure_type` (query performance)
- `confidence_score` (filtering)
- `last_applied_at` (decay operations)

---

## Examples

### Example 1: Learning from File Not Found

```python
# Iteration 1: Failure
User: "Read the README file"
Jarvis tries: read_file('readme.md')
Result: File not found

# Retry Strategist suggests: verification_first
Jarvis tries: list_directory('.') first, then read_file('README.md')
Result: Success!

# System records:
pm.record_success(
    context_type='filesystem',
    failure_type=FailureType.INCORRECT_ASSUMPTIONS,
    strategy=RetryStrategy.VERIFICATION_FIRST,
    notes='Verify file existence and name before reading'
)
```

**Next time:**
```python
# Iteration 2: Same pattern
User: "Read the LICENSE file"
Jarvis queries: pm.query_heuristics('filesystem', FailureType.INCORRECT_ASSUMPTIONS)
Found: verification_first (confidence: 0.5)
Jarvis: Lists directory first, finds 'LICENSE.txt', reads it
Result: Success on first try!
```

### Example 2: Confidence Evolution

```python
# Initial learning
Success 1: confidence = 0.50 (new heuristic)
Success 2: confidence = 0.60 (+0.10)
Success 3: confidence = 0.70 (+0.10)
Failure 1: confidence = 0.50 (-0.20)
Success 4: confidence = 0.60 (+0.10)

# Stats after 5 applications:
usage_count = 5
success_count = 4
failure_count = 1
success_rate = 80%

# With adaptive thresholds:
Required confidence (base 0.4, success rate 80%):
  0.4 * 0.7 = 0.28  # Lowered requirement
Current confidence: 0.60 > 0.28 ✓ Accepted
```

### Example 3: Automatic Decay

```python
# Day 0: Create heuristic
confidence = 0.60
last_applied_at = 2026-01-01

# Day 8: Query (7 day threshold passed)
days_since_use = 8
decay = 8 * 0.01 = 0.08
new_confidence = max(0.0, 0.60 - 0.08) = 0.52

# Day 30: Still unused
days_since_use = 30
decay = 30 * 0.01 = 0.30
new_confidence = max(0.0, 0.60 - 0.30) = 0.30

# Now below threshold (0.40), won't be applied
```

---

## Demos & Testing

### Run Learning Demo

```bash
./venv/bin/python examples/learning_demo.py
```

Shows:
- Current learning state
- Adaptive filtering explanation
- Pattern matching demonstration
- Optional: Simulate learning new heuristics

### View Learning Insights

```python
from memory.procedural_memory import ProceduralMemoryManager
import yaml

with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

pm = ProceduralMemoryManager(config['memory'])
print(pm.get_learning_insights())
```

### Query Heuristics

```python
from orchestrator.retry_schemas import FailureType

heuristics = pm.query_heuristics(
    context_type='filesystem',
    failure_type=FailureType.INCORRECT_ASSUMPTIONS
)

for h in heuristics:
    print(f"{h.effective_strategy.value}: {h.confidence_score:.2%} "
          f"({h.success_count}/{h.usage_count} success)")
```

---

## Maintenance

### Prune Low Confidence Heuristics

Remove heuristics that have dropped below a threshold:

```python
# Delete heuristics with confidence < 0.1
deleted = pm.prune_low_confidence(threshold=0.1)
print(f"Pruned {deleted} low-confidence heuristics")
```

### Manual Decay

Force decay for all stale heuristics:

```python
# Decay heuristics not used in 30 days by 0.05
decayed = pm.decay_confidence(days_threshold=30, decay_amount=0.05)
print(f"Decayed {decayed} heuristics")
```

**Note:** With `procedural_auto_decay: true`, manual decay is usually unnecessary.

---

## Benefits of Enhanced Learning

1. **Self-Improving**: Gets better with every retry success
2. **Adaptive**: Adjusts to changing patterns automatically
3. **Efficient**: Fast SQL queries, no LLM overhead
4. **Transparent**: Inspectable via database or analytics
5. **Robust**: Handles noise through adaptive thresholds
6. **Maintainable**: Auto-decay keeps knowledge fresh
7. **Cross-User**: Everyone benefits from system-wide learning

---

## Comparison: Before vs After

### Before (Basic Procedural Memory)

❌ All heuristics treated equally
❌ Stale knowledge stayed forever
❌ Required manual maintenance
❌ Fixed confidence thresholds
❌ No cross-context learning

### After (Enhanced Learning)

✅ Success rate influences trust
✅ Auto-decay removes stale knowledge
✅ Self-maintaining system
✅ Adaptive thresholds
✅ Pattern matching across contexts
✅ Comprehensive analytics

---

## Future Enhancements

Potential additions:

- **Heuristic consolidation**: Merge similar heuristics automatically
- **Multi-factor matching**: Consider task similarity, not just context
- **Confidence boosting**: Accelerate learning for highly successful patterns
- **Explainability**: Show why a heuristic was applied
- **Manual tuning UI**: Web interface to adjust heuristics
- **A/B testing**: Compare strategy effectiveness

---

## Summary

The enhanced procedural memory system makes Jarvis a **continuously learning AI** that:

🧠 **Learns** from every successful retry
📊 **Tracks** success rates and confidence
🔄 **Adapts** thresholds based on performance
🕐 **Forgets** outdated patterns naturally
🎯 **Generalizes** across similar contexts
📈 **Improves** with every interaction

**Jarvis doesn't just solve problems - it remembers how and gets better every time!**
