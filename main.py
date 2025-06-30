# main.py
import logging
import aiohttp
import asyncio
from datetime import datetime
from telegram.ext import Application, CommandHandler, ContextTypes

import config
import utils

# Настройка логирования
logging.basicConfig(
    filename="logs/bot.log",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    encoding="utf-8"
)

# Глобальные переменные
last_prices = {}
hourly_movers = []

# --- Команды ---
async def start(update, context):
    await update.message.reply_text("Привет! Я бот для отслеживания криптовалют.")

async def online(update, context):
    await update.message.reply_text("🟢 Бот работает!")

async def help_command(update, context):
    message = """
📖 <b>Доступные команды:</b>

/start — Приветствие
/online — Проверка работы бота
/help — Справка
/blacklist — Показать чёрный список монет

🔔 Уведомления о ценах:
- Отправляет уведомление, если цена изменилась на ≥1.5%
- Каждый час отправляет TOP 5 монет с наибольшими колебаниями цены

🔧 Черный список:
- Монеты без пары USDT игнорируются и добавляются в чёрный список
- Используйте /blacklist, чтобы просмотреть список
"""
    await update.message.reply_text(message, parse_mode='HTML')

async def blacklist_command(update, context):
    blacklist = utils.load_blacklist()
    if not blacklist:
        await update.message.reply_text("Чёрный список пуст.")
        return
    
    message = "🗑️ <b>Чёрный список монет:</b>\n\n"
    for symbol in blacklist:
        message += f"• <code>{symbol.upper()}</code>\n"
    
    await update.message.reply_text(message, parse_mode='HTML')

# --- Функция периодической проверки цен ---
async def check_price_changes(context: ContextTypes.DEFAULT_TYPE):
    global last_prices
    try:
        logging.info("Проверка цен на криптовалюты...")
        
        async with aiohttp.ClientSession() as session:
            coins = await utils.get_top_300_coins(session)
            valid_coins = await utils.filter_valid_coins(session, coins)
            
            current_movers = []
            for coin in valid_coins:
                symbol = coin["symbol"]
                current_price = await utils.get_price_change(session, symbol)

                if current_price == 0:
                    continue

                if symbol in last_prices:
                    change_percent = ((current_price - last_prices[symbol]) / last_prices[symbol]) * 100
                    current_movers.append({
                        "symbol": symbol,
                        "change": change_percent,
                        "timestamp": datetime.now().timestamp()
                    })

                    if abs(change_percent) >= config.PRICE_CHANGE_THRESHOLD:
                        direction = "📈 Рост" if change_percent > 0 else "📉 Падение"
                        message = utils.format_alert_message(
                            symbol.upper(),
                            direction,
                            round(abs(change_percent), 2)
                        )
                        await context.bot.send_message(
                            chat_id=config.TELEGRAM_CHAT_ID,
                            text=message,
                            parse_mode='HTML'
                        )
                
                last_prices[symbol] = current_price

            global hourly_movers
            hourly_movers.extend(current_movers)

    except Exception as e:
        logging.error(f"Ошибка при проверке цен: {e}")

# --- Функция генерации топа ---
async def generate_hourly_top(context: ContextTypes.DEFAULT_TYPE):
    global hourly_movers
    try:
        one_hour_ago = datetime.now().timestamp() - 60 * 60
        filtered_movers = [m for m in hourly_movers if m['timestamp'] >= one_hour_ago]
        
        if filtered_movers:
            top_message = utils.format_top_movers_message(filtered_movers)
            await context.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=top_message,
                parse_mode='HTML'
            )
        
        hourly_movers = []  # Очищаем для следующего часа

    except Exception as e:
        logging.error(f"Ошибка при формировании топа: {e}")

# --- Запуск бота ---
if __name__ == '__main__':
    from telegram.ext import Application

    if config.TELEGRAM_BOT_TOKEN.startswith("YOUR_TELEGRAM_"):
        raise ValueError("❌ Не забудьте заменить TELEGRAM_BOT_TOKEN в config.py на реальный токен!")

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Регистрация команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("online", online))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("blacklist", blacklist_command))

    # Регистрация задач
    job_queue = app.job_queue
    job_queue.run_repeating(check_price_changes, interval=config.CHECK_INTERVAL_MINUTES * 60, first=10)
    job_queue.run_repeating(generate_hourly_top, interval=config.HOURLY_INTERVAL_MINUTES * 60, first=60)

    logging.info("Бот запущен. Ожидание команд и проверка цен...")
    app.run_polling(drop_pending_updates=True)