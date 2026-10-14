from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.routes import get_route, section_buttons, tickets_url


def get_route_keyboard(route_id: str = "mow_hkg_via_pek") -> InlineKeyboardMarkup:
    """Card keyboard: ticket search, collapsible sections, return to the menu."""
    route = get_route(route_id)
    rows = []
    url = tickets_url(route)
    if url:
        rows.append([InlineKeyboardButton(text="🔎 Найти билеты", url=url)])
    pair = []
    for button in section_buttons(route):
        pair.append(InlineKeyboardButton(text=button["text"], callback_data=button["callback_data"]))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(text="« Главное меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_route_section_keyboard(route_id: str, *, show_payment_links: bool = False) -> InlineKeyboardMarkup:
    route = get_route(route_id)
    rows = []
    url = tickets_url(route)
    if url:
        rows.append([InlineKeyboardButton(text="🔎 Найти билеты", url=url)])
    if show_payment_links:
        rows.append([
            InlineKeyboardButton(text="Компас оплаты · Китай", callback_data="country_china"),
            InlineKeyboardButton(text="Гонконг", callback_data="country_hong_kong"),
        ])
    rows.append([InlineKeyboardButton(text="« К маршруту", callback_data=f"route_open:{route_id}")])
    rows.append([InlineKeyboardButton(text="« Главное меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
