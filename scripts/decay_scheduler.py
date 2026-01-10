#!/usr/bin/env python3
"""
Memory Decay Scheduler

This script should be run periodically (e.g., daily via cron) to update
decay scores for all active memories and archive those that have decayed
below the threshold.

Add to crontab:
    0 2 * * * cd /home/steve/AI/jarvis && ./venv/bin/python scripts/decay_scheduler.py >> logs/decay.log 2>&1
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from memory import MemoryManager

def load_config():
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Run memory decay update."""
    print("="*70)
    print(f"Memory Decay Scheduler - {datetime.now().isoformat()}")
    print("="*70)

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

        # Get current statistics before decay
        stats_before = memory_manager.get_statistics()
        print(f"\nBefore decay update:")
        print(f"  Total active memories: {stats_before.get('total_memories', 0)}")
        print(f"  Average decay score: {stats_before.get('avg_decay_score', 0)}")
        print(f"  By type: {stats_before.get('by_type', {})}")

        # Run decay update
        print("\nRunning decay calculation...")
        updated_count = memory_manager.decay_memories()

        # Get statistics after decay
        stats_after = memory_manager.get_statistics()
        print(f"\nAfter decay update:")
        print(f"  Total active memories: {stats_after.get('total_memories', 0)}")
        print(f"  Average decay score: {stats_after.get('avg_decay_score', 0)}")
        print(f"  Memories updated: {updated_count}")

        # Calculate changes
        archived = stats_before.get('total_memories', 0) - stats_after.get('total_memories', 0)
        if archived > 0:
            print(f"  Memories archived: {archived}")

        print("\n" + "="*70)
        print("✓ Decay update completed successfully")
        print("="*70)

        return 0

    except Exception as e:
        print(f"\n❌ Error during decay update: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
