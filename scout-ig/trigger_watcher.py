# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Polls bot_settings for scout_trigger=run every 30s and launches scout.py when set."""
import logging
import os
import subprocess
import time

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s watcher — %(message)s")
log = logging.getLogger("watcher")

DATABASE_URL = os.environ["DATABASE_URL"]


def check_and_run() -> None:
    try:
        with psycopg.connect(DATABASE_URL, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT value FROM bot_settings WHERE key = 'scout_trigger'")
            row = cur.fetchone()
            if row and row[0] == "run":
                cur.execute(
                    "UPDATE bot_settings SET value = 'running' WHERE key = 'scout_trigger'"
                )
                log.info("trigger detected — launching scout.py")
                proc = subprocess.Popen(
                    ["python", "/app/scout.py", "--run-now"],
                    stdout=open("/tmp/scout.log", "w"),
                    stderr=subprocess.STDOUT,
                )
                log.info("scout PID %d started", proc.pid)
                proc.wait()
                log.info("scout finished (exit %d)", proc.returncode)
                cur.execute(
                    "UPDATE bot_settings SET value = 'idle' WHERE key = 'scout_trigger'"
                )
    except Exception as e:
        log.error("watcher error: %s", e)


if __name__ == "__main__":
    log.info("trigger watcher started — polling every 30s")
    while True:
        check_and_run()
        time.sleep(30)
