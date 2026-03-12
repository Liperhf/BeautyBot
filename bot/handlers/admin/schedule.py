import logging
from datetime import datetime, time, date

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.master_repo import get_admin_master_id
from bot.db.repositories.schedule_repo import ScheduleRepository
from bot.handlers.admin import IsAdmin
from bot.keyboards.admin import (
    admin_add_exception_type_keyboard,
    admin_back_keyboard,
    admin_day_actions_keyboard,
    admin_dow_picker_keyboard,
    admin_exception_detail_keyboard,
    admin_exceptions_keyboard,
    admin_schedule_keyboard,
)
from bot.states.admin import AdminScheduleStates
from bot.utils.message_manager import message_manager
from bot.utils.time_utils import DAY_NAMES, format_date, format_time

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())



def _parse_time_range(text: str) -> tuple[time, time] | None:
    """Parse 'HH:MM-HH:MM' into (start, end). Returns None on invalid input."""
    text = text.strip().replace(" ", "")
    if "-" not in text:
        return None
    parts = text.split("-", 1)
    try:
        start = datetime.strptime(parts[0], "%H:%M").time()
        end = datetime.strptime(parts[1], "%H:%M").time()
    except ValueError:
        return None
    if start >= end:
        return None
    return start, end


def _parse_date(text: str) -> date | None:
    """Parse 'DD.MM.YYYY' into a date. Returns None on invalid input."""
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y").date()
    except ValueError:
        return None


async def _show_schedule_overview(chat_id: int, bot: Bot, session: AsyncSession) -> None:
    master_id = await get_admin_master_id(session)
    if not master_id:
        await message_manager.send_message(
            bot=bot, chat_id=chat_id,
            text="Мастер не найден.",
            reply_markup=admin_back_keyboard(),
        )
        return

    repo = ScheduleRepository(session)
    templates = await repo.get_templates(master_id)
    template_map = {t.day_of_week: t for t in templates}

    lines = ["📅 <b>Шаблон рабочей недели:</b>\n"]
    for d in range(7):
        t = template_map.get(d)
        if t and t.is_working:
            lines.append(f"  <b>{DAY_NAMES[d]}:</b> {format_time(t.start_time)} – {format_time(t.end_time)}")
        else:
            lines.append(f"  <b>{DAY_NAMES[d]}:</b> выходной")

    future_exceptions = await repo.get_future_exceptions(master_id)
    lines.append(f"\n🗓 Ближайших исключений: {len(future_exceptions)}")

    await message_manager.send_message(
        bot=bot, chat_id=chat_id,
        text="\n".join(lines),
        reply_markup=admin_schedule_keyboard(),
    )


