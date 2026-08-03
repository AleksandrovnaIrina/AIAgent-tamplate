# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""LumysAgent Telegram bot — Telegram <→ Claude (via claude-agent-sdk + MCP servers)."""

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

import sessions
import voice
from claude_runner import run_turn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("lumys.bot")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_IDS = {
    int(x.strip())
    for x in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
    if x.strip()
}

STREAM_EDIT_INTERVAL = 1.5
TG_MAX = 4000


def _allowed(update: Update) -> bool:
    chat_id = update.effective_chat.id if update.effective_chat else None
    return chat_id in ALLOWED_CHAT_IDS


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    await update.message.reply_text(
        "LumysAgent онлайн 🟢\n\n"
        "Я твій HR-асистент. Допомагаю з сорсингом, скрінінгом, аутрічем і трекінгом кандидатів.\n\n"
        "Напиши що потрібно зробити, або /new щоб почати нову сесію."
    )


async def cmd_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    sessions.clear_session(update.effective_chat.id)
    await update.message.reply_text("🔄 Нова сесія розпочата.")


async def _process_text(update: Update, text: str) -> None:
    """Run one Claude turn against `text`, streaming the reply into Telegram."""
    chat_id = update.effective_chat.id
    bot = update.get_bot()

    reply = await update.message.reply_text("…")

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
        result = await run_turn(
            prompt=text,
            resume_session_id=sessions.get_session_id(chat_id),
            on_text_delta=on_delta,
        )
    finally:
        typing_task.cancel()

    if result.session_id:
        sessions.save_session_id(chat_id, result.session_id)

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


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    user_text = (update.message.text or "").strip()
    if not user_text:
        return
    log.info("text from %s (%d chars)", update.effective_chat.id, len(user_text))
    await _process_text(update, user_text)


async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    if not voice.voice_enabled():
        await update.message.reply_text(
            "Голосові повідомлення вимкнені — встанови GROQ_API_KEY у .env щоб увімкнути."
        )
        return

    notice = await update.message.reply_text("🎙 Транскрибую…")
    try:
        tg_file = await update.message.voice.get_file()
        audio_bytes = bytes(await tg_file.download_as_bytearray())
        transcript = await voice.transcribe(audio_bytes)
    except Exception as e:
        log.exception("voice download/transcribe failed")
        await notice.edit_text(f"⚠️ Помилка голосу: {e}")
        return

    if not transcript:
        await notice.edit_text("⚠️ Не вдалося транскрибувати — спробуй ще раз або напиши текстом.")
        return

    await notice.edit_text(f"🎙 {transcript}")
    await _process_text(update, transcript)


def main() -> None:
    if not ALLOWED_CHAT_IDS:
        log.error("TELEGRAM_ALLOWED_CHAT_IDS is empty — bot would accept nobody. Exiting.")
        raise SystemExit(1)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    log.info("LumysAgent starting — allowed chats: %s", sorted(ALLOWED_CHAT_IDS))
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
