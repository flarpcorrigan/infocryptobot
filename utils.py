# utils.py
import config
import aiohttp
import logging
import json
from datetime import datetime, timezone
from telegram.ext import ContextTypes
import asyncio
import pytz

# --- Настройка логирования с временной зоной и уровнем ---
class MoscowTimeFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.msk_tz = pytz.timezone(config.TIMEZONE)

    def formatTime(self, record, datefmt=None):
        utc_time = datetime.fromtimestamp(record.created, tz=timezone.utc)
        msk_time = utc_time.astimezone(self.msk_tz)
        return msk_time.strftime("%Y-%m-%d %H:%M:%S")

# Формат лога: время — уровень — сообщение
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
handler.setFormatter(MoscowTimeFormatter(LOG_FORMAT))
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

# --- Конфигурация времени ---
MSK_TIMEZONE = pytz.timezone(config.TIMEZONE)

def get_local_time_str():
    return datetime.now(timezone.utc).astimezone(MSK_TIMEZONE).strftime("%Y-%m-%d %H:%M")

def format_time(dt: datetime) -> str:
    if dt is None:
        return "Нет данных"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MSK_TIMEZONE).strftime("%Y-%m-%d %H:%M")

# --- Кэширование пар Binance ---
_cached_binance_pairs = set()
_last_exchange_info_time = 0
EXCHANGE_INFO_TTL = 600  # 10 минут

async def get_binance_pairs(session):
    global _cached_binance_pairs, _last_exchange_info_time

    current_time = datetime.now(timezone.utc).timestamp()
    if current_time - _last_exchange_info_time < EXCHANGE_INFO_TTL and _cached_binance_pairs:
        return _cached_binance_pairs

    try:
        url = f"{config.BINANCE_API_URL}/exchangeInfo"
        async with session.get(url, timeout=15) as response:
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Too Many Requests. Жду {retry_after} секунд...")
                await asyncio.sleep(retry_after)
                return load_binance_cache()
            
            if response.status == 200:
                data = await response.json()
                if isinstance(data, dict) and "symbols" in data:
                    _cached_binance_pairs = {s["symbol"] for s in data["symbols"]}
                    _last_exchange_info_time = datetime.now(timezone.utc).timestamp()
                    save_binance_cache(_cached_binance_pairs)
                    return _cached_binance_pairs
                else:
                    logger.warning("Ошибка: в ответе Binance отсутствует ключ 'symbols'")
                    return load_binance_cache()
            else:
                logger.warning(f"Ошибка получения exchangeInfo: {response.status}")
                return load_binance_cache()
    
    except asyncio.TimeoutError:
        logger.error("Ошибка: таймаут при подключении к Binance")
        return load_binance_cache()
    except Exception as e:
        logger.error(f"Критическая ошибка при получении пар с Binance: {e}")
        return load_binance_cache()

def load_binance_cache():
    try:
        with open("data/binance_pairs.json", "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_binance_cache(pairs):
    with open("data/binance_pairs.json", "w", encoding="utf-8") as f:
        json.dump(list(pairs), f, ensure_ascii=False, indent=2)

def load_blacklist():
    try:
        with open("data/blacklist.json", "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_blacklist(blacklist):
    with open("data/blacklist.json", "w", encoding="utf-8") as f:
        json.dump(list(blacklist), f, ensure_ascii=False, indent=2)

# --- Получение монет и цен ---
async def get_top_300_coins(session):
    """Получить топ-300 монет с CoinGecko"""
    coins = []
    try:
        for page in range(1, 4):  # 3 страницы по 100 монет
            url = f"{config.COINGECKO_API_URL}/coins/markets"
            params = {"vs_currency": "usd", "per_page": 100, "page": page}
            
            logger.info(f"Запрос к CoinGecko (страница {page})")
            for attempt in range(3):  # 3 попытки
                try:
                    async with session.get(url, params=params, timeout=15, ssl=False) as response:
                        if response.status == 429:
                            retry_after = int(response.headers.get("Retry-After", 20))
                            logger.warning(f"Too Many Requests. Жду {retry_after} секунд...")
                            await asyncio.sleep(retry_after)
                            continue
                        
                        if response.status == 200:
                            data = await response.json()
                            coins.extend([{"id": coin["id"], "symbol": coin["symbol"]} for coin in data])
                            break  # Успешно
                        else:
                            logger.warning(f"Ошибка получения данных (страница {page}): {response.status}")
                            break
                    
                    await asyncio.sleep(20)  # Пауза между страницами
                
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"Сетевая ошибка (попытка {attempt+1}/3): {e}")
                    await asyncio.sleep(5)
                    continue
        
        return coins
    
    except Exception as e:
        logger.error(f"Ошибка получения топ-300 монет: {e}")
        return []

async def filter_valid_coins(session, coins):
    """Фильтр монет с парой USDT на Binance"""
    blacklist = load_blacklist()
    valid_coins = []
    new_ignored = set()

    symbols = await get_binance_pairs(session)
    
    for coin in coins:
        symbol = coin["symbol"].lower()
        if symbol in ["usdt", "usdc", "busd"] or symbol in blacklist:
            continue
        pair = f"{symbol.upper()}USDT"
        if pair in symbols:
            valid_coins.append(coin)
        else:
            new_ignored.add(symbol)
            logger.info(f"Игнорируем монету {symbol} — нет пары {pair}")

    if new_ignored:
        blacklist.update(new_ignored)
        save_blacklist(blacklist)
    
    return valid_coins

async def get_price_change(session, symbol):
    try:
        url = f"{config.BINANCE_API_URL}/ticker/price"
        params = {"symbol": f"{symbol.upper()}USDT"}
        
        async with session.get(url, params=params, timeout=10, ssl=False) as response:
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 10))
                logger.warning(f"Too Many Requests. Жду {retry_after} секунд...")
                await asyncio.sleep(retry_after)
                return 0
            
            if response.status == 200:
                data = await response.json()
                return float(data["price"])
            else:
                logger.warning(f"Ошибка получения цены для {symbol}: {response.status}")
                return 0
    
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.warning(f"Сетевая ошибка при получении цены {symbol}: {e}")
        return 0
    except Exception as e:
        logger.error(f"Ошибка получения цены для {symbol}: {e}")
        return 0

