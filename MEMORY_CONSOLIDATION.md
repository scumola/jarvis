# Memory Consolidation

The memory consolidation system automatically detects and merges duplicate, similar, and supporting memories to improve memory quality and reduce redundancy.

## Features

### 1. Duplicate Detection
- **Threshold**: Distance < 0.1 (almost identical)
- **Action**: Merge into single memory, archive duplicates
- **Benefit**: Eliminates redundant information

### 2. Similar Memory Detection
- **Threshold**: Distance < 0.3 (similar enough to consider merging)
- **Action**: Flag for review or auto-merge
- **Benefit**: Consolidates related information

### 3. Supporting Memory Detection
- **Threshold**: Distance < 0.5 (related/supporting)
- **Action**: Boost confidence of both memories
- **Benefit**: Strengthen memories with multiple confirmations

## How It Works

### Semantic Similarity
Uses ChromaDB's vector embeddings to calculate cosine distance between memories:
- **0.0** = Identical
- **0.1** = Very similar (duplicates)
- **0.3** = Similar (consider merging)
- **0.5** = Related (supporting)
- **1.0** = Completely different

### Merging Strategy

When duplicates are merged:
1. **Keep** the memory with highest confidence
2. **Archive** other memories as "superseded"
3. **Boost confidence** of kept memory (0.1 per merged memory, cap +0.3)
4. **Boost decay score** (+5 per merged memory, simulates access)
5. **Create relationships** in `memory_relationships` table

### Supporting Memory Boosting

When supporting memories are found:
1. **Boost confidence** by +0.05 for each memory
2. **Create "supports" relationship** in database
3. **No archiving** - both memories remain active

## Usage

### CLI Script

#### Generate Consolidation Report
```bash
./venv/bin/python scripts/consolidate_memories.py --report
```

Sample output:
```
MEMORY CONSOLIDATION REPORT
======================================================================

STATISTICS:
  Total active memories: 10
  Duplicate groups: 1
  Similar groups: 0
  Supporting pairs: 1

DUPLICATES (should merge):
  Found 1 duplicate groups

  1. Distance: 0.0000
     [1] Test memory: User's name is Steve...
             Confidence: 0.95, Decay: 100.0
     [3] Test memory: User's name is Steve...
             Confidence: 0.95, Decay: 100.0

RECOMMENDATIONS:
  1. Merge 1 duplicate groups
  3. Boost confidence for 1 supporting pairs
```

#### Auto-Consolidate (Merge Duplicates)
```bash
./venv/bin/python scripts/consolidate_memories.py --auto
```

#### Auto-Consolidate with Confidence Boosting
```bash
./venv/bin/python scripts/consolidate_memories.py --auto --boost
```

#### Save Report to File
```bash
./venv/bin/python scripts/consolidate_memories.py --report --output consolidation_report.txt
```

### Python API

```python
from memory import MemoryManager, MemoryConsolidator, auto_consolidate

# Initialize
memory_manager = MemoryManager(config['memory'])

# Manual analysis
consolidator = MemoryConsolidator(
    memory_manager.vector_store,
    memory_manager.metadata_store
)

analysis = consolidator.analyze_all_memories()
report = consolidator.generate_consolidation_report(analysis)
print(report)

# Auto-consolidate
results = auto_consolidate(
    vector_store=memory_manager.vector_store,
    metadata_store=memory_manager.metadata_store,
    merge_duplicates=True,
    boost_supporting=True
)

print(f"Merged {results['merged_groups']} groups")
print(f"Boosted {results['boosted_pairs']} pairs")
```

### Manual Merging

```python
# Find duplicates
analysis = consolidator.analyze_all_memories()

# Merge specific duplicate group
for dup in analysis['duplicates']:
    memories = dup['memories']
    kept_id = consolidator.merge_duplicates(
        memories,
        keep_highest_confidence=True
    )
    print(f"Merged into memory {kept_id}")
```

## Database Schema

### Relationships Table

```sql
CREATE TABLE memory_relationships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    memory_id INT NOT NULL,
    related_memory_id INT NOT NULL,
    relationship_type ENUM('supersedes', 'contradicts', 'supports', 'related') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (memory_id) REFERENCES memories(id),
    FOREIGN KEY (related_memory_id) REFERENCES memories(id)
);
```

