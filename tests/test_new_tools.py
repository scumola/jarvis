#!/usr/bin/env python3
"""Test the new fetch_url and edit_file tools."""

import sys
sys.path.insert(0, '.')

from tools.builtin_tools import fetch_url_impl, edit_file_impl
from pathlib import Path

print("="*70)
print("TESTING NEW TOOLS")
print("="*70)

# Test 1: fetch_url with a simple public URL
print("\n1. Testing fetch_url with example.com...")
result = fetch_url_impl("https://example.com", timeout=10, max_size_mb=1)
if result['success']:
    content = result['output']['content']
    print(f"✓ Fetched {result['output']['size_bytes']} bytes")
    print(f"  Content-Type: {result['output']['content_type']}")
    print(f"  First 100 chars: {content[:100]}...")
else:
    print(f"✗ Error: {result['error']}")

# Test 2: fetch_url security - block localhost
print("\n2. Testing fetch_url security (should block localhost)...")
result = fetch_url_impl("http://localhost:8080")
if not result['success']:
    print(f"✓ Security check passed: {result['error']}")
else:
    print(f"✗ Security check FAILED - allowed localhost access!")

# Test 3: fetch_url security - block file://
print("\n3. Testing fetch_url security (should block file:// protocol)...")
result = fetch_url_impl("file:///etc/passwd")
if not result['success']:
    print(f"✓ Security check passed: {result['error']}")
else:
    print(f"✗ Security check FAILED - allowed file:// access!")

# Test 4: edit_file - create a test file, edit it
print("\n4. Testing edit_file...")
test_file = Path("test_edit_temp.txt")

# Create test file
test_file.write_text("Hello World\nThis is a test\nGoodbye World")
print(f"   Created test file: {test_file}")

# Try to edit it
result = edit_file_impl(
    str(test_file),
    old_string="This is a test",
    new_string="This is EDITED!"
)

if result['success']:
    print(f"✓ Edit successful")
    print(f"  File: {result['output']['path']}")
    print(f"  Replaced {result['output']['old_length']} chars with {result['output']['new_length']} chars")

    # Verify the edit
    new_content = test_file.read_text()
    if "This is EDITED!" in new_content:
        print(f"✓ Verified: Edit was applied correctly")
    else:
        print(f"✗ Verification failed: Edit not found in file")
else:
    print(f"✗ Error: {result['error']}")

# Clean up
test_file.unlink()
print(f"   Cleaned up test file")

# Test 5: edit_file safety - prevent ambiguous replacements
print("\n5. Testing edit_file safety (should reject ambiguous replacements)...")
test_file.write_text("test\ntest\ntest")
result = edit_file_impl(str(test_file), "test", "replaced")
if not result['success']:
    print(f"✓ Safety check passed: {result['error']}")
else:
    print(f"✗ Safety check FAILED - allowed ambiguous replacement!")
test_file.unlink()

print("\n" + "="*70)
print("✓ All tests complete!")
print("="*70)
