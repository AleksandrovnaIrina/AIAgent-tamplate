"""LumysAgent Orchestrator — single Telegram entry point that routes to specialized agents."""

import asyncio
import logging
import os
import time

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import files
import sessions
import voice
from router import classify, AgentName
from agents.argus.runner import run_turn as argus_turn
from agents.scout.runner import run_turn as scout_turn
from agents.sirius.runner import run_turn as sirius_turn
from agents.lumys.runner import run_turn as lumys_turn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("lumys.orchestrator")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_IDS = {
    int(x.strip())
    for x in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
    if x.strip()
}

STREAM_EDIT_INTERVAL = 1.5
TG_MAX = 4000

_AGENT_RUNNERS = {
    "argus": argus_turn,
    "scout": scout_turn,
    "sirius": sirius_turn,
    "lumys": lumys_turn,
}

_AGENT_LABELS = {
    "argus": "🔍 Argus",
    "scout": "👥 Scout",
    "sirius": "✍️ Sirius",
    "lumys": "🤖 Lumys",
}


def _allowed(update: Update) -> bool:
    chat_id = update.effective_chat.id if update.effective_chat else None
    return chat_id in ALLOWED_CHAT_IDS


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    await update.message.reply_text(
        "LumysAgent онлайн 🟢\n\n"
        "Я оркестратор — автоматично перенаправляю твій запит до потрібного агента:\n\n"
        "👥 *Scout* — HR: сорсинг, скрінінг, аутріч, Boolean/X-Ray\n"
        "🔍 *Argus* — Instagram: моніторинг конкурентів, caption, каруселі\n"
        "✍️ *Sirius* — Контент: LinkedIn пости, PDF, банери, Notion\n"
        "🤖 *Lumys* — Загальне: пам'ять, нагадування, Gmail, Calendar\n\n"
        "Просто пиши — визначу хто потрібен автоматично.\n"
        "/new — нова сесія",
        parse_mode="Markdown",
    )


async def cmd_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    sessions.clear_session(update.effective_chat.id)
    await update.message.reply_text("🔄 Нова сесія розпочата.")


async def cmd_agent(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show which agent handled the last message."""
    if not _allowed(update):
        return
    _, last_agent = sessions.get_session(update.effective_chat.id)
    label = _AGENT_LABELS.get(last_agent or "lumys", "🤖 Lumys")
    await update.message.reply_text(f"Останній агент: {label}")


async def cmd_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    await _process_text(update, "Зроби самарі нових листів у Gmail")


async def cmd_digest(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    role = " ".join(ctx.args) if ctx.args else ""
    query = f"Знайди кандидатів на Djinni і DOU{' на роль ' + role if role else ''}"
    await _process_text(update, query)


async def cmd_tgsearch(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    keywords = " ".join(ctx.args) if ctx.args else ""
    if not keywords:
        await update.message.reply_text("Використання: /tgsearch <ключові слова>")
        return
    await _process_text(update, f"Пошук в Telegram-каналах: {keywords}")


async def _process_text(update: Update, text: str) -> None:
    chat_id = update.effective_chat.id
    bot = update.get_bot()

    _, last_agent = sessions.get_session(chat_id)

    # Classify intent (fast keyword lookup → LLM fallback)
    agent: AgentName = await classify(text, last_agent)

    # Get this agent's own session (preserves context per agent)
    session_id, _ = sessions.get_session(chat_id, agent)
    runner = _AGENT_RUNNERS[agent]
    label = _AGENT_LABELS[agent]

    reply = await update.message.reply_text(f"{label} думає…")

    state = {"buffer": "", "last_edit": 0.0}
    edit_lock = asyncio.Lock()

    async def _flush() -> None:
        text_to_show = state["buffer"][:TG_MAX] or "…"
        try:
            await reply.edit_text(text_to_show)
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                log.debug("edit_text failed: %s", e)

    async def on_delta(chunk: str) -> None:
        state["buffer"] += chunk
        now = time.monotonic()
        if now - state["last_edit"] >= STREAM_EDIT_INTERVAL:
            state["last_edit"] = now
            async with edit_lock:
                await _flush()

    async def _typing_loop() -> None:
        while True:
            try:
                await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception:
                pass
            await asyncio.sleep(4)

    typing_task = asyncio.create_task(_typing_loop())

    try:
        result = await runner(
            prompt=text,
            resume_session_id=session_id,
            on_text_delta=on_delta,
        )
    finally:
        typing_task.cancel()

    if result.session_id:
        sessions.save_session(chat_id, result.session_id, agent)

    final_text = result.content.strip() or "(немає відповіді)"
    try:
        if len(final_text) <= TG_MAX:
            await reply.edit_text(final_text)
        else:
            await reply.edit_text(final_text[:TG_MAX])
            for i in range(TG_MAX, len(final_text), TG_MAX):
                await update.message.reply_text(final_text[i : i + TG_MAX])
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            log.warning("final edit failed: %s", e)

    log.info("chat=%s agent=%s len=%d", chat_id, agent, len(final_text))


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    user_text = (update.message.text or "").strip()
    if not user_text:
        return
    await _process_text(update, user_text)


async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    if not voice.voice_enabled():
        await update.message.reply_text(
            "Голосові повідомлення вимкнені — встанови GROQ_API_KEY у .env"
        )
        return
    notice = await update.message.reply_text("🎙 Транскрибую…")
    try:
        tg_file = await update.message.voice.get_file()
        audio_bytes = bytes(await tg_file.download_as_bytearray())
        transcript = await voice.transcribe(audio_bytes)
    except Exception as e:
        await notice.edit_text(f"⚠️ Помилка голосу: {e}")
        return
    if not transcript:
        await notice.edit_text("⚠️ Не вдалося транскрибувати — спробуй ще раз.")
        return
    await notice.edit_text(f"🎙 {transcript}")
    await _process_text(update, transcript)


async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    doc = update.message.document or update.message.audio
    if not doc:
        return
    filename = getattr(doc, "file_name", None) or "file"
    if not files.is_supported(filename):
        await update.message.reply_text(
            f"⚠️ Формат не підтримується: `{filename}`\n"
            "Підтримую: PDF, XLSX, DOCX, MP3, M4A, OGG, WAV",
            parse_mode="Markdown",
        )
        return

    caption = (update.message.caption or "").strip()
    notice = await update.message.reply_text("📎 Читаю файл…")
    try:
        tg_file = await doc.get_file()
        file_bytes = bytes(await tg_file.download_as_bytearray())
        extracted = await files.extract(file_bytes, filename)
    except Exception as e:
        await notice.edit_text(f"⚠️ Не вдалося прочитати файл: {e}")
        return

    prompt = f"{extracted}\n\n{caption}" if caption else extracted
    await notice.edit_text(f"📎 Файл прочитано: `{filename}`", parse_mode="Markdown")
    await _process_text(update, prompt)


def main() -> None:
    if not ALLOWED_CHAT_IDS:
        log.error("TELEGRAM_ALLOWED_CHAT_IDS is empty. Exiting.")
        raise SystemExit(1)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("agent", cmd_agent))
    app.add_handler(CommandHandler("email", cmd_email))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(CommandHandler("tgsearch", cmd_tgsearch))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.AUDIO, on_document))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    log.info("LumysAgent Orchestrator starting — chats: %s", sorted(ALLOWED_CHAT_IDS))
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
