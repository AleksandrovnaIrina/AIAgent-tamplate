#!/bin/sh
# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
set -e

CRON_EXPR="${SCOUT_CRON:-0 9 * * 1}"
echo "Scout entrypoint: cron='$CRON_EXPR'"

# Run immediately on first start if flag is set
if [ "${SCOUT_RUN_ON_START:-false}" = "true" ]; then
    echo "Running scout immediately..."
    python /app/scout.py
fi

# Parse cron expression (min hour * * weekday) and loop with sleep
# Simple approach: use supercronic if available, otherwise Python scheduler
exec python -u /app/cron_runner.py
