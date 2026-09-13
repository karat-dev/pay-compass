from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    step_1 = State()  # Приветствие и ценность
    step_2 = State()  # Как это работает
    step_3 = State()  # Что бесплатно, что по подписке
    step_4 = State()  # Согласие и дисклеймер
    soft_resume_prompt = State()  # Мягкое возобновление после паузы > 24ч

class MainMenuStates(StatesGroup):
    idle = State()
    selecting_country = State()
