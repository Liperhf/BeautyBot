from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message


class IsAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return True
