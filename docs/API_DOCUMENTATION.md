# Jarvis API Documentation

## Overview

Jarvis provides a RESTful API for multi-user AI assistant interactions with isolated memory banks, persistent conversations, and role-based access control.

**Base URL**: `http://localhost:8000`
**Interactive Docs**: `http://localhost:8000/docs` (Swagger UI)
**Alternative Docs**: `http://localhost:8000/redoc` (ReDoc)

## Authentication

All API endpoints require authentication using API keys via Bearer token authentication.

### Headers
```http
Authorization: Bearer YOUR_API_KEY_HERE
```

### Obtaining an API Key

Use the user management CLI to create users and get API keys:

```bash
./scripts/manage_users.py create <username> [display_name] [--role master|api_user]
```

**Example**:
```bash
./scripts/manage_users.py create alice "Alice Smith"
# Outputs API key - save it immediately!

./scripts/manage_users.py create admin "Admin User" --role master
# Creates a master user with full access
```

## User Roles

### API User (`api_user`)
- **Read-only access** to filesystem and system operations
- **Cannot** write files, edit files, or perform destructive operations
- **Can** read files, list directories, search content, fetch URLs
- **Has isolated memory bank** - cannot access other users' memories
- Ideal for remote/external users

### Master (`master`)
- **Full access** to all tools and operations
- Can write files, execute commands, and perform system modifications
- **Has isolated memory bank** like API users
- Intended for administrators and trusted local access

## Architecture

### Dual Interface Design

Jarvis supports two simultaneous interfaces:

1. **CLI Interface** (`main.py`)
   - Local, trusted access
   - Always runs with master privileges
   - No API key required
   - Direct terminal interaction

2. **API Interface** (`api/server.py`)
   - Remote, multi-user access
   - Requires API key authentication
   - Role-based restrictions
   - JSON-formatted responses

Both interfaces share the same underlying memory and orchestration systems.

### Memory Isolation

- **Episodic/Semantic Memory**: Isolated per user (user-specific facts, preferences, history)
- **Procedural Memory**: Shared globally (system learns retry strategies from all users)
- **Conversation History**: Persistent per user, survives server restarts

### Session Management

- Per-user Orchestrator instances kept in memory
- Automatic cleanup of inactive sessions (default: 1 hour timeout)
- Conversation history persisted to MySQL database
- Sessions resume automatically on reconnect

## API Endpoints

### Health & Info

#### `GET /`
Root endpoint - API status

**Response**:
```json
{
  "service": "Jarvis API",
  "version": "1.0.0",
  "status": "operational",
  "docs": "/docs"
}
```

#### `GET /health`
Health check endpoint

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-09T10:00:00.000Z"
}
```

### Authentication

#### `GET /api/v1/me`
Get current authenticated user information

**Headers**:
```http
Authorization: Bearer YOUR_API_KEY
```

**Response**:
```json
{
  "user_id": 2,
  "username": "alice",
  "display_name": "Alice Smith",
  "role": "api_user"
}
```

**Status Codes**:
- `200 OK`: Successful authentication
- `401 Unauthorized`: Invalid or expired API key

### Chat

#### `POST /api/v1/chat`
Send a message to Jarvis and get a response

**Headers**:
```http
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**Request Body**:
```json
{
  "message": "What is my name?",
  "stream": false
}
```

**Response**:
```json
{
  "response": "Your name is Alice.",
  "actions_taken": [],
  "verification": {
    "verified": true,
    "confidence": "high",
    "reasoning": "Successfully retrieved user identity from memory",
    "failure_type": null
  },
  "session_id": "da9872a8-14e7-4336-9340-606ac41a84c9"
}
```

**Fields**:
- `response` (string): Jarvis' text response
- `actions_taken` (array): List of tools executed with results
- `verification` (object|null): Verification result from quality check
- `session_id` (string): Unique session identifier

