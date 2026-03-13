import logging
from datetime import date

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.repositories.booking_repo import BookingRepository
from bot.db.repositories.master_repo import MasterRepository, get_admin_master_id
from bot.handlers.admin import IsAdmin
from bot.keyboards.admin import (
    admin_back_keyboard, admin_bookings_keyboard, admin_booking_list_keyboard,
    admin_main_keyboard, admin_booking_actions_keyboard,
)
from bot.services.notification_service import NotificationService
from bot.states.admin import AdminBookingStates
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
        force_new=True,
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

    back_callback = callback.data  # "admin:bookings:today" or "admin:bookings:upcoming"
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text="\n".join(lines),
        reply_markup=admin_booking_list_keyboard(bookings, back_callback=back_callback, page=0),
    )
    await callback.answer()


async def _show_bookings_page(
    callback: CallbackQuery, bot: Bot, session: AsyncSession,
    mode: str, page: int,
) -> None:
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer("Мастер не найден.", show_alert=True)
        return

    repo = BookingRepository(session)
    today = date.today()

    if mode == "t":
        title = f"Записи на <b>{format_date(today)}</b>"
        bookings = await repo.get_bookings_for_date_detailed(master_id, today)
        back_callback = "admin:bookings:today"
    else:
        title = "Предстоящие записи"
        bookings = await repo.get_upcoming_confirmed(master_id)
        back_callback = "admin:bookings:upcoming"

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
        reply_markup=admin_booking_list_keyboard(bookings, back_callback=back_callback, page=page),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:bpg:\d+:[tu]$"))
async def admin_bookings_page(
    callback: CallbackQuery, bot: Bot, session: AsyncSession
) -> None:
    parts = callback.data.split(":")
    page = int(parts[2])
    mode = parts[3]
    await _show_bookings_page(callback, bot, session, mode=mode, page=page)


@router.callback_query(F.data == "admin:bpg:noop")
async def admin_bpg_noop(callback: CallbackQuery) -> None:
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


@router.callback_query(F.data.regexp(r"^admin:booking:\d+:(complete|noshow)$"))
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

    if action == "complete":
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
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:booking:\d+:cancel$"))
async def admin_booking_cancel_start(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    booking_id = int(callback.data.split(":")[2])
    booking = await BookingRepository(session).get_booking_by_id(booking_id)
    if not booking:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="▶ Без причины",
            callback_data=f"admin:booking:{booking_id}:cancel_noreason",
        )],
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"admin:booking:{booking_id}:view")],
    ])
    await state.update_data(cancelling_booking_id=booking_id)
    await state.set_state(AdminBookingStates.waiting_cancel_reason)
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=(
            f"Отмена записи #{booking_id}.\n\n"
            "Введите причину отмены (будет отправлена клиенту) или нажмите «Без причины»:"
        ),
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:booking:\d+:cancel_noreason$"))
async def admin_booking_cancel_noreason(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    booking_id = int(callback.data.split(":")[2])
    await state.clear()
    await _do_cancel_booking(callback, bot, session, booking_id, reason=None)


@router.message(AdminBookingStates.waiting_cancel_reason, F.text)
async def admin_booking_cancel_with_reason(
    message: Message, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    data = await state.get_data()
    booking_id = data.get("cancelling_booking_id")
    reason = message.text.strip()[:500]
    await state.clear()

    class _FakeCallback:
        """Thin shim so _do_cancel_booking can call message_manager uniformly."""
        def __init__(self, msg: Message) -> None:
            self.message = msg
        async def answer(self) -> None:
            pass

    await _do_cancel_booking(_FakeCallback(message), bot, session, booking_id, reason=reason)


async def _do_cancel_booking(
    callback, bot: Bot, session: AsyncSession, booking_id: int, reason: str | None
) -> None:
    repo = BookingRepository(session)
    booking = await repo.get_booking_by_id(booking_id)
    if not booking:
        await message_manager.send_message(
            bot=bot,
            chat_id=callback.message.chat.id,
            text="Запись не найдена.",
            reply_markup=admin_back_keyboard(),
        )
        await callback.answer()
        return

    services_snapshot = [{"name": bs.service.name} for bs in booking.booking_services]
    client_telegram_id = booking.client.telegram_id
    booking_date = booking.date
    booking_time = booking.start_time

    await repo.cancel_booking(booking, by_master=True)
    await session.commit()
    logger.info("Admin cancelled booking #%d (reason: %s)", booking_id, reason)

    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=f"✅ Запись #{booking_id} отменена.",
        reply_markup=admin_back_keyboard(),
    )

    notification = NotificationService(bot)
    await notification.notify_client_cancellation(
        client_telegram_id=client_telegram_id,
        booking_date=booking_date,
        booking_time=booking_time,
        services=services_snapshot,
        reason=reason,
    )
    await callback.answer()
