# Memory Import/Export

Complete backup and restore system for Jarvis memories. Export memories to portable JSON files and restore them when needed.

## Features

### Export Capabilities
- **Metadata**: All memory fields (text, type, confidence, importance, decay score, etc.)
- **Vector Embeddings**: ChromaDB embeddings and documents
- **Relationships**: Memory relationships (supersedes, supports, etc.)
- **Audit Logs**: Optional inclusion of audit trail
- **Selective Export**: Active-only or include archived memories

### Import Capabilities
- **Smart Deduplication**: Skip existing memories by embedding ID
- **Relationship Restoration**: Recreate memory relationships
- **Flexible Options**: Overwrite or skip existing data
- **Dry Run**: Preview what would be imported
- **Error Handling**: Continues on errors, reports issues at end

## Quick Start

### Export Memories

```bash
# Export active memories (recommended for regular backups)
./venv/bin/python scripts/export_memories.py backups/memories_$(date +%Y-%m-%d).json

# Full backup with archived memories
./venv/bin/python scripts/export_memories.py backups/full_backup.json --all

# Include audit logs (larger file)
./venv/bin/python scripts/export_memories.py backups/backup_with_audit.json --audit
```

### Import Memories

```bash
# Preview what would be imported
./venv/bin/python scripts/import_memories.py backups/memories_2026-01-08.json --dry-run

# Import (skips existing memories)
./venv/bin/python scripts/import_memories.py backups/memories_2026-01-08.json

# Import and overwrite existing
./venv/bin/python scripts/import_memories.py backups/memories.json --no-skip
```

## Export Options

### CLI Usage

```bash
./venv/bin/python scripts/export_memories.py <output_file> [options]
```

**Arguments:**
- `output_file` - Path to output JSON file

**Options:**
- `--all` - Include archived/superseded memories (default: active only)
- `--audit` - Include audit logs (can make file large)
- `--no-relationships` - Exclude memory relationships

### Examples

```bash
# Daily backup (active memories only)
./venv/bin/python scripts/export_memories.py backups/daily_$(date +%Y-%m-%d).json

# Full backup with everything
./venv/bin/python scripts/export_memories.py backups/full.json --all --audit

# Minimal backup (no relationships)
./venv/bin/python scripts/export_memories.py backups/minimal.json --no-relationships
```

### Python API

```python
from memory import MemoryManager, MemoryExporter

# Initialize
memory_manager = MemoryManager(config['memory'])
exporter = MemoryExporter(
    memory_manager.vector_store,
    memory_manager.metadata_store
)

# Export
result = exporter.export_all(
    output_path='backups/my_backup.json',
    include_archived=False,
    include_relationships=True,
    include_audit_log=False
)

print(f"Exported {result['memories_exported']} memories")
print(f"File size: {result['file_size_bytes']} bytes")
```

## Import Options

### CLI Usage

```bash
./venv/bin/python scripts/import_memories.py <input_file> [options]
```

**Arguments:**
- `input_file` - Path to input JSON file

**Options:**
- `--no-skip` - Overwrite existing memories (default: skip existing)
- `--no-relationships` - Don't restore memory relationships
- `--dry-run` - Preview import without making changes

### Examples

```bash
# Preview import
./venv/bin/python scripts/import_memories.py backups/memories.json --dry-run

# Standard import (skip existing)
./venv/bin/python scripts/import_memories.py backups/memories.json

# Full restore (overwrite existing)
./venv/bin/python scripts/import_memories.py backups/full.json --no-skip

# Import memories only (no relationships)
./venv/bin/python scripts/import_memories.py backups/memories.json --no-relationships
```

### Python API

```python
from memory import MemoryManager, MemoryImporter

# Initialize
memory_manager = MemoryManager(config['memory'])
importer = MemoryImporter(
    memory_manager.vector_store,
    memory_manager.metadata_store
)

# Import
result = importer.import_all(
    input_path='backups/my_backup.json',
    skip_existing=True,
    restore_relationships=True
)

print(f"Imported: {result['imported']}")
print(f"Skipped: {result['skipped']}")
print(f"Errors: {len(result['errors'])}")
```

## JSON Format

The export file is a JSON document with this structure:

```json
{
  "metadata": {
    "export_date": "2026-01-08T21:32:40.631518",
    "total_memories": 9,
    "include_archived": false,
    "include_relationships": true,
    "include_audit_log": false,
    "version": "1.0"
  },
  "memories": [
    {
      "id": 3,
      "memory_text": "User's name is Steve",
      "memory_type": "identity",
      "embedding_id": "417ce2c3-aace-4aaa-a9a0-cf52531d766a",
      "confidence": 1.0,
      "importance": 0.9,
      "decay_score": 100.0,
      "source_query": null,
      "source_context": null,
      "created_by": "curator_llm",
      "created_at": "2026-01-08T17:02:52",
      "last_accessed_at": "2026-01-08T21:32:06",
      "access_count": 17,
      "status": "active",
      "superseded_by": null,
      "vector_metadata": {
        "memory_type": "identity",
        "memory_id": "3",
        "confidence": "0.95",
        "importance": "0.9"
      },
      "vector_document": "User's name is Steve"
    }
  ],
  "relationships": [
    {
      "id": 2,
      "memory_id": 3,
      "related_memory_id": 1,
      "relationship_type": "supersedes",
      "created_at": "2026-01-08T21:27:48"
    }
  ]
}
```

## Common Workflows

### Daily Backup

Create a daily backup of active memories:

```bash
#!/bin/bash
# daily_backup.sh

BACKUP_DIR="/home/steve/AI/jarvis/backups"
DATE=$(date +%Y-%m-%d)

cd /home/steve/AI/jarvis
./venv/bin/python scripts/export_memories.py "$BACKUP_DIR/daily_$DATE.json"

# Keep only last 7 days
find "$BACKUP_DIR" -name "daily_*.json" -mtime +7 -delete
```

Add to crontab:
```bash
0 2 * * * /home/steve/AI/jarvis/daily_backup.sh >> /home/steve/AI/jarvis/logs/backup.log 2>&1
```

### Weekly Full Backup

Create a weekly full backup with everything:

```bash
#!/bin/bash
# weekly_backup.sh

BACKUP_DIR="/home/steve/AI/jarvis/backups/weekly"
DATE=$(date +%Y-%m-%d)

mkdir -p "$BACKUP_DIR"
cd /home/steve/AI/jarvis
./venv/bin/python scripts/export_memories.py \
    "$BACKUP_DIR/full_$DATE.json" \
    --all \
    --audit
```

Add to crontab (Sunday at 3 AM):
```bash
0 3 * * 0 /home/steve/AI/jarvis/weekly_backup.sh >> /home/steve/AI/jarvis/logs/backup.log 2>&1
```

### Restore from Backup

```bash
# 1. Stop Jarvis (if running)
# 2. Preview the backup
./venv/bin/python scripts/import_memories.py backups/memories_2026-01-08.json --dry-run

# 3. Import (skip existing)
./venv/bin/python scripts/import_memories.py backups/memories_2026-01-08.json

# 4. Or full restore (overwrite existing)
./venv/bin/python scripts/import_memories.py backups/memories_2026-01-08.json --no-skip
```

### Migrate to New System

```bash
# On old system
./venv/bin/python scripts/export_memories.py export_all.json --all --audit

# Copy export_all.json to new system

# On new system
./venv/bin/python scripts/import_memories.py export_all.json
```

### Backup Before Major Changes

```bash
# Before running consolidation or other bulk operations
./venv/bin/python scripts/export_memories.py backups/pre_consolidation_$(date +%Y-%m-%d_%H-%M).json --all
```

## Storage Considerations

### File Sizes (Approximate)

| Memories | Active Only | With Archived | With Audit Logs |
|----------|-------------|---------------|-----------------|
| 10       | ~8 KB       | ~12 KB        | ~15 KB          |
| 100      | ~80 KB      | ~120 KB       | ~200 KB         |
| 1,000    | ~800 KB     | ~1.2 MB       | ~3 MB           |
| 10,000   | ~8 MB       | ~12 MB        | ~30 MB          |

**Note**: Audit logs can significantly increase file size if you have many operations logged.

### Compression

JSON files compress well with gzip:

```bash
# Compress backup
gzip backups/memories_2026-01-08.json
# Creates: backups/memories_2026-01-08.json.gz (typically 70-80% smaller)

# Decompress for import
gunzip backups/memories_2026-01-08.json.gz
```