**Example - Tool Execution**:
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "List files in /tmp"}'
```

**Response with Actions**:
```json
{
  "response": "The /tmp directory contains: test_file.txt, cache/, logs/",
  "actions_taken": [
    {
      "tool_name": "list_directory",
      "success": true,
      "files": ["test_file.txt", "cache", "logs"],
      "file_count": 3
    }
  ],
  "verification": {
    "verified": true,
    "confidence": "high",
    "reasoning": "Successfully listed directory contents",
    "failure_type": null
  },
  "session_id": "da9872a8-14e7-4336-9340-606ac41a84c9"
}
```

**Security Example - Blocked Operation (API User)**:
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer API_USER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a file called test.txt"}'
```

API users will receive an error in `actions_taken`:
```json
{
  "response": "I cannot create files as an API user...",
  "actions_taken": [
    {
      "tool_name": "write_file",
      "success": false,
      "error": "Access denied: Tool 'write_file' is not available for API users. This tool performs local file modifications. Please use the CLI interface for write operations.",
      "blocked_by_security": true
    }
  ]
}
```

### Session Management

#### `GET /api/v1/session`
Get current session information

**Headers**:
```http
Authorization: Bearer YOUR_API_KEY
```

**Response**:
```json
{
  "session_id": "da9872a8-14e7-4336-9340-606ac41a84c9",
  "username": "alice",
  "role": "api_user",
  "message_count": 5,
  "created_at": "2026-01-09T10:00:00.000Z",
  "last_activity": "2026-01-09T10:05:00.000Z"
}
```

#### `POST /api/v1/session/reset`
Reset conversation history (clears messages, preserves long-term memories)

**Headers**:
```http
Authorization: Bearer YOUR_API_KEY
```

**Response**:
```json
{
  "status": "success",
  "message": "Conversation history cleared"
}
```

### Memory Operations

#### `GET /api/v1/memories`
Retrieve user's memories

**Headers**:
```http
Authorization: Bearer YOUR_API_KEY
```

**Query Parameters**:
- `query` (optional): Search query for semantic search
- `limit` (optional, default: 10): Maximum number of memories to return

**Examples**:

**Get recent memories**:
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "http://localhost:8000/api/v1/memories?limit=5"
```

**Semantic search**:
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "http://localhost:8000/api/v1/memories?query=programming&limit=10"
```

**Response**:
```json
{
  "memories": [
    {
      "id": 28,
      "text": "User prefers Python programming",
      "type": "preference",
      "confidence": 0.85,
      "importance": 0.60,
      "decay_score": 100.0,
      "created_at": "2026-01-09T10:01:05.000Z"
    },
    {
      "id": 27,
      "text": "User's name is Alice",
      "type": "identity",
      "confidence": 0.95,
      "importance": 0.80,
      "decay_score": 100.0,
      "created_at": "2026-01-09T10:01:04.000Z"
    }
  ],
  "count": 2
}
```

**Memory Types**:
- `identity`: User facts (name, location, etc.)
- `preference`: Likes/dislikes
- `capability`: System abilities
- `project`: Current work
- `episodic`: Past events
- `social`: Communication style

#### `GET /api/v1/stats`
Get memory system statistics for current user

**Headers**:
```http
Authorization: Bearer YOUR_API_KEY
```

**Response**:
```json
{
  "total_memories": 2,
  "by_type": {
    "identity": 1,
    "preference": 1
  },
  "avg_confidence": 0.90,
  "avg_decay_score": 100.0,
  "user_id": 2,
  "username": "alice"
}
```

## Security & Access Control

### Tool Access Restrictions

API users (`api_user` role) have restricted access to tools:

#### Allowed Tools (Read-Only)
- `read_file` - Read file contents
- `list_directory` - List directory contents
- `find_files` - Search for files
- `grep` - Search file contents
- `head` / `tail` / `wc` - File content utilities
- `diff` - Compare files
- `fetch_url` - Fetch web content
- `web_search` - Search the web
- `get_datetime` - Get current time
- `list_backups` - View available backups

#### Blocked Tools (Write/Destructive)
- `write_file` - Create/write files
- `edit_file` - Modify files
- `delete_file` - Remove files
- `restore_backup` - Restore from backup
- `execute_command` - Run shell commands
- Any other destructive operations

Master users have access to ALL tools without restrictions.

### Memory Isolation

