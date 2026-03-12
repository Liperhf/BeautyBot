from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.db.models import GalleryPhoto


class GalleryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, master_id: int) -> list[GalleryPhoto]:
        result = await self.session.execute(
            select(GalleryPhoto)
            .where(GalleryPhoto.master_id == master_id)
            .order_by(GalleryPhoto.sort_order, GalleryPhoto.id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, photo_id: int) -> GalleryPhoto | None:
        result = await self.session.execute(
            select(GalleryPhoto).where(GalleryPhoto.id == photo_id)
        )
        return result.scalar_one_or_none()

    async def add(self, master_id: int, file_id: str, caption: str | None = None) -> GalleryPhoto:
        photo = GalleryPhoto(master_id=master_id, file_id=file_id, caption=caption)
        self.session.add(photo)
        await self.session.flush()
        return photo

    async def delete(self, photo_id: int) -> None:
        photo = await self.get_by_id(photo_id)
        if photo:
            await self.session.delete(photo)
            await self.session.flush()
