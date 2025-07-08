import os
import asyncio
from aiogram import Bot
from bot.utils.logger import setup_logger
from config.config import LOG_FILE_PATH, CHAT_ID

logger = setup_logger()

class LoggerService:
    def __init__(self):
        self.log_file_path = LOG_FILE_PATH

    async def send_log_file(self, bot: Bot):
        try:
            # Проверка существования и размера файла
            if not os.path.exists(self.log_file_path) or os.path.getsize(self.log_file_path) == 0:
                logger.info("Log file does not exist or is empty.")
                return

            # Отправка файла
            with open(self.log_file_path, 'rb') as log_file:
                await bot.send_document(chat_id=CHAT_ID, document=log_file)
                logger.info("Log file sent to Telegram chat.")

            # Асинхронная очистка файла
            await self.clear_log_file()

        except Exception as e:
            logger.error(f"Failed to send log file: {e}", exc_info=True)

    async def clear_log_file(self):
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sync_clear)
        except Exception as e:
            logger.error(f"Failed to clear log file: {e}", exc_info=True)

    def _sync_clear(self):
        with open(self.log_file_path, 'w') as log_file:
            log_file.truncate(0)
        logger.info("Log file cleared.")
