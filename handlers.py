# handlers.py
import config
import utils
from datetime import datetime, timezone
import logging
import pytz

logger = logging.getLogger(__name__)

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
/status — Статус бота
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

async def status_command(update, context):
    """Показывает текущее состояние бота"""
    try:
        monitored_coins = list(utils.last_prices.keys())
        ignored_coins = utils.load_blacklist()
        last_check = utils.last_check_time
        check_time_str = utils.format_time(last_check) if last_check else "Нет данных"
        
        top_movers = sorted(utils.hourly_movers, key=lambda x: abs(x["change"]), reverse=True)[:5]
        top_str = "\n".join([
            f"{i+1}. {move['symbol'].upper()}: {abs(move['change']):.2f}%"
            for i, move in enumerate(top_movers)
        ]) if top_movers else "Нет данных"

        message = f"""
📊 <b>Статус бота</b>

🕒 Последняя проверка: <code>{check_time_str}</code>
✅ Проверяются монеты: <code>{len(monitored_coins)}</code>
🗑️ Чёрный список: <code>{len(ignored_coins)}</code>
🔥 Топ 5 движений:
{top_str or "Нет данных"}
"""
        await update.message.reply_text(message, parse_mode='HTML')
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении /status: {e}")
        await update.message.reply_text("❌ Не удалось получить статус.")