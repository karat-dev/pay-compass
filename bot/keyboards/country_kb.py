from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_countries_keyboard(countries: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    # 2 buttons per row
    row = []
    for c in countries:
        slug = c.get("slug") or "unknown"
        name = c.get("name") or "Страна"
        row.append(InlineKeyboardButton(text=f"📍 {name}", callback_data=f"country_{slug}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="« Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_country_summary_keyboard(country_slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚨 Сообщить об ошибке", callback_data=f"report_error_{country_slug}")],
        [InlineKeyboardButton(text="⭐ Оформить подписку", callback_data="menu_subscription_info")],
        [InlineKeyboardButton(text="« К выбору стран", callback_data="menu_select_country")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])

def get_subscription_pay_keyboard(stars_price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ Купить доступ на 90 дней ({stars_price} Stars)", callback_data="pay_stars_90_days")],
        [InlineKeyboardButton(text="« Назад в меню", callback_data="back_to_menu")]
    ])