- Each user has a completely isolated memory bank
- Semantic memory retrieval filtered by `user_id`
- Vector store (ChromaDB) queries include `user_id` metadata filter
- MySQL queries enforce `WHERE user_id = ?` constraints
- Users cannot access, view, or modify other users' memories

### Procedural Memory (Shared Learning)

While episodic/semantic memories are isolated, **procedural memory is shared globally**:
- System learns retry strategies from all users' interactions
- If User A encounters an error and the system learns a fix strategy, User B benefits from that learning
- No privacy concern - procedural memories don't contain user-specific data

## User Management

### CLI Commands

The `scripts/manage_users.py` script provides user administration:

```bash
# Create user (default: api_user role)
./scripts/manage_users.py create <username> [display_name]

# Create master user
./scripts/manage_users.py create <username> [display_name] --role master

# List all users
./scripts/manage_users.py list

# Revoke all API keys for a user
./scripts/manage_users.py revoke <username>

# Generate new API key (revokes old ones)
./scripts/manage_users.py regenerate <username>

# Deactivate user account
./scripts/manage_users.py delete <username>
```

### Examples

```bash
# Create API user
./scripts/manage_users.py create alice "Alice Smith"
# Output:
# ======================================================================
# USER CREATED SUCCESSFULLY
# ======================================================================
# User ID:      2
# Username:     alice
# Display Name: Alice Smith
# Role:         api_user
# API Key:      4OrYbT_zdYvzQejq9TQRQ7HlUbpN3MTEyGEDnKGR8Rhn09IJWw8hhCW3N98X0-Cc
# ======================================================================
#
# IMPORTANT: Save this API key - it will not be shown again!

# List users
./scripts/manage_users.py list
# ====================================================================================================
# ID    Username             Display Name              Role       Active   Keys     Last Active
# ====================================================================================================
# 3     steve                Steve (Master)            master     Yes      1/1      Never
# 2     alice                Alice Smith               api_user   Yes      1/1      2026-01-09 10:05
# 1     system               System User               master     Yes      0/0      Never
# ====================================================================================================
```

## Starting the API Server

### Production

```bash
# Start with uvicorn
uvicorn api.server:app --host 0.0.0.0 --port 8000

# Or use the Python module directly
python3 -m api.server
```

### Development (with auto-reload)

```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
```

### Configuration

Edit `config/config.yaml`:

```yaml
api:
  host: "0.0.0.0"  # Listen on all interfaces
  port: 8000  # API server port
  session_timeout: 3600  # Session timeout in seconds (1 hour)
  max_sessions: 10  # Maximum concurrent user sessions
  cors_origins: ["*"]  # Configure for production
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Successful request
- `401 Unauthorized`: Invalid/expired API key
- `500 Internal Server Error`: Server-side error

### Error Response Format

```json
{
  "detail": "Error message describing the issue"
}
```

### Common Errors

**Invalid API Key**:
```json
{
  "detail": "Invalid or expired API key"
}
```

**Tool Access Denied**:
```json
{
  "response": "I cannot perform that operation...",
  "actions_taken": [
    {
      "tool_name": "write_file",
      "success": false,
      "error": "Access denied: Tool 'write_file' is not available for API users...",
      "blocked_by_security": true
    }
  ]
}
```

## Usage Examples

### Complete Workflow Example

```bash
# 1. Create a user
./scripts/manage_users.py create alice "Alice Smith"
# Save the API key from output
API_KEY="4OrYbT_zdYvzQejq9TQRQ7HlUbpN3MTEyGEDnKGR8Rhn09IJWw8hhCW3N98X0-Cc"

# 2. Test authentication
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/api/v1/me

# 3. Have a conversation
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "My name is Alice and I love Python"}'

# 4. Ask a follow-up (uses memory)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "What programming language do I like?"}'

# 5. View stored memories
curl -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/api/v1/memories?limit=5"

# 6. Get session info
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/api/v1/session

# 7. Reset conversation (keeps memories)
curl -X POST -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/api/v1/session/reset
```

### Python Client Example

```python
import requests

