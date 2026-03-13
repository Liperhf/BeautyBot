import logging

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.gallery_repo import GalleryRepository
from bot.db.repositories.master_repo import get_admin_master_id
from bot.keyboards.client import back_to_menu_keyboard, gallery_keyboard
from bot.utils.message_manager import message_manager

logger = logging.getLogger(__name__)
router = Router()


async def _show_gallery_photo(chat_id: int, bot: Bot, photos: list, index: int) -> None:
    photo = photos[index]
    caption = photo.caption or f"Фото {index + 1} из {len(photos)}"
    await message_manager.send_photo(
        bot=bot, chat_id=chat_id,
        photo=photo.file_id,
        caption=caption,
        reply_markup=gallery_keyboard(index, len(photos)),
    )


@router.callback_query(F.data == "gallery")
async def show_gallery(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer("Галерея временно недоступна.", show_alert=True)
        return
    photos = await GalleryRepository(session).get_all(master_id)
    if not photos:
        await message_manager.send_message(
            bot=bot, chat_id=callback.message.chat.id,
            text="🖼 <b>Фотогалерея</b>\n\nФотографии пока не добавлены.",
            reply_markup=back_to_menu_keyboard(),
            force_new=True,
        )
        await callback.answer()
        return
    await _show_gallery_photo(callback.message.chat.id, bot, photos, 0)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^gallery:\d+$"))
async def gallery_page(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    index = int(callback.data.split(":")[1])
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer()
        return
    photos = await GalleryRepository(session).get_all(master_id)
    if not photos or index >= len(photos):
        await callback.answer("Галерея обновилась. Откройте её заново.", show_alert=True)
        return
    await _show_gallery_photo(callback.message.chat.id, bot, photos, index)
    await callback.answer()


@router.callback_query(F.data == "gallery:noop")
async def gallery_noop(callback: CallbackQuery) -> None:
    await callback.answer()
