from datetime import date, time
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.db.models import Booking, BookingService, Master


class BookingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_bookings_for_date(self, master_id: int, booking_date: date) -> list[Booking]:
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.master_id == master_id,
                Booking.date == booking_date,
                Booking.status == "confirmed",
            )
            .order_by(Booking.start_time)
        )
        return list(result.scalars().all())

    async def get_client_upcoming_bookings(self, client_id: int) -> list[Booking]:
        today = date.today()
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.client_id == client_id,
                Booking.date >= today,
                Booking.status == "confirmed",
            )
            .options(
                selectinload(Booking.booking_services).selectinload(BookingService.service),
                selectinload(Booking.master),
            )
            .order_by(Booking.date, Booking.start_time)
        )
        return list(result.scalars().all())

    async def get_client_bookings_history(self, client_id: int, limit: int = 5) -> list[Booking]:
        """Recent completed bookings — used for the 'Записаться снова' feature."""
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.client_id == client_id,
                Booking.status == "completed",
            )
            .options(
                selectinload(Booking.booking_services).selectinload(BookingService.service),
            )
            .order_by(Booking.date.desc(), Booking.start_time.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_booking_by_id(self, booking_id: int) -> Booking | None:
        result = await self.session.execute(
            select(Booking)
            .where(Booking.id == booking_id)
            .options(
                selectinload(Booking.booking_services).selectinload(BookingService.service),
                selectinload(Booking.client),
                selectinload(Booking.master),
            )
        )
        return result.scalar_one_or_none()

    async def _check_overlap_for_update(
        self,
        master_id: int,
        booking_date: date,
        start_time: time,
        end_time: time,
    ) -> bool:
        """Lock overlapping confirmed bookings via SELECT FOR UPDATE.
        Returns True if any overlap exists (slot is taken)."""
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.master_id == master_id,
                Booking.date == booking_date,
                Booking.status == "confirmed",
                Booking.start_time < end_time,
                Booking.end_time > start_time,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none() is not None

    async def create_booking(
        self,
        client_id: int,
        master_id: int,
        booking_date: date,
        start_time: time,
        end_time: time,
        total_price: float,
        total_duration: int,
        comment: str | None,
        services: list[dict],
    ) -> Booking:
        # Race-condition guard: lock overlapping rows before inserting
        if await self._check_overlap_for_update(master_id, booking_date, start_time, end_time):
            raise ValueError("Slot is already taken")

        booking = Booking(
            client_id=client_id,
            master_id=master_id,
            date=booking_date,
            start_time=start_time,
            end_time=end_time,
            total_price=total_price,
            total_duration_minutes=total_duration,
            comment=comment or None,
            status="confirmed",
        )
        self.session.add(booking)
        await self.session.flush()

        for svc in services:
            bs = BookingService(
                booking_id=booking.id,
                service_id=svc["id"],
                price_at_booking=svc["price"],
                duration_at_booking=svc["duration"],
            )
            self.session.add(bs)

        await self.session.flush()
        return booking

    async def cancel_booking(self, booking: Booking, by_master: bool = False) -> Booking:
        booking.status = "cancelled_by_master" if by_master else "cancelled_by_client"
        await self.session.flush()
        return booking

    async def mark_completed(self, booking: Booking) -> Booking:
        booking.status = "completed"
        await self.session.flush()
        return booking

    async def mark_no_show(self, booking: Booking) -> Booking:
        booking.status = "no_show"
        await self.session.flush()
        return booking

    async def get_bookings_for_date_detailed(self, master_id: int, booking_date: date) -> list[Booking]:
        """Like get_bookings_for_date but with eager-loaded client and services."""
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.master_id == master_id,
                Booking.date == booking_date,
                Booking.status == "confirmed",
            )
            .options(
                selectinload(Booking.client),
                selectinload(Booking.booking_services).selectinload(BookingService.service),
            )
            .order_by(Booking.start_time)
        )
        return list(result.scalars().all())

    async def get_upcoming_confirmed(self, master_id: int) -> list[Booking]:
        """All future confirmed bookings with eager-loaded client and services."""
        today = date.today()
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.master_id == master_id,
                Booking.date >= today,
                Booking.status == "confirmed",
            )
            .options(
                selectinload(Booking.client),
                selectinload(Booking.booking_services).selectinload(BookingService.service),
            )
            .order_by(Booking.date, Booking.start_time)
        )
        return list(result.scalars().all())

    async def get_master(self, master_id: int) -> Master | None:
        result = await self.session.execute(
            select(Master).where(Master.id == master_id)
        )
        return result.scalar_one_or_none()

    async def get_upcoming_unnotified(
        self, master_id: int, hours_ahead: int,
        flag_field: Literal["reminder_24h_sent", "reminder_2h_sent"],
    ) -> list[Booking]:
        """Bookings confirmed, not yet notified, starting ~hours_ahead hours from now (±1h window)."""
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from bot.config import settings as cfg

        tz = ZoneInfo(cfg.TIMEZONE)
        now = datetime.now(tz)
        window_start = now + timedelta(hours=hours_ahead - 1)
        window_end = now + timedelta(hours=hours_ahead + 1)

        flag_col = getattr(Booking, flag_field)
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.master_id == master_id,
                Booking.status == "confirmed",
                Booking.date >= window_start.date(),
                Booking.date <= window_end.date(),
                flag_col == False,
            )
            .options(
                selectinload(Booking.client),
                selectinload(Booking.booking_services).selectinload(BookingService.service),
            )
        )
        bookings = list(result.scalars().all())

        # Fine-filter: only bookings whose start datetime falls inside the window
        return [
            b for b in bookings
            if window_start
            <= datetime.combine(b.date, b.start_time, tzinfo=tz)
            <= window_end
        ]
