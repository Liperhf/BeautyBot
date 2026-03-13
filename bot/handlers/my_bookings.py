import logging

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import is_admin_user
from bot.db.repositories.booking_repo import BookingRepository
from bot.db.repositories.client_repo import ClientRepository
from bot.db.models import BookingService
from bot.keyboards.client import (
    back_to_menu_keyboard,
    booking_detail_keyboard,
    cancel_confirm_keyboard,
    main_menu_keyboard,
    my_bookings_keyboard,
)
from bot.services.notification_service import NotificationService
from bot.utils.message_manager import message_manager
from bot.utils.time_utils import format_date, format_duration, format_time

logger = logging.getLogger(__name__)
router = Router()


async def _get_client(session: AsyncSession, telegram_id: int):
    repo = ClientRepository(session)
    return await repo.get_by_telegram_id(telegram_id)


# ── My bookings list ──────────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"my_bookings", "cancel_booking_menu"}))
async def show_my_bookings(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    await state.clear()
    client = await _get_client(session, callback.from_user.id)

    if not client:
        await message_manager.send_message(
            bot=bot,
            chat_id=callback.message.chat.id,
            text="У вас ещё нет записей. Нажмите «Записаться на услугу».",
            reply_markup=back_to_menu_keyboard(),
            force_new=True,
        )
        await callback.answer()
        return

    repo = BookingRepository(session)
    bookings = await repo.get_client_upcoming_bookings(client.id)
    history = await repo.get_client_bookings_history(client.id, limit=3)

    if not bookings and not history:
        await message_manager.send_message(
            bot=bot,
            chat_id=callback.message.chat.id,
            text="У вас нет активных записей.",
            reply_markup=back_to_menu_keyboard(),
            force_new=True,
        )
        await callback.answer()
        return

    parts = []
    if bookings:
        parts.append(f"<b>Предстоящие записи ({len(bookings)}):</b>")
    if history:
        parts.append("История — нажмите для повтора записи.")
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text="\n".join(parts) if parts else "Ваши записи:",
        reply_markup=my_bookings_keyboard(bookings, history=history or None),
        force_new=True,
    )
    await callback.answer()


# ── Booking detail ────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^booking:\d+:view$"))
async def view_booking(
    callback: CallbackQuery, bot: Bot, session: AsyncSession
) -> None:
    booking_id = int(callback.data.split(":")[1])
    repo = BookingRepository(session)
    booking = await repo.get_booking_by_id(booking_id)

    if not booking or booking.client.telegram_id != callback.from_user.id:
        await message_manager.send_message(
            bot=bot,
            chat_id=callback.message.chat.id,
            text="Запись не найдена.",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return

    svc_lines = "\n".join(
        f"  ✔ {bs.service.name} — {int(bs.price_at_booking)} руб."
        for bs in booking.booking_services
    )
    comment_line = f"\n💬 Комментарий: {booking.comment}" if booking.comment else ""

    text = (
        f"🗒 <b>Детали записи #{booking.id}</b>\n\n"
        f"📅 Дата: {format_date(booking.date)}\n"
        f"⏰ Время: {format_time(booking.start_time)} – {format_time(booking.end_time)}\n\n"
        f"✨ Услуги:\n{svc_lines}\n\n"
        f"⏱ Длительность: {format_duration(booking.total_duration_minutes)}\n"
        f"💳 Стоимость: {int(booking.total_price)} руб."
        f"{comment_line}"
    )

    is_completed = booking.status == "completed"
    can_cancel = booking.status == "confirmed"
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=booking_detail_keyboard(booking_id, can_cancel=can_cancel, is_completed=is_completed),
    )
    await callback.answer()


@router.callback_query(F.data == "my_bookings_noop")
async def my_bookings_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ── Cancel flow ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^booking:\d+:cancel$"))
async def cancel_booking_prompt(
    callback: CallbackQuery, bot: Bot, session: AsyncSession
) -> None:
    booking_id = int(callback.data.split(":")[1])
    repo = BookingRepository(session)
    booking = await repo.get_booking_by_id(booking_id)

    if not booking or booking.client.telegram_id != callback.from_user.id:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    text = (
        f"Вы уверены, что хотите отменить запись?\n\n"
        f"📅 {format_date(booking.date)} в {format_time(booking.start_time)}\n"
        f"🧾 {', '.join(bs.service.name for bs in booking.booking_services)}"
    )
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=cancel_confirm_keyboard(booking_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^booking:\d+:confirm_cancel$"))
async def confirm_cancel_booking(
    callback: CallbackQuery, bot: Bot, session: AsyncSession
) -> None:
    booking_id = int(callback.data.split(":")[1])
    repo = BookingRepository(session)
    booking = await repo.get_booking_by_id(booking_id)

    if not booking or booking.client.telegram_id != callback.from_user.id:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    services_snapshot = [
        {"name": bs.service.name} for bs in booking.booking_services
    ]
    booking_date = booking.date
    booking_time = booking.start_time
    master_telegram_id = booking.master.telegram_id
    client_name = booking.client.display_name
    client_phone = booking.client.phone

    await repo.cancel_booking(booking, by_master=False)
    await session.commit()
    logger.info("Booking #%d cancelled by client %d", booking_id, callback.from_user.id)

    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text="✅ Запись успешно отменена.",
        reply_markup=main_menu_keyboard(is_admin=is_admin_user(callback.from_user.id)),
        force_new=True,
    )

    notification = NotificationService(bot)
    await notification.notify_master_cancellation(
        master_telegram_id=master_telegram_id,
        client_name=client_name,
        client_phone=client_phone,
        booking_date=booking_date,
        booking_time=booking_time,
        services=services_snapshot,
        booking_id=booking_id,
    )
    await callback.answer()
