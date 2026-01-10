"""
Built-in tools that ship with Jarvis.
These are the minimal set needed for bootstrapping.
"""

import os
import logging
import shutil
import subprocess
import re
from pathlib import Path
from typing import Any, Dict, List
from fnmatch import fnmatch
from urllib.parse import urlparse
from datetime import datetime
import difflib
import requests
from .schema import ToolSchema, ToolParameter, ToolParameterType, ToolResult

logger = logging.getLogger(__name__)

# Backup directory for file edits
BACKUP_DIR = Path(".jarvis_backups")


# =============================================================================
# Backup Management Helpers
# =============================================================================

def _ensure_backup_dir():
    """Ensure backup directory exists."""
    BACKUP_DIR.mkdir(exist_ok=True)

    # Add to .gitignore if not already there
    gitignore = Path(".gitignore")
    if gitignore.exists():
        content = gitignore.read_text()
        if ".jarvis_backups" not in content:
            with open(gitignore, 'a') as f:
                f.write("\n# Jarvis file edit backups\n.jarvis_backups/\n")


def _create_backup(file_path: Path) -> Path:
    """Create a timestamped backup of a file."""
    _ensure_backup_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.name}.{timestamp}.bak"
    backup_path = BACKUP_DIR / backup_name

    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup: {backup_path}")

    return backup_path


