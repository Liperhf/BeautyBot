from aiogram import Dispatcher

from bot.handlers import start, booking, my_bookings, services_info, about, gallery
from bot.handlers.admin import main_menu as admin_main
from bot.handlers.admin import about as admin_about
from bot.handlers.admin import schedule as admin_schedule
from bot.handlers.admin import services as admin_services
from bot.handlers.admin import gallery as admin_gallery
from bot.handlers.admin import stats as admin_stats


def register_routers(dp: Dispatcher) -> None:
    # Admin routers first (more specific filters)
    dp.include_router(admin_main.router)
    dp.include_router(admin_about.router)
    dp.include_router(admin_schedule.router)
    dp.include_router(admin_services.router)
    dp.include_router(admin_gallery.router)
    dp.include_router(admin_stats.router)
    # Client routers
    dp.include_router(start.router)
    dp.include_router(booking.router)
    dp.include_router(my_bookings.router)
    dp.include_router(services_info.router)
    dp.include_router(about.router)
    dp.include_router(gallery.router)
    # Catch-all for stale callbacks must be last
    dp.include_router(start.fallback_router)
