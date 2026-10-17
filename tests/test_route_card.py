"""Route breakdown card: Moscow → Hong Kong via Beijing."""

from bot.keyboards.menu_kb import get_main_menu_kb
from bot.keyboards.route_kb import get_route_keyboard, get_route_section_keyboard
from database.knowledge_base import TELEGRAM_MESSAGE_LIMIT, split_telegram_html
from database.routes import (
    AVIASALES_MARKER,
    get_route,
    lead_lines,
    load_routes,
    section_buttons,
    tickets_url,
)


def _labels(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def _callbacks(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


def _urls(markup):
    return [button.url for row in markup.inline_keyboard for button in row if button.url]


def test_route_card_loads_from_json():
    routes = load_routes()
    assert "mow_hkg_via_pek" in routes
    route = get_route("mow_hkg_via_pek")
    lines = lead_lines(route["text"])
    assert lines[0] == "Москва → Гонконг через Пекин"
    assert lines[1].startswith("🛂 Виза не нужна")
    assert "Китай до 30 дней" in lines[1]
    assert "Гонконг до 14 дней" in lines[1]
    assert lines[2].startswith("⚠️ Главный риск")
    assert "PKX" in lines[2] and "PEK" in lines[2]

    assert "Аэрофлот" in route["text"]
    assert "https://umnyturizm.example/airlines/aeroflot" in route["text"]
    assert "Cathay Pacific" in route["text"]
    assert len(route["text"]) <= TELEGRAM_MESSAGE_LIMIT

    url = tickets_url(route)
    assert url is not None
    assert f"marker={AVIASALES_MARKER}" in url
    assert "aviasales.ru" in url

    labels = [button["text"] for button in section_buttons(route)]
    assert labels == [
        "Пересадка",
        "Трансфер",
        "Связь",
        "Ввоз и вывоз",
        "Штампы и отметки",
        "Оплата",
    ]
    for button in section_buttons(route):
        body = route["callback_replies"][button["callback_data"]]
        assert body.strip()
        assert "{KIWITAXI_LINK}" not in body
        assert "{AIRALO_LINK}" not in body
        assert "{WELCOME_PICKUPS_LINK}" not in body
        assert all(len(page) <= TELEGRAM_MESSAGE_LIMIT for page in split_telegram_html(body))


def test_route_keyboard_and_menu_entry():
    menu = get_main_menu_kb()
    assert "Разбор маршрута" in _labels(menu)
    assert "menu_route_card" in _callbacks(menu)

    keyboard = get_route_keyboard()
    assert "🔎 Найти билеты" in _labels(keyboard)
    assert any(f"marker={AVIASALES_MARKER}" in url for url in _urls(keyboard))
    assert "route:mow_hkg_via_pek:0" in _callbacks(keyboard)
    assert "route:mow_hkg_via_pek:5" in _callbacks(keyboard)
    assert "back_to_menu" in _callbacks(keyboard)

    payment = get_route_section_keyboard("mow_hkg_via_pek", show_payment_links=True)
    assert "country_china" in _callbacks(payment)
    assert "country_hong_kong" in _callbacks(payment)
    assert "route_open:mow_hkg_via_pek" in _callbacks(payment)
    transfer = get_route("mow_hkg_via_pek")["callback_replies"]["route:mow_hkg_via_pek:1"]
    assert "c1.travelpayouts.com/click" in transfer
    assert f"shmarker={AVIASALES_MARKER}" in transfer
    assert "promo_id=647" in transfer
    assert 'href="https://kiwitaxi.com' not in transfer
    assert "Welcome Pickups" in transfer
    assert "{WELCOME_PICKUPS_LINK}" not in transfer
    assert "PLACEHOLDER" not in transfer
    link = get_route("mow_hkg_via_pek")["callback_replies"]["route:mow_hkg_via_pek:2"]
    assert "Airalo" in link
    assert "{AIRALO_LINK}" not in link
    assert "tp.media" not in link
    assert 'href="https://www.airalo.com' not in link
    assert 'href="https://airalo.tpk.lv/WJxbG8Hh?erid=2VtzqwXiejf"' in link
    pay = get_route("mow_hkg_via_pek")["callback_replies"]["route:mow_hkg_via_pek:5"]
    assert "Компас оплаты → Китай" in pay
    assert "Гонконг" in pay
