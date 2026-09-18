"""Entrypoint for Telegram Video Line Separator Bot."""

import logging
import sys
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot.config import config
from bot.handlers import (
    handle_help,
    handle_incoming_message,
    handle_start,
    handle_status,
    handle_style,
    handle_update,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, config.log_level, logging.INFO),
)
logger = logging.getLogger("bot")


def main() -> None:
    """Initialize and run the Telegram bot."""
    if not config.bot_token or "ABCdefGh" in config.bot_token:
        logger.error(
            "CRITICAL: BOT_TOKEN is not configured! Please provide a valid Telegram bot token "
            "in your .env file or environment variables."
        )
        sys.exit(1)

    logger.info("Initializing Telegram Video Line Separator Bot...")
    logger.info(f"Bot Mode: {config.bot_mode}")
    logger.info(f"Default Style: {config.separator_style}")
    logger.info(f"Whitelisted Chats: {list(config.allowed_chat_ids) if config.allowed_chat_ids else 'All'}")

    # Build Telegram Bot application
    app = ApplicationBuilder().token(config.bot_token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("style", handle_style))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("update", handle_update))

    # Catch all non-command messages to handle videos and update chat timeline state
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_incoming_message))

    logger.info("Starting bot polling... Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
