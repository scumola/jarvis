#!/usr/bin/env python3
"""
Test script to verify model context window auto-detection.
"""

import sys
import yaml

# Add parent directory to path to import modules directly
sys.path.insert(0, '.')

# Import directly to avoid dependency issues
import importlib.util
spec = importlib.util.spec_from_file_location("budget_controller", "memory/budget_controller.py")
budget_controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(budget_controller)

spec2 = importlib.util.spec_from_file_location("model_specs", "memory/model_specs.py")
model_specs = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(model_specs)

# Import schemas for Memory type
spec3 = importlib.util.spec_from_file_location("schemas", "memory/schemas.py")
schemas = importlib.util.module_from_spec(spec3)
sys.modules['memory.schemas'] = schemas
spec3.loader.exec_module(schemas)

# Make model_specs available to budget_controller
sys.modules['memory.model_specs'] = model_specs

BudgetController = budget_controller.BudgetController
get_model_info = model_specs.get_model_info

# Load config
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Get configured model
model_name = config['ollama']['model']

print("="*80)
print("Model Context Window Auto-Detection Test")
print("="*80)

# Show model info
info = get_model_info(model_name)
print(f"\nConfigured Model: {model_name}")
print(f"  Detected Context Window: {info['context_window_formatted']}")
print(f"  Memory Budget: {info['memory_budget_tokens']:,} tokens ({info['recommended_budget']['memory_budget_percentage']*100:.0f}%)")
print(f"  Max Memories: {info['recommended_budget']['hard_cap_memories']}")

# Test BudgetController initialization
print("\n" + "="*80)
print("BudgetController Initialization Test")
print("="*80)

controller = BudgetController(config)
print(f"\nBudgetController Settings:")
print(f"  Total Budget: {controller.max_total_budget:,} tokens")
print(f"  Memory Percentage: {controller.memory_budget_percentage*100:.0f}%")
print(f"  Hard Cap: {controller.hard_cap_memories} memories")
print(f"  Avg Memory Tokens: {controller.avg_memory_tokens}")

# Test budget calculations
print("\n" + "="*80)
print("Budget Calculation Examples")
print("="*80)

test_scenarios = [
    ("Empty conversation", 0),
    ("Small conversation (1K tokens)", 1000),
    ("Medium conversation (10K tokens)", 10000),
    ("Large conversation (50K tokens)", 50000),
    ("Very large conversation (100K tokens)", 100000),
]

for scenario_name, conv_tokens in test_scenarios:
    available = controller.calculate_available_budget(conv_tokens)
    dynamic_k = controller.calculate_dynamic_k(available)
    print(f"\n{scenario_name} ({conv_tokens:,} tokens):")
    print(f"  Available for memories: {available:,} tokens")
    print(f"  Dynamic k: {dynamic_k} memories")

print("\n" + "="*80)
print("Switch Model Test")
print("="*80)

# Test with different models
test_models = [
    "llama3.1:8b",
    "qwen3:8b",
    "qwen3:14b",
]

for test_model in test_models:
    test_config = config.copy()
    test_config['ollama']['model'] = test_model
    test_controller = BudgetController(test_config)
    print(f"\n{test_model}:")
    print(f"  Context Window: {test_controller.max_total_budget:,} tokens")
    print(f"  Memory Budget: {int(test_controller.max_total_budget * test_controller.memory_budget_percentage):,} tokens")
    print(f"  Hard Cap: {test_controller.hard_cap_memories} memories")

print("\n" + "="*80)
print("Test Complete!")
print("="*80)
