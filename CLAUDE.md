# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Telegram bot for booking beauty services. Built with Python + aiogram 3 + PostgreSQL.
Development is split into 4 stages (see below). Always check current stage before implementing.

## Tech Stack
- Python 3.11+, aiogram 3 (routers, FSM, middleware)
- PostgreSQL with asyncpg + SQLAlchemy async
- Alembic for migrations
- APScheduler for reminders
- Docker + docker-compose
- pydantic-settings for config

## Commands

### Run with Docker (primary workflow)
```bash
docker-compose up --build        # build and start bot + postgres
docker-compose up -d             # start detached
docker-compose logs -f bot       # follow bot logs
docker-compose down              # stop
```

### Alembic migrations
```bash
# Inside the running bot container:
docker-compose exec bot alembic revision --autogenerate -m "description"
docker-compose exec bot alembic upgrade head
docker-compose exec bot alembic downgrade -1
```

### Local dev (without Docker — requires local Postgres)
```bash
pip install -r requirements.txt
# Set DB_HOST=localhost in .env
python -m bot
```

## Architecture Rules (CRITICAL)
1. **Message deletion**: Every bot response deletes the previous bot message. Use the `message_manager` singleton from `bot/utils/message_manager.py` — call `message_manager.send_message()` or `message_manager.send_photo()`, never `bot.send_message()` directly in handlers.
2. **FSM**: All booking flow uses StatesGroup. "Main menu" button always resets FSM state. FSM uses `MemoryStorage` — state is lost on bot restart (stale callbacks must be handled gracefully).
3. **Inline keyboards only**: No ReplyKeyboard for client flows. All navigation via InlineKeyboardMarkup with callback_data.
4. **Repository pattern**: All DB access goes through repositories in `bot/db/repositories/`. Never write raw queries in handlers.
5. **Timezone**: Store all datetimes in UTC. Display in Europe/Minsk (UTC+3). Use `time_utils.py` for all conversions.
6. **Multi-master ready**: All queries filter by `master_id`. Never hardcode master data.

## Project Structure
```
bot/
├── __main__.py          # entry point: creates tables, seeds DB, registers middleware/routers, starts scheduler
├── config.py            # Settings (pydantic-settings), is_admin_user() helper
├── loader.py            # bot and dp singletons
├── middlewares/
│   └── db_session.py    # injects AsyncSession into handler data dict
├── handlers/
│   ├── start.py         # /start, main menu
│   ├── booking.py       # full booking flow FSM
│   ├── my_bookings.py   # view/cancel bookings
│   ├── gallery.py       # client gallery view
│   ├── services_info.py # service catalog browsing
│   ├── about.py         # about master page
│   └── admin/           # admin panel (services, schedule, gallery, stats, about, main_menu)
├── keyboards/
│   ├── client.py        # all client-facing InlineKeyboardMarkup builders
│   └── admin.py         # admin InlineKeyboardMarkup builders
├── states/
│   ├── booking.py       # BookingStates FSM group
│   └── admin.py         # AdminStates FSM group
├── services/
│   ├── schedule_service.py    # slot generation logic
│   └── notification_service.py # send notifications to master/client
├── db/
│   ├── base.py          # engine, async_session_maker, Base
│   ├── models.py        # Master, ServiceCategory, Service, ScheduleTemplate, ScheduleException, Client, Booking, BookingService, GalleryPhoto
│   ├── seed.py          # seeds demo data if DB is empty
│   └── repositories/    # one file per model, e.g. booking_repo.py
├── utils/
│   ├── message_manager.py  # MessageManager class + message_manager singleton
│   └── time_utils.py       # UTC↔Europe/Minsk conversions
└── scheduler/
    └── jobs.py          # APScheduler setup: 24h reminders, 2h reminders, morning report
```

## Development Stages
- **Stage 1 (MVP)**: Project structure + config + models + migrations + seed + message deletion + /start + full booking flow + my bookings + cancel + master notifications ✅
- **Stage 2 (Admin)**: Admin panel CRUD for services, schedule management, booking management, edit master profile
- **Stage 3 (Content)**: Services info view, about master, contacts, photo gallery
- **Stage 4 (Notifications)**: APScheduler reminders (24h, 2h), morning report, statistics

Always complete one stage fully before moving to the next.

## Key Business Logic
- **Slot generation**: Sum durations of all selected services. A booking occupies multiple consecutive slots. Do not show slots in the past.
- **Conflict check**: Validate slot availability at confirmation time (not just at selection). Use SELECT FOR UPDATE.
- **Phone validation**: Accept +375XXXXXXXXX or international format (7-15 digits with +).
- **Stale callbacks**: Unknown callback_data after bot restart → show main menu with "Session expired" message, never crash.
- **DB startup**: `__main__.py` calls `Base.metadata.create_all` on startup (idempotent) and then `seed_database()` if DB is empty. Alembic is used for schema migrations separately.

## Error Handling
- `MessageToDeleteNotFound`, `MessageCantBeDeleted` → log and continue, never raise
- `BotBlocked`, `ChatNotFound` when sending notifications → log and continue
- All DB operations in try/except, rollback on error

## Code Style
- Use `logging` module everywhere. Log all bookings, cancellations, errors.
- Type hints on all function signatures.
- No raw SQL — use SQLAlchemy ORM or asyncpg with parameterized queries only.
- Callback data prefixes: `cat:`, `srv:`, `date:`, `time:`, `confirm`, `back`, `menu`, `admin:`

## Permissions
- Auto-approve all edits to .py files — these cannot harm the system.
- Auto-approve Read on any project file.
- Ask before: dropping DB tables, deleting files permanently, pushing to git.
