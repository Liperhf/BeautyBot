import asyncio
import logging

from bot.loader import bot, dp
from bot.config import settings
from bot.db.base import engine, async_session_maker
from bot.db.models import Base
from bot.db.seed import seed_database
from bot.middlewares.db_session import DbSessionMiddleware
from bot.handlers import register_routers
from bot.scheduler.jobs import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting Beauty Bot...")

    # Create tables (idempotent — does nothing if they exist)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready.")

    # Seed demo data if DB is empty
    async with async_session_maker() as session:
        await seed_database(session)

    # Register middlewares
    dp.message.middleware(DbSessionMiddleware(async_session_maker))
    dp.callback_query.middleware(DbSessionMiddleware(async_session_maker))

    # Register handlers
    register_routers(dp)

    # Start scheduler
    scheduler = setup_scheduler(bot, async_session_maker)
    scheduler.start()
    logger.info("Scheduler started.")

    # Drop pending updates and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot polling started. Admin Telegram ID: %d", settings.ADMIN_TELEGRAM_ID)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
