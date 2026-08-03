# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Simple cron runner for Scout — no system crond needed."""
import logging
import os
import subprocess
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
log = logging.getLogger("scout.cron")

CRON = os.environ.get("SCOUT_CRON", "0 9 * * 1")

def parse_cron(expr: str):
    parts = expr.strip().split()
    return int(parts[0]), int(parts[1])  # minute, hour

def should_run(minute: int, hour: int) -> bool:
    now = datetime.utcnow()
    return now.hour == hour and now.minute == minute

def main():
    minute, hour = parse_cron(CRON)
    log.info("Cron runner started — will run scout at %02d:%02d UTC every Monday", hour, minute)

    if os.environ.get("SCOUT_RUN_ON_START", "false").lower() == "true":
        log.info("SCOUT_RUN_ON_START=true — running now")
        subprocess.run(["python", "/app/scout.py"], check=False)

    last_run_day = None
    while True:
        now = datetime.utcnow()
        if should_run(minute, hour) and now.weekday() == 0 and last_run_day != now.date():
            log.info("Running scheduled scout...")
            result = subprocess.run(["python", "/app/scout.py"], check=False)
            log.info("Scout exited with code %d", result.returncode)
            last_run_day = now.date()
        time.sleep(30)

if __name__ == "__main__":
    main()
