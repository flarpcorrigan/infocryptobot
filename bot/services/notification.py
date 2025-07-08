import asyncio
from datetime import datetime, date
from aiogram import Bot
from bot.utils.logger import setup_logger
from config.config import CHAT_ID

logger = setup_logger()

class NotificationService:
    def __init__(self):
        self.tracked_prices = {}
        self.notifications_count = {}  # {symbol: {'count': int, 'last_reset': date}}

    async def send_notification(self, bot: Bot, symbol: str, change_percent: float):
        """Отправка уведомления о значительном изменении цены"""
        now = datetime.now()
        today = now.date()

        # Инициализируем запись для монеты, если её ещё нет
        if symbol not in self.notifications_count:
            self.notifications_count[symbol] = {'count': 0, 'last_reset': None}

        symbol_data = self.notifications_count[symbol]

        # Сбрасываем счетчик, если день изменился
        if symbol_data['last_reset'] != today:
            symbol_data['count'] = 0
            symbol_data['last_reset'] = today

        # Увеличиваем счетчик уведомлений
        symbol_data['count'] += 1

        # Определяем направление и цвет изменения
        if change_percent > 0:
            direction = "📈 Рост"
            change_text = f"+{change_percent:.2f}%"
            emoji = "🟢"
        else:
            direction = "📉 Падение"
            change_text = f"{change_percent:.2f}%"
            emoji = "🔴"

        time_str = now.strftime("%Y-%m-%d %H:%M:%S")

        # Формируем сообщение с Markdown
        message = (
            f"**{direction} цены на `{symbol}`**\n\n"
            f"{emoji} **Изменение:** *{change_text}*\n"
            f"📅 **Время:** *{time_str}*\n"
            f"🔔 **Уведомлений сегодня:** *{symbol_data['count']}*\n"
        )

        try:
            await asyncio.sleep(1)
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
            logger.info(f"Sent notification for {symbol}: {change_text} ({symbol_data['count']} times today)")
        except Exception as e:
            logger.error(f"Failed to send notification for {symbol}: {e}")

    def update_price(self, symbol, price):
        """Обновление цены в словаре"""
        self.tracked_prices[symbol] = price
        logger.debug(f"Updated price for {symbol}: {price}")

    def check_price_change(self, symbol, new_price):
        """Проверка изменения цены"""
        old_price = self.tracked_prices.get(symbol)
        if old_price is None or old_price == 0:
            return None
        change_percent = ((new_price - old_price) / old_price) * 100
        return round(change_percent, 2)