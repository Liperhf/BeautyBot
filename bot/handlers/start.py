import logging

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.config import is_admin_user
from bot.keyboards.client import main_menu_keyboard
from bot.utils.message_manager import message_manager

logger = logging.getLogger(__name__)

router = Router()
fallback_router = Router()

WELCOME_TEXT = (
    "✨ <b>Привет! Я бот онлайн-записи к мастеру Анне.</b>\n\n"
    "Здесь вы можете:\n"
    "💅 Записаться на удобное время\n"
    "📅 Посмотреть свои записи\n"
    "✨ Ознакомиться с услугами и ценами\n"
    "🌸 Узнать о мастере и посмотреть работы\n\n"
    "Выберите действие:"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await message_manager.delete_user_message(bot, message.chat.id, message.message_id)
    await message_manager.send_message(
        bot=bot,
        chat_id=message.chat.id,
        text=WELCOME_TEXT,
        reply_markup=main_menu_keyboard(is_admin=is_admin_user(message.from_user.id)),
    )


@router.callback_query(F.data == "menu")
async def to_main_menu(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text="Главное меню. Выберите действие:",
        reply_markup=main_menu_keyboard(is_admin=is_admin_user(callback.from_user.id)),
    )
    await callback.answer()


# ── Fallback for stale / unknown callbacks ────────────────────────────────────

@fallback_router.callback_query()
async def stale_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    logger.warning("Stale callback from user %d: %s", callback.from_user.id, callback.data)
    await state.clear()
    await message_manager.send_message(
        bot=bot,
        chat_id=callback.message.chat.id,
        text="⚠️ Сессия устарела. Вы в главном меню.",
        reply_markup=main_menu_keyboard(is_admin=is_admin_user(callback.from_user.id)),
    )
    await callback.answer()
