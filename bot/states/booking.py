from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    choosing_category = State()
    choosing_services = State()
    waiting_comment = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()