### Relationship Types

- **supersedes**: New memory replaces old memory (from merging)
- **contradicts**: Memories conflict (not currently used)
- **supports**: Memories agree/reinforce each other
- **related**: General relationship (future use)

## Scheduling

### Periodic Consolidation (Optional)

Add to crontab for weekly consolidation:

```bash
# Every Sunday at 3 AM
0 3 * * 0 cd /home/steve/AI/jarvis && ./venv/bin/python scripts/consolidate_memories.py --auto --boost >> logs/consolidation.log 2>&1
```

### On-Demand

Run manually when you notice:
- Many similar memories about the same topic
- Duplicate entries appearing
- Want to clean up memory database

## Configuration

No configuration needed! The consolidation system uses:
- **ChromaDB** for semantic similarity (already configured)
- **MySQL** for metadata and relationships (already configured)
- **Fixed thresholds** for duplicate/similar/supporting detection

### Thresholds

Located in `memory/consolidation.py`:

```python
DUPLICATE_THRESHOLD = 0.1   # Almost identical
SIMILAR_THRESHOLD = 0.3     # Similar enough to merge
SUPPORTING_THRESHOLD = 0.5  # Related/supporting
```

Adjust these if you want more aggressive or conservative consolidation.

## Benefits

### Memory Quality
- **Higher confidence** for frequently confirmed information
- **No duplicates** cluttering the database
- **Better retrieval** - fewer redundant results

### Performance
- **Fewer embeddings** to search through
- **Faster queries** with consolidated memories
- **Better relevance** ranking

### Maintenance
- **Automatic cleanup** of redundant information
- **Audit trail** of what was merged
- **Reversible** - archived memories remain in database

## Verification

### Check Consolidation Results

```bash
# Before consolidation
./venv/bin/python scripts/consolidate_memories.py --report

# Run consolidation
./venv/bin/python scripts/consolidate_memories.py --auto

# After consolidation
./venv/bin/python scripts/consolidate_memories.py --report
```

### SQL Queries

```sql
-- View all superseded memories
SELECT m1.id, m1.memory_text, m1.status, m2.id AS superseded_by
FROM memories m1
JOIN memories m2 ON m1.superseded_by = m2.id
WHERE m1.status = 'superseded';

-- View all relationships
SELECT
    r.relationship_type,
    m1.id AS memory1_id,
    m1.memory_text AS memory1,
    m2.id AS memory2_id,
    m2.memory_text AS memory2
FROM memory_relationships r
JOIN memories m1 ON r.memory_id = m1.id
JOIN memories m2 ON r.related_memory_id = m2.id
ORDER BY r.created_at DESC;

-- Count relationships by type
SELECT relationship_type, COUNT(*)
FROM memory_relationships
GROUP BY relationship_type;
```

## Troubleshooting

### "No duplicates found" but I know there are duplicates

**Cause**: Memories might have slightly different wording

**Solution**:
1. Check the distance in the report
2. Adjust `DUPLICATE_THRESHOLD` in `consolidation.py`
3. Look at "similar" groups instead

### Merged wrong memories

**Cause**: Distance threshold too high

**Solution**:
1. Check MySQL for archived memories
2. Manually restore if needed:
   ```sql
   UPDATE memories SET status = 'active', superseded_by = NULL WHERE id = X;
   ```
3. Lower the threshold

### Performance is slow

**Cause**: Large number of memories (>1000)

**Solution**:
1. Consolidation is O(n²) for comparing memories
2. Run less frequently
3. Or add batching/chunking to the analysis

## Future Enhancements

Potential improvements:
- **LLM-based merging**: Use LLM to intelligently combine memory texts
- **User approval**: Show merge suggestions before applying
- **Conflict resolution**: Better handling of contradicting memories
- **Smart text merging**: Combine details from multiple similar memories
- **Incremental consolidation**: Only check new memories against existing ones
- **Duplicate prevention**: Check before inserting new memories

---

**Status**: ✅ Fully implemented and tested
**Last Updated**: 2026-01-08
