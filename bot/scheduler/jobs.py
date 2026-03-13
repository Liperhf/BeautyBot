import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select

from bot.config import settings

logger = logging.getLogger(__name__)


async def send_morning_report(bot: Bot, session_pool: async_sessionmaker) -> None:
    """Send today's bookings list to the master every morning."""
    from bot.db.models import Master
    from bot.db.repositories.booking_repo import BookingRepository
    from bot.utils.time_utils import format_time, format_duration
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today_local = datetime.now(ZoneInfo(settings.TIMEZONE)).date()

    async with session_pool() as session:
        result = await session.execute(
            select(Master).where(Master.is_active == True)
        )
        masters = result.scalars().all()

        for master in masters:
            repo = BookingRepository(session)
            bookings = await repo.get_bookings_for_date_detailed(master.id, today_local)

            if not bookings:
                text = "📅 <b>Записи на сегодня:</b>\n\nЗаписей нет. Свободный день!"
            else:
                lines = [f"📅 <b>Записи на сегодня ({len(bookings)}):</b>\n"]
                for b in bookings:
                    svc_names = ", ".join(bs.service.name for bs in b.booking_services)
                    lines.append(
                        f"⏰ {format_time(b.start_time)} — "
                        f"{b.client.display_name} | {svc_names} "
                        f"({format_duration(b.total_duration_minutes)})"
                    )
                text = "\n".join(lines)

            try:
                await bot.send_message(master.telegram_id, text, parse_mode="HTML")
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                logger.warning("Cannot send morning report to master %d: %s", master.telegram_id, e)
            except Exception as e:
                logger.error("Unexpected error sending morning report to master %d: %s", master.telegram_id, e)


async def send_reminders(bot: Bot, session_pool: async_sessionmaker) -> None:
    """Send 24h and 2h booking reminders to clients."""
    from bot.db.models import Master
    from bot.db.repositories.booking_repo import BookingRepository
    from bot.utils.time_utils import format_date, format_time

    async with session_pool() as session:
        result = await session.execute(select(Master).where(Master.is_active == True))
        masters = result.scalars().all()

        for master in masters:
            repo = BookingRepository(session)

            if settings.REMINDER_24H:
                bookings = await repo.get_upcoming_unnotified(master.id, 24, "reminder_24h_sent")
                for b in bookings:
                    svc_names = ", ".join(bs.service.name for bs in b.booking_services)
                    text = (
                        f"⏰ <b>Напоминание о записи</b>\n\n"
                        f"Вы записаны завтра — <b>{format_date(b.date)}</b> в <b>{format_time(b.start_time)}</b>\n"
                        f"🧾 {svc_names}\n\n"
                        f"Ждём вас! Если планы изменились, отмените запись в боте."
                    )
                    try:
                        await bot.send_message(b.client.telegram_id, text, parse_mode="HTML")
                        b.reminder_24h_sent = True
                        logger.info("24h reminder sent for booking #%d to client %d", b.id, b.client.telegram_id)
                    except (TelegramForbiddenError, TelegramBadRequest) as e:
                        logger.warning("Cannot send 24h reminder for booking #%d: %s", b.id, e)
                    except Exception as e:
                        logger.error("Unexpected error sending 24h reminder for booking #%d: %s", b.id, e)

            if settings.REMINDER_2H:
                bookings = await repo.get_upcoming_unnotified(master.id, 2, "reminder_2h_sent")
                for b in bookings:
                    svc_names = ", ".join(bs.service.name for bs in b.booking_services)
                    text = (
                        f"🔔 <b>Скоро ваша запись!</b>\n\n"
                        f"Сегодня в <b>{format_time(b.start_time)}</b> — через ~2 часа\n"
                        f"🧾 {svc_names}\n\n"
                        f"Ждём вас!"
                    )
                    try:
                        await bot.send_message(b.client.telegram_id, text, parse_mode="HTML")
                        b.reminder_2h_sent = True
                        logger.info("2h reminder sent for booking #%d to client %d", b.id, b.client.telegram_id)
                    except (TelegramForbiddenError, TelegramBadRequest) as e:
                        logger.warning("Cannot send 2h reminder for booking #%d: %s", b.id, e)
                    except Exception as e:
                        logger.error("Unexpected error sending 2h reminder for booking #%d: %s", b.id, e)

        await session.commit()


def setup_scheduler(bot: Bot, session_pool: async_sessionmaker) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

    scheduler.add_job(
        send_morning_report,
        trigger="cron",
        hour=settings.MORNING_REPORT_HOUR,
        minute=0,
        kwargs={"bot": bot, "session_pool": session_pool},
        id="morning_report",
        replace_existing=True,
    )

    scheduler.add_job(
        send_reminders,
        trigger="interval",
        minutes=30,
        kwargs={"bot": bot, "session_pool": session_pool},
        id="reminders",
        replace_existing=True,
    )

    return scheduler
