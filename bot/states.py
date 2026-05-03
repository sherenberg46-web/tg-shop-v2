from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    waiting_choice = State()


class GameSearch(StatesGroup):
    waiting_genre = State()
    waiting_platform = State()
    waiting_budget = State()


class SubscriptionSearch(StatesGroup):
    waiting_type = State()


class Consultation(StatesGroup):
    chatting = State()
