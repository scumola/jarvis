# Jarvis - Intelligent AI Assistant with Learning & Memory

A sophisticated local AI assistant featuring multi-user support, persistent memory, autonomous goal execution, self-learning through introspection, and adaptive retry strategies.

## 🌟 Key Features

### 🧠 **Intelligent Memory System**
- **RAG (Retrieval-Augmented Generation)** with ChromaDB vector store + MySQL metadata
- **Multi-user memory isolation** - Each user has private episodic/semantic memories
- **Source trust layer** - Tracks provenance, corroboration, and fact confidence
- **Automatic memory curation** - LLM analyzes interactions and proposes relevant memories
- **Smart retrieval** - Combines semantic similarity, recency decay, and verification trust

### 🎯 **Goal Management & Autonomous Execution**
- **Auto-goal detection** - Automatically identifies multi-step tasks
- **Hierarchical task decomposition** - Breaks complex goals into subtasks with dependencies
- **Autonomous execution** - Executes goals automatically with checkpoints
- **Progress tracking** - Monitor goal status, completion %, and task results

### 🔄 **Adaptive Retry & Learning**
- **Procedural memory** - Learns successful retry strategies from experience
- **Intelligent retry strategies** - Pattern matching for failure types and contexts
- **Introspection & self-critique** - Post-task reflection extracts deep insights:
  - Root cause analysis
  - Inefficiency detection
  - Surprise identification
  - Generalizable lessons
- **Adaptive confidence** - High-success-rate strategies trusted more

### 💬 **Conversation Management**
- **Automatic summarization** - Prevents token limit issues in long conversations
- **Context preservation** - Maintains important details while condensing history
- **Multi-session support** - Persistent conversations across server restarts

### 🌐 **Multi-User Web API**
- **FastAPI REST endpoints** - Full-featured HTTP API
- **API key authentication** - Secure access with MySQL-backed user management
- **Role-based permissions** - Master (full access) vs API users (read-only)
- **Session management** - Per-user orchestrator instances with persistence
- **Dual interface** - CLI for local use + API for remote access

### 🛡️ **Safety & Verification**
- **Result verification** - Separate LLM validates if responses answer the query
- **Automatic retry** - Self-corrects when verification fails
- **Tool access control** - API users restricted to safe, read-only operations
- **Sandbox mode** - Optional sandboxed tool execution

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                    JARVIS ARCHITECTURE                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐              ┌──────────────┐                   │
│  │  CLI (local) │              │ API (FastAPI)│                   │
│  │  Always      │              │  Role-Based   │                   │
│  │  Master      │              │  Multi-User   │                   │
│  └──────┬───────┘              └──────┬────────┘                   │
│         │                              │                            │
│         └──────────────┬───────────────┘                            │
│                        │                                            │
│                        ▼                                            │
│              ┌──────────────────┐                                  │
│              │   Orchestrator    │   (Trusted Computing Base)       │
│              │   (per user)      │   • Validates actions            │
│              └────────┬──────────┘   • Enforces permissions       │
│                       │              • Executes tools safely       │
│         ┌─────────────┼─────────────┬───────────┐                 │
│         │             │             │           │                  │
│         ▼             ▼             ▼           ▼                  │
│   ┌─────────┐   ┌──────────┐  ┌──────────┐ ┌──────────┐         │
│   │Persona  │   │Verifier  │  │Curator   │ │Retry     │         │
│   │  LLM    │   │   LLM    │  │   LLM    │ │Strategist│         │
│   └─────────┘   └──────────┘  └──────────┘ └──────────┘         │
│        │              │             │            │                 │
│        └──────────────┴─────────────┴────────────┘                 │
│                       │                                            │
│                       ▼                                            │
│        ┌──────────────────────────────┐                           │
│        │      Memory Manager           │                           │
│        └────────┬─────────────────────┘                           │
│                 │                                                  │
│         ┌───────┼────────┬──────────────┐                         │
│         │       │        │              │                          │
│         ▼       ▼        ▼              ▼                          │
│   ┌────────┐ ┌────┐ ┌──────────┐  ┌──────────┐                  │
│   │ChromaDB│ │MySQL│ │Procedural│  │  Goals   │                  │
│   │(vector)│ │(meta)│ │  Memory  │  │ Manager  │                  │
│   │User ID │ │User ID│ │  (Global)│  │ (MySQL)  │                  │
│   └────────┘ └────┘ └──────────┘  └──────────┘                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Ollama** with llama3.1:8b (or qwen3:8b) model
- **MySQL 8.0+** for metadata storage
- **ChromaDB** (installed via requirements.txt)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd jarvis

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize databases
python scripts/init_memory_db.py
python scripts/init_procedural_memory_db.py
python scripts/init_api_db.py  # If using API

# Configure
cp config/config.yaml config/config.yaml.local
# Edit config/config.yaml.local with your settings

# Run CLI interface
python main.py

# Or run API server
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

### First Steps

**CLI Mode:**
```
You: Hello, I'm Steve and I like coffee
Jarvis: Nice to meet you, Steve! I've noted your preference for coffee...

You: What do I like?
Jarvis: You like coffee.

You: Create a test directory structure with 3 files
[Auto-goal detection triggers]
```

**API Mode:**
```bash
# Create a user
python scripts/manage_users.py create alice "Alice Smith"
# API key will be printed

# Test the API
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, my name is Alice"}'
```

## 📚 Documentation

Comprehensive documentation available in `docs/`:

