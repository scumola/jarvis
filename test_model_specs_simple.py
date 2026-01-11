#!/usr/bin/env python3
"""
Simple test for model specifications without dependencies.
"""

import re

# Model specifications (copied from model_specs.py)
MODEL_SPECS = {
    # Llama Models
    r"llama3\.1.*": 128_000,
    r"llama3\.2.*": 128_000,
    r"llama-3\.1.*": 128_000,
    r"llama-3\.2.*": 128_000,
    r"llama3:.*": 8_000,
    r"llama-3:.*": 8_000,

    # Qwen Models
    r"qwen2\.5.*1m.*": 1_000_000,
    r"qwen2\.5.*-1m.*": 1_000_000,
    r"qwen2\.5.*": 128_000,
    r"qwen-2\.5.*": 128_000,
    r"qwen3.*": 262_000,
    r"qwen-3.*": 262_000,
    r"qwen2:.*": 32_000,
    r"qwen:.*": 32_000,
}

DEFAULT_CONTEXT_WINDOW = 8_000


def get_context_window(model_name: str) -> int:
    """Get the context window size for a given model name."""
    model_lower = model_name.lower()

    for pattern, context_size in MODEL_SPECS.items():
        if re.search(pattern, model_lower):
            return context_size

    return DEFAULT_CONTEXT_WINDOW


def get_recommended_memory_budget(model_name: str) -> dict:
    """Get recommended memory budget settings for a given model."""
    context_window = get_context_window(model_name)

    if context_window <= 8_000:
        return {
            'max_total_tokens': context_window,
            'memory_budget_percentage': 0.15,
            'hard_cap_memories': 10,
            'avg_memory_tokens': 50,
        }
    elif context_window <= 128_000:
        return {
            'max_total_tokens': context_window,
            'memory_budget_percentage': 0.10,
            'hard_cap_memories': 20,
            'avg_memory_tokens': 50,
        }
    else:
        return {
            'max_total_tokens': context_window,
            'memory_budget_percentage': 0.05,
            'hard_cap_memories': 30,
            'avg_memory_tokens': 50,
        }


# Test different models
print("="*80)
print("Model Context Window Auto-Detection Test")
print("="*80)

test_models = [
    ("llama3.1:8b", "Current config model"),
    ("llama3.1:70b", "Larger Llama 3.1"),
    ("qwen3:8b", "Qwen3 8B"),
    ("qwen3:14b", "Qwen3 14B (escalation model)"),
    ("qwen2.5-14b-instruct-1m", "Qwen 2.5 with 1M context"),
    ("llama3:8b", "Older Llama 3"),
]

for model, description in test_models:
    context = get_context_window(model)
    config = get_recommended_memory_budget(model)
    memory_budget = int(context * config['memory_budget_percentage'])

    print(f"\n{model} ({description}):")
    print(f"  Context Window: {context:,} tokens")
    print(f"  Memory Budget: {memory_budget:,} tokens ({config['memory_budget_percentage']*100:.0f}%)")
    print(f"  Max Memories: {config['hard_cap_memories']}")

print("\n" + "="*80)
print("Budget Calculation Example (llama3.1:8b)")
print("="*80)

# Simulate budget calculations
model = "llama3.1:8b"
config = get_recommended_memory_budget(model)
total_budget = config['max_total_tokens']
memory_pct = config['memory_budget_percentage']

scenarios = [
    0,      # Empty conversation
    1_000,  # Small conversation
    10_000, # Medium conversation
    50_000, # Large conversation
    100_000,# Very large conversation
]

for conv_tokens in scenarios:
    remaining_space = total_budget - conv_tokens
    reserved_budget = int(total_budget * memory_pct)
    available = max(0, min(remaining_space, reserved_budget))
    dynamic_k = available // config['avg_memory_tokens']
    dynamic_k = max(1, min(dynamic_k, config['hard_cap_memories']))

    print(f"\nConversation: {conv_tokens:,} tokens")
    print(f"  Available for memories: {available:,} tokens")
    print(f"  Can retrieve: {dynamic_k} memories")

print("\n" + "="*80)
print("Comparison: Old Config (8K) vs New Auto-Detect (128K)")
print("="*80)

old_total = 8_000
old_pct = 0.15
new_total = 128_000
new_pct = 0.10

print(f"\nOld Config (hard-coded 8K):")
print(f"  Total: {old_total:,} tokens")
print(f"  Memory Budget: {int(old_total * old_pct):,} tokens (15%)")
print(f"  Max Memories: 10")

print(f"\nNew Auto-Detect (llama3.1:8b = 128K):")
print(f"  Total: {new_total:,} tokens")
print(f"  Memory Budget: {int(new_total * new_pct):,} tokens (10%)")
print(f"  Max Memories: 20")

print(f"\nImprovement:")
print(f"  Context Window: {(new_total / old_total):.1f}x larger")
print(f"  Memory Budget: {(int(new_total * new_pct) / int(old_total * old_pct)):.1f}x larger")
print(f"  Max Memories: 2x more")

print("\n" + "="*80)
print("Test Complete!")
print("="*80)
