# Backup & Rollback System

## Overview

Every file edit made by Jarvis is automatically backed up before modification. This provides:
- **Safety**: No edits can permanently destroy data
- **Diff verification**: See exactly what changed
- **Easy rollback**: Restore previous versions anytime
- **Audit trail**: Track all file modifications over time

## How It Works

### Automatic Backup Flow

```
1. User requests edit
   ↓
2. edit_file validates the change
   ↓
3. BACKUP CREATED (.jarvis_backups/)
   ↓
4. Edit is applied
   ↓
5. Diff is generated and shown
   ↓
6. User can verify or rollback
```

### Backup Storage

- **Location**: `.jarvis_backups/` directory in project root
- **Format**: `filename.YYYYMMDD_HHMMSS.bak`
- **Example**: `config.yaml.20260108_135522.bak`
- **Git**: Automatically added to `.gitignore`

## Tools

### 1. edit_file (Enhanced)

**Now includes automatic backup!**

```python
edit_file(
  file_path="config.yaml",
  old_string="timeout: 30",
  new_string="timeout: 60"
)
```

**Returns:**
```python
{
  'success': True,
  'output': {
    'path': '/full/path/to/config.yaml',
    'backup_path': '.jarvis_backups/config.yaml.20260108_135522.bak',
    'diff': '--- config.yaml (before)\n+++ config.yaml (after)\n...'
  }
}
```

**Features:**
- ✅ Creates backup BEFORE editing
- ✅ Shows unified diff of changes
- ✅ Only edits if string appears exactly once
- ✅ Requires approval for destructive action

### 2. list_backups (NEW)

List all available backups, optionally filtered by filename.

```python
# List all backups
list_backups()

# List backups for specific file
list_backups(file_name="config.yaml")
```

**Returns:**
```python
{
  'success': True,
  'output': {
    'backups': [
      {
        'backup_file': '.jarvis_backups/config.yaml.20260108_135523.bak',
        'original_name': 'config.yaml',
        'timestamp': '2026-01-08 13:55:23',
        'size_bytes': 1234
      },
      ...
    ],
    'count': 2,
    'filter': 'config.yaml'
  }
}
```

**Usage with Jarvis:**
```
"Show me all backups"
"List backups for config.yaml"
"What files have I edited recently?"
```

### 3. restore_backup (NEW)

Restore a file from a previous backup.

```python
restore_backup(
  backup_path=".jarvis_backups/config.yaml.20260108_135522.bak"
)
```

**Safety Features:**
- ✅ Creates backup of CURRENT state before restoring
- ✅ Shows diff of what will change
- ✅ Requires approval
- ✅ You can rollback the rollback!

**Returns:**
```python
{
  'success': True,
  'output': {
    'restored_to': '/full/path/to/config.yaml',
    'backup_used': '.jarvis_backups/config.yaml.20260108_135522.bak',
    'pre_restore_backup': '.jarvis_backups/config.yaml.20260108_140000.bak',
    'diff': '--- config.yaml (before)\n+++ config.yaml (after)\n...'
  }
}
```

## Example Workflow

### Making an Edit with Confidence

```
User: "In config.yaml, change max_retries from 2 to 3"

Jarvis: [Proposes edit_file]

System:
  APPROVAL REQUIRED
  Tool: edit_file
  Parameters: {
    "file_path": "config.yaml",
    "old_string": "max_retries: 2",
    "new_string": "max_retries: 3"
  }
  Approve? (yes/no): yes

Jarvis: I've edited config.yaml and created a backup.

  Backup: .jarvis_backups/config.yaml.20260108_135522.bak

  Diff:
  --- config.yaml (before)
  +++ config.yaml (after)
  @@ -27,7 +27,7 @@
   # Verification System
   verification:
     enabled: true
  -  max_retries: 2
  +  max_retries: 3

The change has been successfully applied.
```

### Oops! Need to Rollback

