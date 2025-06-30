# main.py
import logging
import asyncio
from datetime import datetime, timezone
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from handlers import start, online, help_command, blacklist_command, status_command
import utils

# --- Логгер ---
logger = logging.getLogger(__name__)
logger.info("Бот запущен")

# Глобальные переменные
last_prices = {}
hourly_movers = []
last_check_time = None

# --- Запуск бота ---
if __name__ == '__main__':
    from telegram.ext import Application, ContextTypes

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Регистрация команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("online", online))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("blacklist", blacklist_command))
    app.add_handler(CommandHandler("status", status_command))

    # Регистрация задач
    job_queue = app.job_queue
    job_queue.run_repeating(utils.check_price_changes, interval=config.CHECK_INTERVAL_MINUTES * 60, first=10)
    job_queue.run_repeating(utils.generate_hourly_top, interval=config.HOURLY_INTERVAL_MINUTES * 60, first=60)

    # Логирование запуска
    logger = logging.getLogger(__name__)
    logger.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)