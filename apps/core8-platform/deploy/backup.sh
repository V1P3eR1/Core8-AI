#!/usr/bin/env bash
# Nightly backup of the SQLite DB + social media dir. Install: (crontab -l; echo "30 2 * * * /opt/core8/apps/core8-platform/deploy/backup.sh") | crontab -
set -euo pipefail
OUT=/opt/core8-backups; mkdir -p "$OUT"
STAMP=$(date +%F)
docker run --rm -v deploy_db_data:/data -v "$OUT":/out python:3.12-slim \
  python -c "import sqlite3;s=sqlite3.connect('/data/core8.db');d=sqlite3.connect('/out/core8-$STAMP.db');s.backup(d);d.close()"
docker run --rm -v deploy_db_data:/data -v "$OUT":/out alpine tar czf "/out/media-$STAMP.tgz" -C /data media-social 2>/dev/null || true
find "$OUT" -type f -mtime +14 -delete
echo "backup $STAMP ok"