```
User: "Actually, that edit was wrong. Can you restore the previous version?"

Jarvis: [Shows list of backups]

  Available backups for config.yaml:
  - 2026-01-08 13:55:22 (.jarvis_backups/config.yaml.20260108_135522.bak)

Jarvis: [Proposes restore_backup]

System:
  APPROVAL REQUIRED
  Tool: restore_backup
  Approve? yes

Jarvis: I've restored config.yaml from the backup.

  Diff:
  --- config.yaml (before)
  +++ config.yaml (after)
  @@ -27,7 +27,7 @@
  -  max_retries: 3
  +  max_retries: 2

  Note: I also created a backup of the version before restoring,
  just in case: .jarvis_backups/config.yaml.20260108_140000.bak
```

## Diff Format

Jarvis uses **unified diff** format, standard in git and patch tools:

```diff
--- filename (before)
+++ filename (after)
@@ -1,4 +1,4 @@     # Line numbers: old file, new file
 Context line         # Unchanged line
-Old content          # Line removed (red in terminals)
+New content          # Line added (green in terminals)
 More context         # Unchanged line
```

**Reading diffs:**
- `-` lines: Removed from original
- `+` lines: Added in new version
- Regular lines: Context (unchanged)

## Backup Management

### Automatic Cleanup

Currently, backups accumulate forever (by design - safety first).

**Future enhancements:**
- [ ] Configurable retention policy
- [ ] Auto-delete backups older than N days
- [ ] Compress old backups
- [ ] Manual cleanup command

### Manual Cleanup

If you want to clean up old backups:

```bash
# See what's there
ls -lh .jarvis_backups/

# Delete all backups (be careful!)
rm -rf .jarvis_backups/

# Delete old backups (7+ days old)
find .jarvis_backups/ -name "*.bak" -mtime +7 -delete
```

## Safety Guarantees

### 1. Can't Lose Data

✅ Backup created BEFORE any edit
✅ Even restoring creates a backup first
✅ Backups stored in separate directory
✅ Original timestamp preserved

### 2. Can Always See What Changed

✅ Every edit shows unified diff
✅ Can compare any backup to current file
✅ Diff shows context around changes

### 3. Can Always Rollback

✅ Any backup can be restored
✅ Restoring is itself backed up
✅ Can rollback multiple times
✅ Can "undo the undo"

### 4. Audit Trail

✅ Timestamps show when edits happened
✅ Backup filenames include original name
✅ Can reconstruct edit history from backups

## Integration with Git

The backup system is **complementary** to git:

| Feature | Backup System | Git |
|---------|--------------|-----|
| Auto-backup edits | ✅ | ❌ (manual commit) |
| Before every change | ✅ | ❌ (commit on demand) |
| Shows diffs | ✅ | ✅ |
| Rollback support | ✅ | ✅ |
| Full version history | ❌ | ✅ |
| Tracks who/why | ❌ | ✅ |
| Branch/merge | ❌ | ✅ |

**Best Practice:**
- Use **backup system** for safety during development
- Use **git** for proper version control and collaboration
- Backups are short-term safety net
- Git is long-term history

The `.jarvis_backups/` directory is automatically added to `.gitignore` so backups don't pollute your git history.

## Testing

Run the comprehensive backup test:

```bash
./venv/bin/python test_backup_system.py
```

This demonstrates:
- ✅ Automatic backup creation
- ✅ Multiple edits creating multiple backups
- ✅ Timestamped backup naming
- ✅ Unified diff generation
- ✅ Listing backups
- ✅ Filtering by filename
- ✅ Restoring from backup
- ✅ Verification of restored content

## Design Philosophy

> **"Make it safe to experiment"**

The backup system embodies the principle that:
- Jarvis is a tool for exploration and iteration
- Users should feel confident making changes
- Mistakes should be easily reversible
- Every action should be transparent and verifiable

With automatic backups and diffs, users can:
- Try changes without fear
- See exactly what happened
- Rollback instantly if needed
- Build trust in the system

---

**Backup System Status**: ✅ Fully Implemented & Tested
