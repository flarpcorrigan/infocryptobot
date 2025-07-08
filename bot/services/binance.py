import aiohttp
import asyncio
from typing import List, Optional
from config.config import BINANCE_TICKER_URL, BINANCE_PRICE_URL_TEMPLATE, MINIMUM_VOLUME_USDT
from bot.utils.logger import setup_logger

logger = setup_logger()

async def fetch_trading_pairs(session: aiohttp.ClientSession) -> List[str]:
    """Получить список всех пар с USDT и объемом > 2 млн."""
    try:
        async with session.get(BINANCE_TICKER_URL, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                pairs = []
                for ticker in data:
                    try:
                        symbol = ticker.get('symbol', '')
                        if not symbol.endswith("USDT"):
                            continue
                        volume_str = ticker.get('quoteVolume')
                        if volume_str is None:
                            logger.warning(f"Отсутствует quoteVolume для {symbol}")
                            continue
                        volume_usdt = float(volume_str)
                        if volume_usdt >= MINIMUM_VOLUME_USDT:
                            pairs.append(symbol)
                    except (ValueError, TypeError) as ve:
                        logger.warning(f"Некорректный объем для {symbol}: {ve}")
                    except Exception as inner_e:
                        logger.warning(f"Ошибка обработки тикера {ticker}: {inner_e}")
                logger.info(f"Найдено {len(pairs)} пар с USDT и объемом ≥ {MINIMUM_VOLUME_USDT}")
                return pairs
            else:
                logger.error(f"Ошибка загрузки пар: {response.status}")
    except aiohttp.ClientError as client_err:
        logger.error(f"Ошибка сети: {client_err}", exc_info=True)
    except asyncio.TimeoutError:
        logger.error("Таймаут при загрузке пар", exc_info=True)
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
    return []

async def get_crypto_price(session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
    """Получить текущую цену монеты"""
    url = BINANCE_PRICE_URL_TEMPLATE.format(symbol)
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                try:
                    return float(data['price'])
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"Некорректные данные для {symbol}: {data} - Ошибка: {e}")
                    return None
            logger.error(f"Ошибка получения цены для {symbol}: {response.status}")
    except aiohttp.ClientError as client_err:
        logger.error(f"Ошибка сети для {symbol}: {client_err}", exc_info=True)
    except asyncio.TimeoutError:
        logger.error(f"Таймаут для {symbol}", exc_info=True)
    except Exception as e:
        logger.error(f"Ошибка для {symbol}: {e}", exc_info=True)
    return None