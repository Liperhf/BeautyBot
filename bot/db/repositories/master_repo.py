from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.config import settings
from bot.db.models import Master


class MasterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> Master | None:
        result = await self.session.execute(
            select(Master).where(Master.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def update(self, master: Master, **kwargs) -> Master:
        for key, value in kwargs.items():
            setattr(master, key, value)
        await self.session.flush()
        return master


async def get_admin_master_id(session: AsyncSession) -> int | None:
    """Return the master ID for the configured admin, or None if not found."""
    master = await MasterRepository(session).get_by_telegram_id(settings.ADMIN_TELEGRAM_ID)
    return master.id if master else None
