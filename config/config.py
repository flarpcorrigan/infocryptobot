import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # Замените на ваш chat_id
CHECK_INTERVAL_MINUTES = 15
MINIMUM_VOLUME_USDT = 2_000_000  # млн USD
LOG_FILE_PATH = "logs/bot.log"
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
BINANCE_PRICE_URL_TEMPLATE = "https://api.binance.com/api/v3/ticker/price?symbol={}"