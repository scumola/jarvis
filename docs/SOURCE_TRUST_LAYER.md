# Source Trust & Fact Confidence Layer

## Overview

The Source Trust & Fact Confidence Layer transforms Jarvis from a system that blindly stores facts to one that tracks provenance, evaluates reliability, and prefers verified information.

**Core Principle**: "X is probably true, because Y sources agree, Z source is reputable, and it hasn't been contradicted."

## Architecture

### Before (Naive Storage)
```
User: "The Earth is flat"
System: Stores "Earth is flat" with confidence 0.8
```

### After (Source Trust)
```
User: "The Earth is flat"
System: Stores "Earth is flat"
  - source_type: user
  - source_identity: user_statement
  - verification_status: unverified
  - confidence: 0.8

Later, when tool finds contradictory evidence:
System: Updates verification_status to "contradicted"
  - Retrieval heavily penalizes this fact (70% penalty)
  - System prefers facts from reputable tools/sources
```

## Database Schema

### New Fields in `memories` Table

```sql
source_type ENUM('user', 'tool_output', 'web', 'inference', 'unknown')
  -- Where did this fact come from?

source_identity VARCHAR(500)
  -- Specific identifier: domain name, tool name, model name

verification_status ENUM('unverified', 'corroborated', 'contradicted', 'deprecated')
  -- Current verification state

corroboration_count INT DEFAULT 0
  -- How many times has this been verified by other sources?

last_verified_at TIMESTAMP NULL
  -- When was this last checked/verified?
```

### Source Types Explained

| Source Type | Description | Example | Reliability |
|---|---|---|---|
| `user` | Directly stated by user | "My name is Steve" | High for identity, variable for facts |
| `tool_output` | From tool execution | grep found "version 2.0" | Depends on tool |
| `web` | From web search/fetch | Data from wikipedia.org | Depends on domain |
| `inference` | LLM inferred | User asked about Python, probably uses it | Lower confidence |
| `unknown` | Source not determined | Legacy memories | Lowest reliability |

### Verification States

| Status | Meaning | Retrieval Impact | When to Use |
|---|---|---|---|
| `unverified` | Not yet checked | No change (1.0x) | New memories |
| `corroborated` | Confirmed by multiple sources | Boost (+5% per corroboration) | Multiple sources agree |
| `contradicted` | Other evidence disagrees | Heavy penalty (0.3x, 70% reduction) | Conflicting information found |
| `deprecated` | Outdated/no longer relevant | Moderate penalty (0.7x, 30% reduction) | Time-sensitive info expired |

## Python API

### Memory Schema

```python
from memory.schemas import Memory, MemorySourceType, VerificationStatus

memory = Memory(
    memory_text="Python 3.12 is the latest version",
    memory_type=MemoryType.CAPABILITY,
    confidence=0.85,
    importance=0.60,

    # Source Trust fields
    source_type=MemorySourceType.WEB,
    source_identity="python.org",
    verification_status=VerificationStatus.UNVERIFIED,
    corroboration_count=0,
    last_verified_at=None
)
```

### Memory Proposal (from Curator)

```python
from memory.schemas import MemoryProposal, MemorySourceType

proposal = MemoryProposal(
    memory_text="User prefers Python over JavaScript",
    memory_type=MemoryType.PREFERENCE,
    confidence=0.90,
    importance=0.70,
    reasoning="User explicitly stated their preference",

    # NEW: Source tracking
    source_type=MemorySourceType.USER,
    source_identity="user_statement"
)
```

### Update Verification Status

```python
# Mark as corroborated (increases trust)
memory_manager.metadata_store.update_verification_status(
    memory_id=123,
    verification_status="corroborated",
    increment_corroboration=True  # Bumps corroboration_count
)

# Mark as contradicted (decreases trust)
memory_manager.metadata_store.update_verification_status(
    memory_id=456,
    verification_status="contradicted",
    increment_corroboration=False
)
```

## Retrieval Ranking Algorithm

### Enhanced Relevance Score

The retrieval ranking now includes source trust:

