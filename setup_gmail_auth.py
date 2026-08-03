#!/usr/bin/env python3
# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Run this locally to get a fresh Google OAuth token, then upload to server."""
import json
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                          "google-auth-oauthlib", "google-auth"])
    from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

CLIENT_SECRET = Path("secrets/client_secret.json")
TOKEN_OUT = Path("secrets/google-token.json")

if not CLIENT_SECRET.exists():
    print(f"❌ Не знайдено: {CLIENT_SECRET}")
    print("Поклади client_secret.json у папку secrets/")
    sys.exit(1)

print("🌐 Відкриваю браузер для авторизації Google...")
flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
creds = flow.run_local_server(port=0)

TOKEN_OUT.write_text(creds.to_json())
TOKEN_OUT.chmod(0o600)
print(f"✅ Токен збережено: {TOKEN_OUT}")
print()
print("Тепер завантаж на сервер:")
print(f"  scp secrets/google-token.json root@68.183.12.200:/root/lumys-agent/secrets/")
print()
print("І перезапусти mcp-hr:")
print("  ssh root@68.183.12.200 'cd /root/lumys-agent && docker compose restart mcp-hr'")
