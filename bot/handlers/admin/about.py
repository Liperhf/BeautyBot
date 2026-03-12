import logging
import re

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.repositories.master_repo import MasterRepository
from bot.handlers.admin import IsAdmin
from bot.keyboards.admin import admin_about_keyboard, admin_back_keyboard
from bot.states.admin import AdminMasterStates
from bot.utils.message_manager import message_manager

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")

_CANCEL_KB_CB = "admin:about"  # going back clears state and returns to profile


async def _show_profile(chat_id: int, bot: Bot, session: AsyncSession) -> None:
    repo = MasterRepository(session)
    master = await repo.get_by_telegram_id(settings.ADMIN_TELEGRAM_ID)
    if not master:
        await message_manager.send_message(
            bot=bot, chat_id=chat_id,
            text="Профиль мастера не найден в базе данных.",
            reply_markup=admin_back_keyboard(),
        )
        return

    photo_status = "✅ загружено" if master.photo_file_id else "не загружено"
    text = (
        f"👤 <b>Профиль мастера</b>\n\n"
        f"<b>Имя:</b> {master.name or '—'}\n"
        f"<b>Телефон:</b> {master.contact_phone or '—'}\n"
        f"<b>Instagram:</b> {master.contact_instagram or '—'}\n"
        f"<b>Адрес:</b> {master.contact_address or '—'}\n"
        f"<b>Фото:</b> {photo_status}\n\n"
        f"<b>О мастере:</b>\n{master.about_text or '—'}"
    )
    if master.photo_file_id:
        await message_manager.send_photo(
            bot=bot, chat_id=chat_id,
            photo=master.photo_file_id,
            caption=text,
            reply_markup=admin_about_keyboard(),
        )
    else:
        await message_manager.send_message(
            bot=bot, chat_id=chat_id,
            text=text,
            reply_markup=admin_about_keyboard(),
        )


# ── Entry point ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:about")
async def admin_about(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await state.clear()
    await _show_profile(callback.message.chat.id, bot, session)
    await callback.answer()


# ── Edit about text ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:about:edit_text")
async def edit_text_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(AdminMasterStates.waiting_about_text)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="✏️ Введите новый текст <b>«О мастере»</b> (до 4000 символов).\n\nМожно использовать переносы строк.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminMasterStates.waiting_about_text, F.text)
async def edit_text_save(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    text = message.text.strip()
    if not text or len(text) > 4000:
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Текст должен быть от 1 до 4000 символов. Попробуйте ещё раз.",
            reply_markup=admin_back_keyboard(),
        )
        return
    repo = MasterRepository(session)
    master = await repo.get_by_telegram_id(settings.ADMIN_TELEGRAM_ID)
    if master:
        await repo.update(master, about_text=text)
        await session.commit()
    await state.clear()
    logger.info("Master about_text updated by admin")
    await _show_profile(message.chat.id, bot, session)


# ── Edit phone ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:about:edit_phone")
async def edit_phone_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(AdminMasterStates.waiting_phone)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="✏️ Введите новый <b>номер телефона</b> (пример: +375291234567):",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminMasterStates.waiting_phone, F.text)
async def edit_phone_save(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    phone = message.text.strip()
    if not PHONE_RE.match(phone):
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Неверный формат телефона. Введите в формате <b>+375291234567</b>:",
            reply_markup=admin_back_keyboard(),
        )
        return
    repo = MasterRepository(session)
    master = await repo.get_by_telegram_id(settings.ADMIN_TELEGRAM_ID)
    if master:
        await repo.update(master, contact_phone=phone)
        await session.commit()
    await state.clear()
    await _show_profile(message.chat.id, bot, session)


# ── Edit Instagram ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:about:edit_instagram")
async def edit_instagram_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(AdminMasterStates.waiting_instagram)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="✏️ Введите ник в <b>Instagram</b> (с @ или без):",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminMasterStates.waiting_instagram, F.text)
async def edit_instagram_save(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    username = message.text.strip().lstrip("@")
    if not username:
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Введите ник Instagram:",
            reply_markup=admin_back_keyboard(),
        )
        return
    repo = MasterRepository(session)
    master = await repo.get_by_telegram_id(settings.ADMIN_TELEGRAM_ID)
    if master:
        await repo.update(master, contact_instagram=f"@{username}")
        await session.commit()
    await state.clear()
    await _show_profile(message.chat.id, bot, session)


# ── Edit address ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:about:edit_address")
async def edit_address_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(AdminMasterStates.waiting_address)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="✏️ Введите новый <b>адрес</b> кабинета:",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminMasterStates.waiting_address, F.text)
async def edit_address_save(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    address = message.text.strip()
    if not address:
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Введите адрес:",
            reply_markup=admin_back_keyboard(),
        )
        return
    repo = MasterRepository(session)
    master = await repo.get_by_telegram_id(settings.ADMIN_TELEGRAM_ID)
    if master:
        await repo.update(master, contact_address=address)
        await session.commit()
    await state.clear()
    await _show_profile(message.chat.id, bot, session)


# ── Edit photo ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:about:edit_photo")
async def edit_photo_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(AdminMasterStates.waiting_photo)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="📷 Отправьте новое <b>фото мастера</b>:",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminMasterStates.waiting_photo, F.photo)
async def edit_photo_save(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    file_id = message.photo[-1].file_id  # largest available size
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    repo = MasterRepository(session)
    master = await repo.get_by_telegram_id(settings.ADMIN_TELEGRAM_ID)
    if master:
        await repo.update(master, photo_file_id=file_id)
        await session.commit()
    await state.clear()
    logger.info("Master photo updated by admin")
    await _show_profile(message.chat.id, bot, session)


@router.message(AdminMasterStates.waiting_photo)
async def edit_photo_wrong_type(message: Message, bot: Bot) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    await message_manager.send_message(
        bot=bot, chat_id=message.chat.id,
        text="Пожалуйста, отправьте именно фотографию (не файл и не текст).",
        reply_markup=admin_back_keyboard(),
    )
