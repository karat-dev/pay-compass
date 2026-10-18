from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.keyboards.miniapp_kb import miniapp_url
from database.routes import get_route, section_buttons, ticket_links


def get_route_keyboard(route_id: str = "mow_hkg_via_pek") -> InlineKeyboardMarkup:
    """Card keyboard: ticket search, collapsible sections, return to the menu."""
    route = get_route(route_id)
    rows = []
    for link in ticket_links(route):
        rows.append([InlineKeyboardButton(text=link["label"], url=link["url"])])
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
    for link in ticket_links(route):
        rows.append([InlineKeyboardButton(text=link["label"], url=link["url"])])
    if show_payment_links:
        buttons = [
            InlineKeyboardButton(
                text=target["button"],
                web_app=WebAppInfo(url=miniapp_url(f"section_{target['slug']}_2_pay_on_site")),
            )
            for target in route.get("payment_targets") or []
        ]
        if buttons:
            rows.append(buttons)
    rows.append([InlineKeyboardButton(text="« К маршруту", callback_data=f"route_open:{route_id}")])
    rows.append([InlineKeyboardButton(text="« Главное меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
