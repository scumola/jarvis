# Jarvis API Quick Start Guide

Get up and running with the Jarvis multi-user API in 5 minutes!

## Prerequisites

- Python 3.10+ with virtual environment activated
- MySQL database running (host: tools, database: jarvis)
- Dependencies installed: `pip install -r requirements.txt`

## Step 1: Initialize Database

The database should already be initialized. Verify:

```bash
mysql -h tools -u steve -pkoala1 jarvis -e "SHOW TABLES;"
```

You should see: `users`, `api_keys`, `conversation_sessions`, `memories`, etc.

If not initialized, run:

```bash
./venv/bin/python scripts/init_api_db.py
```

## Step 2: Create Your First User

Create an API user:

```bash
./venv/bin/python scripts/manage_users.py create myuser "My Name"
```

**IMPORTANT**: Save the API key that's displayed! It won't be shown again.

Example output:
```
======================================================================
USER CREATED SUCCESSFULLY
======================================================================
User ID:      2
Username:     myuser
Display Name: My Name
Role:         api_user
API Key:      abc123...xyz789
======================================================================

IMPORTANT: Save this API key - it will not be shown again!
```

## Step 3: Start the API Server

```bash
./venv/bin/python -m api.server
```

Or with auto-reload for development:

```bash
uvicorn api.server:app --reload
```

The server will start on `http://localhost:8000`

## Step 4: Test Your Setup

Open a new terminal and test the API:

### Health Check
```bash
curl http://localhost:8000/
```

Expected response:
```json
{
  "service": "Jarvis API",
  "version": "1.0.0",
  "status": "operational"
}
```

### Authenticate
```bash
API_KEY="your-api-key-here"  # Replace with your actual key

curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/api/v1/me
```

Expected response:
```json
{
  "user_id": 2,
  "username": "myuser",
  "display_name": "My Name",
  "role": "api_user"
}
```

### Chat
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello! My name is John and I like JavaScript."}'
```

Response (after ~15-30 seconds):
```json
{
  "response": "Hello, John! Nice to meet you...",
  "actions_taken": [],
  "session_id": "..."
}
```

### View Your Memories
```bash
curl -H "Authorization: Bearer $API_KEY" \
  "http://localhost:8000/api/v1/memories?limit=5"
```

You should see memories about your name and JavaScript preference!

## Step 5: Explore the Interactive Docs

Open your browser to:

**Swagger UI**: http://localhost:8000/docs

This provides an interactive interface to:
- View all endpoints
- Test API calls directly in the browser
- See request/response schemas
- No need to write curl commands!

## Common Operations

### Create a Master User (Full Access)

```bash
./venv/bin/python scripts/manage_users.py create admin "Admin User" --role master
```

Master users can perform ALL operations including file writes.

### List All Users

```bash
./venv/bin/python scripts/manage_users.py list
```

### Regenerate API Key

```bash
./venv/bin/python scripts/manage_users.py regenerate myuser
```

### Reset Conversation

```bash
curl -X POST -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/api/v1/session/reset
```

Clears conversation history but keeps long-term memories.

## Python Client Example

Create a file `test_client.py`:

```python
import requests
import json

API_KEY = "your-api-key-here"  # Replace with your actual key
BASE_URL = "http://localhost:8000"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def chat(message):
    """Send a message to Jarvis"""
    response = requests.post(
        f"{BASE_URL}/api/v1/chat",
        headers=headers,
        json={"message": message},
        timeout=90  # Chat can take time
    )
    return response.json()

def get_memories(limit=10):
    """Get your memories"""
    response = requests.get(
        f"{BASE_URL}/api/v1/memories",
        headers=headers,
        params={"limit": limit}
    )
    return response.json()

# Test it
if __name__ == "__main__":
    # Chat
    print("Chatting with Jarvis...")
    result = chat("What's my name?")
    print(f"Response: {result['response']}")
    print(f"Session: {result['session_id']}")
    print()

    # Get memories
    print("Fetching memories...")
    memories = get_memories(5)
    print(f"Total memories: {memories['count']}")
    for mem in memories['memories']:
        print(f"  [{mem['type']}] {mem['text']}")
```

Run it:
```bash
python test_client.py
```

## Security Notes

### API User (Default Role)
- ✅ Can READ files, directories, web content
- ✅ Can search and grep files
- ❌ CANNOT write, edit, or delete files
- ❌ CANNOT execute system commands

### Master User
- ✅ Full access to ALL operations
- ✅ Can write files, execute commands
- Use for trusted administrators only

### Best Practices
1. **Never share API keys** - Each user should have their own
2. **Rotate keys regularly** - Use `regenerate` command
3. **Use master role sparingly** - Only for trusted users
4. **Monitor logs** - Check `/tmp/api_server.log` for issues

## CLI vs API

You can use **BOTH** simultaneously:

### CLI (Local, Master Access)
```bash
./venv/bin/python main.py
```
- No API key required
- Always runs with master privileges
- Direct terminal interaction

### API (Remote, Role-Based)
```bash
# API server running on :8000
curl -H "Authorization: Bearer $API_KEY" ...
```
- Requires API key
- Role-based restrictions
- JSON responses for programmatic access

## Troubleshooting

### "Address already in use"
Another server is running on port 8000:
```bash
pkill -f "python -m api.server"
./venv/bin/python -m api.server
```

### "Invalid or expired API key"
Check if your key is active:
```bash
./venv/bin/python scripts/manage_users.py list
```

If needed, regenerate:
```bash
./venv/bin/python scripts/manage_users.py regenerate myuser
```

### Chat requests timeout
Chat operations can take 30-60 seconds. Increase your timeout:
```python
requests.post(..., timeout=90)  # 90 seconds
```

### Can't connect to database
Verify MySQL is running and accessible:
```bash
mysql -h tools -u steve -pkoala1 jarvis -e "SELECT 1;"
```

## Next Steps

1. **Read the full documentation**: `docs/API_DOCUMENTATION.md`
2. **Review test results**: `docs/API_TESTING_SUMMARY.md`
3. **Explore the interactive docs**: http://localhost:8000/docs
4. **Build your application**: Use the Python client example as a starting point

## Need Help?

- Check logs: `tail -f /tmp/api_server.log`
- View errors: Check the API response `detail` field
- Test in browser: Use Swagger UI at `/docs`
- Review code: All API code is in `api/` directory

---

🎉 **You're ready to go!** Start chatting with Jarvis via the API!
