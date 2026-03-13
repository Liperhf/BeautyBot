import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from bot.config import settings
from bot.db.models import (
    Master, ServiceCategory, Service, ScheduleTemplate,
    Client, Booking, BookingService,
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

# Fake telegram_ids start at 1_000_001 — they will never collide with real users
DEMO_CLIENTS = [
    {"telegram_id": 1_000_001, "display_name": "Алина Соколова",    "phone": "+375291111001"},
    {"telegram_id": 1_000_002, "display_name": "Дарья Петрова",     "phone": "+375291111002"},
    {"telegram_id": 1_000_003, "display_name": "Марина Иванова",    "phone": "+375291111003"},
    {"telegram_id": 1_000_004, "display_name": "Виктория Сидорова", "phone": "+375291111004"},
    {"telegram_id": 1_000_005, "display_name": "Ольга Козлова",     "phone": "+375291111005"},
    {"telegram_id": 1_000_006, "display_name": "Наталья Новикова",  "phone": "+375291111006"},
    {"telegram_id": 1_000_007, "display_name": "Юлия Морозова",    "phone": "+375291111007"},
    {"telegram_id": 1_000_008, "display_name": "Светлана Волкова",  "phone": "+375291111008"},
    {"telegram_id": 1_000_009, "display_name": "Анастасия Зайцева", "phone": "+375291111009"},
    {"telegram_id": 1_000_010, "display_name": "Екатерина Попова",  "phone": "+375291111010"},
    {"telegram_id": 1_000_011, "display_name": "Ирина Лебедева",    "phone": "+375291111011"},
    {"telegram_id": 1_000_012, "display_name": "Татьяна Семёнова",  "phone": "+375291111012"},
    {"telegram_id": 1_000_013, "display_name": "Людмила Павлова",   "phone": "+375291111013"},
    {"telegram_id": 1_000_014, "display_name": "Галина Михайлова",  "phone": "+375291111014"},
    {"telegram_id": 1_000_015, "display_name": "Валерия Фёдорова",  "phone": "+375291111015"},
]

# (date_str, time_str, status, service_flat_index)
# Service flat index order matches SEED_CATEGORIES sort_order then Service sort_order:
#   0=Лам.ресниц(60мин,45р)  1=Лам.бровей(40мин,35р)  2=Комплекс(90мин,70р)  3=Хна(30мин,20р)
#   4=Голень(30мин,22р)  5=Бедро(30мин,27р)  6=Голень+бедро(50мин,45р)
#  18=Массаж лица(45мин,40р)  21=Карбокси лица(45мин,50р)
DEMO_BOOKINGS = [
    # ── Прошедшие (completed) ──
    ("2026-03-05", "10:00", "completed",  0),  # Алина    — Лам. ресниц
    ("2026-03-05", "11:30", "completed",  4),  # Дарья    — Голень
    ("2026-03-06", "10:00", "completed",  1),  # Марина   — Лам. бровей
    ("2026-03-06", "12:00", "completed", 18),  # Виктория — Массаж лица
    ("2026-03-07", "10:00", "completed",  2),  # Ольга    — Комплекс
    ("2026-03-07", "13:00", "completed", 21),  # Наталья  — Карбокси лица
    ("2026-03-12", "10:00", "completed",  5),  # Юлия     — Бедро
    ("2026-03-12", "11:00", "completed",  3),  # Светлана — Окрашивание хной
    # ── Текущий день / предстоящие (confirmed) ──
    ("2026-03-13", "10:00", "confirmed",  0),  # Анастасия — Лам. ресниц
    ("2026-03-13", "12:00", "confirmed", 18),  # Екатерина — Массаж лица
    ("2026-03-14", "10:00", "confirmed",  6),  # Ирина     — Голень + бедро
    ("2026-03-14", "12:00", "confirmed",  2),  # Татьяна   — Комплекс
    ("2026-03-19", "10:00", "confirmed", 21),  # Людмила   — Карбокси лица
    ("2026-03-21", "10:00", "confirmed",  1),  # Галина    — Лам. бровей
    ("2026-03-28", "10:00", "confirmed",  4),  # Валерия   — Голень
]


async def seed_database(session: AsyncSession) -> None:
    # ── 1. Seed master, categories, services ────────────────────────────────
    result = await session.execute(select(func.count()).select_from(Master))
    count = result.scalar()
    if not count or count == 0:
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
    else:
        logger.info("Database already seeded, skipping master data.")

    # ── 2. Seed demo bookings ────────────────────────────────────────────────
    result_b = await session.execute(select(func.count()).select_from(Booking))
    if (result_b.scalar() or 0) > 0:
        logger.info("Demo bookings already present, skipping.")
        return

    master_row = await session.execute(
        select(Master).where(Master.telegram_id == settings.ADMIN_TELEGRAM_ID)
    )
    master = master_row.scalar_one()

    all_svcs_row = await session.execute(
        select(Service)
        .join(Service.category)
        .order_by(ServiceCategory.sort_order, Service.sort_order)
    )
    all_services = all_svcs_row.scalars().all()

    for demo in DEMO_CLIENTS:
        session.add(Client(**demo))
    await session.flush()

    clients_row = await session.execute(
        select(Client)
        .where(Client.telegram_id.in_([c["telegram_id"] for c in DEMO_CLIENTS]))
        .order_by(Client.telegram_id)
    )
    clients = clients_row.scalars().all()

    for idx, (date_str, time_str, status, svc_idx) in enumerate(DEMO_BOOKINGS):
        client = clients[idx]
        svc = all_services[svc_idx]
        booking_date = date.fromisoformat(date_str)
        h, m = map(int, time_str.split(":"))
        start = time(h, m)
        end = (datetime.combine(booking_date, start) + timedelta(minutes=svc.duration_minutes)).time()

        booking = Booking(
            client_id=client.id,
            master_id=master.id,
            date=booking_date,
            start_time=start,
            end_time=end,
            total_price=svc.price,
            total_duration_minutes=svc.duration_minutes,
            status=status,
        )
        session.add(booking)
        await session.flush()

        session.add(BookingService(
            booking_id=booking.id,
            service_id=svc.id,
            price_at_booking=svc.price,
            duration_at_booking=svc.duration_minutes,
        ))

    await session.commit()
    logger.info("Demo bookings seeded: %d records.", len(DEMO_BOOKINGS))
