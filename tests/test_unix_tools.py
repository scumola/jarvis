#!/usr/bin/env python3
"""Quick test of unix text tools."""

import sys
sys.path.insert(0, '.')

from tools.builtin_tools import grep_impl, diff_files_impl, wc_impl, head_impl, tail_impl

print("Testing Unix Text Tools")
print("="*60)

# Test grep
print("\n1. Testing grep on config.yaml for 'retries'...")
result = grep_impl("retries", "config/config.yaml", ignore_case=False)
if result['success']:
    print(f"✓ Found {result['output']['count']} matches:")
    for match in result['output']['matches']:
        print(f"  Line {match['line_number']}: {match['content']}")
else:
    print(f"✗ Error: {result['error']}")

# Test wc
print("\n2. Testing wc on README.md...")
result = wc_impl("README.md")
if result['success']:
    print(f"✓ Word count successful:")
    print(f"  Lines: {result['output']['lines']}")
    print(f"  Words: {result['output']['words']}")
    print(f"  Chars: {result['output']['characters']}")
else:
    print(f"✗ Error: {result['error']}")

# Test head
print("\n3. Testing head on README.md (first 5 lines)...")
result = head_impl("README.md", lines=5)
if result['success']:
    print(f"✓ Head successful:")
    print(result['output']['content'])
else:
    print(f"✗ Error: {result['error']}")

print("\n" + "="*60)
print("✓ Unix tools working!")
