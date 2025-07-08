import asyncio
import aiohttp
import sys
import os

# Добавляем корневую папку в PYTHONPATH, если запускаем main.py напрямую
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import Router
from datetime import datetime

from config.config import TELEGRAM_BOT_TOKEN, CHAT_ID, CHECK_INTERVAL_MINUTES
from bot.services.binance import fetch_trading_pairs, get_crypto_price
from bot.services.notification import NotificationService
from bot.services.logger_service import LoggerService
from bot.utils.logger import setup_logger

logger = setup_logger()

notification_service = NotificationService()
logger_service = LoggerService()

# Создаем роутер
router = Router()

# Регистрация обработчика команд
def register_handlers(dp: Dispatcher):
    dp.include_router(router)

@router.message(Command("status"))
async def cmd_status(message: Message):
    """
    Обработчик команды /status
    Показывает состояние бота: доступность Binance и количество отслеживаемых монет
    """
    logger.info("Status command received.")

    # Проверка связи с Binance
    async with aiohttp.ClientSession() as session:
        test_symbol = "BTCUSDT"
        price = await get_crypto_price(session, test_symbol)
        if price is not None:
            binance_status = "✅ Доступна"
        else:
            binance_status = "❌ Недоступна"

    # Количество отслеживаемых монет
    tracked_coins_count = len(notification_service.tracked_prices)

    status_message = (
        "📊 *Статус бота*\n\n"
        f"🌐 Связь с Binance: {binance_status}\n"
        f"🪙 Отслеживаемых монет: *{tracked_coins_count}*\n"
    )

    await message.answer(status_message, parse_mode="Markdown")

@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Обработчик команды /help
    Выводит подробное описание работы бота
    """
    logger.info("Help command received.")
    
    help_text = (
        "📘 *Принцип работы бота*\n\n"
        "🤖 Этот бот автоматически отслеживает цены на криптовалюту на бирже Binance и отправляет уведомления "
        "о значительных изменениях цен. Бот работает без необходимости ручного добавления монет или подписки.\n\n"
        "📊 *Основные функции*:\n"
        "🔹 Отслеживание всех монет в паре с USDT\n"
        "🔹 Фильтрация по объему торгов (только монеты с объемом > $2,000,000 за 24 часа)\n"
        "🔹 Проверка цен каждые 15 минут\n"
        "🔹 Уведомления при изменении цены на 2% и более\n"
        "🔹 Подсчет количества уведомлений по каждой монете за сутки\n"
        "🔹 Ежедневная отправка логов в Telegram и их очистка\n\n"
        "📈 *Формат уведомлений*:\n"
        "Каждое уведомление содержит:\n"
        "- Направление изменения цены (Рост / Падение)\n"
        "- Символ монеты (например, BTCUSDT)\n"
        "- Процент изменения цены\n"
        "- Точное время уведомления\n"
        "- Количество уведомлений по этой монете за текущие сутки\n\n"
        "📌 Пример уведомления:\n"
        "```\n"
        "Рост цены на *BTCUSDT*\n"
        "Изменение: *+2.50%*\n"
        "Время: *2025-04-05 14:30:22*\n"
        "Количество уведомлений: *3*\n"
        "```\n\n"
        "🛠 *Доступные команды*:\n"
        "- `/status` — Показывает текущее состояние бота (доступность Binance и количество отслеживаемых монет)\n"
        "- `/help` — Выводит это сообщение\n\n"
        "🕒 *Ежедневные задачи*:\n"
        "- В полночь сбрасывается счетчик уведомлений по монетам\n"
        "- Логи бота отправляются в Telegram и файл очищается\n\n"
        "ℹ️ Бот работает автономно. Все монеты добавляются автоматически, подписка не требуется."
    )
    
    await message.answer(help_text, parse_mode="Markdown")

async def check_prices(bot: Bot):
    """Основной цикл проверки цен"""
    async with aiohttp.ClientSession() as session:
        while True:
            logger.info("Fetching USDT trading pairs...")
            symbols = await fetch_trading_pairs(session)

            logger.info(f"Checking prices for {len(symbols)} pairs...")
            for symbol in symbols:
                price = await get_crypto_price(session, symbol)
                if price is None:
                    continue
                change = notification_service.check_price_change(symbol, price)
                if change is not None and abs(change) >= 2:
                    await notification_service.send_notification(bot, symbol, change)
                notification_service.update_price(symbol, price)
            await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)

async def send_daily_logs(bot: Bot):
    """Отправка логов в чат и их очистка"""
    while True:
        await asyncio.sleep(86400)  # 24 часа
        logger.info("Sending daily logs to chat.")
        await logger_service.send_log_file(bot)

async def reset_notifications_count():
    """Сброс счетчика уведомлений в полночь"""
    while True:
        now = datetime.now()
        seconds_until_midnight = ((24 - now.hour - 1) * 3600 + (60 - now.minute - 1) * 60 + (60 - now.second))
        await asyncio.sleep(seconds_until_midnight)
        notification_service.notifications_count.clear()
        logger.info("Daily notification counters reset.")

async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    register_handlers(dp)

    asyncio.create_task(check_prices(bot))
    asyncio.create_task(send_daily_logs(bot))
    asyncio.create_task(reset_notifications_count())

    logger.info("Bot started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())