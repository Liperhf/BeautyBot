# Beauty Bot — Claude Instructions

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

## Architecture Rules (CRITICAL)
1. **Message deletion**: Every bot response deletes the previous bot message. Use `message_manager.py` utility — never send messages directly without going through it.
2. **FSM**: All booking flow uses StatesGroup. "Main menu" button always resets FSM.
3. **Inline keyboards only**: No ReplyKeyboard for client flows. All navigation via InlineKeyboardMarkup with callback_data.
4. **Repository pattern**: All DB access goes through repositories in `bot/db/repositories/`. Never write raw queries in handlers.
5. **Timezone**: Store all datetimes in UTC. Display in Europe/Minsk (UTC+3). Use `time_utils.py` for all conversions.
6. **Multi-master ready**: All queries filter by `master_id`. Never hardcode master data.

## Project Structure
```
beauty_bot/
├── bot/
│   ├── __main__.py
│   ├── config.py
│   ├── loader.py
│   ├── middlewares/         # delete_previous.py, db_session.py
│   ├── handlers/
│   │   ├── start.py
│   │   ├── booking.py
│   │   ├── my_bookings.py
│   │   ├── services_info.py
│   │   ├── about.py
│   │   └── admin/
│   ├── keyboards/           # client.py, admin.py
│   ├── states/              # booking.py, admin.py
│   ├── services/            # business logic layer
│   ├── db/
│   │   ├── base.py
│   │   ├── models.py
│   │   └── repositories/
│   ├── utils/               # message_manager.py, time_utils.py
│   └── scheduler/
├── alembic/
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## Development Stages
- **Stage 1 (MVP)**: Project structure + config + models + migrations + seed + message deletion + /start + full booking flow + my bookings + cancel + master notifications
- **Stage 2 (Admin)**: Admin panel CRUD for services, schedule management, booking management, edit master profile
- **Stage 3 (Content)**: Services info view, about master, contacts, photo gallery
- **Stage 4 (Notifications)**: APScheduler reminders (24h, 2h), morning report, statistics

Always complete one stage fully before moving to the next.

## Key Business Logic
- **Slot generation**: Sum durations of all selected services. A booking occupies multiple consecutive slots. Do not show slots in the past.
- **Conflict check**: Validate slot availability at confirmation time (not just at selection). Use SELECT FOR UPDATE.
- **Phone validation**: Accept +375XXXXXXXXX or international format (7-15 digits with +).
- **Stale callbacks**: Unknown callback_data after bot restart → show main menu with "Session expired" message, never crash.

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
