import html
import logging
import re
from datetime import date, time, datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings, is_admin_user
from bot.db.repositories.booking_repo import BookingRepository
from bot.db.repositories.client_repo import ClientRepository
from bot.db.repositories.service_repo import ServiceRepository
from bot.db.models import Master
from bot.keyboards.client import (
    back_to_menu_keyboard,
    categories_keyboard,
    comment_step_keyboard,
    confirm_booking_keyboard,
    dates_keyboard,
    main_menu_keyboard,
    name_step_keyboard,
    phone_step_keyboard,
    services_keyboard,
    times_keyboard,
)
from bot.services.notification_service import NotificationService
from bot.services.schedule_service import ScheduleService
from bot.states.booking import BookingStates
from bot.utils.message_manager import message_manager
from bot.utils.time_utils import format_date, format_duration, format_time

logger = logging.getLogger(__name__)
router = Router()

PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_master_id(session: AsyncSession) -> int:
    from sqlalchemy import select
    result = await session.execute(
        select(Master).where(Master.is_active == True).limit(1)
    )
    master = result.scalar_one_or_none()
    return master.id if master else 1


def _services_summary(selected: list[dict]) -> tuple[str, float, int]:
    """Returns (formatted list text, total_price, total_duration)."""
    lines = "\n".join(f"  ✔ {s['name']} — {int(s['price'])} руб." for s in selected)
    total_price = sum(s["price"] for s in selected)
    total_duration = sum(s["duration"] for s in selected)
    return lines, total_price, total_duration


async def _show_categories(
    chat_id: int, state: FSMContext, bot: Bot, session: AsyncSession, master_id: int,
    force_new: bool = False,
) -> None:
    data = await state.get_data()
    selected = data.get("selected_services", [])
    service_repo = ServiceRepository(session)
    categories = await service_repo.get_active_categories(master_id)

    header = f"👤 {html.escape(str(data.get('name', '')))}  📞 {html.escape(str(data.get('phone', '')))}\n\n"
    if selected:
        header += f"<b>Уже выбрано:</b> {len(selected)} усл. на {int(sum(s['price'] for s in selected))} руб.\n\n"
    header += "<b>Выберите группу услуг:</b>"

    await state.set_state(BookingStates.choosing_category)
    await message_manager.send_message(
        bot=bot,
        chat_id=chat_id,
        text=header,
        reply_markup=categories_keyboard(categories),
        force_new=force_new,
    )


# ── Step 1: Start booking ─────────────────────────────────────────────────────

