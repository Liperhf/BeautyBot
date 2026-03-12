import logging
from datetime import date

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.repositories.booking_repo import BookingRepository
from bot.db.repositories.master_repo import MasterRepository
from bot.handlers.admin import IsAdmin
from bot.keyboards.admin import (
    admin_back_keyboard, admin_bookings_keyboard, admin_booking_list_keyboard,
    admin_main_keyboard, admin_booking_actions_keyboard,
)
from bot.services.notification_service import NotificationService
from bot.utils.message_manager import message_manager
from bot.utils.time_utils import format_date, format_duration, format_time

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ── Admin main menu ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text="⚙️ <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=admin_main_keyboard(),
    )
    await callback.answer()


# ── Bookings section ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:bookings")
async def admin_bookings(callback: CallbackQuery, bot: Bot) -> None:
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text="📋 <b>Записи клиентов</b>\n\nВыберите период:",
        reply_markup=admin_bookings_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"admin:bookings:today", "admin:bookings:upcoming"}))
async def admin_bookings_list(
    callback: CallbackQuery, bot: Bot, session: AsyncSession
) -> None:
    master = await MasterRepository(session).get_by_telegram_id(settings.ADMIN_TELEGRAM_ID)
    if not master:
        await callback.answer("Мастер не найден в базе данных.", show_alert=True)
        return

    repo = BookingRepository(session)
    today = date.today()

    if callback.data == "admin:bookings:today":
        title = f"Записи на <b>{format_date(today)}</b>"
        bookings = await repo.get_bookings_for_date_detailed(master.id, today)
    else:
        title = "Предстоящие записи"
        bookings = await repo.get_upcoming_confirmed(master.id)

    if not bookings:
        await message_manager.send_message(
            bot=bot,
            chat_id=callback.message.chat.id,
            text=f"{title}\n\nЗаписей нет.",
            reply_markup=admin_back_keyboard(),
        )
        await callback.answer()
        return

    lines = [f"{title} ({len(bookings)}):\n"]
    for b in bookings:
        svc_names = ", ".join(bs.service.name for bs in b.booking_services)
        lines.append(
            f"<b>{format_date(b.date)} {format_time(b.start_time)}</b>\n"
            f"  👤 {b.client.display_name} — {b.client.phone}\n"
            f"  🧾 {svc_names}\n"
            f"  💳 {int(b.total_price)} руб. · ⏱ {format_duration(b.total_duration_minutes)}\n"
        )

    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text="\n".join(lines),
        reply_markup=admin_booking_list_keyboard(bookings),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:booking:\d+:view$"))
async def admin_view_booking(
    callback: CallbackQuery, bot: Bot, session: AsyncSession
) -> None:
    booking_id = int(callback.data.split(":")[2])
    booking = await BookingRepository(session).get_booking_by_id(booking_id)
    if not booking:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    svc_lines = "\n".join(f"  • {bs.service.name}" for bs in booking.booking_services)
    comment_line = f"\n💬 {booking.comment}" if booking.comment else ""
    text = (
        f"📋 <b>Запись #{booking.id}</b>\n\n"
        f"👤 {booking.client.display_name} ({booking.client.phone})\n"
        f"📅 {format_date(booking.date)} в {format_time(booking.start_time)}\n\n"
        f"🧾 Услуги:\n{svc_lines}\n\n"
        f"💳 {int(booking.total_price)} руб. · ⏱ {format_duration(booking.total_duration_minutes)}"
        f"{comment_line}"
    )
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=admin_booking_actions_keyboard(booking_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:booking:\d+:(cancel|complete|noshow)$"))
async def admin_booking_action(
    callback: CallbackQuery, bot: Bot, session: AsyncSession
) -> None:
    parts = callback.data.split(":")
    booking_id = int(parts[2])
    action = parts[3]

    repo = BookingRepository(session)
    booking = await repo.get_booking_by_id(booking_id)
    if not booking:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    services_snapshot = [{"name": bs.service.name} for bs in booking.booking_services]

    if action == "cancel":
        await repo.cancel_booking(booking, by_master=True)
        action_text = "отменена"
    elif action == "complete":
        await repo.mark_completed(booking)
        action_text = "помечена как выполненная"
    else:
        await repo.mark_no_show(booking)
        action_text = "помечена как неявка"

    await session.commit()
    logger.info("Admin action '%s' on booking #%d", action, booking_id)

    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=f"✅ Запись #{booking_id} {action_text}.",
        reply_markup=admin_back_keyboard(),
    )

    # Notify client on cancellation
    if action == "cancel":
        notification = NotificationService(bot)
        await notification.notify_client_cancellation(
            client_telegram_id=booking.client.telegram_id,
            booking_date=booking.date,
            booking_time=booking.start_time,
            services=services_snapshot,
        )

    await callback.answer()
