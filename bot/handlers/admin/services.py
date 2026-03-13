import logging
from decimal import Decimal, InvalidOperation

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Service
from bot.db.repositories.master_repo import get_admin_master_id
from bot.db.repositories.service_repo import ServiceRepository
from bot.handlers.admin import IsAdmin
from bot.keyboards.admin import (
    admin_back_keyboard,
    admin_categories_keyboard,
    admin_category_actions_keyboard,
    admin_confirm_delete_keyboard,
    admin_service_actions_keyboard,
    admin_services_keyboard,
)
from bot.states.admin import AdminServiceStates
from bot.utils.message_manager import message_manager

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())



async def _show_category(chat_id: int, bot: Bot, cat_id: int, session: AsyncSession) -> None:
    cat = await ServiceRepository(session).get_category_by_id(cat_id)
    if not cat:
        return
    status = "активна" if cat.is_active else "отключена"
    await message_manager.send_message(
        bot=bot, chat_id=chat_id,
        text=(
            f"📦 <b>{cat.name}</b>\n\n"
            f"<b>Статус:</b> {status}\n"
            f"<b>Описание:</b> {cat.description or '—'}"
        ),
        reply_markup=admin_category_actions_keyboard(cat_id, cat.is_active),
    )


async def _show_service(chat_id: int, bot: Bot, svc: Service) -> None:
    status = "активна" if svc.is_active else "отключена"
    await message_manager.send_message(
        bot=bot, chat_id=chat_id,
        text=(
            f"🔧 <b>{svc.name}</b>\n\n"
            f"<b>Цена:</b> {int(svc.price)} руб.\n"
            f"<b>Длительность:</b> {svc.duration_minutes} мин.\n"
            f"<b>Статус:</b> {status}\n"
            f"<b>Описание:</b> {svc.description or '—'}"
        ),
        reply_markup=admin_service_actions_keyboard(svc.id, svc.category_id, svc.is_active),
    )


# ── Category list ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:services")
async def admin_services(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await state.clear()
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer("Мастер не найден.", show_alert=True)
        return
    categories = await ServiceRepository(session).get_all_categories_admin(master_id)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="📦 <b>Услуги и категории</b>\n\nВыберите категорию:",
        reply_markup=admin_categories_keyboard(categories),
    )
    await callback.answer()


# ── Category view ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:cat:\d+:view$"))
async def category_view(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    cat_id = int(callback.data.split(":")[2])
    if not await ServiceRepository(session).get_category_by_id(cat_id):
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    await _show_category(callback.message.chat.id, bot, cat_id, session)
    await callback.answer()


# ── Create category ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:cat:new")
async def category_new(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await state.set_state(AdminServiceStates.waiting_category_name)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Введите <b>название</b> новой категории:",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminServiceStates.waiting_category_name, F.text)
async def category_name_input(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    name = message.text.strip()
    if not name or len(name) > 100:
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Название должно быть от 1 до 100 символов. Попробуйте ещё раз:",
            reply_markup=admin_back_keyboard(),
        )
        return
    data = await state.get_data()
    if "edit_category_id" in data:
        cat_id = data["edit_category_id"]
        await ServiceRepository(session).update_category(cat_id, name=name)
        await session.commit()
        logger.info("Category #%d name updated by admin", cat_id)
        await state.clear()
        await _show_category(message.chat.id, bot, cat_id, session)
    else:
        # Creating new category — ask for description next
        await state.update_data(cat_name=name)
        await state.set_state(AdminServiceStates.waiting_category_description)
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text=f"Название: <b>{name}</b>\n\nВведите <b>описание</b> (или <code>-</code> чтобы пропустить):",
            reply_markup=admin_back_keyboard(),
        )


@router.message(AdminServiceStates.waiting_category_description, F.text)
async def category_desc_input(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    raw = message.text.strip()
    description = None if raw == "-" else raw
    data = await state.get_data()
    if "edit_category_id" in data:
        cat_id = data["edit_category_id"]
        await ServiceRepository(session).update_category(cat_id, description=description)
        await session.commit()
        logger.info("Category #%d description updated by admin", cat_id)
        await state.clear()
        await _show_category(message.chat.id, bot, cat_id, session)
    else:
        # Finish creating category
        master_id = await get_admin_master_id(session)
        if not master_id:
            await state.clear()
            return
        repo = ServiceRepository(session)
        await repo.create_category(master_id, data["cat_name"], description)
        await session.commit()
        logger.info("Category '%s' created by admin", data["cat_name"])
        await state.clear()
        categories = await repo.get_all_categories_admin(master_id)
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="✅ Категория создана.\n\n📦 <b>Услуги и категории</b>",
            reply_markup=admin_categories_keyboard(categories),
        )


# ── Edit category name / description ─────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:cat:\d+:edit_name$"))
async def category_edit_name_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    cat_id = int(callback.data.split(":")[2])
    await state.clear()
    await state.update_data(edit_category_id=cat_id)
    await state.set_state(AdminServiceStates.waiting_category_name)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Введите новое <b>название</b> категории:",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:cat:\d+:edit_desc$"))
