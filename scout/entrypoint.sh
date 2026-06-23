#!/bin/sh
set -e

CRON_EXPR="${SCOUT_CRON:-0 9 * * 1}"

echo "Scout entrypoint: cron='$CRON_EXPR'"

# Write crontab
echo "$CRON_EXPR cd /app && python scout.py >> /var/log/scout.log 2>&1" > /etc/crontabs/root

# Run immediately on first start if flag is set
if [ "${SCOUT_RUN_ON_START:-false}" = "true" ]; then
    echo "Running scout immediately..."
    python /app/scout.py
fi

# Start crond in foreground
exec crond -f -l 2
