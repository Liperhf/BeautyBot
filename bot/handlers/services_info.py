import logging

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.master_repo import get_admin_master_id
from bot.db.repositories.service_repo import ServiceRepository
from bot.keyboards.client import (
    back_to_menu_keyboard,
    services_info_back_keyboard,
    services_info_categories_keyboard,
    services_info_service_detail_keyboard,
    services_info_services_keyboard,
)
from bot.utils.message_manager import message_manager
from bot.utils.time_utils import format_duration

logger = logging.getLogger(__name__)
router = Router()



@router.callback_query(F.data == "services_info")
async def show_categories(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer("Информация временно недоступна.", show_alert=True)
        return
    categories = await ServiceRepository(session).get_active_categories(master_id)
    if not categories:
        await message_manager.send_message(
            bot=bot, chat_id=callback.message.chat.id,
            text="✨ <b>Услуги и цены</b>\n\nСписок услуг пока не заполнен.",
            reply_markup=back_to_menu_keyboard(),
            force_new=True,
        )
        await callback.answer()
        return
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="✨ <b>Услуги и цены</b>\n\nВыберите категорию:",
        reply_markup=services_info_categories_keyboard(categories),
        force_new=True,
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^si:cat:\d+$"))
async def show_services_in_category(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    cat_id = int(callback.data.split(":")[2])
    repo = ServiceRepository(session)
    cat = await repo.get_category_by_id(cat_id)
    if not cat:
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    services = await repo.get_active_services_by_category(cat_id)
    if not services:
        await message_manager.send_message(
            bot=bot, chat_id=callback.message.chat.id,
            text=f"🌿 <b>{cat.name}</b>\n\nВ этой категории пока нет услуг.",
            reply_markup=services_info_back_keyboard(),
        )
        await callback.answer()
        return
    lines = [f"🌿 <b>{cat.name}</b>"]
    if cat.description:
        lines.append(f"<i>{cat.description}</i>")
    lines.append("")
    for svc in services:
        lines.append(
            f"• <b>{svc.name}</b> — {int(svc.price)} руб. / {format_duration(svc.duration_minutes)}"
        )
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="\n".join(lines),
        reply_markup=services_info_services_keyboard(services, cat_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^si:svc:\d+$"))
async def show_service_detail(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    svc_id = int(callback.data.split(":")[2])
    svc = await ServiceRepository(session).get_service_by_id(svc_id)
    if not svc:
        await callback.answer("Услуга не найдена.", show_alert=True)
        return
    lines = [
        f"✨ <b>{svc.name}</b>\n",
        f"💰 <b>Цена:</b> {int(svc.price)} руб.",
        f"⏱ <b>Длительность:</b> {format_duration(svc.duration_minutes)}",
    ]
    if svc.description:
        lines.append(f"\n{svc.description}")
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="\n".join(lines),
        reply_markup=services_info_service_detail_keyboard(svc.category_id),
    )
    await callback.answer()
