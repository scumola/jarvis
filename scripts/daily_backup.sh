#!/bin/bash
# Daily Memory Backup Script
#
# Backs up active Jarvis memories to a dated JSON file.
# Keeps last 7 days of backups, deletes older ones.
#
# Add to crontab:
# 0 2 * * * /home/steve/AI/jarvis/scripts/daily_backup.sh >> /home/steve/AI/jarvis/logs/backup.log 2>&1

JARVIS_DIR="/home/steve/AI/jarvis"
BACKUP_DIR="$JARVIS_DIR/backups/daily"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Log start
echo "=================================================================="
echo "Daily Memory Backup - $TIMESTAMP"
echo "=================================================================="
echo ""

# Change to Jarvis directory
cd "$JARVIS_DIR" || exit 1

# Run export
./venv/bin/python scripts/export_memories.py "$BACKUP_DIR/daily_$DATE.json"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Backup successful"

    # Delete backups older than 7 days
    echo "Cleaning up old backups (older than 7 days)..."
    DELETED=$(find "$BACKUP_DIR" -name "daily_*.json" -mtime +7 -delete -print | wc -l)
    echo "Deleted $DELETED old backup(s)"
else
    echo ""
    echo "✗ Backup failed"
    exit 1
fi

echo ""
echo "=================================================================="