API_KEY = "your-api-key-here"
BASE_URL = "http://localhost:8000"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Chat
response = requests.post(
    f"{BASE_URL}/api/v1/chat",
    headers=headers,
    json={"message": "Hello, Jarvis!"}
)
data = response.json()
print(f"Response: {data['response']}")
print(f"Session ID: {data['session_id']}")

# Get memories
response = requests.get(
    f"{BASE_URL}/api/v1/memories",
    headers=headers,
    params={"limit": 10}
)
memories = response.json()
print(f"Total memories: {memories['count']}")
for memory in memories['memories']:
    print(f"- [{memory['type']}] {memory['text']}")
```

## Testing & Verification

### Test Security Restrictions

```bash
# Create API user and master user
./scripts/manage_users.py create api_user "API User"
./scripts/manage_users.py create master_user "Master User" --role master

API_USER_KEY="<api_user_key>"
MASTER_KEY="<master_user_key>"

# API user tries to write file (should be blocked)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $API_USER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a file called test.txt"}'
# Expect: Error message about access denied

# Master user writes file (should succeed)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a file /tmp/master_test.txt with content Hello"}'
# Expect: Success
```

### Verify Memory Isolation

```bash
# Check database directly
mysql -h tools -u steve -pkoala1 jarvis -e "
SELECT u.username, m.id, m.memory_type, m.memory_text
FROM memories m
JOIN users u ON m.user_id = u.id
WHERE u.username IN ('api_user', 'master_user')
ORDER BY u.username, m.created_at DESC;"
```

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255),
    role ENUM('master', 'api_user') DEFAULT 'api_user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE
);
```

### API Keys Table
```sql
CREATE TABLE api_keys (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    api_key VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP NULL,
    expires_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### Memories Table (with user_id)
```sql
CREATE TABLE memories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,  -- NEW: For multi-user isolation
    memory_text TEXT NOT NULL,
    memory_type ENUM('identity', 'preference', 'capability', 'project', 'episodic', 'social'),
    embedding_id VARCHAR(36) NOT NULL UNIQUE,
    confidence FLOAT NOT NULL,
    importance FLOAT NOT NULL,
    decay_score FLOAT NOT NULL,
    -- ... other fields
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### Conversation Sessions Table
```sql
CREATE TABLE conversation_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_id VARCHAR(64) NOT NULL UNIQUE,
    conversation_history JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

## Performance Considerations

### Session Management
- In-memory sessions for active users (fast access)
- Automatic cleanup after `session_timeout` (default: 1 hour)
- Optimized for few users (2-10) with long conversations
- Database persistence ensures no conversation loss

### Memory Retrieval
- ChromaDB vector search with metadata filtering
- MySQL connection pooling (default: 5 connections)
- Semantic search limited to user's own memories
- Default retrieval limit: 10 memories (configurable)

### Scalability
- Current design: 2-10 concurrent users
- Per-user Orchestrator instances (higher memory usage)
- For 100+ users, consider request-scoped orchestrators

## Troubleshooting

### API Key Not Working
```bash
# Check if key is active
mysql -h tools -u steve -pkoala1 jarvis -e "
SELECT ak.api_key, ak.is_active, ak.expires_at, u.username
FROM api_keys ak
JOIN users u ON ak.user_id = u.id
WHERE ak.api_key = 'YOUR_KEY_HERE';"
```

### Server Not Starting
```bash
# Check if port is in use
lsof -i :8000

# Kill existing process
pkill -f "python -m api.server"

# Start fresh
./venv/bin/python -m api.server
```

### Memory Not Persisting
```bash
# Check conversation_sessions table
mysql -h tools -u steve -pkoala1 jarvis -e "
SELECT user_id, session_id, updated_at, is_active
FROM conversation_sessions
ORDER BY updated_at DESC
LIMIT 5;"
```

## Support & Resources

- **Interactive API Docs**: http://localhost:8000/docs
- **Issue Tracker**: https://github.com/anthropics/claude-code/issues
- **Configuration**: `config/config.yaml`
- **User Management**: `scripts/manage_users.py`
- **Server Logs**: `/tmp/api_server.log` (or check stdout)

## Version

**API Version**: 1.0.0
**Last Updated**: 2026-01-09
