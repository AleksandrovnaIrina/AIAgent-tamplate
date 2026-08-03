#!/usr/bin/env bash
# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
# Render crontab from SCOUT_CRON / ARGUS_ANALYSIS_CRON env vars.
set -euo pipefail

CRON="${SCOUT_CRON:-0 6 * * 1}"
# 10:00 Warsaw CEST = 08:00 UTC (summer). Override ARGUS_ANALYSIS_CRON in .env if needed.
ANALYSIS_CRON="${ARGUS_ANALYSIS_CRON:-0 8 * * 1}"
CRONTAB=/app/crontab.rendered

echo "${CRON} python /app/scout.py" > "${CRONTAB}"
echo "${ANALYSIS_CRON} python /app/argus_analysis.py" >> "${CRONTAB}"

echo "Scout — scrape: ${CRON} | analysis: ${ANALYSIS_CRON} (UTC)"

# Run trigger watcher in background
python /app/trigger_watcher.py &

exec supercronic -passthrough-logs "${CRONTAB}"
