#!/usr/bin/env python3
"""
Memory Import Script

Import memories from a JSON backup file.
Restores metadata, vector embeddings, and relationships.

Usage:
    # Import from backup (skip existing memories)
    ./venv/bin/python scripts/import_memories.py backup.json

    # Import and overwrite existing memories
    ./venv/bin/python scripts/import_memories.py backup.json --no-skip

    # Import without restoring relationships
    ./venv/bin/python scripts/import_memories.py backup.json --no-relationships

    # Dry run (show what would be imported)
    ./venv/bin/python scripts/import_memories.py backup.json --dry-run
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from memory import MemoryManager
from memory.import_export import MemoryImporter


def load_config():
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def preview_import(input_file: Path) -> dict:
    """Preview what will be imported."""
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    metadata = data.get('metadata', {})
    memories = data.get('memories', [])
    relationships = data.get('relationships', [])
    audit_logs = data.get('audit_logs', [])

    return {
        'export_date': metadata.get('export_date', 'Unknown'),
        'version': metadata.get('version', 'Unknown'),
        'total_memories': len(memories),
        'total_relationships': len(relationships),
        'total_audit_logs': len(audit_logs),
        'by_type': {},
        'by_status': {}
    }


def main():
    """Run memory import."""
    parser = argparse.ArgumentParser(
        description='Import memories from JSON backup file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import from backup (skip existing)
  python scripts/import_memories.py backups/memories_2026-01-08.json

  # Overwrite existing memories
  python scripts/import_memories.py backups/memories.json --no-skip

  # Preview what would be imported
  python scripts/import_memories.py backups/memories.json --dry-run
        """
    )

    parser.add_argument(
        'input_file',
        type=str,
        help='Input JSON file path'
    )

    parser.add_argument(
        '--no-skip',
        action='store_true',
        help='Overwrite existing memories (default: skip existing)'
    )

    parser.add_argument(
        '--no-relationships',
        action='store_true',
        help='Do not restore memory relationships'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview import without making changes'
    )

    args = parser.parse_args()

    print("=" * 70)
    print(f"Memory Import - {datetime.now().isoformat()}")
    print("=" * 70)
    print()

    try:
        # Check input file exists
        input_file = Path(args.input_file)
        if not input_file.exists():
            print(f"❌ Input file not found: {args.input_file}")
            return 1

        # Preview import
        print("Reading import file...")
        preview = preview_import(input_file)

        print(f"\nBackup information:")
        print(f"  Export date: {preview['export_date']}")
        print(f"  Version: {preview['version']}")
        print(f"  Total memories: {preview['total_memories']}")
        print(f"  Total relationships: {preview['total_relationships']}")
        if preview['total_audit_logs'] > 0:
            print(f"  Total audit logs: {preview['total_audit_logs']}")

        # Dry run - just show preview
        if args.dry_run:
            print("\n" + "=" * 70)
            print("DRY RUN - No changes will be made")
            print("=" * 70)
            print()
            print("Run without --dry-run to perform import")
            return 0

        # Confirm import
        print(f"\nImport settings:")
        print(f"  Skip existing memories: {'No (overwrite)' if args.no_skip else 'Yes'}")
        print(f"  Restore relationships: {'No' if args.no_relationships else 'Yes'}")
        print()

        # Load configuration
        config = load_config()
        memory_config = config.get('memory', {})

        if not memory_config.get('enabled', False):
            print("❌ Memory system is disabled in config")
            print("   Enable memory.enabled in config/config.yaml")
            return 1

        print("✓ Configuration loaded")

        # Initialize Memory Manager
        memory_manager = MemoryManager(memory_config)
        print("✓ Memory Manager initialized")

        # Create importer
        importer = MemoryImporter(
            memory_manager.vector_store,
            memory_manager.metadata_store
        )

        # Run import
        print("\nImporting memories...")
        result = importer.import_all(
            input_path=args.input_file,
            skip_existing=not args.no_skip,
            restore_relationships=not args.no_relationships
        )

        # Print results
        print("\n" + "=" * 70)
        print("IMPORT COMPLETE")
        print("=" * 70)
        print()

        print(f"Total in file: {result['total_in_file']}")
        print(f"✓ Imported: {result['imported']}")
        print(f"⊘ Skipped (already exist): {result['skipped']}")
        if not args.no_relationships:
            print(f"✓ Relationships restored: {result['relationships_imported']}")

        if result['errors']:
            print(f"\n⚠️  Encountered {len(result['errors'])} errors:")
            for err in result['errors'][:5]:
                print(f"   - {err}")
            if len(result['errors']) > 5:
                print(f"   ... and {len(result['errors']) - 5} more")

        print("\n" + "=" * 70)

        return 0

    except Exception as e:
        print(f"\n❌ Error during import: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
