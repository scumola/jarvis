#!/usr/bin/env python3
"""Direct unit test of find_files tool (no LLM needed)."""

import sys
sys.path.insert(0, '.')

from tools.builtin_tools import find_files_impl

print("Direct test of find_files_impl function")
print("="*60)

# Test 1: Find all Python files
print("\nTest 1: Find all .py files")
result = find_files_impl(pattern="*.py", search_path=".", max_results=20)
if result['success']:
    print(f"✓ Found {result['output']['count']} Python files")
    print("  First 5 matches:")
    for match in result['output']['matches'][:5]:
        print(f"    - {match['path']}")
else:
    print(f"✗ Error: {result['error']}")

# Test 2: Find __init__.py files
print("\nTest 2: Find __init__.py files")
result = find_files_impl(pattern="__init__.py")
if result['success']:
    print(f"✓ Found {result['output']['count']} __init__.py files")
    for match in result['output']['matches']:
        print(f"    - {match['path']}")
else:
    print(f"✗ Error: {result['error']}")

# Test 3: Find in specific subdirectory
print("\nTest 3: Find .py files in tools directory")
result = find_files_impl(pattern="*.py", search_path="tools")
if result['success']:
    print(f"✓ Found {result['output']['count']} files in tools/")
    for match in result['output']['matches']:
        print(f"    - {match['path']}")
else:
    print(f"✗ Error: {result['error']}")

# Test 4: Security test - try to search outside CWD (should fail)
print("\nTest 4: Security test - try to search /etc (should fail)")
result = find_files_impl(pattern="*", search_path="/etc", max_results=5)
if not result['success']:
    print(f"✓ Security check passed: {result['error']}")
else:
    print(f"✗ Security check FAILED - was able to search outside CWD!")

print("\n" + "="*60)
print("✓ All tests complete!")
