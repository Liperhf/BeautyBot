import logging
from datetime import date, time

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from bot.utils.time_utils import format_date, format_time, format_duration

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def notify_master_new_booking(
        self,
        master_telegram_id: int,
        client_name: str,
        client_phone: str,
        client_username: str | None,
        services: list[dict],
        booking_date: date,
        booking_time: time,
        total_price: float,
        total_duration: int,
        comment: str | None,
        booking_id: int,
    ) -> None:
        services_text = "\n".join(f"  • {s['name']}" for s in services)
        username_line = f"@{client_username}" if client_username else "нет username"
        comment_line = f"\n💬 Комментарий: {comment}" if comment else ""

        text = (
            f"🔔 <b>Новая запись!</b>\n\n"
            f"👤 Клиент: {client_name} ({username_line})\n"
            f"📞 Телефон: {client_phone}\n\n"
            f"🧾 Услуги:\n{services_text}\n\n"
            f"⏱ Длительность: {format_duration(total_duration)}\n"
            f"💳 Стоимость: {int(total_price)} руб.\n"
            f"📅 Дата: {format_date(booking_date)}\n"
            f"⏰ Время: {format_time(booking_time)}"
            f"{comment_line}\n\n"
            f"#запись_{booking_id}"
        )
        await self._send(master_telegram_id, text)

    async def notify_master_cancellation(
        self,
        master_telegram_id: int,
        client_name: str,
        client_phone: str,
        booking_date: date,
        booking_time: time,
        services: list[dict],
        booking_id: int,
    ) -> None:
        services_text = ", ".join(s["name"] for s in services)
        text = (
            f"🚫 <b>Отмена записи!</b>\n\n"
            f"👤 Клиент: {client_name}\n"
            f"📞 Телефон: {client_phone}\n\n"
            f"🧾 Услуги: {services_text}\n"
            f"📅 Дата: {format_date(booking_date)}\n"
            f"⏰ Время: {format_time(booking_time)}\n\n"
            f"#запись_{booking_id}"
        )
        await self._send(master_telegram_id, text)

    async def notify_client_cancellation(
        self,
        client_telegram_id: int,
        booking_date: date,
        booking_time: time,
        services: list[dict],
    ) -> None:
        services_text = ", ".join(s["name"] for s in services)
        text = (
            f"🚫 <b>Ваша запись отменена мастером.</b>\n\n"
            f"🧾 Услуги: {services_text}\n"
            f"📅 Дата: {format_date(booking_date)}\n"
            f"⏰ Время: {format_time(booking_time)}\n\n"
            f"Для повторной записи воспользуйтесь ботом."
        )
        await self._send(client_telegram_id, text)

    async def _send(self, chat_id: int, text: str) -> None:
        try:
            await self.bot.send_message(chat_id, text, parse_mode="HTML")
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.warning("Cannot notify chat %d: %s", chat_id, e)
        except Exception as e:
            logger.error("Unexpected error notifying chat %d: %s", chat_id, e)