# ── Entry point ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:schedule")
async def admin_schedule(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await state.clear()
    await _show_schedule_overview(callback.message.chat.id, bot, session)
    await callback.answer()


# ── Day-of-week editor ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:schedule:edit_day")
async def schedule_edit_day(callback: CallbackQuery, bot: Bot) -> None:
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Выберите день недели для редактирования:",
        reply_markup=admin_dow_picker_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:schedule:day:[0-6]$"))
async def schedule_day_view(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    dow = int(callback.data.split(":")[3])
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer("Мастер не найден.", show_alert=True)
        return

    template = await ScheduleRepository(session).get_template_for_day_any(master_id, dow)
    is_working = template.is_working if template else False

    if template and is_working:
        info = f"{format_time(template.start_time)} – {format_time(template.end_time)}"
    else:
        info = "выходной"

    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text=f"<b>{DAY_NAMES[dow]}</b>: {info}\n\nВыберите действие:",
        reply_markup=admin_day_actions_keyboard(dow, is_working),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:schedule:day:[0-6]:set_off$"))
async def schedule_set_off(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    dow = int(callback.data.split(":")[3])
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer("Мастер не найден.", show_alert=True)
        return
    await ScheduleRepository(session).set_day_off(master_id, dow)
    await session.commit()
    logger.info("Day %d set to day-off by admin", dow)
    await _show_schedule_overview(callback.message.chat.id, bot, session)
    await callback.answer(f"{DAY_NAMES[dow]} теперь выходной.")


@router.callback_query(F.data.regexp(r"^admin:schedule:day:[0-6]:set_hours$"))
async def schedule_set_hours_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    dow = int(callback.data.split(":")[3])
    await state.update_data(editing_dow=dow, editing_field="template")
    await state.set_state(AdminScheduleStates.waiting_custom_hours)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text=f"Введите рабочие часы для <b>{DAY_NAMES[dow]}</b> в формате <b>ЧЧ:ММ-ЧЧ:ММ</b>\n\nПример: <code>10:00-18:00</code>",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminScheduleStates.waiting_custom_hours, F.text)
async def schedule_set_hours_save(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    data = await state.get_data()
    parsed = _parse_time_range(message.text)

    if not parsed:
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Неверный формат. Введите часы в виде <b>ЧЧ:ММ-ЧЧ:ММ</b>, например <code>10:00-18:00</code>:",
            reply_markup=admin_back_keyboard(),
        )
        return

    start_time, end_time = parsed
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback_answer_error(message, bot, state)
        return

    editing_field = data.get("editing_field")
    if editing_field == "template":
        dow = data.get("editing_dow")
        await ScheduleRepository(session).upsert_template(master_id, dow, start_time, end_time)
        await session.commit()
        logger.info("Template day %d set to %s-%s by admin", dow, start_time, end_time)
        await state.clear()
        await _show_schedule_overview(message.chat.id, bot, session)
    elif editing_field == "exception":
        exc_date_str = data.get("exc_date")
        exc_date = date.fromisoformat(exc_date_str)
        await ScheduleRepository(session).add_exception(
            master_id, exc_date, is_day_off=False, start_time=start_time, end_time=end_time
        )
        await session.commit()
        logger.info("Custom exception added for %s by admin", exc_date)
        await state.clear()
        await _show_exceptions(message.chat.id, bot, session, master_id)


async def callback_answer_error(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    await message_manager.send_message(
        bot=bot, chat_id=message.chat.id,
        text="Ошибка: мастер не найден.",
        reply_markup=admin_back_keyboard(),
    )


# ── Exceptions ────────────────────────────────────────────────────────────────

async def _show_exceptions(chat_id: int, bot: Bot, session: AsyncSession, master_id: int) -> None:
    exceptions = await ScheduleRepository(session).get_future_exceptions(master_id)
    if not exceptions:
        text = "🗓 <b>Исключения в расписании</b>\n\nНет запланированных исключений."
    else:
        text = f"🗓 <b>Исключения в расписании ({len(exceptions)}):</b>\n\nНажмите на дату для удаления."
    await message_manager.send_message(
        bot=bot, chat_id=chat_id,
        text=text,
        reply_markup=admin_exceptions_keyboard(exceptions),
    )


@router.callback_query(F.data == "admin:schedule:exceptions")
async def schedule_exceptions(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await state.clear()
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer("Мастер не найден.", show_alert=True)
        return
    await _show_exceptions(callback.message.chat.id, bot, session, master_id)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:schedule:exc:\d+:view$"))
async def exception_view(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    exc_id = int(callback.data.split(":")[3])
    exc = await ScheduleRepository(session).get_exception_by_id(exc_id)
    if not exc:
        await callback.answer("Исключение не найдено.", show_alert=True)
        return
    if exc.is_day_off:
        info = f"🚫 Выходной день\n<b>Дата:</b> {format_date(exc.date)}"
    else:
        info = (
            f"🕐 Особые часы работы\n"
            f"<b>Дата:</b> {format_date(exc.date)}\n"
            f"<b>Часы:</b> {format_time(exc.start_time)} – {format_time(exc.end_time)}"
        )
    if exc.reason:
        info += f"\n<b>Причина:</b> {exc.reason}"

    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text=info,
        reply_markup=admin_exception_detail_keyboard(exc_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:schedule:exc:\d+:delete$"))
async def exception_delete(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    exc_id = int(callback.data.split(":")[3])
    await ScheduleRepository(session).delete_exception(exc_id)
    await session.commit()
    logger.info("Exception #%d deleted by admin", exc_id)
    master_id = await get_admin_master_id(session)
    await _show_exceptions(callback.message.chat.id, bot, session, master_id)
    await callback.answer("Исключение удалено.")


# ── Add exception ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:schedule:add_exc")
async def add_exception_type(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Выберите тип исключения:",
        reply_markup=admin_add_exception_type_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"admin:schedule:add_dayoff", "admin:schedule:add_custom"}))
async def add_exception_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    exc_type = "dayoff" if callback.data == "admin:schedule:add_dayoff" else "custom"
    await state.update_data(exc_type=exc_type)
    await state.set_state(AdminScheduleStates.waiting_exception_date)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Введите дату в формате <b>ДД.ММ.ГГГГ</b>\n\nПример: <code>25.03.2026</code>",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminScheduleStates.waiting_exception_date, F.text)
async def add_exception_date(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    exc_date = _parse_date(message.text)
    if not exc_date or exc_date < date.today():
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Неверная дата или дата в прошлом. Введите дату в формате <b>ДД.ММ.ГГГГ</b>:",
            reply_markup=admin_back_keyboard(),
        )
        return

    master_id = await get_admin_master_id(session)
    if not master_id:
        await state.clear()
        return

    # Check for duplicate
    existing = await ScheduleRepository(session).get_exception_for_date(master_id, exc_date)
    if existing:
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text=f"На {format_date(exc_date)} уже есть исключение. Сначала удалите его.",
            reply_markup=admin_back_keyboard(),
        )
        return

    data = await state.get_data()
    exc_type = data.get("exc_type")

    if exc_type == "dayoff":
        await ScheduleRepository(session).add_exception(master_id, exc_date, is_day_off=True)
        await session.commit()
        logger.info("Day-off exception added for %s by admin", exc_date)
        await state.clear()
        await _show_exceptions(message.chat.id, bot, session, master_id)
    else:
        # custom hours — need time range next
        await state.update_data(exc_date=exc_date.isoformat(), editing_field="exception")
        await state.set_state(AdminScheduleStates.waiting_custom_hours)
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text=f"Дата: <b>{format_date(exc_date)}</b>\n\nВведите особые часы работы в формате <b>ЧЧ:ММ-ЧЧ:ММ</b>:",
            reply_markup=admin_back_keyboard(),
        )


@router.message(AdminScheduleStates.waiting_exception_date)
async def add_exception_date_wrong(message: Message, bot: Bot) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    await message_manager.send_message(
        bot=bot, chat_id=message.chat.id,
        text="Введите дату в формате <b>ДД.ММ.ГГГГ</b>, например <code>25.03.2026</code>:",
        reply_markup=admin_back_keyboard(),
    )
