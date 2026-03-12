from datetime import date, time

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.time_utils import format_date, format_time


# ── Helpers ──────────────────────────────────────────────────────────────────

def _nav_row(*buttons: tuple[str, str]) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=t, callback_data=c) for t, c in buttons]


# ── Main menu ─────────────────────────────────────────────────────────────────

def main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💅 Записаться на услугу", callback_data="book_start")
    builder.button(text="🗒 Мои записи", callback_data="my_bookings")
    builder.button(text="🚫 Отменить запись", callback_data="cancel_booking_menu")
    builder.button(text="✨ Услуги и цены", callback_data="services_info")
    builder.button(text="📸 Фотогалерея", callback_data="gallery")
    builder.button(text="🌸 О мастере", callback_data="about_master")
    builder.button(text="💬 Контактная информация", callback_data="contacts")
    if is_admin:
        builder.button(text="⚙️ Админ-панель", callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="menu")
    return builder.as_markup()


# ── Booking flow ──────────────────────────────────────────────────────────────

def name_step_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="menu")
    return builder.as_markup()


def phone_step_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀ Назад", callback_data="book_back_to_name")
    builder.button(text="🏠 В главное меню", callback_data="menu")
    builder.adjust(2)
    return builder.as_markup()


def categories_keyboard(
    categories: list, back_callback: str = "book_start_fresh"
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        rows.append([InlineKeyboardButton(text=cat.name, callback_data=f"cat:{cat.id}")])
    rows.append(_nav_row(("◀ Назад", back_callback), ("🏠 Меню", "menu")))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_keyboard(
    services: list, selected_ids: list[int], category_id: int
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for svc in services:
        icon = "✅" if svc.id in selected_ids else "⚪"
        rows.append([
            InlineKeyboardButton(
                text=f"{icon} {svc.name} — {int(svc.price)} руб.",
                callback_data=f"srv:{svc.id}",
            )
        ])
    rows.append([InlineKeyboardButton(text="✅ Готово — к выбору даты", callback_data="book_services_done")])
    rows.append([InlineKeyboardButton(text="🔄 Выбрать из другой группы", callback_data="book_other_category")])
    rows.append(_nav_row(("◀ Назад", f"cat_back:{category_id}"), ("🏠 Меню", "menu")))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def comment_step_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="▶ Пропустить — к выбору даты", callback_data="book_skip_comment")],
        _nav_row(("◀ Назад", "book_back_to_services"), ("🏠 Меню", "menu")),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dates_keyboard(dates: list[date]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=format_date(d), callback_data=f"date:{d.isoformat()}")
        for d in dates
    ]
    rows: list[list[InlineKeyboardButton]] = [
        buttons[i: i + 3] for i in range(0, len(buttons), 3)
    ]
    rows.append(_nav_row(("◀ Назад", "book_back_to_comment"), ("🏠 Меню", "menu")))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def times_keyboard(times: list[time], _booking_date: date | None = None) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=format_time(t), callback_data=f"time:{t.strftime('%H:%M')}")
        for t in times
    ]
    rows: list[list[InlineKeyboardButton]] = [
        buttons[i: i + 4] for i in range(0, len(buttons), 4)
    ]
    rows.append([InlineKeyboardButton(text="◀ Выбрать другую дату", callback_data="book_back_to_dates")])
    rows.append([InlineKeyboardButton(text="🏠 Меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_booking_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="✅ Подтвердить запись", callback_data="book_confirm")],
        _nav_row(("◀ Назад", "book_back_to_time"), ("🏠 Меню", "menu")),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── My bookings ───────────────────────────────────────────────────────────────

def my_bookings_keyboard(bookings: list) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for booking in bookings:
        label = f"{format_date(booking.date)} {format_time(booking.start_time)}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"booking:{booking.id}:view")])
    rows.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def booking_detail_keyboard(booking_id: int, can_cancel: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_cancel:
        rows.append([InlineKeyboardButton(
            text="🚫 Отменить эту запись", callback_data=f"booking:{booking_id}:cancel"
        )])
    rows.append(_nav_row(("◀ К списку записей", "my_bookings"), ("🏠 Меню", "menu")))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_confirm_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        _nav_row(
            ("✅ Да, отменить", f"booking:{booking_id}:confirm_cancel"),
            ("◀ Нет, вернуться", f"booking:{booking_id}:view"),
        )
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Services info ─────────────────────────────────────────────────────────────

def services_info_back_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        _nav_row(("◀ К категориям", "services_info"), ("🏠 Меню", "menu")),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_info_categories_keyboard(categories: list) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        rows.append([InlineKeyboardButton(text=cat.name, callback_data=f"si:cat:{cat.id}")])
    rows.append(_nav_row(("🏠 В главное меню", "menu"),))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_info_services_keyboard(services: list, cat_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for svc in services:
        label = f"{svc.name} — {int(svc.price)} руб."
        rows.append([InlineKeyboardButton(text=label, callback_data=f"si:svc:{svc.id}")])
    rows.append(_nav_row(("◀ К категориям", "services_info"), ("🏠 Меню", "menu")))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_info_service_detail_keyboard(cat_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        _nav_row(("◀ Назад к услугам", f"si:cat:{cat_id}"), ("🏠 Меню", "menu")),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Gallery ───────────────────────────────────────────────────────────────────

def gallery_keyboard(index: int, total: int) -> InlineKeyboardMarkup:
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"gallery:{index - 1}"))
    nav.append(InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="gallery:noop"))
    if index < total - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"gallery:{index + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[nav, _nav_row(("🏠 В главное меню", "menu"))])
