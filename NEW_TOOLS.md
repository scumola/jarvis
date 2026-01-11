# New Tools: fetch_url & edit_file

## Overview

Two new tools have been added to Jarvis, extending its capabilities for web access and code modification:

1. **fetch_url** - Safely fetch content from web URLs
2. **edit_file** - Surgically edit files with find-and-replace

Both tools were suggested by Jarvis itself during a "machine building machines" interaction!

---

## fetch_url

### Purpose
Fetch content from HTTP/HTTPS URLs to enable:
- Web scraping
- API calls
- Documentation retrieval
- Remote file downloads

### Security Features

#### 1. Protocol Restrictions
- ✅ Allows: `http://` and `https://`
- ❌ Blocks: `file://`, `ftp://`, and all other protocols

#### 2. Network Access Control
Blocks access to:
- `localhost`, `127.0.0.1`, `::1` (loopback)
- `192.168.*` (private network)
- `10.*` (private network)
- `172.16.* - 172.31.*` (private network)
- `169.254.*` (link-local)

This prevents:
- Reading local files via file://
- Accessing internal network services
- Port scanning local network
- SSRF (Server-Side Request Forgery) attacks

#### 3. Size Limits
- Default: 10MB maximum download
- Configurable per request
- Enforced during streaming (doesn't download full file first)

#### 4. Timeout Protection
- Default: 10 second timeout
- Prevents hanging on slow/malicious servers

### Usage Examples

```python
# Fetch a web page
fetch_url("https://example.com")

# Fetch with custom timeout
fetch_url("https://api.example.com/data", timeout=30)

# Fetch larger content
fetch_url("https://example.com/bigfile.txt", max_size_mb=50)
```

### Returns

Success:
```python
{
  'success': True,
  'output': {
    'content': '...',           # Full text content
    'status_code': 200,          # HTTP status
    'url': 'https://...',        # Final URL (after redirects)
    'content_type': 'text/html', # MIME type
    'size_bytes': 1234           # Content size
  }
}
```

Error:
```python
{
  'success': False,
  'error': 'Access to local network hosts is not allowed: localhost'
}
```

---

## edit_file

### Purpose
Perform surgical edits to files without rewriting the entire file. Safer than `write_file` for code modifications.

### Safety Features

#### 1. Uniqueness Requirement
- Old string must appear **exactly once** in the file
- If appears 0 times → Error: "String not found"
- If appears 2+ times → Error: "String appears N times, provide more specific string"

This prevents:
- Accidental multiple replacements
- Wrong file modifications
- Hard-to-debug changes

#### 2. Requires Approval
- Marked as dangerous operation
- User must approve each edit
- Shows what will be changed

#### 3. Read-Before-Write
- File must exist
- Old content is validated before writing
- Atomic operation (all or nothing)

### Usage Examples

```python
# Fix a typo
edit_file(
  file_path="README.md",
  old_string="## Instal",
  new_string="## Install"
)

# Update a function
edit_file(
  file_path="tools/schema.py",
  old_string="def old_function():\n    pass",
  new_string="def new_function():\n    return True"
)

# Change configuration
edit_file(
  file_path="config.yaml",
  old_string="enabled: false",
  new_string="enabled: true"
)
```

### Returns

Success:
```python
{
  'success': True,
  'output': {
    'path': '/full/path/to/file',
    'old_length': 14,        # Chars in old_string
    'new_length': 15,        # Chars in new_string
    'file_size_before': 1234,
    'file_size_after': 1235
  }
}
```

Error:
```python
{
  'success': False,
  'error': 'String appears 3 times in file. Please provide more specific string.'
}
```

---

## Use Cases

### fetch_url Examples

**Documentation Lookup:**
```
User: "Fetch the Python requests library documentation homepage"
Jarvis: fetch_url("https://requests.readthedocs.io/")
```

**API Integration:**
```
User: "Get the latest weather data from the API"
Jarvis: fetch_url("https://api.weather.gov/...")
```

**Content Analysis:**
```
User: "What's on the Hacker News front page?"
Jarvis: fetch_url("https://news.ycombinator.com")
```

### edit_file Examples

**Code Refactoring:**
```
User: "Change the timeout from 30 to 60 in config.yaml"
Jarvis: edit_file(
  "config.yaml",
  "timeout: 30",
  "timeout: 60"
)
```

**Documentation Updates:**
```
User: "Fix the typo in README where it says 'teh' instead of 'the'"
Jarvis: edit_file(
  "README.md",
  "teh system",
  "the system"
)
```

**Self-Modification:**
```
User: "Add yourself a new tool by editing builtin_tools.py"
Jarvis: Can read the file, understand structure, propose precise edit!
```

---

## Comparison with Existing Tools

### edit_file vs write_file

| Feature | edit_file | write_file |
|---------|-----------|------------|
| Use Case | Modify existing files | Create new/replace entire files |
| Risk Level | Lower (surgical) | Higher (overwrites) |
| Validation | Checks string appears once | None |
| Best For | Code changes, fixes | New files, templates |

### fetch_url vs read_file

| Feature | fetch_url | read_file |
|---------|-----------|-----------|
| Source | Remote URLs | Local filesystem |
| Security | Blocks local network | Reads any file in CWD |
| Use Case | Web content, APIs | Local files, configs |

---

## Testing

Run the test suite:

```bash
./venv/bin/python test_new_tools.py
```

Tests verify:
- ✅ fetch_url can retrieve example.com
- ✅ fetch_url blocks localhost
- ✅ fetch_url blocks file:// protocol
- ✅ edit_file performs replacements correctly
- ✅ edit_file rejects ambiguous replacements

---

## Future Enhancements

### fetch_url
- [ ] POST/PUT/DELETE support (currently GET only)
- [ ] Request headers customization
- [ ] Authentication support (API keys, OAuth)
- [ ] Domain whitelist/blacklist configuration
- [ ] Response caching

### edit_file
- [ ] Multi-line aware matching
- [ ] Regex pattern support
- [ ] Preview mode (show diff before applying)
- [ ] Batch edits (multiple replacements in one call)
- [ ] Backup/undo mechanism

---

## The Meta Achievement 🎉

**Jarvis suggested fetch_url as its own capability gap!**

This demonstrates the "machine building machines" principle:
1. User asked: "What tool should we add next?"
2. Jarvis analyzed existing tools
3. Jarvis identified it couldn't fetch URLs
4. Jarvis proposed the fetch_url tool
5. We implemented it with safety enhancements

Now Jarvis can:
- Identify what it needs
- Propose solutions
- Use edit_file to modify its own code (with approval)

The bootstrapping loop is complete!
