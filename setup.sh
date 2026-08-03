#!/bin/bash
# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════╗"
echo "║     LumysAgent — Setup Wizard        ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"

if [ -f .env ]; then
    echo -e "${YELLOW}⚠️  .env already exists. Overwrite? [y/N]${NC}"
    read -r overwrite
    if [[ "$overwrite" != "y" && "$overwrite" != "Y" ]]; then
        echo "Keeping existing .env. Skipping to Docker launch."
        docker compose up -d
        exit 0
    fi
fi

echo ""
echo -e "${BOLD}── Обов'язкові налаштування ────────────${NC}"

read -rp "PostgreSQL пароль (придумай складний): " POSTGRES_PASSWORD
read -rp "Telegram Bot Token (@BotFather): " TELEGRAM_BOT_TOKEN
read -rp "Твій Telegram Chat ID (@userinfobot): " TELEGRAM_ALLOWED_CHAT_IDS
TELEGRAM_DIGEST_CHAT_ID="$TELEGRAM_ALLOWED_CHAT_IDS"
read -rp "Claude OAuth Token (claude.ai → Settings → API): " CLAUDE_CODE_OAUTH_TOKEN

echo ""
echo -e "${BOLD}── Scout (можна пропустити — натисни Enter) ──${NC}"

read -rp "Apify Token (для Djinni/DOU скрапінгу): " APIFY_TOKEN
read -rp "Brave Search API Key (для LinkedIn X-Ray): " BRAVE_API_KEY

echo ""
echo -e "${BOLD}── Google Workspace (опціонально) ─────${NC}"

read -rp "Google Service Account JSON (Enter щоб пропустити): " GOOGLE_CREDENTIALS_JSON
read -rp "Google Sheets ID (Enter щоб пропустити): " GOOGLE_SHEET_ID
read -rp "Google Calendar ID (Enter щоб пропустити): " GOOGLE_CALENDAR_ID

echo ""
echo -e "${BOLD}── Голос (опціонально) ─────────────────${NC}"
read -rp "Groq API Key (Enter щоб пропустити): " GROQ_API_KEY

# Write .env
cat > .env <<EOF
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_ALLOWED_CHAT_IDS=${TELEGRAM_ALLOWED_CHAT_IDS}
TELEGRAM_DIGEST_CHAT_ID=${TELEGRAM_DIGEST_CHAT_ID}

CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}

APIFY_TOKEN=${APIFY_TOKEN}
BRAVE_API_KEY=${BRAVE_API_KEY}

GOOGLE_CREDENTIALS_JSON=${GOOGLE_CREDENTIALS_JSON}
GOOGLE_SHEET_ID=${GOOGLE_SHEET_ID}
GOOGLE_CALENDAR_ID=${GOOGLE_CALENDAR_ID}

GROQ_API_KEY=${GROQ_API_KEY}

CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_TURNS=20
SCOUT_CRON=0 9 * * 1
SCOUT_RUN_ON_START=false
EOF

echo -e "\n${GREEN}✅ .env створено${NC}"

echo ""
echo -e "${BOLD}── Налаштування вакансій ───────────────${NC}"
echo "Відкрий vacancies.yml і додай свої вакансії, або залиш приклад."
echo ""

echo -e "${BOLD}── Запуск Docker ───────────────────────${NC}"
docker compose up -d --build

echo ""
echo -e "${GREEN}${BOLD}✅ LumysAgent запущено!${NC}"
echo ""
echo "Перевір логи:       docker compose logs -f telegram-bot"
echo "Запустити скаут:    docker compose run scout"
echo "Зупинити:           docker compose down"
echo ""
echo -e "${CYAN}Напиши /start у Telegram — бот має відповісти 🟢${NC}"