```python
# Base relevance components
base_relevance = (
    (1.0 - semantic_distance) * 0.35 +  # Semantic match (35%)
    memory.confidence * 0.30 +          # LLM confidence (30%)
    memory.importance * 0.20 +          # Importance (20%)
    (decay_score / 100.0) * 0.10 +      # Vitality/freshness (10%)
    (min(corroboration_count, 5) / 5.0) * 0.05  # Corroboration (5%)
)

# Verification trust multiplier
if verification_status == "corroborated":
    multiplier = 1.0 + (corroboration_count * 0.05)  # +5% per corroboration
elif verification_status == "contradicted":
    multiplier = 0.3  # 70% penalty
elif verification_status == "deprecated":
    multiplier = 0.7  # 30% penalty
else:  # unverified
    multiplier = 1.0  # No change

# Final score
relevance = base_relevance * multiplier
```

### Example Scoring

**Scenario**: Query for "What programming language do I prefer?"

| Memory | Semantic Match | Confidence | Verification | Corroborations | Final Score | Rank |
|---|---|---|---|---|---|---|
| "User prefers Python" | 0.95 | 0.90 | corroborated | 3 | 0.89 × 1.15 = **1.02** | #1 |
| "User likes JavaScript" | 0.90 | 0.75 | unverified | 0 | 0.78 × 1.0 = **0.78** | #2 |
| "User dislikes Python" | 0.93 | 0.80 | contradicted | 0 | 0.82 × 0.3 = **0.25** | #3 |

**Result**: System returns "User prefers Python" as the most reliable fact.

## Curator LLM Integration

### Updated Prompt

The curator now includes source analysis instructions:

```
SOURCE TYPES (where did this fact come from):
- user: Directly stated by the user
- tool_output: From a tool execution result
- web: From web search or fetch_url
- inference: LLM inferred from conversation

GUIDELINES:
...
8. ALWAYS identify the source_type for fact verification

OUTPUT FORMAT:
{
    "memory_text": "...",
    "memory_type": "...",
    "confidence": 0.85,
    "importance": 0.70,
    "source_type": "user",  # NEW
    "source_identity": "user_statement",  # NEW
    "reasoning": "..."
}
```

### Source Type Inference

If curator doesn't specify source_type, the system infers it:

```python
if memory_type in [MemoryType.IDENTITY, MemoryType.PREFERENCE]:
    source_type = MemorySourceType.USER  # Likely direct user statement
else:
    source_type = MemorySourceType.INFERENCE  # System inferred
```

## Usage Patterns

### Pattern 1: User-Stated Facts

```
User: "My name is Alice and I work at Google"

Curator proposes:
1. "User's name is Alice"
   - source_type: user
   - confidence: 1.0 (explicitly stated)

2. "User works at Google"
   - source_type: user
   - confidence: 1.0 (explicitly stated)

System stores both as unverified but high confidence.
```

### Pattern 2: Tool-Verified Facts

```
User: "What version of Python is installed?"
Tool: grep shows "Python 3.11.5"

Curator proposes:
"Python 3.11.5 is installed on the system"
  - source_type: tool_output
  - source_identity: grep
  - confidence: 0.95

System: Marks as corroborated if another tool confirms later.
```

### Pattern 3: Web-Sourced Facts

```
User: "Look up the latest Python version"
Tool: fetch_url from python.org shows "3.12"

Curator proposes:
"Python 3.12 is the latest version"
  - source_type: web
  - source_identity: python.org
  - confidence: 0.90

System: Can re-verify by fetching again later.
```

### Pattern 4: Contradiction Detection

```
Existing memory:
"Earth is flat" (source: user, unverified)

User: "Search for Earth shape"
Tool: web_search returns multiple sources saying spherical

Curator proposes:
"Earth is spherical"
  - source_type: web
  - source_identity: nasa.gov
  - confidence: 1.0

System:
1. Detects contradiction with existing memory
2. Updates old memory: verification_status = "contradicted"
3. Stores new memory as corroborated
4. Retrieval heavily penalizes the "flat" memory
```

## Implementation Status

### ✅ Completed

1. **Database Schema**
   - Added 5 new fields to memories table
   - Migration script executed successfully
   - Indexes created for performance

