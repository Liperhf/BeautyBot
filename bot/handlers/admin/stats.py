import logging
from datetime import date

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.master_repo import get_admin_master_id
from bot.db.repositories.stats_repo import StatsRepository
from bot.handlers.admin import IsAdmin
from bot.keyboards.admin import admin_back_keyboard
from bot.utils.message_manager import message_manager

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(IsAdmin())


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, bot: Bot, session: AsyncSession) -> None:
    master_id = await get_admin_master_id(session)
    if not master_id:
        await callback.answer("Мастер не найден.", show_alert=True)
        return

    repo = StatsRepository(session)
    today = date.today()

    status_counts = await repo.get_status_counts(master_id)
    revenue = await repo.get_total_revenue(master_id)
    expected_revenue = await repo.get_expected_revenue(master_id)
    clients_count = await repo.get_unique_clients_count(master_id)
    monthly = await repo.get_monthly_stats(master_id, today.year, today.month)
    top_services = await repo.get_top_services(master_id)

    total = sum(status_counts.values())
    completed = status_counts.get("completed", 0)
    cancelled = status_counts.get("cancelled_by_client", 0) + status_counts.get("cancelled_by_master", 0)
    no_show = status_counts.get("no_show", 0)
    confirmed = status_counts.get("confirmed", 0)

    month_names = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]
    month_label = f"{month_names[today.month]} {today.year}"

    lines = [
        "📊 <b>Статистика</b>\n",
        "<b>За всё время:</b>",
        f"  Записей всего: {total}",
        f"  ✅ Выполнено: {completed}",
        f"  📅 Предстоит: {confirmed}",
        f"  🚫 Отменено: {cancelled}",
        f"  ❌ Неявки: {no_show}",
        f"  💰 Выручка: {int(revenue)} руб.",
        f"  🔮 Ожидается: {int(expected_revenue)} руб.",
        f"  👥 Уникальных клиентов: {clients_count}",
        "",
        f"<b>{month_label}:</b>",
        f"  Записей: {monthly['completed'] + monthly['confirmed'] + monthly['cancelled'] + monthly['no_show']}",
        f"  ✅ Выполнено: {monthly['completed']}",
        f"  🚫 Отменено: {monthly['cancelled']}",
        f"  💰 Выручка: {int(monthly['revenue'])} руб.",
        f"  🔮 Ожидается: {int(monthly['expected_revenue'])} руб.",
    ]

    if top_services:
        lines.append("")
        lines.append("<b>Топ услуг:</b>")
        for i, (name, cnt) in enumerate(top_services, 1):
            lines.append(f"  {i}. {name} — {cnt} зап.")

    await message_manager.send_message(
        bot=bot, chat_id=callback.message.chat.id,
        text="\n".join(lines),
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()
