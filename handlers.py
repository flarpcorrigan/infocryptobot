# handlers.py
import config
import utils
from datetime import datetime, timezone
import logging
import pytz
import aiohttp

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
/ping — Диагностика подключения к API
/blacklist — Показать чёрный список монет

🔔 Уведомления о ценах:
- Отправляет уведомление, если цена изменилась на ≥1.5%
- Каждый час отправляет TOP 5 монет с наибольшими колебаниями цены

🔧 Черный список:
- Монеты без пары USDT игнорируются и добавляются в чёрный список
- Используйте /blacklist, чтобы просмотреть список
"""
    await update.message.reply_text(message, parse_mode="HTML")


async def blacklist_command(update, context):
    blacklist = utils.load_blacklist()
    if not blacklist:
        await update.message.reply_text("Чёрный список пуст.")
        return

    message = "🗑️ <b>Чёрный список монет:</b>\n\n"
    for symbol in blacklist:
        message += f"• <code>{symbol.upper()}</code>\n"

    await update.message.reply_text(message, parse_mode="HTML")


async def status_command(update, context):
    """Показывает текущее состояние бота"""
    try:
        from utils import last_prices, hourly_movers, last_check_time

        monitored_coins = list(last_prices.keys())
        ignored_coins = utils.load_blacklist()
        check_time_str = (
            utils.format_time(last_check_time) if last_check_time else "Нет данных"
        )

        top_movers = hourly_movers
        top_str = (
            "\n".join(
                [
                    f"{i+1}. {move['symbol'].upper()}: {abs(move['change']):.2f}%"
                    for i, move in enumerate(
                        sorted(
                            top_movers, key=lambda x: abs(x["change"]), reverse=True
                        )[:5]
                    )
                ]
            )
            if top_movers
            else "Нет данных"
        )

        message = f"""
📊 <b>Статус бота</b>

🕒 Последняя проверка цен: <code>{check_time_str}</code>
✅ Проверяются монеты: <code>{len(monitored_coins)}</code>
🗑️ Чёрный список: <code>{len(ignored_coins)}</code>
🔥 Топ 5 движений:
{top_str}
"""
        await update.message.reply_text(message, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при выполнении /status: {e}")
        await update.message.reply_text("❌ Не удалось получить статус.")


async def ping_command(update, context):
    """Проверяет доступность API Binance и CoinGecko"""
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            # Проверка Binance
            binance_ping = None
            try:
                async with session.get(f"{config.BINANCE_API_URL}/time", timeout=10) as r:
                    if r.status == 200:
                        server_time = (await r.json())["serverTime"] / 1000
                        binance_time = datetime.fromtimestamp(server_time, tz=timezone.utc)
                        binance_ping = f"🟢 Binance: {utils.format_time(binance_time)}"
                    else:
                        binance_ping = f"🔴 Binance: {r.status}"
            except Exception as e:
                binance_ping = f"🔴 Binance: {str(e)}"

            # Проверка CoinGecko (реальный эндпоинт)
            coingecko_ping = None
            try:
                url = " https://api.coingecko.com/api/v3/coins/markets "
                params = {"vs_currency": "usd", "per_page": 1}
                async with session.get(url, params=params, timeout=10) as r:
                    if r.status == 200:
                        data = await r.json()
                        if isinstance(data, list) and len(data) > 0:
                            coingecko_ping = "🟢 CoinGecko: доступен"
                        else:
                            coingecko_ping = "🔴 CoinGecko: пустой ответ"
                    else:
                        coingecko_ping = f"🔴 CoinGecko: {r.status}"
            except Exception as e:
                coingecko_ping = f"🔴 CoinGecko: {str(e)}"

            # Отправляем результат
            message = f"""
📡 <b>Результат диагностики</b>

{binance_ping}
{coingecko_ping}

🕒 Время сервера: {utils.get_local_time_str()}
"""
            await update.message.reply_text(message, parse_mode='HTML')
    
    except Exception as e:
        logger.error(f"Ошибка при выполнении /ping: {e}")
        await update.message.reply_text("❌ Не удалось выполнить диагностику.")