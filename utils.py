# utils.py
import config
import aiohttp
import logging
import json
from datetime import datetime, timedelta
import aiohttp
import asyncio
import os

# Настройка логирования
logging.basicConfig(
    filename="logs/bot.log",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    encoding="utf-8"
)

# Кэширование пар Binance
_cached_binance_pairs = set()
_last_exchange_info_time = 0
EXCHANGE_INFO_TTL = 600  # 10 минут

async def get_binance_pairs(session):
    """Загружает список пар USDT с Binance через /exchangeInfo"""
    global _cached_binance_pairs, _last_exchange_info_time

    current_time = datetime.now().timestamp()

    # Используем кэш, если он ещё актуален
    if current_time - _last_exchange_info_time < EXCHANGE_INFO_TTL and _cached_binance_pairs:
        return _cached_binance_pairs

    try:
        for attempt in range(3):  # 3 попытки
            url = f"{config.BINANCE_API_URL}/exchangeInfo"
            async with session.get(url, timeout=15) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logging.warning(f"Too Many Requests. Жду {retry_after} секунд...")
                    await asyncio.sleep(retry_after)
                    continue
                
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict) and "symbols" in data:
                        _cached_binance_pairs = {s["symbol"] for s in data["symbols"]}
                        _last_exchange_info_time = current_time
                        # Сохраняем кэш в файл
                        with open("data/binance_pairs.json", "w", encoding="utf-8") as f:
                            json.dump(list(_cached_binance_pairs), f, ensure_ascii=False, indent=2)
                        return _cached_binance_pairs
                    else:
                        logging.warning("Ошибка: в ответе Binance отсутствует ключ 'symbols'")
                        return load_binance_cache()
                
                else:
                    logging.warning(f"Ошибка получения exchangeInfo: {response.status}")
                    return load_binance_cache()
        
        return load_binance_cache()
    
    except asyncio.TimeoutError:
        logging.error("Ошибка: таймаут при подключении к Binance")
        return load_binance_cache()
    except Exception as e:
        logging.error(f"Критическая ошибка при получении пар с Binance: {e}")
        return load_binance_cache()

def load_binance_cache():
    """Загружает пары из кэш-файла"""
    try:
        with open("data/binance_pairs.json", "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_blacklist(blacklist):
    """Сохраняет чёрный список монет"""
    with open("data/blacklist.json", "w", encoding="utf-8") as f:
        json.dump(list(blacklist), f, ensure_ascii=False, indent=2)

def load_blacklist():
    """Загружает чёрный список монет"""
    try:
        with open("data/blacklist.json", "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

async def get_top_300_coins(session):
    """Получить топ-300 монет с CoinGecko"""
    coins = []
    try:
        for page in range(1, 4):  # 3 страницы по 100 монет
            url = f"{config.COINGECKO_API_URL}/coins/markets"
            params = {"vs_currency": "usd", "per_page": 100, "page": 1}
            
            logging.info(f"Запрос к CoinGecko (страница {page})")
            for attempt in range(3):  # 3 попытки
                try:
                    async with session.get(url, params=params, timeout=15) as response:
                        if response.status == 429:
                            retry_after = int(response.headers.get("Retry-After", 20))
                            logging.warning(f"Too Many Requests. Жду {retry_after} секунд...")
                            await asyncio.sleep(retry_after)
                            continue
                        
                        if response.status == 200:
                            data = await response.json()
                            coins.extend([{"id": coin["id"], "symbol": coin["symbol"]} for coin in data])
                            break  # Успешно
                        else:
                            logging.warning(f"Ошибка получения данных (страница {page}): {response.status}")
                            break
                    
                    await asyncio.sleep(20)  # Пауза между страницами
                
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logging.warning(f"Сетевая ошибка (попытка {attempt+1}/3): {e}")
                    await asyncio.sleep(5)
                    continue
        
        return coins
    
    except Exception as e:
        logging.error(f"Ошибка получения топ-300 монет: {e}")
        return []

async def filter_valid_coins(session, coins):
    """Фильтр монет с парой USDT на Binance"""
    blacklist = load_blacklist()
    valid_coins = []
    new_ignored = set()

    # Загружаем пары Binance
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
            logging.info(f"Игнорируем монету {symbol} — нет пары {pair}")

    # Обновляем чёрный список
    if new_ignored:
        blacklist.update(new_ignored)
        save_blacklist(blacklist)
    
    return valid_coins

async def get_price_change(session, symbol):
    """Получить текущую цену с Binance"""
    try:
        url = f"{config.BINANCE_API_URL}/ticker/price"
        params = {"symbol": f"{symbol.upper()}USDT"}
        
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 10))
                logging.warning(f"Too Many Requests. Жду {retry_after} секунд...")
                await asyncio.sleep(retry_after)
                return 0
            
            if response.status == 200:
                data = await response.json()
                return float(data["price"])
            else:
                logging.warning(f"Ошибка получения цены для {symbol}: {response.status}")
                return 0
    
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logging.warning(f"Сетевая ошибка при получении цены {symbol}: {e}")
        return 0
    except Exception as e:
        logging.error(f"Ошибка получения цены для {symbol}: {e}")
        return 0

def format_alert_message(symbol, direction, percent):
    """Форматирует уведомление об изменении цены"""
    emoji = "🟢" if direction == "📈 Рост" else "🔴"
    return f"""
{emoji} <b>{direction} цены на {symbol.upper()}!</b>
📊 Изменение: <b>{percent:.2f}%</b>
🕒 Время: {datetime.now().strftime("%Y-%m-%d %H:%M")}
"""

def format_top_movers_message(movers):
    """Форматирует топ-5 монет"""
    if not movers:
        return "📉 Нет значительных движений за час."
    
    message = "🔥 <b>Топ 5 движений за час:</b>\n\n"
    movers_sorted = sorted(movers, key=lambda x: abs(x['change']), reverse=True)[:5]
    
    for i, move in enumerate(movers_sorted, 1):
        emoji = "🟢" if move['change'] > 0 else "🔴"
        message += f"{i}. {emoji} <b>{move['symbol'].upper()}</b>: <code>{abs(move['change']):.2f}%</code>\n"
    
    message += f"\n🕒 Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    return message