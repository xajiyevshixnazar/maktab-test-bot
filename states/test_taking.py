from aiogram.fsm.state import State, StatesGroup


class TestTakingState(StatesGroup):
    taking_test = State()
