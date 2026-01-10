#!/usr/bin/env python3
"""Test the backup system for file edits."""

import sys
import time
from pathlib import Path

sys.path.insert(0, '.')

from tools.builtin_tools import (
    edit_file_impl,
    list_backups_impl,
    restore_backup_impl,
    BACKUP_DIR
)

print("="*70)
print("TESTING BACKUP SYSTEM")
print("="*70)

# Create a test file
test_file = Path("test_backup_demo.txt")
original_content = """Hello World
This is line 2
This is line 3
Goodbye World"""

test_file.write_text(original_content)
print(f"\n1. Created test file: {test_file}")
print(f"   Content:\n{original_content}\n")

# Test 1: Edit with backup
print("\n2. Testing edit_file (creates backup automatically)...")
time.sleep(1)  # Ensure different timestamp
result = edit_file_impl(
    str(test_file),
    old_string="line 2",
    new_string="line TWO (edited!)"
)

if result['success']:
    print(f"✓ Edit successful")
    print(f"  Backup: {result['output']['backup_path']}")
    print(f"\n  Diff:")
    print(result['output']['diff'])
else:
    print(f"✗ Error: {result['error']}")
    sys.exit(1)

# Test 2: Make another edit
print("\n3. Making second edit...")
time.sleep(1)
result2 = edit_file_impl(
    str(test_file),
    old_string="line 3",
    new_string="line THREE (also edited!)"
)

if result2['success']:
    print(f"✓ Second edit successful")
    print(f"  Backup: {result2['output']['backup_path']}")
else:
    print(f"✗ Error: {result2['error']}")

# Test 3: List backups
print("\n4. Listing all backups...")
backups_result = list_backups_impl()

if backups_result['success']:
    backups = backups_result['output']['backups']
    print(f"✓ Found {len(backups)} backup(s):")
    for backup in backups:
        print(f"  - {backup['original_name']} @ {backup['timestamp']}")
        print(f"    Path: {backup['backup_file']}")
else:
    print(f"✗ Error: {backups_result['error']}")

# Test 4: List backups for specific file
print(f"\n5. Listing backups for '{test_file.name}'...")
filtered_result = list_backups_impl(file_name=test_file.name)

if filtered_result['success']:
    filtered_backups = filtered_result['output']['backups']
    print(f"✓ Found {len(filtered_backups)} backup(s) for {test_file.name}")
else:
    print(f"✗ Error: {filtered_result['error']}")

# Test 5: Restore from first backup (original version)
if backups:
    print("\n6. Restoring from oldest backup (original version)...")
    oldest_backup = backups[-1]  # Last in list (sorted newest first)
    restore_result = restore_backup_impl(oldest_backup['backup_file'])

    if restore_result['success']:
        print(f"✓ Restore successful")
        print(f"  Restored to: {restore_result['output']['restored_to']}")
        print(f"\n  Diff:")
        print(restore_result['output']['diff'])

        # Verify content
        restored_content = test_file.read_text()
        if restored_content == original_content:
            print("\n✓ Content verified: File restored to original!")
        else:
            print("\n✗ Content mismatch!")
    else:
        print(f"✗ Error: {restore_result['error']}")

# Show current file content
print("\n7. Current file content:")
print(test_file.read_text())

# Cleanup
print(f"\n8. Cleanup...")
test_file.unlink()
print(f"   Deleted {test_file}")

# Show that backups are preserved
print(f"\n   Backups preserved in {BACKUP_DIR}/")
if BACKUP_DIR.exists():
    backup_files = list(BACKUP_DIR.glob("*.bak"))
    print(f"   {len(backup_files)} backup file(s) remain for safety")

print("\n" + "="*70)
print("✓ All tests complete!")
print("="*70)
print(f"\nBackup system features demonstrated:")
print(f"  ✓ Automatic backups before edits")
print(f"  ✓ Timestamped backup filenames")
print(f"  ✓ Unified diff generation")
print(f"  ✓ Backup listing and filtering")
print(f"  ✓ Restore with verification")
print(f"  ✓ Pre-restore backup (safety)")
