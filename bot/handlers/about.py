import logging

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.models import Master
from bot.db.repositories.master_repo import MasterRepository
from bot.keyboards.client import back_to_menu_keyboard
from bot.utils.message_manager import message_manager

logger = logging.getLogger(__name__)
router = Router()


async def _get_master(session: AsyncSession) -> Master | None:
    return await MasterRepository(session).get_by_telegram_id(settings.ADMIN_TELEGRAM_ID)


@router.callback_query(F.data == "about_master")
async def about_master(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    master = await _get_master(session)
    if not master:
        await message_manager.send_message(
            bot=bot, chat_id=callback.message.chat.id,
            text="🌸 <b>О мастере</b>\n\nИнформация пока не заполнена.",
            reply_markup=back_to_menu_keyboard(),
            force_new=True,
        )
        await callback.answer()
        return

    name = master.name or "Мастер"
    text = f"🌸 <b>{name}</b>\n\n{master.about_text or 'Информация о мастере пока не заполнена.'}"

    if master.photo_file_id:
        await message_manager.send_photo(
            bot=bot, chat_id=callback.message.chat.id,
            photo=master.photo_file_id,
            caption=text,
            reply_markup=back_to_menu_keyboard(),
        )
    else:
        await message_manager.send_message(
            bot=bot, chat_id=callback.message.chat.id,
            text=text,
            reply_markup=back_to_menu_keyboard(),
            force_new=True,
        )
    await callback.answer()


@router.callback_query(F.data == "contacts")
async def contacts(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    master = await _get_master(session)
    lines = ["💬 <b>Контактная информация</b>\n"]
    if master:
        if master.contact_phone:
            lines.append(f"📱 <b>Телефон:</b> {master.contact_phone}")
        if master.contact_instagram:
            lines.append(f"🌐 <b>Instagram:</b> {master.contact_instagram}")
        if master.contact_address:
            lines.append(f"📍 <b>Адрес:</b> {master.contact_address}")
    if len(lines) == 1:
        lines.append("Контактная информация пока не заполнена.")
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="\n".join(lines),
        reply_markup=back_to_menu_keyboard(),
        force_new=True,
    )
    await callback.answer()
