from datetime import date, time, datetime

import pytz

from bot.config import settings

DAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def get_tz() -> pytz.BaseTzInfo:
    return pytz.timezone(settings.TIMEZONE)


def now_local() -> datetime:
    return datetime.now(get_tz())


def format_date(d: date) -> str:
    """15.03 (Пт)"""
    return f"{d.strftime('%d.%m')} ({DAY_NAMES[d.weekday()]})"


def format_date_full(d: date) -> str:
    """15 марта (Пятница)"""
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    days_full = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return f"{d.day} {months[d.month - 1]} ({days_full[d.weekday()]})"


def format_time(t: time) -> str:
    return t.strftime("%H:%M")


def format_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}ч {m}мин"
    if h:
        return f"{h}ч"
    return f"{m}мин"
