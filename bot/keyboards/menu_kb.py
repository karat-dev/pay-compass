from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Выбрать страну", callback_data="menu_select_country")],
        [InlineKeyboardButton(text="Разбор маршрута", callback_data="menu_route_card")],
        [InlineKeyboardButton(text="⚠️ Скам-предупреждения", callback_data="menu_scam_warnings")],
        [InlineKeyboardButton(text="📰 Наш канал", url="https://t.me/travel_payments_news")],
        [InlineKeyboardButton(text="ℹ️ О проекте", callback_data="menu_about_project")]
    ])
