from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from bot.db.models import Booking, BookingService, Service


class StatsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_status_counts(self, master_id: int) -> dict[str, int]:
        result = await self.session.execute(
            select(Booking.status, func.count().label("cnt"))
            .where(Booking.master_id == master_id)
            .group_by(Booking.status)
        )
        return {row.status: row.cnt for row in result}

    async def get_total_revenue(self, master_id: int) -> Decimal:
        result = await self.session.execute(
            select(func.coalesce(func.sum(Booking.total_price), 0))
            .where(Booking.master_id == master_id, Booking.status == "completed")
        )
        return result.scalar() or Decimal(0)

    async def get_unique_clients_count(self, master_id: int) -> int:
        result = await self.session.execute(
            select(func.count(func.distinct(Booking.client_id)))
            .where(Booking.master_id == master_id)
        )
        return result.scalar() or 0

    async def get_monthly_stats(
        self, master_id: int, year: int, month: int
    ) -> dict[str, int | Decimal]:
        first_day = date(year, month, 1)
        # Last day of month
        if month == 12:
            last_day = date(year + 1, 1, 1)
        else:
            last_day = date(year, month + 1, 1)

        counts = await self.session.execute(
            select(Booking.status, func.count().label("cnt"))
            .where(
                Booking.master_id == master_id,
                Booking.date >= first_day,
                Booking.date < last_day,
            )
            .group_by(Booking.status)
        )
        status_map = {row.status: row.cnt for row in counts}

        revenue = await self.session.execute(
            select(func.coalesce(func.sum(Booking.total_price), 0))
            .where(
                Booking.master_id == master_id,
                Booking.status == "completed",
                Booking.date >= first_day,
                Booking.date < last_day,
            )
        )
        return {
            "confirmed": status_map.get("confirmed", 0),
            "completed": status_map.get("completed", 0),
            "cancelled": (
                status_map.get("cancelled_by_client", 0)
                + status_map.get("cancelled_by_master", 0)
            ),
            "no_show": status_map.get("no_show", 0),
            "revenue": revenue.scalar() or Decimal(0),
        }

    async def get_top_services(self, master_id: int, limit: int = 5) -> list[tuple[str, int]]:
        result = await self.session.execute(
            select(Service.name, func.count().label("cnt"))
            .join(BookingService, BookingService.service_id == Service.id)
            .join(Booking, Booking.id == BookingService.booking_id)
            .where(Booking.master_id == master_id)
            .group_by(Service.name)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [(row.name, row.cnt) for row in result]
