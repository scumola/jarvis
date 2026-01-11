# Model Context Window Auto-Detection

## Overview

The memory budget system now **automatically detects** the correct context window size based on the configured LLM model. This eliminates the need to manually update token limits when switching between models.

## What Changed

### Before (Hard-Coded)
```yaml
context_budgeting:
  max_total_tokens: 8000  # Had to manually update this
  memory_budget_percentage: 0.15
  hard_cap_memories: 10
```

**Problems:**
- llama3.1:8b was configured for only 8K tokens (should be 128K!)
- Manual updates required when switching models
- Easy to forget to update, causing poor performance

### After (Auto-Detected)
```yaml
context_budgeting:
  enabled: true
  # max_total_tokens: AUTO-DETECTED from model name
  # memory_budget_percentage: AUTO-DETECTED (optimal for context size)
  # hard_cap_memories: AUTO-DETECTED (optimal for context size)
  avg_memory_tokens: 50
  min_memories: 1
```

**Benefits:**
- Context window automatically matched to model
- Optimal memory budget percentages for each model size
- Can override any setting by uncommenting and specifying a value

## Supported Models

### Llama Models

| Model | Context Window | Memory Budget | Max Memories |
|-------|----------------|---------------|--------------|
| llama3.1:8b | 128K tokens | 12.8K (10%) | 20 |
| llama3.1:70b | 128K tokens | 12.8K (10%) | 20 |
| llama3.1:405b | 128K tokens | 12.8K (10%) | 20 |
| llama3.2:* | 128K tokens | 12.8K (10%) | 20 |
| llama3:8b (older) | 8K tokens | 1.2K (15%) | 10 |

### Qwen Models

| Model | Context Window | Memory Budget | Max Memories |
|-------|----------------|---------------|--------------|
| qwen3:8b | 262K tokens | 13.1K (5%) | 30 |
| qwen3:14b | 262K tokens | 13.1K (5%) | 30 |
| qwen3:30b | 262K tokens | 13.1K (5%) | 30 |
| qwen2.5:* | 128K tokens | 12.8K (10%) | 20 |
| qwen2.5-*-1m | 1M tokens | 50K (5%) | 30 |
| qwen2:* (older) | 32K tokens | 3.2K (10%) | 20 |

## How It Works

### 1. Model Detection

The system reads `ollama.model` from `config.yaml`:
```yaml
ollama:
  model: "llama3.1:8b"  # Or "qwen3:14b", etc.
```

### 2. Context Window Lookup

The `memory/model_specs.py` module contains a registry of known models:
```python
MODEL_SPECS = {
    r"llama3\.1.*": 128_000,   # 128K tokens
    r"qwen3.*": 262_000,        # 262K tokens
    # ... more models
}
```

Pattern matching determines the context window size.

### 3. Optimal Budget Calculation

Based on context window size:
- **Small (≤8K)**: 15% for memories, cap at 10
- **Medium (≤128K)**: 10% for memories, cap at 20
- **Large (>128K)**: 5% for memories, cap at 30

This ensures:
- Small models: Conservative allocation (don't starve conversation)
- Large models: Generous allocation (utilize available space)

### 4. Override Support

You can override any auto-detected value:
```yaml
context_budgeting:
  max_total_tokens: 100000      # Override auto-detection
  memory_budget_percentage: 0.20  # Use 20% instead of default
  hard_cap_memories: 25           # Custom cap
```

## Performance Improvement

For **llama3.1:8b** (current config):

```
Old (hard-coded 8K):
  Total: 8,000 tokens
  Memory Budget: 1,200 tokens (15%)
  Max Memories: 10

New (auto-detect 128K):
  Total: 128,000 tokens
  Memory Budget: 12,800 tokens (10%)
  Max Memories: 20

Improvement:
  Context Window: 16x larger
  Memory Budget: 10.7x larger
  Max Memories: 2x more
```

## Switching Models

Just change the model in config.yaml:

```yaml
# Switch from Llama to Qwen
ollama:
  # model: "llama3.1:8b"
  model: "qwen3:14b"
```

The system automatically:
- Detects qwen3:14b has 262K context window
- Allocates 13.1K tokens for memories (5%)
- Sets max memories to 30
- No other config changes needed!

## Adding New Models

To add support for a new model, edit `memory/model_specs.py`:

```python
MODEL_SPECS = {
    # Existing models...

    # New model
    r"new-model.*": 256_000,  # 256K context window
}
```

The pattern is a Python regex that matches the model name (case-insensitive).

## Testing

Run the test script to verify detection:
```bash
python3 memory/model_specs.py
```

Or test with your config:
```bash
python3 test_model_specs_simple.py
```

## Files Modified

1. **memory/model_specs.py** (NEW)
   - Model registry with context window sizes
   - Auto-detection logic
   - Recommended budget calculations

2. **memory/budget_controller.py** (UPDATED)
   - Now accepts `model_name` parameter
   - Auto-detects from config if not provided
   - Falls back to explicit config values if set

3. **config/config.yaml** (UPDATED)
   - Removed hard-coded `max_total_tokens: 8000`
   - Added comments explaining auto-detection
   - Updated summarization to use full 128K context

4. **memory/manager.py** (NO CHANGE NEEDED)
   - Already passes config to BudgetController
   - Auto-detection works automatically

## Sources

- [Llama 3.1 Announcement](https://ai.meta.com/blog/meta-llama-3-1/) (128K context)
- [Qwen 2.5-1M Documentation](https://qwenlm.github.io/blog/qwen2.5-1m/) (1M context)
- [Qwen3 Specifications](https://www.datastudios.org/post/qwen-context-window-token-limits-memory-policy-and-2025-rules) (262K context)
