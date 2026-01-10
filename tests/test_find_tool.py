#!/usr/bin/env python3
"""Test the new find_files tool."""

import sys
import yaml
import logging

sys.path.insert(0, '.')

from orchestrator import Orchestrator

# Quiet logging
logging.basicConfig(level=logging.WARNING)

# Load config
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Create orchestrator
orchestrator = Orchestrator(config)

print("Testing find_files tool...")
print("="*60)

# Test 1: Find all Python files
print("\nTest 1: Find all Python files (*.py)")
result = orchestrator.process_user_input("Find all Python files in the project")
print(f"Response: {result['response'][:200]}...")

# Test 2: Find all __init__.py files
print("\n" + "="*60)
print("\nTest 2: Find all __init__.py files")
result = orchestrator.process_user_input("Find all __init__.py files")
print(f"Response: {result['response'][:200]}...")

# Test 3: List available tools to confirm find_files is registered
print("\n" + "="*60)
print("\nTest 3: Check available tools")
result = orchestrator.process_user_input("What tools do you have available?")
print(f"Response: {result['response']}")

print("\n" + "="*60)
print("✓ Tests complete!")