## Import Behavior

### Duplicate Detection

Memories are considered duplicates if they have the same `embedding_id`. When importing:

- **Default behavior** (`skip_existing=True`): Existing memories are skipped
- **With `--no-skip`** (`skip_existing=False`): Would overwrite, but currently skips to prevent data loss

### Relationship Restoration

Relationships are restored using ID mapping:
1. Old memory IDs in export file
2. New memory IDs in database
3. Mapping created during import
4. Relationships created with new IDs

**Note**: Relationships are only restored if both memories were successfully imported or already exist.

### Error Handling

Import continues even if some memories fail:
- Errors are collected and reported at end
- Successfully imported memories are committed
- Failed memories are skipped
- Exit code indicates success (0) or failure (1)

## Safety Features

### Export Safety
- **Non-destructive**: Export never modifies the database
- **Atomic writes**: File written completely or not at all
- **Timestamp metadata**: Know when export was created
- **Version tracking**: Future compatibility

### Import Safety
- **Dry run option**: Preview without changes
- **Skip by default**: Won't overwrite existing data unless told to
- **Error isolation**: One bad memory won't fail entire import
- **Audit trail**: All imports are logged

## Troubleshooting

### Export Issues

**Problem**: Export file is very large

**Solution**:
```bash
# Exclude audit logs
./venv/bin/python scripts/export_memories.py backup.json

# Export active only
./venv/bin/python scripts/export_memories.py backup.json  # Default behavior

# Compress after export
gzip backup.json
```

**Problem**: "Memory system is disabled"

**Solution**:
```yaml
# config/config.yaml
memory:
  enabled: true
```

### Import Issues

**Problem**: "Input file not found"

**Solution**: Check file path is correct and file exists

**Problem**: All memories skipped

**Cause**: Memories already exist (detected by embedding_id)

**Solution**: This is normal behavior. Use `--no-skip` to force overwrite (not recommended)

**Problem**: "Skipping relationship - memories not found"

**Cause**: Relationship references memories that don't exist

**Solution**:
- Normal if importing partial backup
- Export with `--all` to include archived memories
- Or export/import from same database state

**Problem**: Some memories failed to import

**Solution**:
- Check error messages in output
- Verify database schema is up to date
- Check memory data is valid JSON

## Best Practices

### Regular Backups

1. **Daily active backups**: Small, fast, recovers recent work
2. **Weekly full backups**: Everything, for disaster recovery
3. **Pre-operation backups**: Before consolidation, bulk changes
4. **Retention policy**: Keep daily for 7 days, weekly for 4 weeks

### Backup Verification

Periodically test your backups:

```bash
# 1. Export current state
./venv/bin/python scripts/export_memories.py test_export.json

# 2. Preview import (dry run)
./venv/bin/python scripts/import_memories.py test_export.json --dry-run

# 3. Check no errors reported
```

### Disaster Recovery Plan

1. **Keep backups off-system**: Copy to another machine/cloud
2. **Version backups**: Don't overwrite old backups immediately
3. **Test restores**: Verify backups work before you need them
4. **Document procedure**: Keep recovery steps accessible

### Export Strategy

**Recommended schedule**:
- **Daily**: Active memories only (automated via cron)
- **Weekly**: Full backup with archived (automated via cron)
- **Before major changes**: Manual full backup
- **Before updates**: Manual full backup

## Integration with Git

While memories are in MySQL/ChromaDB, exports can be version controlled:

```bash
# Add to .gitignore (don't commit backups)
backups/*.json

# But keep structure
git add backups/.gitkeep

# Or version control specific backups
git add backups/initial_setup.json
git commit -m "Initial memory state"
```

## Future Enhancements

Potential improvements:
- **Incremental backups**: Only export changed memories
- **Compression**: Built-in gzip compression
- **Encryption**: Encrypt sensitive memories
- **Cloud sync**: Automatic backup to S3/Dropbox
- **Backup rotation**: Automatic cleanup of old backups
- **Differential restore**: Only import new/changed memories
- **Merge conflicts**: Handle when same memory changed in both places

---

**Status**: ✅ Fully implemented and tested
**Last Updated**: 2026-01-08
