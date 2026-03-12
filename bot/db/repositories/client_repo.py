from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.db.models import Client


class ClientRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> Client | None:
        result = await self.session.execute(
            select(Client).where(Client.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        display_name: str,
        phone: str,
    ) -> Client:
        client = Client(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            display_name=display_name,
            phone=phone,
        )
        self.session.add(client)
        await self.session.flush()
        return client

    async def update(self, client: Client, **kwargs) -> Client:
        for key, value in kwargs.items():
            setattr(client, key, value)
        await self.session.flush()
        return client