@router.callback_query(F.data == "book_start")
async def booking_start(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    await state.clear()
    master_id = await _get_master_id(session)
    await state.update_data(master_id=master_id, selected_services=[])

    client_repo = ClientRepository(session)
    client = await client_repo.get_by_telegram_id(callback.from_user.id)

    if client and client.phone and client.display_name:
        await state.update_data(
            name=client.display_name, phone=client.phone, client_exists=True
        )
        await _show_categories(callback.message.chat.id, state, bot, session, master_id, force_new=True)
    else:
        await state.set_state(BookingStates.waiting_name)
        await message_manager.send_message(
            bot=bot,
            chat_id=callback.message.chat.id,
            text="Для записи мне нужны ваши данные.\n\n<b>Введите ваше имя</b> ➡️",
            reply_markup=name_step_keyboard(),
            force_new=True,
        )
    await callback.answer()


# Allow re-entering the flow from category selection back-button
@router.callback_query(F.data == "book_start_fresh")
async def booking_start_fresh(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    await booking_start(callback, state, bot, session)


# ── Step 2: Name ──────────────────────────────────────────────────────────────

@router.message(BookingStates.waiting_name)
async def process_name(message: Message, state: FSMContext, bot: Bot) -> None:
    name = message.text.strip() if message.text else ""
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)

    if not 2 <= len(name) <= 100:
        await message_manager.send_message(
            bot=bot,
            chat_id=message.chat.id,
            text="Пожалуйста, введите корректное имя (2–100 символов).",
            reply_markup=name_step_keyboard(),
        )
        return

    await state.update_data(name=name)
    await state.set_state(BookingStates.waiting_phone)
    await message_manager.send_message(
        bot=bot,
        chat_id=message.chat.id,
        text=f"Ваше имя: <b>{html.escape(name)}</b>\n\n<b>Введите номер телефона</b> (пример: +375441234567) ➡️",
        reply_markup=phone_step_keyboard(),
    )


@router.callback_query(F.data == "book_back_to_name", BookingStates.waiting_phone)
async def back_to_name(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(BookingStates.waiting_name)
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text="<b>Введите ваше имя</b> ➡️",
        reply_markup=name_step_keyboard(),
    )
    await callback.answer()


# ── Step 3: Phone ─────────────────────────────────────────────────────────────

@router.message(BookingStates.waiting_phone)
async def process_phone(
    message: Message, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    phone = message.text.strip() if message.text else ""
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    data = await state.get_data()

    if not PHONE_RE.match(phone):
        await message_manager.send_message(
            bot=bot,
            chat_id=message.chat.id,
            text=(
                f"Ваше имя: <b>{html.escape(str(data.get('name', '')))}</b>\n\n"
                "Неверный формат. Введите телефон в формате <b>+375441234567</b> ➡️"
            ),
            reply_markup=phone_step_keyboard(),
        )
        return

    await state.update_data(phone=phone)
    master_id = data.get("master_id", 1)
    await _show_categories(message.chat.id, state, bot, session, master_id)


# ── Step 4: Category ──────────────────────────────────────────────────────────

@router.callback_query(BookingStates.choosing_category, F.data.startswith("cat:"))
async def choose_category(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    category_id = int(callback.data.split(":", 1)[1])
    await state.update_data(current_category_id=category_id)

    service_repo = ServiceRepository(session)
    category = await service_repo.get_category_by_id(category_id)
    services = await service_repo.get_active_services_by_category(category_id)

    if not services:
        await callback.answer("В этой категории пока нет услуг.", show_alert=True)
        return

    data = await state.get_data()
    selected_ids = [s["id"] for s in data.get("selected_services", [])]

    text = f"<b>{category.name}</b>"
    if category.description:
        text += f"\n<i>{category.description}</i>"
    text += "\n\nВыберите услуги (можно несколько):"

    await state.set_state(BookingStates.choosing_services)
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=services_keyboard(services, selected_ids, category_id),
    )
    await callback.answer()


# ── Step 5: Services toggle ───────────────────────────────────────────────────

@router.callback_query(BookingStates.choosing_services, F.data.startswith("srv:"))
async def toggle_service(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    service_id = int(callback.data.split(":", 1)[1])
    service_repo = ServiceRepository(session)
    service = await service_repo.get_service_by_id(service_id)

    if not service:
        await callback.answer("Услуга не найдена.")
        return

    data = await state.get_data()
    selected: list[dict] = data.get("selected_services", [])
    selected_ids = [s["id"] for s in selected]

    if service_id in selected_ids:
        selected = [s for s in selected if s["id"] != service_id]
        await callback.answer(f"Убрано: {service.name}")
    else:
        selected.append({
            "id": service.id,
            "name": service.name,
            "price": float(service.price),
            "duration": service.duration_minutes,
        })
        await callback.answer(f"Добавлено: {service.name}")

    await state.update_data(selected_services=selected)

    # Update keyboard in-place — no message deletion needed
    category_id = data.get("current_category_id")
    services = await service_repo.get_active_services_by_category(category_id)
    new_selected_ids = [s["id"] for s in selected]
    try:
        await callback.message.edit_reply_markup(
            reply_markup=services_keyboard(services, new_selected_ids, category_id)
        )
    except Exception:
        pass


@router.callback_query(BookingStates.choosing_services, F.data == "book_services_done")
async def services_done(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    selected = data.get("selected_services", [])

    if not selected:
        await callback.answer("Выберите хотя бы одну услугу!", show_alert=True)
        return

    lines, total_price, total_duration = _services_summary(selected)
    text = (
        f"<b>Выбранные услуги:</b>\n{lines}\n\n"
        f"💳 Общая стоимость: <b>{int(total_price)} руб.</b>\n"
        f"⏱ Продолжительность: <b>{format_duration(total_duration)}</b>\n\n"
        "Введите комментарий для мастера или перейдите к следующему шагу ➡️"
    )
    await state.set_state(BookingStates.waiting_comment)
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=comment_step_keyboard(),
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_services, F.data == "book_other_category")
async def other_category(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    data = await state.get_data()
    await _show_categories(callback.message.chat.id, state, bot, session, data.get("master_id", 1))
    await callback.answer()


@router.callback_query(BookingStates.choosing_services, F.data.startswith("cat_back:"))
async def back_from_services(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    data = await state.get_data()
    await _show_categories(callback.message.chat.id, state, bot, session, data.get("master_id", 1))
    await callback.answer()


# ── Step 6: Comment ───────────────────────────────────────────────────────────

@router.message(BookingStates.waiting_comment)
async def process_comment(
    message: Message, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    comment = message.text.strip() if message.text else ""
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    if len(comment) > 500:
        await message_manager.send_message(
            bot=bot,
            chat_id=message.chat.id,
            text=f"Комментарий слишком длинный ({len(comment)} симв.). Максимум — 500 символов:",
            reply_markup=comment_step_keyboard(),
        )
        return
    await state.update_data(comment=comment)
    await _show_dates(message.chat.id, state, bot, session)


@router.callback_query(BookingStates.waiting_comment, F.data == "book_skip_comment")
async def skip_comment(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    await state.update_data(comment="")
    await _show_dates(callback.message.chat.id, state, bot, session)
    await callback.answer()


@router.callback_query(BookingStates.waiting_comment, F.data == "book_back_to_services")
async def back_to_services(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    data = await state.get_data()
    category_id = data.get("current_category_id")

    if not category_id:
        await _show_categories(callback.message.chat.id, state, bot, session, data.get("master_id", 1))
        await callback.answer()
        return

    service_repo = ServiceRepository(session)
    category = await service_repo.get_category_by_id(category_id)
    services = await service_repo.get_active_services_by_category(category_id)
    selected_ids = [s["id"] for s in data.get("selected_services", [])]

    text = f"<b>{category.name}</b>\n\nВыберите услуги (можно несколько):"
    await state.set_state(BookingStates.choosing_services)
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=services_keyboard(services, selected_ids, category_id),
    )
    await callback.answer()


# ── Step 7: Date ──────────────────────────────────────────────────────────────

async def _show_dates(
    chat_id: int, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    data = await state.get_data()
    selected = data.get("selected_services", [])
    total_duration = sum(s["duration"] for s in selected)
    master_id = data.get("master_id", 1)

    schedule_service = ScheduleService(session)
    available_dates = await schedule_service.get_available_dates(master_id, total_duration)

    if not available_dates:
        await message_manager.send_message(
            bot=bot,
            chat_id=chat_id,
            text="К сожалению, на ближайшие 3 недели нет свободных дат. Попробуйте позже.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    await state.set_state(BookingStates.choosing_date)
    await message_manager.send_message(
        bot=bot,
        chat_id=chat_id,
        text="<b>Выберите дату</b> для записи ➡️",
        reply_markup=dates_keyboard(available_dates),
    )


@router.callback_query(BookingStates.choosing_date, F.data.startswith("date:"))
async def choose_date(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    date_str = callback.data.split(":", 1)[1]
    booking_date = date.fromisoformat(date_str)
    await state.update_data(booking_date=date_str)

    data = await state.get_data()
    total_duration = sum(s["duration"] for s in data.get("selected_services", []))
    master_id = data.get("master_id", 1)

    schedule_service = ScheduleService(session)
    available_times = await schedule_service.get_available_slots(master_id, booking_date, total_duration)

    if not available_times:
        fresh_dates = await schedule_service.get_available_dates(master_id, total_duration)
        await message_manager.send_message(
            bot=bot,
            chat_id=callback.message.chat.id,
            text=f"На <b>{format_date(booking_date)}</b> нет свободного времени. Выберите другую дату.",
            reply_markup=dates_keyboard(fresh_dates),
        )
        await callback.answer()
        return

    await state.set_state(BookingStates.choosing_time)
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=f"<b>Выберите время</b> для записи на <b>{format_date(booking_date)}</b> ➡️",
        reply_markup=times_keyboard(available_times),
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_date, F.data == "book_back_to_comment")
async def back_to_comment(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    selected = data.get("selected_services", [])
    lines, total_price, total_duration = _services_summary(selected)
    text = (
        f"<b>Выбранные услуги:</b>\n{lines}\n\n"
        f"💳 Общая стоимость: <b>{int(total_price)} руб.</b>\n"
        f"⏱ Продолжительность: <b>{format_duration(total_duration)}</b>\n\n"
        "Введите комментарий или перейдите к следующему шагу ➡️"
    )
    await state.set_state(BookingStates.waiting_comment)
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=comment_step_keyboard(),
    )
    await callback.answer()


# ── Step 8: Time ──────────────────────────────────────────────────────────────

@router.callback_query(BookingStates.choosing_time, F.data.startswith("time:"))
async def choose_time(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    time_str = callback.data.split(":", 1)[1]
    await state.update_data(booking_time=time_str)

    data = await state.get_data()
    selected = data.get("selected_services", [])
    lines, total_price, total_duration = _services_summary(selected)
    # Rebuild lines without price for confirmation screen
    svc_lines = "\n".join(f"  ✔ {s['name']}" for s in selected)
    booking_date = date.fromisoformat(data["booking_date"])
    comment = data.get("comment", "")

    text = (
        f"📋 <b>Подтвердите запись:</b>\n\n"
        f"👤 Имя: {html.escape(str(data.get('name', '')))}\n"
        f"📞 Телефон: {html.escape(str(data.get('phone', '')))}\n\n"
        f"🧾 Услуги:\n{svc_lines}\n\n"
        f"⏱ Продолжительность: {format_duration(total_duration)}\n"
        f"💳 Стоимость: {int(total_price)} руб.\n"
        f"📅 Дата: {format_date(booking_date)}\n"
        f"⏰ Время: {time_str}\n"
    )
    if comment:
        text += f"💬 Комментарий: {html.escape(comment)}\n"
    text += "\n<b>Всё верно?</b>"

    await state.set_state(BookingStates.confirming)
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=confirm_booking_keyboard(),
    )
    await callback.answer()


@router.callback_query(BookingStates.choosing_time, F.data == "book_back_to_dates")
async def back_to_dates(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    await _show_dates(callback.message.chat.id, state, bot, session)
    await callback.answer()


# ── Step 9: Confirm ───────────────────────────────────────────────────────────

@router.callback_query(BookingStates.confirming, F.data == "book_confirm")
async def confirm_booking(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    data = await state.get_data()
    master_id = data.get("master_id", 1)
    selected = data.get("selected_services", [])
    _, total_price, total_duration = _services_summary(selected)
    booking_date = date.fromisoformat(data["booking_date"])
    booking_time = time.fromisoformat(data["booking_time"])
    end_dt = datetime.combine(booking_date, booking_time) + timedelta(minutes=total_duration)
    end_time = end_dt.time()

    # Re-check slot availability (race condition guard)
    schedule_service = ScheduleService(session)
    available = await schedule_service.get_available_slots(master_id, booking_date, total_duration)
    if booking_time not in available:
        await message_manager.send_message(
            bot=bot,
            chat_id=callback.message.chat.id,
            text="Этот слот только что заняли. Пожалуйста, выберите другое время.",
            reply_markup=back_to_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return

    # Get or create client
    client_repo = ClientRepository(session)
    client = await client_repo.get_by_telegram_id(callback.from_user.id)
    if client:
        client = await client_repo.update(
            client,
            display_name=data.get("name"),
            phone=data.get("phone"),
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
    else:
        client = await client_repo.create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            display_name=data.get("name"),
            phone=data.get("phone"),
        )

    # Create booking (SELECT FOR UPDATE inside prevents race conditions)
    booking_repo = BookingRepository(session)
    try:
        booking = await booking_repo.create_booking(
            client_id=client.id,
            master_id=master_id,
            booking_date=booking_date,
            start_time=booking_time,
            end_time=end_time,
            total_price=total_price,
            total_duration=total_duration,
            comment=data.get("comment") or None,
            services=[{"id": s["id"], "price": s["price"], "duration": s["duration"]} for s in selected],
        )
    except ValueError:
        await message_manager.send_message(
            bot=bot,
            chat_id=callback.message.chat.id,
            text="Этот слот только что заняли. Пожалуйста, выберите другое время.",
            reply_markup=back_to_menu_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return
    await session.commit()
    logger.info(
        "Booking #%d created: client=%d master=%d date=%s time=%s",
        booking.id, client.id, master_id, booking_date, booking_time,
    )

    # Confirmation to client
    svc_lines = "\n".join(f"  ✔ {s['name']}" for s in selected)
    success_text = (
        f"✅ <b>Вы записаны!</b>\n\n"
        f"📅 Дата: {format_date(booking_date)}\n"
        f"⏰ Время: {format_time(booking_time)}\n"
        f"🧾 Услуги:\n{svc_lines}\n"
        f"💳 Стоимость: {int(total_price)} руб.\n\n"
        f"Ждём вас! Если нужно отменить — нажмите «Мои записи»."
    )
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=success_text,
        reply_markup=main_menu_keyboard(is_admin=is_admin_user(callback.from_user.id)),
        force_new=True,
    )

    # Notify master
    master_record = await booking_repo.get_master(master_id)
    if master_record:
        notification = NotificationService(bot)
        await notification.notify_master_new_booking(
            master_telegram_id=master_record.telegram_id,
            client_name=data.get("name", ""),
            client_phone=data.get("phone", ""),
            client_username=callback.from_user.username,
            services=selected,
            booking_date=booking_date,
            booking_time=booking_time,
            total_price=total_price,
            total_duration=total_duration,
            comment=data.get("comment") or "",
            booking_id=booking.id,
        )

    await state.clear()
    await callback.answer()


@router.callback_query(BookingStates.confirming, F.data == "book_back_to_time")
async def back_to_time(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    data = await state.get_data()
    booking_date = date.fromisoformat(data["booking_date"])
    total_duration = sum(s["duration"] for s in data.get("selected_services", []))
    master_id = data.get("master_id", 1)

    schedule_service = ScheduleService(session)
    available_times = await schedule_service.get_available_slots(master_id, booking_date, total_duration)

    await state.set_state(BookingStates.choosing_time)
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text=f"<b>Выберите время</b> для записи на <b>{format_date(booking_date)}</b> ➡️",
        reply_markup=times_keyboard(available_times),
    )
    await callback.answer()


# ── Repeat booking ────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^booking:\d+:repeat$"))
async def repeat_booking(
    callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    booking_id = int(callback.data.split(":")[1])
    repo = BookingRepository(session)
    booking = await repo.get_booking_by_id(booking_id)

    if not booking or booking.client.telegram_id != callback.from_user.id:
        await callback.answer("Запись не найдена.", show_alert=True)
        return

    from bot.db.repositories.service_repo import ServiceRepository as _SR
    svc_repo = _SR(session)
    services = []
    for bs in booking.booking_services:
        svc = await svc_repo.get_service_by_id(bs.service_id)
        if svc and svc.is_active:
            services.append({
                "id": svc.id,
                "name": svc.name,
                "price": float(bs.price_at_booking),
                "duration": bs.duration_at_booking,
            })

    if not services:
        await callback.answer("Услуги из этой записи больше недоступны.", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        master_id=booking.master_id,
        selected_services=services,
        name=booking.client.display_name,
        phone=booking.client.phone,
        client_exists=True,
    )
    await _show_dates(callback.message.chat.id, state, bot, session)
    await callback.answer()
