#!/usr/bin/env bash
# Render crontab from SCOUT_CRON env, then run supercronic + trigger watcher.
set -euo pipefail

CRON="${SCOUT_CRON:-0 6 * * 1}"
CRONTAB=/app/crontab.rendered

echo "${CRON} python /app/scout.py" > "${CRONTAB}"

echo "Scout starting — schedule: ${CRON}"

# Run trigger watcher in background
python /app/trigger_watcher.py &

exec supercronic -passthrough-logs "${CRONTAB}"
