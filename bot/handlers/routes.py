from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards.route_kb import get_route_keyboard, get_route_section_keyboard
from database.knowledge_base import split_telegram_html
from database.repositories.users import UserRepository
from database.routes import DEFAULT_ROUTE_ID, get_route, route_id_from_callback

routes_router = Router(name="routes")


async def _show_route_card(callback: CallbackQuery, route_id: str) -> None:
    route = get_route(route_id)
    await callback.message.edit_text(
        route["text"],
        reply_markup=get_route_keyboard(route_id),
        parse_mode=route.get("parse_mode") or "HTML",
        disable_web_page_preview=True,
    )


@routes_router.callback_query(F.data == "menu_route_card")
async def handle_route_menu(callback: CallbackQuery):
    await callback.answer()
    await UserRepository.log_event(callback.from_user.id, "view_route_card", {"route": DEFAULT_ROUTE_ID})
    await _show_route_card(callback, DEFAULT_ROUTE_ID)


@routes_router.callback_query(F.data.startswith("route_open:"))
async def handle_route_open(callback: CallbackQuery):
    await callback.answer()
    route_id = callback.data.split(":", 1)[1]
    await _show_route_card(callback, route_id)


@routes_router.callback_query(F.data.startswith("route:"))
async def handle_route_section(callback: CallbackQuery):
    await callback.answer()
    route_id = route_id_from_callback(callback.data)
    if not route_id:
        return
    route = get_route(route_id)
    body = route["callback_replies"].get(callback.data)
    if not body:
        await callback.message.answer("Раздел маршрута обновляется...")
        return
    await UserRepository.log_event(
        callback.from_user.id,
        "view_route_section",
        {"route": route_id, "section": callback.data},
    )
    pages = split_telegram_html(body)
    text = pages[0]
    show_payment = callback.data.endswith(":5")
    await callback.message.edit_text(
        text,
        reply_markup=get_route_section_keyboard(route_id, show_payment_links=show_payment),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