def _generate_diff(old_content: str, new_content: str, filename: str = "file") -> str:
    """Generate a unified diff between old and new content."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"{filename} (before)",
        tofile=f"{filename} (after)",
        lineterm=''
    )

    return ''.join(diff)


# =============================================================================
# Tool Implementations
# =============================================================================

def read_file_impl(file_path: str, max_lines: int = None) -> Dict[str, Any]:
    """
    Read a file from the filesystem.
    Safe read-only operation.
    """
    try:
        path = Path(file_path).resolve()

        # Basic safety check - don't read outside project root
        # (In production, this should be more sophisticated)
        if not path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        if not path.is_file():
            return {'success': False, 'error': f'Not a file: {file_path}'}

        with open(path, 'r', encoding='utf-8') as f:
            if max_lines:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)
                content = ''.join(lines)
                truncated = i >= max_lines
            else:
                content = f.read()
                truncated = False

        return {
            'success': True,
            'output': {
                'content': content,
                'path': str(path),
                'size_bytes': path.stat().st_size,
                'truncated': truncated
            }
        }

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return {'success': False, 'error': str(e)}


def write_file_impl(file_path: str, content: str, append: bool = False) -> Dict[str, Any]:
    """
    Write content to a file.
    DANGEROUS - modifies filesystem.
    """
    try:
        path = Path(file_path).resolve()

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        mode = 'a' if append else 'w'
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)

        return {
            'success': True,
            'output': {
                'path': str(path),
                'bytes_written': len(content.encode('utf-8')),
                'appended': append
            }
        }

    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}")
        return {'success': False, 'error': str(e)}


def create_directory_impl(dir_path: str, parents: bool = True) -> Dict[str, Any]:
    """
    Create a directory (like mkdir).
    SAFE: Creates parent directories by default if they don't exist.
    """
    try:
        path = Path(dir_path).resolve()

        # Check if directory already exists
        if path.exists():
            if path.is_dir():
                return {
                    'success': True,
                    'output': {
                        'path': str(path),
                        'created': False,
                        'message': 'Directory already exists'
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'Path exists but is not a directory: {dir_path}'
                }

        # Create directory
        path.mkdir(parents=parents, exist_ok=True)

        return {
            'success': True,
            'output': {
                'path': str(path),
                'created': True,
                'message': f'Successfully created directory: {dir_path}'
            }
        }

    except Exception as e:
        logger.error(f"Error creating directory {dir_path}: {e}")
        return {'success': False, 'error': str(e)}


def list_directory_impl(dir_path: str, recursive: bool = False) -> Dict[str, Any]:
    """
    List contents of a directory.
    Safe read-only operation.
    """
    try:
        path = Path(dir_path).resolve()

        if not path.exists():
            return {'success': False, 'error': f'Directory not found: {dir_path}'}

        if not path.is_dir():
            return {'success': False, 'error': f'Not a directory: {dir_path}'}

        if recursive:
            entries = []
            for item in path.rglob('*'):
                entries.append({
                    'name': item.name,
                    'path': str(item.relative_to(path)),
                    'type': 'file' if item.is_file() else 'directory',
                    'size_bytes': item.stat().st_size if item.is_file() else None
                })
        else:
            entries = []
            for item in path.iterdir():
                entries.append({
                    'name': item.name,
                    'path': str(item.relative_to(path)),
                    'type': 'file' if item.is_file() else 'directory',
                    'size_bytes': item.stat().st_size if item.is_file() else None
                })

        return {
            'success': True,
            'output': {
                'path': str(path),
                'entries': sorted(entries, key=lambda x: (x['type'], x['name'])),
                'count': len(entries)
            }
        }

    except Exception as e:
        logger.error(f"Error listing directory {dir_path}: {e}")
        return {'success': False, 'error': str(e)}


def find_files_impl(pattern: str, search_path: str = ".", max_results: int = 100) -> Dict[str, Any]:
    """
    Find files matching a pattern.
    SECURITY: Only searches within the specified path (defaults to CWD) and its children.
    Uses glob-style patterns (*, ?, []).
    """
    try:
        base_path = Path(search_path).resolve()
        cwd = Path.cwd().resolve()

        # Security check: ensure search_path is within or is the current working directory
        try:
            base_path.relative_to(cwd)
        except ValueError:
            return {
                'success': False,
                'error': f'Security: Cannot search outside current working directory. Requested: {search_path}'
            }

        if not base_path.exists():
            return {'success': False, 'error': f'Path not found: {search_path}'}

        if not base_path.is_dir():
            return {'success': False, 'error': f'Not a directory: {search_path}'}

        # Search for matching files
        matches = []
        count = 0

        # Directories to skip (common non-project directories)
        skip_dirs = {'venv', '__pycache__', '.git', 'node_modules', '.venv', 'env'}

        for item in base_path.rglob('*'):
            # Skip if we've hit the max results
            if count >= max_results:
                break

            # Skip common non-project directories
            if any(skip_dir in item.parts for skip_dir in skip_dirs):
                continue

            # Check if filename matches the pattern
            if fnmatch(item.name, pattern):
                try:
                    rel_path = item.relative_to(cwd)
                except ValueError:
                    rel_path = item  # Shouldn't happen due to security check above

                matches.append({
                    'name': item.name,
                    'path': str(rel_path),
                    'type': 'file' if item.is_file() else 'directory',
                    'size_bytes': item.stat().st_size if item.is_file() else None
                })
                count += 1

        return {
            'success': True,
            'output': {
                'pattern': pattern,
                'search_path': str(base_path.relative_to(cwd) if base_path != cwd else '.'),
                'matches': sorted(matches, key=lambda x: x['path']),
                'count': len(matches),
                'truncated': count >= max_results
            }
        }

    except Exception as e:
        logger.error(f"Error finding files with pattern {pattern}: {e}")
        return {'success': False, 'error': str(e)}


def fetch_url_impl(url: str, timeout: int = 10, max_size_mb: int = 10) -> Dict[str, Any]:
    """
    Fetch content from a URL using HTTP GET.
    SECURITY: Blocks local network access, file:// protocol, and enforces size limits.
    """
    try:
        # Parse and validate URL
        parsed = urlparse(url)

        # Security check 1: Only allow http/https
        if parsed.scheme not in ['http', 'https']:
            return {
                'success': False,
                'error': f'Only http:// and https:// URLs are allowed. Got: {parsed.scheme}://'
            }

        # Security check 2: Block local network access
        hostname = parsed.hostname
        if hostname:
            hostname_lower = hostname.lower()
            blocked_hosts = [
                'localhost',
                '127.0.0.1',
                '0.0.0.0',
                '::1',
            ]
            blocked_prefixes = [
                '192.168.',
                '10.',
                '172.16.', '172.17.', '172.18.', '172.19.',
                '172.20.', '172.21.', '172.22.', '172.23.',
                '172.24.', '172.25.', '172.26.', '172.27.',
                '172.28.', '172.29.', '172.30.', '172.31.',
                '169.254.',  # Link-local
            ]

            if hostname_lower in blocked_hosts:
                return {
                    'success': False,
                    'error': f'Access to local network hosts is not allowed: {hostname}'
                }

            for prefix in blocked_prefixes:
                if hostname_lower.startswith(prefix):
                    return {
                        'success': False,
                        'error': f'Access to private network ranges is not allowed: {hostname}'
                    }

        # Make request with streaming to enforce size limit
        response = requests.get(
            url,
            timeout=timeout,
            stream=True,
            headers={'User-Agent': 'Jarvis/1.0'}
        )
        response.raise_for_status()

        # Check content length if provided
        content_length = response.headers.get('Content-Length')
        max_size_bytes = max_size_mb * 1024 * 1024

        if content_length and int(content_length) > max_size_bytes:
            return {
                'success': False,
                'error': f'Content too large: {int(content_length)} bytes (max: {max_size_bytes})'
            }

        # Download with size limit
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size_bytes:
                return {
                    'success': False,
                    'error': f'Content exceeded size limit of {max_size_mb}MB'
                }

        # Decode content
        text_content = content.decode('utf-8', errors='replace')

        return {
            'success': True,
            'output': {
                'content': text_content,
                'status_code': response.status_code,
                'url': response.url,  # Final URL after redirects
                'content_type': response.headers.get('Content-Type', 'unknown'),
                'size_bytes': len(content)
            }
        }

    except requests.exceptions.Timeout:
        return {'success': False, 'error': f'Request timed out after {timeout} seconds'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'HTTP error: {str(e)}'}
    except Exception as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return {'success': False, 'error': str(e)}


def edit_file_impl(file_path: str, old_string: str, new_string: str) -> Dict[str, Any]:
    """
    Edit a file by replacing old_string with new_string.
    SAFE:
    - Creates backup before editing
    - Only replaces if old_string appears exactly once
    - Generates diff for verification
    - Backup can be restored if needed
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        if not path.is_file():
            return {'success': False, 'error': f'Not a file: {file_path}'}

        # Read current content
        with open(path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # Check if old_string exists
        if old_string not in original_content:
            return {
                'success': False,
                'error': f'String not found in file. Cannot perform replacement.'
            }

        # Check if old_string appears multiple times
        count = original_content.count(old_string)
        if count > 1:
            return {
                'success': False,
                'error': f'String appears {count} times in file. Please provide a more specific string that appears only once.'
            }

        # CREATE BACKUP BEFORE EDITING
        backup_path = _create_backup(path)

        # Perform replacement
        new_content = original_content.replace(old_string, new_string)

        # Generate diff for verification
        diff = _generate_diff(original_content, new_content, path.name)

        # Write new content
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return {
            'success': True,
            'output': {
                'path': str(path),
                'backup_path': str(backup_path),
                'old_length': len(old_string),
                'new_length': len(new_string),
                'file_size_before': len(original_content),
                'file_size_after': len(new_content),
                'diff': diff
            }
        }

    except Exception as e:
        logger.error(f"Error editing file {file_path}: {e}")
        return {'success': False, 'error': str(e)}


def list_backups_impl(file_name: str = None) -> Dict[str, Any]:
    """
    List available backups, optionally filtered by filename.
    """
    try:
        _ensure_backup_dir()

        if not BACKUP_DIR.exists() or not any(BACKUP_DIR.iterdir()):
            return {
                'success': True,
                'output': {
                    'backups': [],
                    'count': 0
                }
            }

        backups = []
        for backup_file in BACKUP_DIR.iterdir():
            if backup_file.is_file() and backup_file.suffix == '.bak':
                # Parse filename: originalname.timestamp.bak
                parts = backup_file.stem.rsplit('.', 1)
                if len(parts) == 2:
                    original_name = parts[0]
                    timestamp_str = parts[1]

                    # Filter by filename if specified
                    if file_name and original_name != file_name:
                        continue

                    try:
                        # Parse timestamp
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        backups.append({
                            'backup_file': str(backup_file),
                            'original_name': original_name,
                            'timestamp': timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            'size_bytes': backup_file.stat().st_size
                        })
                    except ValueError:
                        # Skip malformed backup names
                        continue

        # Sort by timestamp (most recent first)
        backups.sort(key=lambda x: x['timestamp'], reverse=True)

        return {
            'success': True,
            'output': {
                'backups': backups,
                'count': len(backups),
                'filter': file_name if file_name else 'all files'
            }
        }

    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return {'success': False, 'error': str(e)}


def restore_backup_impl(backup_path: str) -> Dict[str, Any]:
    """
    Restore a file from backup.
    DANGEROUS: Overwrites the current file with the backup.
    """
    try:
        backup_file = Path(backup_path)

        if not backup_file.exists():
            return {'success': False, 'error': f'Backup not found: {backup_path}'}

        if not backup_file.is_file():
            return {'success': False, 'error': f'Not a file: {backup_path}'}

        # Parse the original filename from backup name
        # Format: originalname.timestamp.bak
        parts = backup_file.stem.rsplit('.', 1)
        if len(parts) != 2:
            return {'success': False, 'error': 'Invalid backup filename format'}

        original_name = parts[0]

        # Determine target path (same directory as where we are)
        cwd = Path.cwd()
        target_path = cwd / original_name

        # Read backup content
        backup_content = backup_file.read_text(encoding='utf-8')

        # If target exists, create a backup of current state before restoring
        if target_path.exists():
            current_content = target_path.read_text(encoding='utf-8')
            pre_restore_backup = _create_backup(target_path)
            logger.info(f"Created pre-restore backup: {pre_restore_backup}")

            # Generate diff
            diff = _generate_diff(current_content, backup_content, original_name)
        else:
            diff = f"File {original_name} does not exist, will be created from backup"
            pre_restore_backup = None

        # Restore the backup
        target_path.write_text(backup_content, encoding='utf-8')

        return {
            'success': True,
            'output': {
                'restored_to': str(target_path),
                'backup_used': str(backup_file),
                'pre_restore_backup': str(pre_restore_backup) if pre_restore_backup else None,
                'diff': diff
            }
        }

    except Exception as e:
        logger.error(f"Error restoring backup {backup_path}: {e}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# Unix Text Tools
# =============================================================================

def grep_impl(pattern: str, file_path: str, ignore_case: bool = False,
              line_numbers: bool = True, context: int = 0) -> Dict[str, Any]:
    """
    Search for a pattern in a file (like unix grep).
    Returns matching lines with optional context.
    """
    try:
        path = Path(file_path).resolve()
        cwd = Path.cwd().resolve()

        # Security: ensure file is within CWD
        try:
            path.relative_to(cwd)
        except ValueError:
            return {'success': False, 'error': 'Can only grep files within current directory'}

        if not path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        if not path.is_file():
            return {'success': False, 'error': f'Not a file: {file_path}'}

        # Read file
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        # Compile regex pattern
        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return {'success': False, 'error': f'Invalid regex pattern: {e}'}

        # Find matches
        matches = []
        for i, line in enumerate(lines, 1):
            if regex.search(line):
                match_info = {
                    'line_number': i,
                    'content': line.rstrip('\n')
                }

                # Add context lines if requested
                if context > 0:
                    before = []
                    after = []
                    for j in range(max(0, i - context - 1), i - 1):
                        before.append(lines[j].rstrip('\n'))
                    for j in range(i, min(len(lines), i + context)):
                        after.append(lines[j].rstrip('\n'))

                    match_info['before'] = before
                    match_info['after'] = after

                matches.append(match_info)

        return {
            'success': True,
            'output': {
                'pattern': pattern,
                'file': str(path),
                'matches': matches,
                'count': len(matches)
            }
        }

    except Exception as e:
        logger.error(f"Error in grep {pattern} {file_path}: {e}")
        return {'success': False, 'error': str(e)}


def diff_files_impl(file1: str, file2: str, unified: bool = True) -> Dict[str, Any]:
    """
    Compare two files and show differences (like unix diff).
    """
    try:
        path1 = Path(file1).resolve()
        path2 = Path(file2).resolve()

        if not path1.exists():
            return {'success': False, 'error': f'File not found: {file1}'}
        if not path2.exists():
            return {'success': False, 'error': f'File not found: {file2}'}

        # Read files
        with open(path1, 'r', encoding='utf-8', errors='replace') as f:
            content1 = f.read()
        with open(path2, 'r', encoding='utf-8', errors='replace') as f:
            content2 = f.read()

        # Generate diff
        if unified:
            diff_text = _generate_diff(content1, content2, file1)
        else:
            # Simple line-by-line comparison
            lines1 = content1.splitlines()
            lines2 = content2.splitlines()
            diff_text = f"< {file1}\n> {file2}\n\n"
            diff_text += "\n".join(difflib.ndiff(lines1, lines2))

        # Check if files are identical
        identical = content1 == content2

        return {
            'success': True,
            'output': {
                'file1': str(path1),
                'file2': str(path2),
                'identical': identical,
                'diff': diff_text if not identical else 'Files are identical'
            }
        }

    except Exception as e:
        logger.error(f"Error in diff {file1} {file2}: {e}")
        return {'success': False, 'error': str(e)}


def wc_impl(file_path: str) -> Dict[str, Any]:
    """
    Count lines, words, and characters in a file (like unix wc).
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        if not path.is_file():
            return {'success': False, 'error': f'Not a file: {file_path}'}

        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        lines = content.count('\n')
        words = len(content.split())
        chars = len(content)
        bytes_size = path.stat().st_size

        return {
            'success': True,
            'output': {
                'file': str(path),
                'lines': lines,
                'words': words,
                'characters': chars,
                'bytes': bytes_size
            }
        }

    except Exception as e:
        logger.error(f"Error in wc {file_path}: {e}")
        return {'success': False, 'error': str(e)}


def head_impl(file_path: str, lines: int = 10) -> Dict[str, Any]:
    """
    Show the first N lines of a file (like unix head).
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        if not path.is_file():
            return {'success': False, 'error': f'Not a file: {file_path}'}

        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content_lines = []
            for i, line in enumerate(f):
                if i >= lines:
                    break
                content_lines.append(line.rstrip('\n'))

        return {
            'success': True,
            'output': {
                'file': str(path),
                'lines_requested': lines,
                'lines_returned': len(content_lines),
                'content': '\n'.join(content_lines)
            }
        }

    except Exception as e:
        logger.error(f"Error in head {file_path}: {e}")
        return {'success': False, 'error': str(e)}


def tail_impl(file_path: str, lines: int = 10) -> Dict[str, Any]:
    """
    Show the last N lines of a file (like unix tail).
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        if not path.is_file():
            return {'success': False, 'error': f'Not a file: {file_path}'}

        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()

        # Get last N lines
        content_lines = [line.rstrip('\n') for line in all_lines[-lines:]]

        return {
            'success': True,
            'output': {
                'file': str(path),
                'lines_requested': lines,
                'lines_returned': len(content_lines),
                'content': '\n'.join(content_lines)
            }
        }

    except Exception as e:
        logger.error(f"Error in tail {file_path}: {e}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# News & Information Tools
# =============================================================================

def get_news_headlines_impl(query: str = "breaking news", max_results: int = 10) -> Dict[str, Any]:
    """
    Fetch news headlines from searxng instance.
    Returns formatted news results with deduplication.
    """
    try:
        # Searxng instance
        base_url = "http://tools.badcheese.com:8888/search"

        # Build search params
        params = {
            'q': query,
            'format': 'json',
            'categories': 'news',  # Focus on news results
        }

        # Fetch results
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()
        results = data.get('results', [])

        if not results:
            return {
                'success': True,
                'output': {
                    'query': query,
                    'headlines': [],
                    'count': 0,
                    'message': 'No news results found'
                }
            }

        # Parse and format headlines
        headlines = []
        seen_titles = set()  # Simple deduplication by title

        for result in results[:max_results * 2]:  # Fetch extra for dedup
            title = result.get('title', '').strip()
            url = result.get('url', '')
            content = result.get('content', '').strip()
            published = result.get('publishedDate', '')

            # Skip if we've seen this title (case-insensitive)
            title_lower = title.lower()
            if title_lower in seen_titles:
                continue
            seen_titles.add(title_lower)

            # Skip if title is too short (likely not a real headline)
            if len(title) < 10:
                continue

            headline = {
                'title': title,
                'url': url,
                'snippet': content[:200] if content else '',
                'published': published,
            }
            headlines.append(headline)

            # Stop if we have enough
            if len(headlines) >= max_results:
                break

        return {
            'success': True,
            'output': {
                'query': query,
                'headlines': headlines,
                'count': len(headlines),
                'total_found': len(results)
            }
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching news: {e}")
        return {'success': False, 'error': f'Failed to fetch news: {str(e)}'}
    except Exception as e:
        logger.error(f"Error in get_news_headlines: {e}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# Tool Schemas
# =============================================================================

READ_FILE_SCHEMA = ToolSchema(
    name="read_file",
    description="Read the contents of a text file from the filesystem",
    category="filesystem",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="Path to the file to read",
            required=True
        ),
        ToolParameter(
            name="max_lines",
            type=ToolParameterType.INTEGER,
            description="Maximum number of lines to read (optional, reads all if not specified)",
            required=False,
            default=None
        )
    ]
)

WRITE_FILE_SCHEMA = ToolSchema(
    name="write_file",
    description="Write content to a file (creates or overwrites)",
    category="filesystem",
    requires_approval=True,  # Destructive action
    dangerous=True,
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="Path to the file to write",
            required=True
        ),
        ToolParameter(
            name="content",
            type=ToolParameterType.STRING,
            description="Content to write to the file",
            required=True
        ),
        ToolParameter(
            name="append",
            type=ToolParameterType.BOOLEAN,
            description="If true, append to file instead of overwriting",
            required=False,
            default=False
        )
    ]
)

CREATE_DIRECTORY_SCHEMA = ToolSchema(
    name="create_directory",
    description="Create a new directory (like mkdir). Creates parent directories by default if they don't exist.",
    category="filesystem",
    requires_approval=True,  # Modifies filesystem
    dangerous=False,  # Not truly dangerous, just creates dirs
    parameters=[
        ToolParameter(
            name="dir_path",
            type=ToolParameterType.STRING,
            description="Path to the directory to create",
            required=True
        ),
        ToolParameter(
            name="parents",
            type=ToolParameterType.BOOLEAN,
            description="If true, create parent directories as needed (default true)",
            required=False,
            default=True
        )
    ]
)

LIST_DIRECTORY_SCHEMA = ToolSchema(
    name="list_directory",
    description="List files and subdirectories in a directory",
    category="filesystem",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="dir_path",
            type=ToolParameterType.STRING,
            description="Path to the directory to list",
            required=True
        ),
        ToolParameter(
            name="recursive",
            type=ToolParameterType.BOOLEAN,
            description="If true, list all files recursively",
            required=False,
            default=False
        )
    ]
)

FIND_FILES_SCHEMA = ToolSchema(
    name="find_files",
    description="Find files matching a pattern in current directory and subdirectories (glob-style: *.py, test*, etc.)",
    category="filesystem",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="pattern",
            type=ToolParameterType.STRING,
            description="Glob-style pattern to match filenames (e.g., '*.py', 'test*', '*.txt')",
            required=True
        ),
        ToolParameter(
            name="search_path",
            type=ToolParameterType.STRING,
            description="Directory to search in (defaults to current directory, restricted to CWD and children)",
            required=False,
            default="."
        ),
        ToolParameter(
            name="max_results",
            type=ToolParameterType.INTEGER,
            description="Maximum number of results to return (default 100)",
            required=False,
            default=100
        )
    ]
)

FETCH_URL_SCHEMA = ToolSchema(
    name="fetch_url",
    description="Fetch content from a URL (http/https only, blocks local networks)",
    category="web",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="url",
            type=ToolParameterType.STRING,
            description="URL to fetch (must be http:// or https://)",
            required=True
        ),
        ToolParameter(
            name="timeout",
            type=ToolParameterType.INTEGER,
            description="Request timeout in seconds (default 10)",
            required=False,
            default=10
        ),
        ToolParameter(
            name="max_size_mb",
            type=ToolParameterType.INTEGER,
            description="Maximum content size in MB (default 10)",
            required=False,
            default=10
        )
    ]
)

EDIT_FILE_SCHEMA = ToolSchema(
    name="edit_file",
    description="Edit a file by replacing a specific string (creates backup, shows diff, string must appear exactly once)",
    category="filesystem",
    requires_approval=True,  # Destructive action
    dangerous=True,
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="Path to the file to edit",
            required=True
        ),
        ToolParameter(
            name="old_string",
            type=ToolParameterType.STRING,
            description="String to find and replace (must appear exactly once in file)",
            required=True
        ),
        ToolParameter(
            name="new_string",
            type=ToolParameterType.STRING,
            description="String to replace with",
            required=True
        )
    ]
)

LIST_BACKUPS_SCHEMA = ToolSchema(
    name="list_backups",
    description="List available file backups (created by edit_file)",
    category="filesystem",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="file_name",
            type=ToolParameterType.STRING,
            description="Filter backups by original filename (optional)",
            required=False,
            default=None
        )
    ]
)

RESTORE_BACKUP_SCHEMA = ToolSchema(
    name="restore_backup",
    description="Restore a file from backup (shows diff, creates backup of current state before restoring)",
    category="filesystem",
    requires_approval=True,  # Destructive action
    dangerous=True,
    parameters=[
        ToolParameter(
            name="backup_path",
            type=ToolParameterType.STRING,
            description="Path to the backup file (from list_backups)",
            required=True
        )
    ]
)

GREP_SCHEMA = ToolSchema(
    name="grep",
    description="Search for a pattern in a file (regex supported)",
    category="text_tools",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="pattern",
            type=ToolParameterType.STRING,
            description="Pattern to search for (regex)",
            required=True
        ),
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="File to search in",
            required=True
        ),
        ToolParameter(
            name="ignore_case",
            type=ToolParameterType.BOOLEAN,
            description="Case-insensitive search (default false)",
            required=False,
            default=False
        ),
        ToolParameter(
            name="context",
            type=ToolParameterType.INTEGER,
            description="Number of context lines before/after match (default 0)",
            required=False,
            default=0
        )
    ]
)

DIFF_SCHEMA = ToolSchema(
    name="diff",
    description="Compare two files and show differences",
    category="text_tools",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="file1",
            type=ToolParameterType.STRING,
            description="First file to compare",
            required=True
        ),
        ToolParameter(
            name="file2",
            type=ToolParameterType.STRING,
            description="Second file to compare",
            required=True
        ),
        ToolParameter(
            name="unified",
            type=ToolParameterType.BOOLEAN,
            description="Use unified diff format (default true)",
            required=False,
            default=True
        )
    ]
)

WC_SCHEMA = ToolSchema(
    name="wc",
    description="Count lines, words, and characters in a file",
    category="text_tools",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="File to analyze",
            required=True
        )
    ]
)

HEAD_SCHEMA = ToolSchema(
    name="head",
    description="Show the first N lines of a file",
    category="text_tools",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="File to read",
            required=True
        ),
        ToolParameter(
            name="lines",
            type=ToolParameterType.INTEGER,
            description="Number of lines to show (default 10)",
            required=False,
            default=10
        )
    ]
)

TAIL_SCHEMA = ToolSchema(
    name="tail",
    description="Show the last N lines of a file",
    category="text_tools",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="file_path",
            type=ToolParameterType.STRING,
            description="File to read",
            required=True
        ),
        ToolParameter(
            name="lines",
            type=ToolParameterType.INTEGER,
            description="Number of lines to show (default 10)",
            required=False,
            default=10
        )
    ]
)

GET_NEWS_HEADLINES_SCHEMA = ToolSchema(
    name="get_news_headlines",
    description="Fetch latest news headlines from searxng (auto-deduplicates similar headlines)",
    category="news",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="query",
            type=ToolParameterType.STRING,
            description="Search query for news (default: 'breaking news')",
            required=False,
            default="breaking news"
        ),
        ToolParameter(
            name="max_results",
            type=ToolParameterType.INTEGER,
            description="Maximum number of headlines to return (default 10)",
            required=False,
            default=10
        )
    ]
)

# =============================================================================
# Date/Time Tool
# =============================================================================

def get_datetime_impl(format: str = "full") -> Dict[str, Any]:
    """
    Get the current date and time.

    Provides current datetime information in various formats.
    """
    try:
        now = datetime.now()

        if format == "full":
            # Full ISO format with timezone info
            output = {
                'datetime': now.isoformat(),
                'date': now.strftime("%Y-%m-%d"),
                'time': now.strftime("%H:%M:%S"),
                'day_of_week': now.strftime("%A"),
                'month': now.strftime("%B"),
                'year': now.year,
                'timezone': now.astimezone().tzname(),
                'timestamp': int(now.timestamp())
            }
        elif format == "date":
            # Date only
            output = {
                'date': now.strftime("%Y-%m-%d"),
                'day_of_week': now.strftime("%A"),
                'month': now.strftime("%B"),
                'year': now.year
            }
        elif format == "time":
            # Time only
            output = {
                'time': now.strftime("%H:%M:%S"),
                'hour': now.hour,
                'minute': now.minute,
                'second': now.second
            }
        elif format == "timestamp":
            # Unix timestamp
            output = {
                'timestamp': int(now.timestamp()),
                'timestamp_ms': int(now.timestamp() * 1000)
            }
        else:
            # Default to full
            output = {
                'datetime': now.isoformat(),
                'date': now.strftime("%Y-%m-%d"),
                'time': now.strftime("%H:%M:%S")
            }

        return {
            'success': True,
            'output': output
        }

    except Exception as e:
        logger.error(f"Error getting datetime: {e}")
        return {'success': False, 'error': str(e)}


GET_DATETIME_SCHEMA = ToolSchema(
    name="get_datetime",
    description="Get the current date and time in various formats (full/date/time/timestamp)",
    category="system",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="format",
            type=ToolParameterType.STRING,
            description="Format type: 'full' (default), 'date', 'time', or 'timestamp'",
            required=False,
            default="full"
        )
    ]
)


def web_search_impl(query: str, max_results: int = 5, check_facts: bool = True) -> Dict[str, Any]:
    """
    Multi-source web search with fact-checking.

    Searches across SearXNG and Wikipedia, consolidates results,
    and provides confidence ratings based on source agreement.

    Args:
        query: Search query
        max_results: Maximum number of results to return (default: 5)
        check_facts: Whether to perform fact-checking (default: True)

    Returns:
        Dict with:
        - success: bool
        - output: search results with confidence and warnings
        - error: str (if failed)
    """
    try:
        from .web_search import WebSearcher

        searcher = WebSearcher()
        result = searcher.search_multi_source(
            query=query,
            max_results=max_results,
            check_facts=check_facts
        )

        return result

    except ImportError:
        return {
            'success': False,
            'error': 'Web search module not available'
        }
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


WEB_SEARCH_SCHEMA = ToolSchema(
    name="web_search",
    description=(
        "Search the internet using multiple sources with built-in fact-checking. "
        "Searches SearXNG (metasearch engine) and Wikipedia for factual queries. "
        "Returns results with confidence ratings based on source agreement. "
        "Use this to find current information, verify facts, or research topics. "
        "Especially useful for factual queries about people, events, statistics, and current affairs."
    ),
    category="web",
    requires_approval=False,
    dangerous=False,
    parameters=[
        ToolParameter(
            name="query",
            type=ToolParameterType.STRING,
            description="The search query. Can be a question or keywords.",
            required=True
        ),
        ToolParameter(
            name="max_results",
            type=ToolParameterType.INTEGER,
            description="Maximum number of results to return (1-20, default: 5)",
            required=False,
            default=5
        ),
        ToolParameter(
            name="check_facts",
            type=ToolParameterType.BOOLEAN,
            description="Whether to perform fact-checking and source verification (default: true)",
            required=False,
            default=True
        )
    ]
)


# Map of built-in tools
BUILTIN_TOOLS = {
    'read_file': (READ_FILE_SCHEMA, read_file_impl),
    'write_file': (WRITE_FILE_SCHEMA, write_file_impl),
    'edit_file': (EDIT_FILE_SCHEMA, edit_file_impl),
    'create_directory': (CREATE_DIRECTORY_SCHEMA, create_directory_impl),
    'list_directory': (LIST_DIRECTORY_SCHEMA, list_directory_impl),
    'find_files': (FIND_FILES_SCHEMA, find_files_impl),
    'fetch_url': (FETCH_URL_SCHEMA, fetch_url_impl),
    'list_backups': (LIST_BACKUPS_SCHEMA, list_backups_impl),
    'restore_backup': (RESTORE_BACKUP_SCHEMA, restore_backup_impl),
    'grep': (GREP_SCHEMA, grep_impl),
    'diff': (DIFF_SCHEMA, diff_files_impl),
    'wc': (WC_SCHEMA, wc_impl),
    'head': (HEAD_SCHEMA, head_impl),
    'tail': (TAIL_SCHEMA, tail_impl),
    'get_news_headlines': (GET_NEWS_HEADLINES_SCHEMA, get_news_headlines_impl),
    'get_datetime': (GET_DATETIME_SCHEMA, get_datetime_impl),
    'web_search': (WEB_SEARCH_SCHEMA, web_search_impl),
}
