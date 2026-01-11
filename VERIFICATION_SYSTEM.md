# Verification System

## Overview

The Verification System is a self-correction mechanism that ensures Jarvis's responses actually answer the user's queries. It implements a verify-then-retry loop with corrective feedback.

## How It Works

### 1. Normal Execution Flow

```
User Query → Persona LLM → Tool Execution → Response Generation
```

### 2. With Verification (NEW!)

```
User Query → Persona LLM → Tool Execution → Response Generation
                ↓
           Verifier LLM
                ↓
         ✓ Verified? → Return Response
                ↓
         ✗ Not Verified
                ↓
    Add Corrective Feedback → Retry (up to max_retries)
```

## Architecture

### Verifier LLM (Stateless)

A separate LLM invocation that:
- Receives the original user query
- Receives tool execution results
- Receives the assistant's final response
- **Evaluates**: Did we actually answer the user's question?
- **Provides**: Reasoning + suggestions for improvement if failed

### Key Features

1. **Stateless Verification**: Each verification is independent, no conversation history
2. **High Confidence Required**: Only accepts results that clearly answer the query
3. **Corrective Feedback**: If verification fails, suggests what to try instead
4. **Automatic Retry**: System retries with feedback (configurable max retries)
5. **Graceful Degradation**: Returns best attempt if max retries reached

## Configuration

In `config/config.yaml`:

```yaml
verification:
  enabled: true  # Enable/disable verification
  max_retries: 2  # Max retry attempts (default: 2)
```

## Example Scenarios

### Scenario 1: Successful Verification

```
User: "Find all Python files in the project"
Tool: find_files(pattern="*.py") → 14 files found
Response: "I found 14 Python files: main.py, ..."

Verifier:
{
  "verified": true,
  "confidence": "high",
  "reasoning": "Query asked for Python files, tool found them all"
}
→ Response returned to user ✓
```

### Scenario 2: Failed Verification with Retry

```
User: "Read the README file"
Tool: read_file("readme.md") → FILE NOT FOUND
Response: "The file readme.md does not exist"

Verifier:
{
  "verified": false,
  "confidence": "medium",
  "reasoning": "File not found, but README typically exists",
  "suggestion": "Try different capitalization: README.md, Readme.md"
}

→ RETRY with corrective feedback

User (retry): "Read the README file
[SYSTEM FEEDBACK: Try different capitalization: README.md]"
Tool: read_file("README.md") → SUCCESS
Response: "Here's the README content..."

Verifier:
{
  "verified": true,
  "confidence": "high",
  "reasoning": "Successfully read README file"
}
→ Response returned to user ✓
```

### Scenario 3: Wrong Tool Selected

```
User: "What is the capital of France?"
Tool: find_files(pattern="*france*") → 0 files
Response: "No files found matching 'france'"

Verifier:
{
  "verified": false,
  "confidence": "high",
  "reasoning": "Query asks about geography, but file tools used",
  "suggestion": "Need web search or knowledge tool, not file operations"
}

→ RETRY (but current tools insufficient)
→ After max_retries: Return unverified response with explanation
```

## Benefits

1. **Self-Correction**: Catches mistakes automatically
2. **Better User Experience**: Higher chance of getting the right answer
3. **Debugging**: Verification reasoning helps understand failures
4. **Quality Control**: Ensures responses match query intent
5. **Extensibility**: As new tools are added, verification adapts

## Performance Considerations

- **Extra LLM Call**: Adds 1 verification call per query (fast, ~2-5 seconds)
- **Retry Overhead**: Failed verifications trigger retries (adds time)
- **Configurable**: Can disable verification if speed is critical

## Future Enhancements

- [ ] Cache verification patterns for common queries
- [ ] Confidence-based retry thresholds (only retry on high-confidence failures)
- [ ] Verification metrics and logging for analysis
- [ ] Different verification strategies per tool type
- [ ] User feedback incorporation into verification model

## Testing

Run the verification test:

```bash
./venv/bin/python test_verification.py
```

This demonstrates:
- Successful verification
- Verification reasoning
- Confidence levels

## Design Philosophy

> "Trust, but verify"

The verification system embodies the principle from DESIGN.md:
- **The LLM reasons** (Persona proposes solutions)
- **The orchestrator decides** (Executes and verifies)
- **The system acts** (Tools execute)
- **Verification ensures quality** (Verifier checks results)

This multi-LLM approach provides checks and balances, preventing a single LLM from both proposing AND validating its own solutions.
