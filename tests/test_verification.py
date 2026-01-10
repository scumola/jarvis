#!/usr/bin/env python3
"""Test the verification system with various scenarios."""

import sys
import yaml
import logging

sys.path.insert(0, '.')

from orchestrator import Orchestrator

# Set up logging to show verification process
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)

# Load config
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Ensure verification is enabled
config['verification']['enabled'] = True
config['verification']['max_retries'] = 2

print("="*70)
print("VERIFICATION SYSTEM TEST")
print("="*70)
print("\nInitializing Jarvis with verification enabled...")
orchestrator = Orchestrator(config)
print("✓ Ready\n")

# Test 1: Should verify successfully
print("="*70)
print("TEST 1: Query that should verify successfully")
print("="*70)
print("Query: 'Find all Python files in the project'\n")

result = orchestrator.process_user_input("Find all Python files in the project")

print(f"\nResponse: {result['response'][:200]}...")
print(f"\nActions taken: {len(result.get('actions_taken', []))}")

verification = result.get('verification', {})
print(f"\nVerification Result:")
print(f"  Verified: {verification.get('verified', 'N/A')}")
print(f"  Confidence: {verification.get('confidence', 'N/A')}")
print(f"  Reasoning: {verification.get('reasoning', 'N/A')}")

print("\n" + "="*70)
print("✓ Test 1 Complete")
print("="*70)
