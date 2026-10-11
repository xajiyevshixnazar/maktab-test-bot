from aiogram.fsm.state import State, StatesGroup


class CreateTestState(StatesGroup):
    waiting_for_title = State()
    waiting_for_duration = State()
    waiting_for_questions = State()
