import logging
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from bot.config import settings
from bot.db.models import (
    Master, ServiceCategory, Service, ScheduleTemplate,
)

logger = logging.getLogger(__name__)

# Schedule: Thu=3, Fri=4, Sat=5
WORKING_DAYS = [3, 4, 5]

SEED_CATEGORIES = [
    {
        "name": "Ламинирование ресниц и бровей",
        "description": "Придаёт ресницам и бровям ухоженный вид на 4-6 недель",
        "sort_order": 1,
        "services": [
            {"name": "Ламинирование ресниц", "duration_minutes": 60, "price": 45.00,
             "description": "Классическое ламинирование, придаёт объём и изгиб", "sort_order": 1},
            {"name": "Ламинирование бровей", "duration_minutes": 40, "price": 35.00,
             "description": "Укладка и фиксация формы бровей", "sort_order": 2},
            {"name": "Комплекс ресницы + брови", "duration_minutes": 90, "price": 70.00,
             "description": "Ламинирование ресниц и бровей в одну процедуру", "sort_order": 3},
            {"name": "Окрашивание бровей хной", "duration_minutes": 30, "price": 20.00,
             "description": "Долговременное окрашивание натуральной хной", "sort_order": 4},
        ],
    },
    {
        "name": "Депиляция женская",
        "description": "Мягкое удаление волос воском и сахарной пастой",
        "sort_order": 2,
        "services": [
            {"name": "Голень", "duration_minutes": 30, "price": 22.00, "sort_order": 1},
            {"name": "Бедро", "duration_minutes": 30, "price": 27.00, "sort_order": 2},
            {"name": "Голень + бедро", "duration_minutes": 50, "price": 45.00, "sort_order": 3},
            {"name": "Подмышки", "duration_minutes": 20, "price": 18.00, "sort_order": 4},
            {"name": "Руки (до локтя)", "duration_minutes": 25, "price": 20.00, "sort_order": 5},
            {"name": "Бикини классика", "duration_minutes": 30, "price": 30.00, "sort_order": 6},
            {"name": "Бикини глубокое", "duration_minutes": 40, "price": 42.00, "sort_order": 7},
            {"name": "Усики / подбородок", "duration_minutes": 15, "price": 12.00, "sort_order": 8},
        ],
    },
    {
        "name": "Депиляция мужская",
        "description": "Удаление нежелательных волос для мужчин",
        "sort_order": 3,
        "services": [
            {"name": "Спина", "duration_minutes": 40, "price": 45.00, "sort_order": 1},
            {"name": "Грудь", "duration_minutes": 30, "price": 38.00, "sort_order": 2},
            {"name": "Живот", "duration_minutes": 20, "price": 28.00, "sort_order": 3},
            {"name": "Подмышки", "duration_minutes": 20, "price": 18.00, "sort_order": 4},
            {"name": "Руки (до локтя)", "duration_minutes": 30, "price": 28.00, "sort_order": 5},
            {"name": "Спина + грудь", "duration_minutes": 60, "price": 75.00, "sort_order": 6},
        ],
    },
    {
        "name": "Массаж лица и головы",
        "description": "Расслабляющие и лифтинговые техники",
        "sort_order": 4,
        "services": [
            {"name": "Массаж лица (лифтинг)", "duration_minutes": 45, "price": 40.00,
             "description": "Улучшает овал лица, снимает отёки", "sort_order": 1},
            {"name": "Массаж головы", "duration_minutes": 30, "price": 28.00,
             "description": "Снимает напряжение, стимулирует кровообращение", "sort_order": 2},
            {"name": "Комплекс лицо + голова", "duration_minutes": 70, "price": 60.00,
             "description": "Полноценный расслабляющий комплекс", "sort_order": 3},
        ],
    },
    {
        "name": "Карбокситерапия",
        "description": "Неинвазивная процедура омоложения с CO₂",
        "sort_order": 5,
        "services": [
            {"name": "Карбокситерапия лица", "duration_minutes": 45, "price": 50.00,
             "description": "Насыщение кожи кислородом, лифтинг, сияние", "sort_order": 1},
            {"name": "Карбокситерапия зона тела", "duration_minutes": 30, "price": 40.00,
             "description": "Коррекция локальных зон (живот, бёдра)", "sort_order": 2},
            {"name": "Курс карбокси лица (5 сеансов)", "duration_minutes": 45, "price": 220.00,
             "description": "Курсовая программа со скидкой — 5 процедур", "sort_order": 3},
        ],
    },
]


async def seed_database(session: AsyncSession) -> None:
    result = await session.execute(select(func.count()).select_from(Master))
    count = result.scalar()
    if count and count > 0:
        logger.info("Database already seeded, skipping.")
        return

    logger.info("Seeding database with demo data...")

    master = Master(
        telegram_id=settings.ADMIN_TELEGRAM_ID,
        name="Анна",
        about_text=(
            "Привет! Меня зовут Анна, я профессиональный бьюти-мастер с опытом более 5 лет.\n\n"
            "Специализируюсь на ламинировании ресниц и бровей, всех видах депиляции, "
            "массаже лица и карбокситерапии.\n\n"
            "Работаю только с проверенными материалами премиум-класса. "
            "Жду вас в своём уютном кабинете!"
        ),
        contact_phone="+375291234567",
        contact_instagram="@anna_beauty_master",
        contact_address="г. Минск, ул. Примерная, 10, каб. 5 (3-й этаж)",
        timezone="Europe/Minsk",
        is_active=True,
    )
    session.add(master)
    await session.flush()

    for day in WORKING_DAYS:
        template = ScheduleTemplate(
            master_id=master.id,
            day_of_week=day,
            start_time=time(10, 0),
            end_time=time(18, 0),
            slot_interval_minutes=30,
            is_working=True,
        )
        session.add(template)

    for cat_data in SEED_CATEGORIES:
        services = cat_data.pop("services")
        category = ServiceCategory(master_id=master.id, **cat_data)
        session.add(category)
        await session.flush()

        for svc_data in services:
            svc = Service(category_id=category.id, **svc_data)
            session.add(svc)

    await session.commit()
    logger.info("Database seeded successfully.")
