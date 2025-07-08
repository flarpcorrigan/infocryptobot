import os
import logging
from logging.handlers import TimedRotatingFileHandler

def setup_logger():
    # Определяем путь к директории с логами относительно скрипта
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, "logs")
    
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        print(f"Не удалось создать директорию для логов: {e}")
        return None

    logger = logging.getLogger("CryptoPriceBot")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Файловый хендлер
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, "bot.log"),
        when="midnight",
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Консольный хендлер
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Избегаем дублирования хендлеров
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger