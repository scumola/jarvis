#!/usr/bin/env python3
"""
Memory Export Script

Export all memories to a JSON backup file.
Includes metadata, vector embeddings, relationships, and optionally audit logs.

Usage:
    # Export active memories only
    ./venv/bin/python scripts/export_memories.py backup.json

    # Export all memories (including archived)
    ./venv/bin/python scripts/export_memories.py backup.json --all

    # Include audit logs
    ./venv/bin/python scripts/export_memories.py backup.json --audit

    # Full backup with everything
    ./venv/bin/python scripts/export_memories.py backup.json --all --audit
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from memory import MemoryManager
from memory.import_export import MemoryExporter


def load_config():
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def format_bytes(size: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def main():
    """Run memory export."""
    parser = argparse.ArgumentParser(
        description='Export memories to JSON backup file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export active memories
  python scripts/export_memories.py backups/memories_2026-01-08.json

  # Full backup with archived memories and audit logs
  python scripts/export_memories.py backups/full_backup.json --all --audit

  # Quick backup (active memories only, no audit logs)
  python scripts/export_memories.py backups/quick_backup.json
        """
    )

    parser.add_argument(
        'output_file',
        type=str,
        help='Output JSON file path'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Include archived/superseded memories'
    )

    parser.add_argument(
        '--audit',
        action='store_true',
        help='Include audit logs (can make file large)'
    )

    parser.add_argument(
        '--no-relationships',
        action='store_true',
        help='Exclude memory relationships'
    )

    args = parser.parse_args()

    print("=" * 70)
    print(f"Memory Export - {datetime.now().isoformat()}")
    print("=" * 70)
    print()

    try:
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

        # Create exporter
        exporter = MemoryExporter(
            memory_manager.vector_store,
            memory_manager.metadata_store
        )

        # Get statistics before export
        stats = memory_manager.get_statistics()
        print(f"\nMemory statistics:")
        print(f"  Total active memories: {stats.get('total_memories', 0)}")
        print(f"  Average decay score: {stats.get('avg_decay_score', 0):.1f}")

        print(f"\nExport settings:")
        print(f"  Include archived: {'Yes' if args.all else 'No'}")
        print(f"  Include relationships: {'No' if args.no_relationships else 'Yes'}")
        print(f"  Include audit logs: {'Yes' if args.audit else 'No'}")
        print()

        # Run export
        print("Exporting memories...")
        result = exporter.export_all(
            output_path=args.output_file,
            include_archived=args.all,
            include_relationships=not args.no_relationships,
            include_audit_log=args.audit
        )

        # Print results
        print("\n" + "=" * 70)
        print("EXPORT COMPLETE")
        print("=" * 70)
        print()

        print(f"✓ Exported {result['memories_exported']} memories")
        if not args.no_relationships:
            print(f"✓ Exported {result['relationships_exported']} relationships")
        if args.audit:
            print(f"✓ Exported {result['audit_logs_exported']} audit log entries")

        print()
        print(f"Output file: {result['file_path']}")
        print(f"File size: {format_bytes(result['file_size_bytes'])}")

        print("\n" + "=" * 70)

        return 0

    except Exception as e:
        print(f"\n❌ Error during export: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
