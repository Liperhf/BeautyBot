from aiogram.fsm.state import State, StatesGroup


class AdminServiceStates(StatesGroup):
    waiting_category_name = State()
    waiting_category_description = State()
    waiting_service_name = State()
    waiting_service_price = State()
    waiting_service_duration = State()
    waiting_service_description = State()


class AdminScheduleStates(StatesGroup):
    waiting_exception_date = State()
    waiting_exception_reason = State()
    waiting_custom_hours = State()


class AdminMasterStates(StatesGroup):
    waiting_about_text = State()
    waiting_photo = State()
    waiting_phone = State()
    waiting_instagram = State()
    waiting_address = State()


class AdminGalleryStates(StatesGroup):
    waiting_photo = State()
