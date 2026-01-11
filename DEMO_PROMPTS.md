# Demo Prompts for Testing Jarvis

Try these prompts to see Jarvis in action! Run `./venv/bin/python main.py` to start.

## 🎯 Self-Awareness & Meta Capabilities

```
What files exist in the current directory?
```
Shows: `list_directory` tool usage

```
What tools do you currently have available?
```
Shows: Self-awareness of capabilities

```
Find all Python files in the project
```
Shows: `find_files` tool with pattern matching

```
Find all __init__.py files
```
Shows: Precise pattern matching across subdirectories

## 📖 Reading & Understanding Code

```
Read the DESIGN.md file and give me a brief summary of what your purpose is
```
Shows: File reading + comprehension

```
Read the orchestrator/engine.py file and briefly explain what the orchestrator does
```
Shows: Code reading + explanation

```
List all Python files in the tools directory
```
Shows: Targeted searching

```
Read your own main.py file and explain how you work
```
Shows: Meta-awareness - Jarvis reading its own code!

## 🏗️ Self-Building Capabilities

```
Read the builtin_tools.py file and suggest a new tool we should add
```
Shows: Understanding existing code + suggesting improvements

```
What would be a good next tool to implement for your capabilities?
```
Shows: Understanding capability gaps

```
Read the schema.py file and explain how tools are defined
```
Shows: Understanding the tool system architecture

## ✍️ Write Operations (Tests Approval Flow)

```
Create a file called test.txt with the content 'Hello from Jarvis'
```
Shows: Write approval flow - you'll be prompted to approve/deny

```
Write a simple Python script that prints 'Hello World' to a file named hello.py
```
Shows: Code generation + write approval

## 🔍 Advanced Searches

```
Find all files that start with 'test'
```
Shows: Glob pattern matching with wildcards

```
Find all YAML files in the project
```
Shows: Extension-based searching

## 🤖 Multi-Step Tasks

```
Find all Python files in the tools directory, then read one and explain what it does
```
Shows: Multi-step reasoning with tool chaining

```
Explore the project structure and give me a summary of how the codebase is organized
```
Shows: Complex exploration task

## 🌐 Web Access (NEW!)

```
Fetch the content from https://example.com
```
Shows: URL fetching capability with security controls

```
What tools do you have available now?
```
Shows: Jarvis now includes fetch_url and edit_file

## ✏️ Code Editing (NEW!)

```
Read the config.yaml file and show me the verification settings
```
Shows: Understanding current configuration

```
In config.yaml, change max_retries from 2 to 3
```
Shows: Surgical file editing with approval (will prompt you!)

## 🎪 The Ultimate Meta Demo

```
Read your own source code in the llm_roles directory and help me understand how you process my requests
```
Shows: Complete meta-awareness - Jarvis explaining its own architecture!

```
Suggest a new tool we should add, then use edit_file to add it yourself
```
Shows: The full "machine building machines" loop!

---

## Tips

- Use `/reset` to clear conversation history
- Use `/quit` to exit
- Destructive operations (like `write_file`) will prompt for approval
- The `<think>` tags from the model are automatically hidden in output
