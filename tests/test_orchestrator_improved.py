#!/usr/bin/env python3
"""Test the improved orchestrator with formatted tool results."""

import sys
import yaml
import logging

sys.path.insert(0, '.')

from orchestrator import Orchestrator

# Quieter logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s'
)

# Load config
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Create orchestrator
print("Initializing Jarvis with improved result formatting...")
orchestrator = Orchestrator(config)
print("✓ Ready\n")

print("="*70)
print("TEST: Find all Python files")
print("="*70)

result = orchestrator.process_user_input("Find all Python files in the project")

print(f"\nJarvis Response:\n{result['response']}")
print(f"\n✓ Test complete")