async def category_edit_desc_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    cat_id = int(callback.data.split(":")[2])
    await state.clear()
    await state.update_data(edit_category_id=cat_id)
    await state.set_state(AdminServiceStates.waiting_category_description)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Введите новое <b>описание</b> категории (или <code>-</code> чтобы очистить):",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


# ── Toggle category ───────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:cat:\d+:toggle$"))
async def category_toggle(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    cat_id = int(callback.data.split(":")[2])
    cat = await ServiceRepository(session).get_category_by_id(cat_id)
    if not cat:
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    action = "отключена" if cat.is_active else "включена"
    cat.is_active = not cat.is_active
    await session.flush()
    await session.commit()
    logger.info("Category #%d toggled (%s) by admin", cat_id, action)
    await _show_category(callback.message.chat.id, bot, cat_id, session)
    await callback.answer(f"Категория {action}.")


# ── Delete category ───────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:cat:\d+:delete$"))
async def category_delete_confirm(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    cat_id = int(callback.data.split(":")[2])
    repo = ServiceRepository(session)
    cat = await repo.get_category_by_id(cat_id)
    if not cat:
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    count = await repo.count_services_in_category(cat_id)
    if count > 0:
        await message_manager.send_message(
            bot=bot, chat_id=callback.message.chat.id,
            text=(
                f"⚠️ <b>Удаление категории «{cat.name}»</b>\n\n"
                f"В категории <b>{count} услуг</b>. Для удаления категории сначала удалите все услуги.\n\n"
                f"Перейти к списку услуг?"
            ),
            reply_markup=admin_confirm_delete_keyboard(
                confirm_data=f"admin:cat:{cat_id}:services",
                cancel_data=f"admin:cat:{cat_id}:view",
                confirm_text="📋 Перейти к услугам",
            ),
        )
    else:
        await message_manager.send_message(
            bot=bot, chat_id=callback.message.chat.id,
            text=f"🗑 Удалить категорию «{cat.name}»? Действие необратимо.",
            reply_markup=admin_confirm_delete_keyboard(
                confirm_data=f"admin:cat:{cat_id}:delete_ok",
                cancel_data=f"admin:cat:{cat_id}:view",
            ),
        )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:cat:\d+:delete_ok$"))
async def category_delete_do(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    cat_id = int(callback.data.split(":")[2])
    repo = ServiceRepository(session)
    await repo.delete_category(cat_id)
    await session.commit()
    logger.info("Category #%d deleted by admin", cat_id)
    master_id = await get_admin_master_id(session)
    categories = await repo.get_all_categories_admin(master_id)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="🗑 Категория удалена.\n\n📦 <b>Услуги и категории</b>",
        reply_markup=admin_categories_keyboard(categories),
    )
    await callback.answer("Удалено.")


# ── Services list in category ─────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:cat:\d+:services$"))
async def category_services_list(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    cat_id = int(callback.data.split(":")[2])
    repo = ServiceRepository(session)
    cat = await repo.get_category_by_id(cat_id)
    if not cat:
        await callback.answer("Категория не найдена.", show_alert=True)
        return
    services = await repo.get_all_services_in_category_admin(cat_id)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text=f"📋 <b>Услуги в категории «{cat.name}»</b>",
        reply_markup=admin_services_keyboard(services, cat_id),
    )
    await callback.answer()


# ── Service view ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:svc:\d+:view$"))
async def service_view(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    svc_id = int(callback.data.split(":")[2])
    svc = await ServiceRepository(session).get_service_by_id(svc_id)
    if not svc:
        await callback.answer("Услуга не найдена.", show_alert=True)
        return
    await _show_service(callback.message.chat.id, bot, svc)
    await callback.answer()


# ── Create service (multi-step FSM) ──────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:svc:new:\d+$"))
async def service_new(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    cat_id = int(callback.data.split(":")[3])
    await state.clear()
    await state.update_data(new_svc_cat_id=cat_id)
    await state.set_state(AdminServiceStates.waiting_service_name)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Введите <b>название</b> новой услуги:",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.message(AdminServiceStates.waiting_service_name, F.text)
async def service_name_input(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    name = message.text.strip()
    if not name or len(name) > 150:
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Название должно быть от 1 до 150 символов:",
            reply_markup=admin_back_keyboard(),
        )
        return
    data = await state.get_data()
    if "edit_service_id" in data:
        svc_id = data["edit_service_id"]
        await ServiceRepository(session).update_service(svc_id, name=name)
        await session.commit()
        logger.info("Service #%d name updated by admin", svc_id)
        await state.clear()
        svc = await ServiceRepository(session).get_service_by_id(svc_id)
        await _show_service(message.chat.id, bot, svc)
    else:
        await state.update_data(svc_name=name)
        await state.set_state(AdminServiceStates.waiting_service_price)
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text=f"Название: <b>{name}</b>\n\nВведите <b>цену</b> (руб.), например <code>1500</code>:",
            reply_markup=admin_back_keyboard(),
        )


@router.message(AdminServiceStates.waiting_service_price, F.text)
async def service_price_input(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Введите корректную цену (положительное число), например <code>1500</code>:",
            reply_markup=admin_back_keyboard(),
        )
        return
    data = await state.get_data()
    if "edit_service_id" in data:
        svc_id = data["edit_service_id"]
        await ServiceRepository(session).update_service(svc_id, price=price)
        await session.commit()
        logger.info("Service #%d price updated by admin", svc_id)
        await state.clear()
        svc = await ServiceRepository(session).get_service_by_id(svc_id)
        await _show_service(message.chat.id, bot, svc)
    else:
        await state.update_data(svc_price=str(price))
        await state.set_state(AdminServiceStates.waiting_service_duration)
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text=f"Цена: <b>{int(price)} руб.</b>\n\nВведите <b>длительность</b> в минутах, например <code>60</code>:",
            reply_markup=admin_back_keyboard(),
        )


@router.message(AdminServiceStates.waiting_service_duration, F.text)
async def service_duration_input(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    try:
        duration = int(message.text.strip())
        if duration <= 0 or duration > 480:
            raise ValueError
    except ValueError:
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text="Введите длительность в минутах (1–480):",
            reply_markup=admin_back_keyboard(),
        )
        return
    data = await state.get_data()
    if "edit_service_id" in data:
        svc_id = data["edit_service_id"]
        await ServiceRepository(session).update_service(svc_id, duration_minutes=duration)
        await session.commit()
        logger.info("Service #%d duration updated by admin", svc_id)
        await state.clear()
        svc = await ServiceRepository(session).get_service_by_id(svc_id)
        await _show_service(message.chat.id, bot, svc)
    else:
        await state.update_data(svc_duration=duration)
        await state.set_state(AdminServiceStates.waiting_service_description)
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text=f"Длительность: <b>{duration} мин.</b>\n\nВведите <b>описание</b> (или <code>-</code> чтобы пропустить):",
            reply_markup=admin_back_keyboard(),
        )


@router.message(AdminServiceStates.waiting_service_description, F.text)
async def service_desc_input(message: Message, state: FSMContext, bot: Bot, session: AsyncSession) -> None:
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    raw = message.text.strip()
    description = None if raw == "-" else raw
    data = await state.get_data()
    repo = ServiceRepository(session)
    if "edit_service_id" in data:
        svc_id = data["edit_service_id"]
        await repo.update_service(svc_id, description=description)
        await session.commit()
        logger.info("Service #%d description updated by admin", svc_id)
        await state.clear()
        svc = await repo.get_service_by_id(svc_id)
        await _show_service(message.chat.id, bot, svc)
    else:
        cat_id = data["new_svc_cat_id"]
        await repo.create_service(
            category_id=cat_id,
            name=data["svc_name"],
            price=Decimal(data["svc_price"]),
            duration_minutes=data["svc_duration"],
            description=description,
        )
        await session.commit()
        logger.info("Service '%s' created in category #%d by admin", data["svc_name"], cat_id)
        await state.clear()
        cat = await repo.get_category_by_id(cat_id)
        services = await repo.get_all_services_in_category_admin(cat_id)
        await message_manager.send_message(
            bot=bot, chat_id=message.chat.id,
            text=f"✅ Услуга создана.\n\n📋 <b>Услуги в категории «{cat.name}»</b>",
            reply_markup=admin_services_keyboard(services, cat_id),
        )


# ── Edit service individual fields ────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:svc:\d+:edit_name$"))
async def service_edit_name(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    svc_id = int(callback.data.split(":")[2])
    await state.clear()
    await state.update_data(edit_service_id=svc_id)
    await state.set_state(AdminServiceStates.waiting_service_name)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Введите новое <b>название</b> услуги:",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:svc:\d+:edit_price$"))
