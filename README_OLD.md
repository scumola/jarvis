# Jarvis - Local Voice-Driven Agent

A local, persistent, voice-interactive AI agent that can converse naturally and safely interact with your system.

## Current Status: Bootstrap Phase

This is the minimal viable system that allows Jarvis to help build itself.

### What Works Now

- **Core Orchestrator**: Trusted computing base that mediates all LLM-system interactions
- **Tool System**: Registry-based tool management with strict schemas
- **File System Tools**:
  - `read_file` - Read files from filesystem
  - `write_file` - Write files (requires approval)
  - `edit_file` - Surgical string replacement (auto-backup, diff, rollback support)
  - `list_directory` - List directory contents
  - `find_files` - Find files by glob pattern (CWD-restricted)
  - `list_backups` - List file backups created by edit_file
  - `restore_backup` - Rollback to previous file version
- **Unix Text Tools** (NEW!):
  - `grep` - Search patterns in files (regex support)
  - `diff` - Compare two files
  - `wc` - Count lines/words/chars
  - `head` - Show first N lines
  - `tail` - Show last N lines
- **Web Tools**:
  - `fetch_url` - Fetch content from URLs (blocks local networks)
  - `get_news_headlines` - Fetch latest news from searxng (auto-deduplicates)
- **Multi-LLM Architecture**:
  - **Persona LLM**: Conversational agent (main interface)
  - **Verifier LLM**: Validates if results answered the query (NEW!)
- **Self-Correction**: Automatic retry with corrective feedback if verification fails
- **Text Interface**: Command-line interface with persistent history (↑/↓ arrows)

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│                   (Text for now)                         │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR                           │
│         (Trusted Computing Base)                         │
│  • Validates all actions                                 │
│  • Enforces permissions                                  │
│  • Executes tools safely                                 │
│  • Maintains audit logs                                  │
└─────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────────┐    ┌────────────────────────────┐
│   Persona LLM        │    │   Tool Registry            │
│   (Ollama)           │    │   • Built-in tools         │
│   • Conversations    │    │   • Custom tools           │
│   • Proposes actions │    │   • Schemas & validation   │
└──────────────────────┘    └────────────────────────────┘
```

### Design Principles

1. **LLMs never execute directly** - They only propose structured actions
2. **Orchestrator decides** - All execution goes through the trusted orchestrator
3. **Tools are explicit** - No free-form shell access
4. **Safety first** - Destructive actions require approval
5. **Extensible** - System can propose and add new tools over time

## Quick Start

### Prerequisites

- Python 3.9+
- Ollama server running with qwen3:8b model
- Access to the Ollama server (default: `gpu:11434`)

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run Jarvis
python main.py
```

### Usage

```
You: Hello, can you list the files in the current directory?

Jarvis: I'll list the files in the current directory for you.
```json
{
  "action": "tool_call",
  "tool_name": "list_directory",
  "parameters": {"dir_path": "."},
  "reasoning": "User wants to see files in current directory"
}
```

[Actions executed: 1]
```

### Commands

- `/reset` - Reset conversation history
- `/quit` - Exit Jarvis

## Next Steps

With this bootstrap system running, Jarvis can now help build:

- [ ] Memory system (RAG with vector database)
- [ ] Additional LLM roles (Safety, Debug, Memory Curator)
- [ ] Voice I/O (STT/TTS integration with Kokoro)
- [ ] More sophisticated tools
- [ ] MySQL integration for metadata
- [ ] LED panel "face" display on Raspberry Pi
- [ ] Tool self-proposal system

## Configuration

Edit `config/config.yaml` to configure:
- Ollama server connection
- Tool behavior
- Logging settings
- Future: TTS/STT, memory, etc.

## Project Structure

```
jarvis/
├── config/           # Configuration files
├── orchestrator/     # Core orchestration engine
├── llm_roles/        # LLM role implementations
├── tools/            # Tool system and implementations
├── data/             # Persistent data (registries, etc.)
├── logs/             # Application logs
└── main.py           # Entry point
```

## Philosophy

> The LLM reasons.
> The orchestrator decides.
> The system acts.
> Memory shapes behavior.
> Safety overrides cleverness.

---

See [DESIGN.md](DESIGN.md) for complete system design and architecture.
