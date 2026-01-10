#!/usr/bin/env python3
"""
Memory Consolidation Script

Analyzes memories for duplicates, similar memories, and supporting relationships.
Can run in analysis-only mode or auto-consolidate mode.

Usage:
    # Analysis only (report)
    ./venv/bin/python scripts/consolidate_memories.py --report

    # Auto-consolidate duplicates
    ./venv/bin/python scripts/consolidate_memories.py --auto

    # Auto-consolidate with boosting
    ./venv/bin/python scripts/consolidate_memories.py --auto --boost
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from memory import MemoryManager
from memory.consolidation import MemoryConsolidator, auto_consolidate


def load_config():
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Run memory consolidation."""
    parser = argparse.ArgumentParser(
        description='Memory Consolidation Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate consolidation report
  python scripts/consolidate_memories.py --report

  # Auto-merge duplicates only
  python scripts/consolidate_memories.py --auto

  # Auto-merge duplicates and boost supporting memories
  python scripts/consolidate_memories.py --auto --boost

  # Save report to file
  python scripts/consolidate_memories.py --report --output report.txt
        """
    )

    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate consolidation report (analysis only)'
    )

    parser.add_argument(
        '--auto',
        action='store_true',
        help='Automatically consolidate memories'
    )

    parser.add_argument(
        '--boost',
        action='store_true',
        help='Boost confidence for supporting memories (use with --auto)'
    )

    parser.add_argument(
        '--output',
        '-o',
        type=str,
        help='Save report to file (use with --report)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.report and not args.auto:
        parser.error("Must specify either --report or --auto")

    if args.boost and not args.auto:
        parser.error("--boost can only be used with --auto")

    print("=" * 70)
    print(f"Memory Consolidation - {datetime.now().isoformat()}")
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

        # Get statistics
        stats = memory_manager.get_statistics()
        print(f"\nActive memories: {stats.get('total_memories', 0)}")
        print()

        if args.report:
            # Generate report
            print("Running consolidation analysis...")
            consolidator = MemoryConsolidator(
                memory_manager.vector_store,
                memory_manager.metadata_store
            )

            analysis = consolidator.analyze_all_memories()
            report = consolidator.generate_consolidation_report(analysis)

            # Print report
            print(report)

            # Save to file if requested
            if args.output:
                output_path = Path(args.output)
                output_path.write_text(report)
                print(f"\n✓ Report saved to {args.output}")

        elif args.auto:
            # Auto-consolidate
            print("Running auto-consolidation...")
            print(f"  Merge duplicates: Yes")
            print(f"  Boost supporting: {'Yes' if args.boost else 'No'}")
            print()

            results = auto_consolidate(
                vector_store=memory_manager.vector_store,
                metadata_store=memory_manager.metadata_store,
                merge_duplicates=True,
                boost_supporting=args.boost
            )

            # Print results
            print("\n" + "=" * 70)
            print("CONSOLIDATION RESULTS")
            print("=" * 70)
            print()

            stats = results['analysis']['statistics']
            print(f"Total memories analyzed: {stats['total_memories']}")
            print(f"Duplicate groups found: {stats['duplicate_groups']}")
            print(f"Similar groups found: {stats['similar_groups']}")
            print(f"Supporting pairs found: {stats['supporting_pairs']}")
            print()

            print(f"✓ Merged {results['merged_groups']} duplicate groups")
            if args.boost:
                print(f"✓ Boosted {results['boosted_pairs']} supporting pairs")

            if results['errors']:
                print(f"\n⚠️  Encountered {len(results['errors'])} errors:")
                for err in results['errors'][:5]:
                    print(f"   - {err}")

        print("\n" + "=" * 70)
        print("✓ Consolidation complete")
        print("=" * 70)

        return 0

    except Exception as e:
        print(f"\n❌ Error during consolidation: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
