# Unix Text Tools & Command History

## What Was Added

### 🔧 **5 New Unix Text Tools**

Jarvis now has professional text manipulation tools like every unix power user:

1. **grep** - Search for patterns in files
   - Regex support
   - Case-insensitive option
   - Context lines (show lines before/after matches)

2. **diff** - Compare two files
   - Unified diff format (like git)
   - Shows exactly what changed

3. **wc** - Word count
   - Lines, words, characters, bytes

4. **head** - Show first N lines of a file

5. **tail** - Show last N lines of a file

### 📜 **Command History with Up/Down Arrows**

- Press ↑ to recall previous commands
- Press ↓ to move forward in history
- History persists across sessions (~/.jarvis_history)
- Stores last 1000 commands

---

## Why This Matters: The Config Edit Problem

### The Issue You Encountered

When you asked Jarvis to "Edit config.yaml and change max_retries from 2 to 3", it **failed silently**.

**What happened:**
```
Jarvis searched for: "max_retries: 2"
Actual file has:      "  max_retries: 2  # Maximum retry attempts"
                       ^^              ^^^^^^^^^^^^^^^^^^^^^^^^^^
                       Leading spaces  Comment after
```

The exact string wasn't found, so nothing changed!

### How Unix Tools Fix This

**Now Jarvis can:**

```
1. User: "Use grep to find 'retries' in config.yaml"

   Jarvis: grep("retries", "config/config.yaml")

   Result:
   Line 29:   max_retries: 2  # Maximum retry attempts if verification fails

2. User: "Now edit that line, including the indentation and comment"

   Jarvis: edit_file(
     file_path="config/config.yaml",
     old_string="  max_retries: 2  # Maximum retry attempts if verification fails",
     new_string="  max_retries: 3  # Maximum retry attempts if verification fails"
   )

   ✓ Success! Exact match found and changed.
```

### The Unix Way of Working

These tools let Jarvis work like a unix expert:

**Example Workflow:**
```bash
# Find what we're looking for
grep "timeout" config.yaml

# Count how big a file is
wc README.md

# Check the start of a file
head -20 main.py

# See the end of a log file
tail logs/jarvis.log

# Compare two versions
diff config.yaml .jarvis_backups/config.yaml.20260108_135522.bak
```

---

## Tool Details

### grep

**Usage:**
```python
grep(
  pattern="retries",          # Regex pattern
  file_path="config.yaml",     # File to search
  ignore_case=False,           # Case-sensitive by default
  context=2                    # Show 2 lines before/after match
)
```

**Returns:**
```python
{
  'pattern': 'retries',
  'file': 'config/config.yaml',
  'matches': [
    {
      'line_number': 29,
      'content': '  max_retries: 2  # Maximum retry attempts',
      'before': ['verification:', '  enabled: true'],  # If context > 0
      'after': ['', '# Logging']                        # If context > 0
    }
  ],
  'count': 1
}
```

**Security:**
- Only searches files within CWD
- Regex validation (won't crash on invalid patterns)

### diff

**Usage:**
```python
diff(
  file1="config.yaml",
  file2=".jarvis_backups/config.yaml.20260108_135522.bak",
  unified=True  # Unified diff format (default)
)
```

**Returns:**
```python
{
  'file1': 'config.yaml',
  'file2': '.jarvis_backups/config.yaml.20260108_135522.bak',
  'identical': False,
  'diff': '--- config.yaml (before)\n+++ config.yaml (after)\n...'
}
```

### wc

**Usage:**
```python
wc(file_path="README.md")
```

**Returns:**
```python
{
  'file': 'README.md',
  'lines': 148,
  'words': 593,
  'characters': 4688,
  'bytes': 4688
}
```

### head / tail

**Usage:**
```python
head(file_path="main.py", lines=10)  # First 10 lines
tail(file_path="logs/jarvis.log", lines=20)  # Last 20 lines
```

---

## Command History

### How It Works

When you start Jarvis:
1. Loads `~/.jarvis_history` (if exists)
2. Enables readline (up/down arrow support)
3. Saves history on exit

**Features:**
- ↑ Arrow: Previous command
- ↓ Arrow: Next command
- Ctrl+R: Reverse search (if terminal supports it)
- Persistent across sessions
- 1000 command limit

**File Location:**
```
~/.jarvis_history
```

You can view/edit it manually:
```bash
cat ~/.jarvis_history
tail -20 ~/.jarvis_history  # Last 20 commands
```

---

## Better Together: Workflow Example

**Scenario:** Find and edit a configuration setting

```
You: "Use grep to find all occurrences of 'timeout' in config files"

Jarvis: [Uses grep on config/*.yaml]
Found 3 matches:
  config/config.yaml:8:   timeout: 180
  config/config.yaml:10:  timeout: 120
  ...

You: "Use head to show me the first 15 lines of config.yaml so I can see the context"

Jarvis: [Uses head(file_path="config/config.yaml", lines=15)]
[Shows ollama configuration section]

You: "Edit line 8 to change timeout from 180 to 240, include the full line with spaces"

Jarvis: [Uses edit_file with exact string match]
✓ Backup created
✓ Change applied
[Shows diff]

You: "Use grep again to verify the change"

Jarvis: [Uses grep to confirm new value]
Line 8:   timeout: 240 ✓
```

Press ↑ to repeat any of these commands later!

---

## Testing

### Unix Tools Test

```bash
./venv/bin/python test_unix_tools.py
```

Verifies:
- ✓ grep finds patterns with line numbers
- ✓ wc counts lines/words/chars
- ✓ head shows first N lines

### Command History Test

```bash
./venv/bin/python main.py
```

Then:
1. Type some commands
2. Press ↑ arrow - previous command appears
3. Exit and restart Jarvis
4. Press ↑ arrow - previous session's commands still there!

---

## Why These Tools Are Fundamental

### Unix Philosophy

> Write programs that do one thing and do it well.
> Write programs to work together.

These tools embody that philosophy:

- **grep**: Find things
- **wc**: Count things
- **head/tail**: Show parts
- **diff**: Compare things

Combined, they let Jarvis:
- Explore files intelligently
- Understand structure before editing
- Verify changes after editing
- Work incrementally and safely

### Real-World Scenarios

**Debugging:**
```
tail logs/jarvis.log             # See recent errors
grep "ERROR" logs/jarvis.log     # Find all errors
wc logs/jarvis.log               # How big is the log?
```

**Code Review:**
```
find_files "*.py"                # Find all Python files
grep "TODO" main.py              # Find todos
diff main.py.old main.py         # What changed?
```

**Configuration:**
```
grep "enabled" config.yaml       # Find all enabled flags
head config.yaml                 # See top-level settings
```

---

## Current Tool Count: **13 Tools**

1. read_file
2. write_file
3. **edit_file** (with backup/diff/rollback)
4. list_directory
5. find_files
6. fetch_url
7. list_backups
8. restore_backup
9. **grep** ← NEW
10. **diff** ← NEW
11. **wc** ← NEW
12. **head** ← NEW
13. **tail** ← NEW

Jarvis is becoming a power user! 🚀

---

## Next Steps

With these tools, Jarvis can now:

✅ Search files before editing (grep)
✅ Verify exact strings to match (grep with context)
✅ Check file sizes before reading (wc)
✅ Preview files (head)
✅ Monitor logs (tail)
✅ Compare versions (diff)
✅ Recall commands easily (history)

**Still TODO:**
- [ ] News headlines tool (searxng integration)
- [ ] LED panel face display
- [ ] More advanced text tools (sed/awk - if needed)

---

**Status:** ✅ Unix Tools & Command History Fully Implemented