2. **Python Models**
   - Added MemorySourceType enum
   - Added VerificationStatus enum
   - Updated Memory and MemoryProposal schemas

3. **MetadataStore Updates**
   - insert_memory() handles new fields
   - _row_to_memory() populates new fields
   - Added update_verification_status() method

4. **MemoryManager Updates**
   - Intelligent source_type inference
   - Enhanced retrieval ranking with trust multipliers
   - Corroboration count in scoring

5. **Curator LLM Updates**
   - Prompt includes source analysis instructions
   - JSON parsing handles source_type and source_identity
   - Fallback to inference if not provided

### 🔄 Pending Enhancements

1. **Automatic Corroboration**
   - When storing similar facts, increment corroboration_count
   - Requires semantic similarity check in store_memory()

2. **Re-verification Triggers**
   - Periodic background task to re-check web sources
   - Re-verify facts when confidence drops below threshold

3. **Source Reputation System**
   - Track reliability of domains and tools
   - Adjust confidence based on source history

4. **Temporal Awareness**
   - Mark time-sensitive facts for re-verification
   - Auto-deprecate outdated information

## Testing

### Manual Testing

```bash
# Start CLI
python main.py

# Test user-stated fact
You: My name is Steve and I prefer TypeScript

# Check database
mysql -h tools -u steve -pkoala1 jarvis -e "
SELECT memory_text, source_type, source_identity, verification_status
FROM memories
WHERE user_id = 1
ORDER BY created_at DESC LIMIT 5;"

# Expected:
# memory_text: "User's name is Steve"
# source_type: user
# source_identity: curator_llm
# verification_status: unverified
```

### API Testing

```bash
API_KEY="your-api-key"

# Create memory via chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "I work at Anthropic"}'

# Check memories
curl -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/api/v1/memories?limit=5"

# Should show source_type in response
```

## Future Directions

### 1. Multi-Source Fact Fusion

When multiple sources provide the same fact:
- Aggregate confidence scores
- Track all source identities
- Automatic corroboration

### 2. Source Reputation Tracking

```sql
CREATE TABLE source_reputation (
    source_identity VARCHAR(500) PRIMARY KEY,
    source_type ENUM('tool', 'domain'),
    accuracy_score FLOAT,  -- Historical accuracy
    usage_count INT,       -- How often cited
    last_verified_at TIMESTAMP
);
```

### 3. Fact Expiration

Time-sensitive facts auto-deprecate:
```python
if memory.memory_type == MemoryType.EPISODIC:
    if (now - memory.created_at) > timedelta(days=90):
        # Mark as deprecated
        memory_manager.metadata_store.update_verification_status(
            memory.id,
            "deprecated"
        )
```

### 4. User Feedback Loop

Allow users to correct facts:
```
User: "Actually, I prefer Python, not TypeScript"

System:
1. Contradicts old memory
2. Stores new memory with higher confidence
3. Learns to trust user corrections
```

## Benefits

### Before Source Trust
```
Problem: System treats all facts equally
- User says "Earth is flat" -> Stored with confidence 0.8
- Another user says "Earth is round" -> Stored with confidence 0.8
- System randomly picks which to return
```

### After Source Trust
```
Solution: System evaluates reliability
- User says "Earth is flat" -> Stored, source: user, unverified
- Web search from NASA -> Contradicts previous fact
- System updates old fact to "contradicted" (70% penalty)
- Retrieval heavily prefers the NASA-sourced fact
- System becomes robust, not gullible
```

## Summary

The Source Trust & Fact Confidence Layer makes Jarvis:

1. **Accountable**: Every fact has a traceable source
2. **Skeptical**: New facts start unverified
3. **Learning**: Corroboration increases trust
4. **Self-Correcting**: Contradictions are detected and penalized
5. **Intelligent**: Retrieval prefers reliable, verified facts

This transforms Jarvis from a passive recorder to an active fact evaluator.

---

**Status**: ✅ Core Implementation Complete
**Date**: 2026-01-09
**Next**: Test with real-world scenarios and implement automatic corroboration