async def service_edit_price(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    svc_id = int(callback.data.split(":")[2])
    await state.clear()
    await state.update_data(edit_service_id=svc_id)
    await state.set_state(AdminServiceStates.waiting_service_price)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Введите новую <b>цену</b> (руб.):",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:svc:\d+:edit_duration$"))
async def service_edit_duration(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    svc_id = int(callback.data.split(":")[2])
    await state.clear()
    await state.update_data(edit_service_id=svc_id)
    await state.set_state(AdminServiceStates.waiting_service_duration)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Введите новую <b>длительность</b> в минутах:",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:svc:\d+:edit_desc$"))
async def service_edit_desc(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    svc_id = int(callback.data.split(":")[2])
    await state.clear()
    await state.update_data(edit_service_id=svc_id)
    await state.set_state(AdminServiceStates.waiting_service_description)
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Введите новое <b>описание</b> (или <code>-</code> чтобы очистить):",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


# ── Toggle service ────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:svc:\d+:toggle$"))
async def service_toggle(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    svc_id = int(callback.data.split(":")[2])
    repo = ServiceRepository(session)
    svc = await repo.get_service_by_id(svc_id)
    if not svc:
        await callback.answer("Услуга не найдена.", show_alert=True)
        return
    action = "отключена" if svc.is_active else "включена"
    svc.is_active = not svc.is_active
    await session.flush()
    await session.commit()
    logger.info("Service #%d toggled (%s) by admin", svc_id, action)
    svc = await repo.get_service_by_id(svc_id)
    await _show_service(callback.message.chat.id, bot, svc)
    await callback.answer(f"Услуга {action}.")


# ── Delete service ────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^admin:svc:\d+:delete$"))
async def service_delete_confirm(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    svc_id = int(callback.data.split(":")[2])
    count = await ServiceRepository(session).count_bookings_for_service(svc_id)
    if count > 0:
        await callback.answer(
            f"Нельзя удалить: у услуги {count} записей. Отключите её вместо удаления.",
            show_alert=True,
        )
        return
    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="Удалить эту услугу? Действие необратимо.",
        reply_markup=admin_confirm_delete_keyboard(
            confirm_data=f"admin:svc:{svc_id}:delete_ok",
            cancel_data=f"admin:svc:{svc_id}:view",
        ),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:svc:\d+:delete_ok$"))
async def service_delete_do(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    svc_id = int(callback.data.split(":")[2])
    repo = ServiceRepository(session)
    svc = await repo.get_service_by_id(svc_id)
    cat_id = svc.category_id if svc else None
    await repo.delete_service(svc_id)
    await session.commit()
    logger.info("Service #%d deleted by admin", svc_id)
    if cat_id:
        cat = await repo.get_category_by_id(cat_id)
        services = await repo.get_all_services_in_category_admin(cat_id)
        await message_manager.send_message(
            bot=bot, chat_id=callback.message.chat.id,
            text=f"🗑 Услуга удалена.\n\n📋 <b>Услуги в категории «{cat.name}»</b>",
            reply_markup=admin_services_keyboard(services, cat_id),
        )
    await callback.answer("Удалено.")
