from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from bot.db.models import ServiceCategory, Service, BookingService


class ServiceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_categories(self, master_id: int) -> list[ServiceCategory]:
        result = await self.session.execute(
            select(ServiceCategory)
            .where(ServiceCategory.master_id == master_id, ServiceCategory.is_active == True)
            .order_by(ServiceCategory.sort_order, ServiceCategory.id)
        )
        return list(result.scalars().all())

    async def get_category_by_id(self, category_id: int) -> ServiceCategory | None:
        result = await self.session.execute(
            select(ServiceCategory).where(ServiceCategory.id == category_id)
        )
        return result.scalar_one_or_none()

    async def get_active_services_by_category(self, category_id: int) -> list[Service]:
        result = await self.session.execute(
            select(Service)
            .where(Service.category_id == category_id, Service.is_active == True)
            .order_by(Service.sort_order, Service.id)
        )
        return list(result.scalars().all())

    async def get_service_by_id(self, service_id: int) -> Service | None:
        result = await self.session.execute(
            select(Service).where(Service.id == service_id)
        )
        return result.scalar_one_or_none()

    async def get_services_by_ids(self, service_ids: list[int]) -> list[Service]:
        result = await self.session.execute(
            select(Service).where(Service.id.in_(service_ids))
        )
        return list(result.scalars().all())

    async def get_all_categories_with_services(self, master_id: int) -> list[ServiceCategory]:
        result = await self.session.execute(
            select(ServiceCategory)
            .where(ServiceCategory.master_id == master_id, ServiceCategory.is_active == True)
            .options(selectinload(ServiceCategory.services))
            .order_by(ServiceCategory.sort_order, ServiceCategory.id)
        )
        return list(result.scalars().all())

    # ── Admin CRUD ────────────────────────────────────────────────────────────

    async def get_all_categories_admin(self, master_id: int) -> list[ServiceCategory]:
        """All categories (active + inactive) with services eagerly loaded."""
        result = await self.session.execute(
            select(ServiceCategory)
            .where(ServiceCategory.master_id == master_id)
            .options(selectinload(ServiceCategory.services))
            .order_by(ServiceCategory.sort_order, ServiceCategory.id)
        )
        return list(result.scalars().all())

    async def get_all_services_in_category_admin(self, category_id: int) -> list[Service]:
        """All services (active + inactive) in a category."""
        result = await self.session.execute(
            select(Service)
            .where(Service.category_id == category_id)
            .order_by(Service.sort_order, Service.id)
        )
        return list(result.scalars().all())

    async def count_services_in_category(self, category_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).where(Service.category_id == category_id)
        )
        return result.scalar() or 0

    async def count_bookings_for_service(self, service_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).where(BookingService.service_id == service_id)
        )
        return result.scalar() or 0

    async def create_category(
        self, master_id: int, name: str, description: str | None = None
    ) -> ServiceCategory:
        cat = ServiceCategory(master_id=master_id, name=name, description=description)
        self.session.add(cat)
        await self.session.flush()
        return cat

    async def update_category(self, category_id: int, **kwargs) -> ServiceCategory | None:
        cat = await self.get_category_by_id(category_id)
        if cat:
            for key, value in kwargs.items():
                setattr(cat, key, value)
            await self.session.flush()
        return cat

    async def delete_category(self, category_id: int) -> None:
        cat = await self.get_category_by_id(category_id)
        if cat:
            await self.session.delete(cat)
            await self.session.flush()

    async def create_service(
        self,
        category_id: int,
        name: str,
        price: Decimal,
        duration_minutes: int,
        description: str | None = None,
    ) -> Service:
        svc = Service(
            category_id=category_id,
            name=name,
            price=price,
            duration_minutes=duration_minutes,
            description=description,
        )
        self.session.add(svc)
        await self.session.flush()
        return svc

    async def update_service(self, service_id: int, **kwargs) -> Service | None:
        svc = await self.get_service_by_id(service_id)
        if svc:
            for key, value in kwargs.items():
                setattr(svc, key, value)
            await self.session.flush()
        return svc

    async def delete_service(self, service_id: int) -> None:
        svc = await self.get_service_by_id(service_id)
        if svc:
            await self.session.delete(svc)
            await self.session.flush()
