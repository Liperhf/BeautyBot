from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.time_utils import DAY_NAMES


def admin_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Услуги и категории", callback_data="admin:services")
    builder.button(text="📅 Расписание", callback_data="admin:schedule")
    builder.button(text="📋 Записи клиентов", callback_data="admin:bookings")
    builder.button(text="📊 Статистика", callback_data="admin:stats")
    builder.button(text="👤 О мастере", callback_data="admin:about")
    builder.button(text="🖼 Фотогалерея", callback_data="admin:gallery")
    builder.button(text="🏠 В главное меню", callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀ Назад в админ-панель", callback_data="admin:menu")
    builder.button(text="🏠 В главное меню", callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_bookings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записи на сегодня", callback_data="admin:bookings:today")
    builder.button(text="📆 Предстоящие записи", callback_data="admin:bookings:upcoming")
    builder.button(text="◀ Назад", callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


# ── Services keyboards ────────────────────────────────────────────────────────

def admin_categories_keyboard(categories: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        icon = "✅" if cat.is_active else "⛔"
        svc_count = len([s for s in cat.services]) if cat.services else 0
        builder.button(
            text=f"{icon} {cat.name} ({svc_count} усл.)",
            callback_data=f"admin:cat:{cat.id}:view",
        )
    builder.button(text="➕ Новая категория", callback_data="admin:cat:new")
    builder.button(text="◀ Назад", callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_category_actions_keyboard(category_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "⛔ Отключить" if is_active else "✅ Включить"
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"admin:cat:{category_id}:edit_name")],
        [InlineKeyboardButton(text="✏️ Изменить описание", callback_data=f"admin:cat:{category_id}:edit_desc")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin:cat:{category_id}:toggle")],
        [InlineKeyboardButton(text="📋 Услуги в категории", callback_data=f"admin:cat:{category_id}:services")],
        [InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"admin:cat:{category_id}:delete")],
        [InlineKeyboardButton(text="◀ Назад к списку", callback_data="admin:services"),
         InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_services_keyboard(services: list, category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for svc in services:
        icon = "✅" if svc.is_active else "⛔"
        builder.button(
            text=f"{icon} {svc.name} — {int(svc.price)} руб.",
            callback_data=f"admin:svc:{svc.id}:view",
        )
    builder.button(text="➕ Новая услуга", callback_data=f"admin:svc:new:{category_id}")
    builder.button(text="◀ К категории", callback_data=f"admin:cat:{category_id}:view")
    builder.adjust(1)
    return builder.as_markup()


def admin_service_actions_keyboard(service_id: int, category_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "⛔ Отключить" if is_active else "✅ Включить"
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="✏️ Название", callback_data=f"admin:svc:{service_id}:edit_name"),
         InlineKeyboardButton(text="✏️ Цена", callback_data=f"admin:svc:{service_id}:edit_price")],
        [InlineKeyboardButton(text="✏️ Длительность", callback_data=f"admin:svc:{service_id}:edit_duration"),
         InlineKeyboardButton(text="✏️ Описание", callback_data=f"admin:svc:{service_id}:edit_desc")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin:svc:{service_id}:toggle")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:svc:{service_id}:delete")],
        [InlineKeyboardButton(text="◀ К услугам", callback_data=f"admin:cat:{category_id}:services"),
         InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_confirm_delete_keyboard(
    confirm_data: str, cancel_data: str, confirm_text: str = "✅ Да, удалить"
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=confirm_text, callback_data=confirm_data),
         InlineKeyboardButton(text="◀ Нет", callback_data=cancel_data)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Schedule keyboards ────────────────────────────────────────────────────────

def admin_schedule_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить день недели", callback_data="admin:schedule:edit_day")
    builder.button(text="🗓 Исключения (выходные/особые дни)", callback_data="admin:schedule:exceptions")
    builder.button(text="◀ Назад", callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_dow_picker_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=DAY_NAMES[d], callback_data=f"admin:schedule:day:{d}") for d in range(4)],
        [InlineKeyboardButton(text=DAY_NAMES[d], callback_data=f"admin:schedule:day:{d}") for d in range(4, 7)],
        [InlineKeyboardButton(text="◀ Назад", callback_data="admin:schedule")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_day_actions_keyboard(dow: int, is_working: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🕐 Задать часы работы", callback_data=f"admin:schedule:day:{dow}:set_hours")],
        [InlineKeyboardButton(text="⏸ Перерыв между записями", callback_data=f"admin:schedule:day:{dow}:set_break")],
        [InlineKeyboardButton(text="🚫 Сделать выходным", callback_data=f"admin:schedule:day:{dow}:set_off")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="admin:schedule:edit_day")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_exceptions_keyboard(exceptions: list) -> InlineKeyboardMarkup:
    from bot.utils.time_utils import format_date, format_time
    builder = InlineKeyboardBuilder()
    for exc in exceptions:
        if exc.is_day_off:
            label = f"🚫 {format_date(exc.date)}"
        else:
            label = f"🕐 {format_date(exc.date)} {format_time(exc.start_time)}–{format_time(exc.end_time)}"
        builder.button(text=label, callback_data=f"admin:schedule:exc:{exc.id}:view")
    builder.button(text="➕ Добавить исключение", callback_data="admin:schedule:add_exc")
    builder.button(text="◀ Назад", callback_data="admin:schedule")
    builder.adjust(1)
    return builder.as_markup()


def admin_exception_detail_keyboard(exc_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:schedule:exc:{exc_id}:delete")],
        [InlineKeyboardButton(text="◀ Назад к списку", callback_data="admin:schedule:exceptions")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_add_exception_type_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🚫 Выходной день", callback_data="admin:schedule:add_dayoff"),
         InlineKeyboardButton(text="🕐 Особые часы", callback_data="admin:schedule:add_custom")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="admin:schedule:exceptions")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── About keyboards ───────────────────────────────────────────────────────────

def admin_about_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Текст «О мастере»", callback_data="admin:about:edit_text")
    builder.button(text="✏️ Телефон", callback_data="admin:about:edit_phone")
    builder.button(text="✏️ Instagram", callback_data="admin:about:edit_instagram")
    builder.button(text="✏️ Адрес", callback_data="admin:about:edit_address")
    builder.button(text="📷 Фото мастера", callback_data="admin:about:edit_photo")
    builder.button(text="◀ Назад", callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


# ── Existing list keyboard ────────────────────────────────────────────────────

_BOOKING_PAGE_SIZE = 8


def admin_booking_list_keyboard(
    bookings: list, back_callback: str = "admin:bookings", page: int = 0
) -> InlineKeyboardMarkup:
    from bot.utils.time_utils import format_time, format_date
    builder = InlineKeyboardBuilder()

    start = page * _BOOKING_PAGE_SIZE
    end = start + _BOOKING_PAGE_SIZE
    page_bookings = bookings[start:end]
    total_pages = max(1, (len(bookings) + _BOOKING_PAGE_SIZE - 1) // _BOOKING_PAGE_SIZE)

    # Encode mode from back_callback for pagination buttons
    mode = "t" if back_callback == "admin:bookings:today" else "u"

    for b in page_bookings:
        builder.button(
            text=f"{format_date(b.date)} {format_time(b.start_time)} — {b.client.display_name}",
            callback_data=f"admin:booking:{b.id}:view",
        )
    builder.adjust(1)

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀ Пред.", callback_data=f"admin:bpg:{page-1}:{mode}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="admin:bpg:noop"))
        if end < len(bookings):
            nav.append(InlineKeyboardButton(text="След. ▶", callback_data=f"admin:bpg:{page+1}:{mode}"))
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="◀ Назад", callback_data=back_callback))
    return builder.as_markup()


# ── Gallery keyboards ─────────────────────────────────────────────────────────

def admin_gallery_keyboard(photos: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in photos:
        label = f"📷 {p.caption or f'Фото #{p.id}'}"
        builder.button(text=label, callback_data=f"admin:gallery:photo:{p.id}:view")
    builder.button(text="➕ Добавить фото", callback_data="admin:gallery:add")
    builder.button(text="◀ Назад", callback_data="admin:menu")
    builder.adjust(1)
    return builder.as_markup()


def admin_gallery_photo_keyboard(photo_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:gallery:photo:{photo_id}:delete")],
        [InlineKeyboardButton(text="◀ Назад к галерее", callback_data="admin:gallery")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_booking_actions_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="🚫 Отменить (от имени мастера)", callback_data=f"admin:booking:{booking_id}:cancel")],
        [InlineKeyboardButton(text="✅ Выполнена", callback_data=f"admin:booking:{booking_id}:complete"),
         InlineKeyboardButton(text="❌ Неявка", callback_data=f"admin:booking:{booking_id}:noshow")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="admin:bookings:today")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
