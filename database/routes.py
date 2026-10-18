"""Route breakdown cards built from measurements and rules."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from database.partners import disclosure, link_replacements, marker

AVIASALES_MARKER = marker()


def _load_raw_routes() -> List[Dict[str, Any]]:
    from database.route_model import build_routes

    return build_routes()


def substitute_placeholders(text: str) -> str:
    for token, replacement in link_replacements().items():
        text = text.replace(token, replacement)
    return text.replace("{PARTNER_NOTE}", disclosure())


def route_id_from_callback(callback_data: str) -> Optional[str]:
    """route:mow_hkg_via_pek:0 -> mow_hkg_via_pek."""
    parts = (callback_data or "").split(":")
    if len(parts) >= 2 and parts[0] == "route":
        return parts[1]
    return None


def _route_id(raw: Dict[str, Any]) -> str:
    for row in raw.get("reply_markup", {}).get("inline_keyboard") or []:
        for button in row:
            found = route_id_from_callback(button.get("callback_data") or "")
            if found:
                return found
    stem = Path(raw.get("_file") or "route").stem
    return stem.replace(".tg", "")


def prepare_route(raw: Dict[str, Any]) -> Dict[str, Any]:
    replies = {
        key: substitute_placeholders(value)
        for key, value in (raw.get("callback_replies") or {}).items()
    }
    prepared = {
        "id": raw.get("id") or _route_id(raw),
        "parse_mode": raw.get("parse_mode") or "HTML",
        "text": substitute_placeholders(raw.get("text") or ""),
        "reply_markup": raw.get("reply_markup") or {"inline_keyboard": []},
        "callback_replies": replies,
    }
    for key in (
        "ticket_links",
        "payment_callbacks",
        "payment_targets",
        "departure_city_id",
        "destination_slug",
        "iata",
        "airlines",
        "airline_gap",
        "summary",
        "lead_facts",
        "section_facts",
        "section_roles",
    ):
        if key in raw:
            prepared[key] = raw[key]
    return prepared


def load_routes() -> Dict[str, Dict[str, Any]]:
    return {card["id"]: card for card in (prepare_route(raw) for raw in _load_raw_routes())}


ROUTES = load_routes()
DEFAULT_ROUTE_ID = "mow_hkg_via_pek"


def get_route(route_id: str = DEFAULT_ROUTE_ID) -> Dict[str, Any]:
    return ROUTES[route_id]


def lead_lines(text: str) -> List[str]:
    import re

    plain = re.sub(r"<[^>]+>", "", text or "")
    return [line.strip() for line in plain.splitlines() if line.strip()]


def ticket_links(route: Dict[str, Any]) -> List[Dict[str, str]]:
    links = route.get("ticket_links") or []
    if links:
        return links
    url = None
    for row in route.get("reply_markup", {}).get("inline_keyboard") or []:
        for button in row:
            candidate = button.get("url") or ""
            if "aviasales" in candidate:
                url = candidate
                break
    if not url:
        return []
    return [{"label": "🔎 Найти билеты", "url": url}]


def tickets_url(route: Dict[str, Any]) -> Optional[str]:
    links = ticket_links(route)
    if not links:
        return None
    return links[0]["url"]


def section_buttons(route: Dict[str, Any]) -> List[Dict[str, str]]:
    buttons = []
    for row in route.get("reply_markup", {}).get("inline_keyboard") or []:
        for button in row:
            if button.get("callback_data"):
                buttons.append({"text": button.get("text") or "", "callback_data": button["callback_data"]})
    return buttons
