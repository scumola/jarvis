#!/bin/bash
# Weekly Full Memory Backup Script
#
# Backs up ALL Jarvis memories (including archived) with relationships.
# Keeps last 4 weeks of backups.
#
# Add to crontab (Sunday at 3 AM):
# 0 3 * * 0 /home/steve/AI/jarvis/scripts/weekly_backup.sh >> /home/steve/AI/jarvis/logs/backup.log 2>&1

JARVIS_DIR="/home/steve/AI/jarvis"
BACKUP_DIR="$JARVIS_DIR/backups/weekly"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Log start
echo "=================================================================="
echo "Weekly Full Memory Backup - $TIMESTAMP"
echo "=================================================================="
echo ""

# Change to Jarvis directory
cd "$JARVIS_DIR" || exit 1

# Run full export (all memories + audit logs)
./venv/bin/python scripts/export_memories.py \
    "$BACKUP_DIR/full_$DATE.json" \
    --all \
    --audit

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Full backup successful"

    # Delete backups older than 28 days (4 weeks)
    echo "Cleaning up old backups (older than 28 days)..."
    DELETED=$(find "$BACKUP_DIR" -name "full_*.json" -mtime +28 -delete -print | wc -l)
    echo "Deleted $DELETED old backup(s)"

    # Compress older backups (older than 7 days)
    echo "Compressing backups older than 7 days..."
    find "$BACKUP_DIR" -name "full_*.json" -mtime +7 ! -name "*.gz" -exec gzip {} \;
    echo "Compression complete"
else
    echo ""
    echo "✗ Full backup failed"
    exit 1
fi

echo ""
echo "=================================================================="
