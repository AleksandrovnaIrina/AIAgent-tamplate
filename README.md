# LumysAgent

Персональний AI-агент для HR і рекрутингу. Telegram-бот на базі Claude Agent SDK з 4 спеціалізованими агентами.

> © 2026 Iryna Subbotina ([@IrynaS_HR](https://t.me/IrynaS_HR)). All Rights Reserved. Публічна видимість репозиторію — лише для портфоліо/демонстрації, це **не** ліцензія на використання. Копіювання, розповсюдження, присвоєння авторства чи комерційне використання без письмового дозволу заборонено. Деталі — у [LICENSE](LICENSE) та [NOTICE](NOTICE).

## Агенти

| Агент | Що робить |
|-------|-----------|
| **Scout** | Сорсинг кандидатів — Boolean/X-Ray пошук, LinkedIn, Djinni, DOU, аналіз резюме |
| **Argus** | Аналіз конкурентів — моніторинг Instagram Reels конкурентів, тижневий дайджест |
| **Sirius** | Контент і комунікація — аутріч-повідомлення, пости, LinkedIn-повідомлення, Notion |
| **Lumys** | Організація — Gmail, Google Calendar, нагадування, загальні питання |

### Команди в Telegram

```
/scout  — перейти до агента сорсингу
/argus  — перейти до агента моніторингу конкурентів
/sirius — перейти до агента контенту
/lumys  — перейти до загального агента
/post   — створити пост
/find   — знайти кандидатів
/1on1   — підготувати 1:1
/new    — очистити контекст, нова сесія
```

Голосові повідомлення транскрибуються автоматично (Groq Whisper).

---

## Архітектура

```
Telegram
  └── orchestrator (router + Claude Agent SDK)
        ├── mcp-memory  :3100  — PostgreSQL пам'ять
        ├── mcp-hr      :3200  — Calendar / Gmail / Sheets / Reminders / Brave Search
        ├── mcp-scout   :3400  — Sourcing tools / Djinni / LinkedIn X-Ray
        ├── mcp-argus   :3500  — Instagram competitor tools
        └── mcp-sirius  :3600  — Notion / Drive / Content tools

scout-hr  (cron) — щотижневий скаут кандидатів Djinni/DOU/LinkedIn
scout-ig  (cron) — щотижневий скрапінг Instagram Reels + аналіз конкурентів (Argus)
```

---

## Вимоги

- **Сервер:** Ubuntu 22.04+, мінімум 2 GB RAM (Digital Ocean Basic $12/mo достатньо)
- **Docker** + **Docker Compose** v2
- **Аккаунти:** Telegram Bot, Claude API (claude.ai), Apify, Groq

---

## Встановлення

### 1. Клонуй репозиторій

```bash
git clone https://github.com/aleksandrovnairina/lumys-agent.git
cd lumys-agent
```

### 2. Налаштуй змінні оточення

```bash
cp .env.example .env
nano .env
```

Заповни всі необхідні змінні (детальніше нижче).

### 3. Налаштуй Google (обов'язково для Sheets/Calendar/Gmail)

**Service Account** (для Sheets/Calendar без входу):
1. [console.cloud.google.com](https://console.cloud.google.com) → IAM → Service Accounts → Create
2. Ролі: Editor або конкретні (Sheets, Calendar)
3. Ключ → JSON → зберегти як `secrets/google_credentials.json`
4. Поділися таблицями з email сервіс-акаунту

**OAuth** (для Gmail і Sheets у mcp-scout/mcp-sirius):
```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
python setup_gmail_auth.py
```
Скрипт відкриє браузер → авторизуй → збереже `secrets/google-token.json`

### 4. Налаштуй список конкурентів (для Argus)

```bash
cp competitors.yml.example competitors.yml
nano competitors.yml  # додай Instagram-хендли конкурентів
```

### 5. Запусти

```bash
docker compose up -d
```

Перевірити логи:
```bash
docker compose logs -f orchestrator
docker compose logs -f scout-ig
```

---

## Змінні оточення

### Обов'язкові

| Змінна | Де взяти |
|--------|----------|
| `POSTGRES_PASSWORD` | Придумай складний пароль |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_ALLOWED_CHAT_IDS` | [@userinfobot](https://t.me/userinfobot) → твій Chat ID |
| `TELEGRAM_DIGEST_CHAT_ID` | Зазвичай той самий Chat ID |
| `CLAUDE_CODE_OAUTH_TOKEN` | [claude.ai](https://claude.ai) → Settings → API Keys |

### Scout (кандидати)

| Змінна | Де взяти |
|--------|----------|
| `APIFY_TOKEN` | [apify.com](https://apify.com) → Account → Integrations |
| `BRAVE_API_KEY` | [brave.com/search/api](https://brave.com/search/api) |
| `CANDIDATE_SHEET_ID` | ID Google Таблиці для кандидатів (з URL) |
| `RESEARCH_SHEET_ID` | ID Google Таблиці для досліджень |

### Google Workspace

| Змінна | Де взяти |
|--------|----------|
| `GOOGLE_CREDENTIALS_JSON` | Вміст `secrets/google_credentials.json` (Service Account) |
| `GOOGLE_SHEET_ID` | ID основної Google Таблиці |
| `GOOGLE_CALENDAR_ID` | ID Google Календаря |

### Argus (конкуренти)

| Змінна | Де взяти |
|--------|----------|
| `ARGUS_SHEET_ID` | ID Google Таблиці для аналізу конкурентів |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |

### Sirius (контент)

| Змінна | Де взяти |
|--------|----------|
| `NOTION_TOKEN` | [notion.so/my-integrations](https://notion.so/my-integrations) |
| `NOTION_DATABASE_ID` | ID Notion бази даних (з URL) |
| `SIRIUS_DRIVE_FOLDER_ID` | ID папки Google Drive |

### Голос

| Змінна | Де взяти |
|--------|----------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → API Keys |

### Cron розклад (опціонально)

| Змінна | За замовчуванням | Що робить |
|--------|-----------------|-----------|
| `SCOUT_CRON` | `0 9 * * 1` | HR Scout — щопонеділка о 9:00 |
| `IG_SCOUT_CRON` | `0 6 * * 1` | Instagram Scout — щопонеділка о 6:00 |
| `ARGUS_ANALYSIS_CRON` | `0 8 * * 1` | Аналіз конкурентів — щопонеділка о 8:00 |

---

## Секрети (папка `secrets/`)

Папка `secrets/` не потрапляє в git. Помісти туди:

```
secrets/
├── google_credentials.json   # Service Account (для mcp-hr, mcp-argus)
├── client_secret.json        # OAuth client (для setup_gmail_auth.py)
└── google-token.json         # OAuth token (генерується автоматично)
```

---

## Корисні команди

```bash
# Перезапустити один сервіс
docker compose restart orchestrator

# Подивитись логи
docker compose logs -f scout-ig

# Запустити Instagram Scout вручну
docker compose exec scout-ig python /app/scout.py

# Запустити аналіз конкурентів вручну
docker compose exec scout-ig python /app/argus_analysis.py

# Запустити HR Scout вручну
docker compose run --rm scout-hr python scout.py

# Підключитись до БД
docker compose exec postgres psql -U lumys -d lumys

# Перевірити кількість постів конкурентів
docker compose exec postgres psql -U lumys -d lumys -c \
  "SELECT competitor_handle, COUNT(*) FROM scout_posts GROUP BY 1 ORDER BY 2 DESC"

# Перезапустити все
docker compose down && docker compose up -d
```

---

## Структура

```
lumys-agent/
├── orchestrator/        # Telegram бот + router + Claude runner
├── agents/              # Системні промпти для кожного агента
│   ├── scout/
│   ├── argus/
│   ├── sirius/
│   └── lumys/
├── mcp-memory/          # MCP сервер пам'яті (PostgreSQL)
├── mcp-hr/              # MCP: Calendar / Gmail / Sheets / Reminders
├── mcp-scout/           # MCP: Djinni / LinkedIn / резюме
├── mcp-argus/           # MCP: Instagram competitor tools
├── mcp-sirius/          # MCP: Notion / Drive / Content
├── scout/               # HR Scout cron (Djinni, DOU, LinkedIn X-Ray)
├── scout-ig/            # Instagram Scout cron + Argus аналіз
├── postgres/            # init.sql — схема БД
├── secrets/             # Ключі (не в git)
├── competitors.yml      # Список конкурентів (не в git)
├── competitors.yml.example
├── vacancies.yml        # Активні вакансії для HR Scout
├── docker-compose.yml
├── .env.example
└── setup_gmail_auth.py  # Скрипт OAuth авторизації Gmail
```

---

## Ліцензія

**Proprietary — All Rights Reserved.** Не MIT, не open source. Повні умови — у файлах [LICENSE](LICENSE) та [NOTICE](NOTICE). Публікація коду в публічному репозиторії зроблена для демонстрації і не є наданням прав на використання.