- **[API_QUICK_START.md](docs/API_QUICK_START.md)** - Get started with the web API in 5 minutes
- **[API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)** - Complete API reference
- **[GOAL_MANAGEMENT.md](docs/GOAL_MANAGEMENT.md)** - Goal system usage and examples
- **[PROCEDURAL_LEARNING.md](docs/PROCEDURAL_LEARNING.md)** - How Jarvis learns from experience
- **[CONVERSATION_SUMMARIZATION.md](docs/CONVERSATION_SUMMARIZATION.md)** - Long conversation support
- **[SOURCE_TRUST_LAYER.md](docs/SOURCE_TRUST_LAYER.md)** - Fact verification and provenance
- **[IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md)** - Complete feature list

## 🛠️ Available Tools

### File System
- `read_file`, `write_file`, `edit_file`, `create_directory`
- `list_directory`, `find_files`
- `list_backups`, `restore_backup`

### Unix Text Tools
- `grep`, `diff`, `wc`, `head`, `tail`

### Web Tools
- `fetch_url`, `web_search`, `get_news_headlines`

### System Tools
- `get_datetime`

## 🎮 Demo Scripts

Run interactive demos in `examples/`:

```bash
# Learning & procedural memory
python examples/learning_demo.py

# Goal management
python examples/goal_demo.py
python examples/goal_decomposition_demo.py
python examples/auto_goal_demo.py

# Introspection & self-critique
python examples/introspection_demo.py

# Conversation summarization
python examples/summarization_demo.py
```

## 🧪 Testing

```bash
# Run unit tests
python -m pytest tests/

# Test all demos
./test_all_demos.sh

# Individual test files
python tests/test_memory_system.py
python tests/test_goal_management.py
python tests/test_source_trust.py
```

## ⚙️ Configuration

Edit `config/config.yaml`:

```yaml
# Ollama LLM
ollama:
  host: "gpu"  # or "localhost"
  port: 11434
  model: "llama3.1:8b"
  timeout: 300

# Memory system
memory:
  enabled: true
  vector_db_path: "data/vector_store"
  mysql_host: "localhost"
  mysql_database: "jarvis"

# Procedural learning
  procedural_enabled: true
  procedural_adaptive: true  # Adaptive confidence thresholds
  procedural_auto_decay: true  # Auto-decay unused heuristics

# Goals
goals:
  enabled: true
  auto_detect: true  # Auto-detect multi-step tasks
  auto_execute_goals: true  # Execute autonomously

# Summarization
summarization:
  enabled: true
  max_tokens: 8000
  trigger_threshold: 0.7  # Summarize at 70% full

# API
api:
  host: "0.0.0.0"
  port: 8000
  session_timeout: 3600
```

## 🗂️ Project Structure

```
jarvis/
├── api/                  # Web API (FastAPI)
│   ├── server.py        # Main API server
│   ├── auth.py          # Authentication
│   ├── session_manager.py
│   └── tool_filter.py   # Role-based access control
├── orchestrator/        # Core orchestration engine
│   ├── engine.py        # Main orchestrator
│   └── retry_schemas.py
├── llm_roles/           # Specialized LLM roles
│   ├── persona.py       # Conversational agent
│   ├── verifier.py      # Result verification
│   ├── curator.py       # Memory curation
│   ├── retry_strategist.py
│   ├── goal_decomposer.py
│   ├── summarizer.py
│   └── introspection.py # Self-critique
├── memory/              # Memory system
│   ├── manager.py       # Memory manager
│   ├── vector_store.py  # ChromaDB interface
│   ├── metadata_store.py # MySQL interface
│   └── procedural_memory.py
├── goals/               # Goal management
│   ├── manager.py
│   └── schemas.py
├── tools/               # Tool system
│   ├── registry.py
│   ├── builtin_tools.py
│   └── web_search.py
├── config/              # Configuration
│   └── config.yaml
├── docs/                # Documentation
├── examples/            # Demo scripts
├── scripts/             # Utility scripts
│   ├── init_*.py       # Database initialization
│   └── manage_users.py  # User management CLI
├── tests/               # Unit tests
├── data/                # Persistent data
│   ├── vector_store/   # ChromaDB data
│   └── backups/        # File backups
├── logs/                # Application logs
├── main.py              # CLI entry point
└── requirements.txt
```

## 🎯 Key Design Principles

1. **LLMs propose, orchestrator decides** - LLMs never execute directly
2. **Memory shapes behavior** - Learning from experience over time
3. **Multi-user isolation** - Private memories, shared learning
4. **Safety first** - Verification, permissions, sandboxing
5. **Introspective learning** - Understanding WHY, not just WHAT
6. **Autonomous but supervised** - Can work independently with checkpoints

## 🔐 Security

- **API key authentication** with MySQL storage
- **Role-based access control** (master vs. api_user)
- **Tool filtering** - API users restricted to read-only operations
- **No file writes** for remote users (API)
- **SQL injection protection** - Parameterized queries throughout
- **CORS configuration** - Adjust for production use

## 📊 Statistics & Insights

Check system learning state:

```python
from memory.procedural_memory import ProceduralMemoryManager

pm = ProceduralMemoryManager(config['memory'])
print(pm.get_learning_insights())
```

View memory statistics:

```bash
curl -H "Authorization: Bearer YOUR_KEY" \
  http://localhost:8000/api/v1/stats
```

## 🤝 Contributing

This is currently a personal project. Feedback and suggestions welcome!

## 📝 License

[To be determined]

## 🙏 Acknowledgments

- **Ollama** for local LLM inference
- **ChromaDB** for vector storage
- **FastAPI** for web framework
- **Claude Sonnet 4.5** for helping build Jarvis

---

## Philosophy

> The LLM reasons.
> The orchestrator decides.
> The system acts.
> Memory shapes behavior.
> Reflection enables wisdom.
> Safety overrides cleverness.

Built with ❤️ for learning and experimentation.
