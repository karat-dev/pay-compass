from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Выбрать страну", callback_data="menu_select_country")],
        [InlineKeyboardButton(text="⚠️ Скам-предупреждения", callback_data="menu_scam_warnings")],
        [InlineKeyboardButton(text="📰 Наш канал", url="https://t.me/travel_payments_news")],
        [InlineKeyboardButton(text="⭐ О подписке", callback_data="menu_subscription_info")],
        [InlineKeyboardButton(text="ℹ️ О проекте", callback_data="menu_about_project")]
    ])
