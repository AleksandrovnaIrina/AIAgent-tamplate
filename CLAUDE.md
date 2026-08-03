# LumysAgent

> © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — see [LICENSE](LICENSE) / [NOTICE](NOTICE). Not for redistribution or reuse without permission.

Персональний AI-агент для HR і рекрутингу. Telegram-бот на базі Claude Agent SDK.

## Можливості

- **Сорсинг:** Boolean і X-Ray пошук (LinkedIn, Djinni, DOU, GitHub)
- **Скрінінг:** аналіз резюме та LinkedIn-профілів за ICP-методологією
- **Аутріч:** персоналізовані повідомлення для LinkedIn, Email, Telegram
- **Трекінг:** Google Sheets, статуси кандидатів, нотатки
- **Організація:** Google Calendar, Gmail, нагадування
- **Auto-Scout:** щотижневий дайджест нових кандидатів з Djinni, DOU, LinkedIn

## Швидкий старт

```bash
git clone https://github.com/YOUR_USERNAME/lumys-agent
cd lumys-agent
chmod +x setup.sh && ./setup.sh
```

## Архітектура

```
Telegram → telegram-bot (Claude Agent SDK)
                ├── mcp-memory (PostgreSQL, port 3100)
                └── mcp-hr (HR tools, port 3200)
                         ├── Google Sheets / Calendar / Gmail
                         ├── Brave Search (web_search)
                         └── Telegram sender

scout (cron) → Djinni + DOU + LinkedIn X-Ray → Telegram digest
```

## Команди в Telegram

- `/start` — привітання
- `/new` — нова сесія (очистити контекст)
- Голосові повідомлення — транскрибуються через Groq Whisper

## Структура

```
lumys-agent/
├── telegram-bot/    # Telegram бот + Claude runner
├── mcp-memory/      # MCP сервер пам'яті (PostgreSQL)
├── mcp-hr/          # MCP сервер HR-інструментів
├── scout/           # Авто-скаут кандидатів
├── postgres/        # Схема БД
├── vacancies.yml    # Вакансії для скауту
└── docker-compose.yml
```
