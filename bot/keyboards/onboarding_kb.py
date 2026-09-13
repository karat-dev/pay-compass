from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_step_1_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продолжить →", callback_data="onboarding_next_2")]
    ])

def get_step_2_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Понятно →", callback_data="onboarding_next_3")]
    ])

def get_step_3_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Хорошо →", callback_data="onboarding_next_4")]
    ])

def get_step_4_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Согласен и продолжить", callback_data="onboarding_consent_accept")],
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="onboarding_show_privacy")]
    ])

def get_soft_resume_kb(saved_step: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Продолжить с шага {saved_step}", callback_data=f"onboarding_resume_{saved_step}")],
        [InlineKeyboardButton(text="Начать заново", callback_data="onboarding_restart_confirm")]
    ])
