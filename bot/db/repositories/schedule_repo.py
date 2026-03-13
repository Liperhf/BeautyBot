from datetime import date, time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.db.models import ScheduleTemplate, ScheduleException


class ScheduleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_templates(self, master_id: int) -> list[ScheduleTemplate]:
        result = await self.session.execute(
            select(ScheduleTemplate)
            .where(ScheduleTemplate.master_id == master_id)
            .order_by(ScheduleTemplate.day_of_week)
        )
        return list(result.scalars().all())

    async def get_template_for_day(self, master_id: int, day_of_week: int) -> ScheduleTemplate | None:
        result = await self.session.execute(
            select(ScheduleTemplate).where(
                ScheduleTemplate.master_id == master_id,
                ScheduleTemplate.day_of_week == day_of_week,
                ScheduleTemplate.is_working == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_template_for_day_any(self, master_id: int, day_of_week: int) -> ScheduleTemplate | None:
        """Return template regardless of is_working status."""
        result = await self.session.execute(
            select(ScheduleTemplate).where(
                ScheduleTemplate.master_id == master_id,
                ScheduleTemplate.day_of_week == day_of_week,
            )
        )
        return result.scalar_one_or_none()

    async def get_exception_for_date(self, master_id: int, check_date: date) -> ScheduleException | None:
        result = await self.session.execute(
            select(ScheduleException).where(
                ScheduleException.master_id == master_id,
                ScheduleException.date == check_date,
            )
        )
        return result.scalar_one_or_none()

    async def add_exception(
        self,
        master_id: int,
        exception_date: date,
        is_day_off: bool,
        start_time: time | None = None,
        end_time: time | None = None,
        reason: str | None = None,
    ) -> ScheduleException:
        exc = ScheduleException(
            master_id=master_id,
            date=exception_date,
            is_day_off=is_day_off,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
        )
        self.session.add(exc)
        await self.session.flush()
        return exc

    async def get_exception_by_id(self, exception_id: int) -> ScheduleException | None:
        result = await self.session.execute(
            select(ScheduleException).where(ScheduleException.id == exception_id)
        )
        return result.scalar_one_or_none()

    async def get_future_exceptions(self, master_id: int) -> list[ScheduleException]:
        today = date.today()
        result = await self.session.execute(
            select(ScheduleException)
            .where(
                ScheduleException.master_id == master_id,
                ScheduleException.date >= today,
            )
            .order_by(ScheduleException.date)
        )
        return list(result.scalars().all())

    async def delete_exception(self, exception_id: int) -> None:
        exc = await self.get_exception_by_id(exception_id)
        if exc:
            await self.session.delete(exc)
            await self.session.flush()

    async def upsert_template(
        self,
        master_id: int,
        day_of_week: int,
        start_time: time,
        end_time: time,
        slot_interval_minutes: int = 30,
    ) -> ScheduleTemplate:
        result = await self.session.execute(
            select(ScheduleTemplate).where(
                ScheduleTemplate.master_id == master_id,
                ScheduleTemplate.day_of_week == day_of_week,
            )
        )
        template = result.scalar_one_or_none()
        if template:
            template.start_time = start_time
            template.end_time = end_time
            template.slot_interval_minutes = slot_interval_minutes
            template.is_working = True
        else:
            template = ScheduleTemplate(
                master_id=master_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                slot_interval_minutes=slot_interval_minutes,
                is_working=True,
            )
            self.session.add(template)
        await self.session.flush()
        return template

    async def set_day_off(self, master_id: int, day_of_week: int) -> ScheduleTemplate:
        result = await self.session.execute(
            select(ScheduleTemplate).where(
                ScheduleTemplate.master_id == master_id,
                ScheduleTemplate.day_of_week == day_of_week,
            )
        )
        template = result.scalar_one_or_none()
        if template:
            template.is_working = False
        else:
            template = ScheduleTemplate(
                master_id=master_id,
                day_of_week=day_of_week,
                start_time=time(9, 0),
                end_time=time(18, 0),
                is_working=False,
            )
            self.session.add(template)
        await self.session.flush()
        return template
