from datetime import date, time, timedelta, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.schedule_repo import ScheduleRepository
from bot.db.repositories.booking_repo import BookingRepository


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._schedule_repo = ScheduleRepository(session)
        self._booking_repo = BookingRepository(session)

    async def get_available_dates(
        self, master_id: int, duration_minutes: int, days_ahead: int = 21
    ) -> list[date]:
        available: list[date] = []
        today = date.today()
        for i in range(days_ahead):
            check_date = today + timedelta(days=i)
            slots = await self.get_available_slots(master_id, check_date, duration_minutes)
            if slots:
                available.append(check_date)
        return available

    async def get_available_slots(
        self, master_id: int, check_date: date, duration_minutes: int
    ) -> list[time]:
        exception = await self._schedule_repo.get_exception_for_date(master_id, check_date)
        if exception:
            if exception.is_day_off:
                return []
            start_time = exception.start_time
            end_time = exception.end_time
            slot_interval = 30
        else:
            template = await self._schedule_repo.get_template_for_day(
                master_id, check_date.weekday()
            )
            if not template:
                return []
            start_time = template.start_time
            end_time = template.end_time
            slot_interval = template.slot_interval_minutes

        all_slots = self._generate_slots(start_time, end_time, slot_interval, duration_minutes)
        existing = await self._booking_repo.get_bookings_for_date(master_id, check_date)
        now = datetime.now()

        available: list[time] = []
        for slot in all_slots:
            if check_date == date.today():
                if datetime.combine(check_date, slot) <= now:
                    continue
            slot_end = self._add_minutes(slot, duration_minutes)
            if not self._has_conflict(slot, slot_end, existing):
                available.append(slot)
        return available

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_slots(
        start: time, end: time, interval: int, duration: int
    ) -> list[time]:
        slots: list[time] = []
        pivot = date.today()
        current = datetime.combine(pivot, start)
        end_dt = datetime.combine(pivot, end)
        while current < end_dt:
            slot_end = current + timedelta(minutes=duration)
            if slot_end <= end_dt:
                slots.append(current.time())
            current += timedelta(minutes=interval)
        return slots

    @staticmethod
    def _add_minutes(t: time, minutes: int) -> time:
        dt = datetime.combine(date.today(), t) + timedelta(minutes=minutes)
        return dt.time()

    @staticmethod
    def _has_conflict(start: time, end: time, bookings: list) -> bool:
        for b in bookings:
            if start < b.end_time and end > b.start_time:
                return True
        return False