def format_alert_message(symbol, direction, percent):
    emoji = "🟢" if direction == "📈 Рост" else "🔴"
    timestamp = get_local_time_str()
    return f"""
{emoji} <b>{direction} цены на {symbol.upper()}!</b>
📊 Изменение: <b>{percent:.2f}%</b>
🕒 Время: {timestamp}
"""

def format_top_movers_message(movers):
    if not movers:
        return "📉 Нет значительных движений за час."
    
    message = "🔥 <b>Топ 5 движений за час:</b>\n\n"
    movers_sorted = sorted(movers, key=lambda x: abs(x['change']), reverse=True)[:5]
    
    for i, move in enumerate(movers_sorted, 1):
        emoji = "🟢" if move['change'] > 0 else "🔴"
        message += f"{i}. {emoji} <b>{move['symbol'].upper()}</b>: <code>{abs(move['change']):.2f}%</code>\n"
    
    message += f"\n🕒 Обновлено: {get_local_time_str()}"
    return message

def get_local_time_str():
    return datetime.now(timezone.utc).astimezone(MSK_TIMEZONE).strftime("%Y-%m-%d %H:%M")

# --- Глобальные переменные ---
last_prices = {}
hourly_movers = []
last_check_time = None

# --- Функции проверки цен ---
async def check_price_changes(context: ContextTypes.DEFAULT_TYPE):
    global last_prices, last_check_time
    try:
        logger.info("Проверка цен на криптовалюты...")

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            coins = await get_top_300_coins(session)
            valid_coins = await filter_valid_coins(session, coins)

            current_movers = []
            for coin in valid_coins:
                symbol = coin["symbol"]
                current_price = await get_price_change(session, symbol)

                if current_price == 0:
                    continue

                if symbol in last_prices:
                    change_percent = ((current_price - last_prices[symbol]) / last_prices[symbol]) * 100
                    current_movers.append({
                        "symbol": symbol,
                        "change": change_percent,
                        "timestamp": datetime.now(timezone.utc).timestamp()
                    })

                    if abs(change_percent) >= config.PRICE_CHANGE_THRESHOLD:
                        direction = "📈 Рост" if change_percent > 0 else "📉 Падение"
                        message = format_alert_message(
                            symbol.upper(),
                            direction,
                            round(abs(change_percent), 2)
                        )
                        await context.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
                
                last_prices[symbol] = current_price

            hourly_movers.extend(current_movers)
            last_check_time = datetime.now(timezone.utc)

    except Exception as e:
        logger.error(f"Ошибка при проверке цен: {e}")

async def generate_hourly_top(context: ContextTypes.DEFAULT_TYPE):
    global hourly_movers
    try:
        one_hour_ago = datetime.now(timezone.utc).timestamp() - 60 * 60
        filtered_movers = [m for m in hourly_movers if m['timestamp'] >= one_hour_ago]
        
        if filtered_movers:
            top_message = format_top_movers_message(filtered_movers)
            await context.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=top_message, parse_mode='HTML')
        
        hourly_movers = []  # Очищаем для следующего часа

    except Exception as e:
        logger.error(f"Ошибка при формировании топа: {e}")