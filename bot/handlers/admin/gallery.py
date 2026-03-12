import logging

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.gallery_repo import GalleryRepository
from bot.db.repositories.master_repo import get_admin_master_id
from bot.handlers.admin import IsAdmin
from bot.keyboards.admin import (
    admin_back_keyboard,
    admin_confirm_delete_keyboard,
    admin_gallery_keyboard,
    admin_gallery_photo_keyboard,
)
from bot.states.admin import AdminGalleryStates
from bot.utils.message_manager import message_manager

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())



async def _show_gallery_list(chat_id: int, bot: Bot, session: AsyncSession, master_id: int) -> None:
    photos = await GalleryRepository(session).get_all(master_id)
    count = len(photos)
    text = f"🖼 <b>Фотогалерея</b>\n\nФотографий: {count}" if count else "🖼 <b>Фотогалерея</b>\n\nФотографий пока нет."
    await message_manager.send_message(
        bot=bot, chat_id=chat_id,
        text=text,
        reply_markup=admin_gallery_keyboard(photos),
    )


@router.callback_query(F.data == "admin:gallery")
async def admin_gallery(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await state.clear()
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer("Мастер не найден.", show_alert=True)
        return
    await _show_gallery_list(callback.message.chat.id, bot, session, master_id)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:gallery:photo:\d+:view$"))
async def gallery_photo_view(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    photo_id = int(callback.data.split(":")[3])
    photo = await GalleryRepository(session).get_by_id(photo_id)
    if not photo:
        await callback.answer("Фото не найдено.", show_alert=True)
        return
    caption = photo.caption or f"Фото #{photo.id}"
    await message_manager.send_photo(
        bot=bot, chat_id=callback.message.chat.id,
        photo=photo.file_id,
        caption=caption,
        reply_markup=admin_gallery_photo_keyboard(photo_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:gallery:photo:\d+:delete$"))
async def gallery_photo_delete_confirm(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    photo_id = int(callback.data.split(":")[3])
    photo = await GalleryRepository(session).get_by_id(photo_id)
    if not photo:
        await callback.answer("Фото не найдено.", show_alert=True)
        return
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Удалить это фото из галереи?",
        reply_markup=admin_confirm_delete_keyboard(
            confirm_data=f"admin:gallery:photo:{photo_id}:delete_ok",
            cancel_data=f"admin:gallery:photo:{photo_id}:view",
        ),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:gallery:photo:\d+:delete_ok$"))
async def gallery_photo_delete_do(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    photo_id = int(callback.data.split(":")[3])
    await GalleryRepository(session).delete(photo_id)
    await session.commit()
    logger.info("Gallery photo #%d deleted by admin", photo_id)
    master_id = await get_admin_master_id(session)
    await _show_gallery_list(callback.message.chat.id, bot, session, master_id)
    await callback.answer("Фото удалено.")


@router.callback_query(F.data == "admin:gallery:add")
async def gallery_add_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await state.set_state(AdminGalleryStates.waiting_photo)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="📷 Отправьте фотографию для добавления в галерею.\n\nМожно также добавить подпись в следующем сообщении.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminGalleryStates.waiting_photo, F.photo)
async def gallery_add_photo(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    file_id = message.photo[-1].file_id
    caption = message.caption.strip() if message.caption else None
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    master_id = await get_admin_master_id(session)
    if not master_id:
        await state.clear()
        return
    await GalleryRepository(session).add(master_id, file_id, caption)
    await session.commit()
    logger.info("Gallery photo added by admin (master %d)", master_id)
    await state.clear()
    await _show_gallery_list(message.chat.id, bot, session, master_id)


@router.message(AdminGalleryStates.waiting_photo)
async def gallery_add_wrong_type(message: Message, bot: Bot) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    await message_manager.send_message(
        bot=bot, chat_id=message.chat.id,
        text="Пожалуйста, отправьте именно фотографию (не файл и не текст).",
        reply_markup=admin_back_keyboard(),
    )
