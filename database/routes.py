"""Route breakdown cards loaded from generated Telegram JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROUTES_DIR = Path(__file__).with_name("data") / "routes"
AVIASALES_MARKER = "765617"

# Placeholders in the generated card. Real affiliate links can replace these URLs later.
PLACEHOLDER_LINKS = {
    "{KIWITAXI_LINK}": '<a href="https://kiwitaxi.com/">KiwiTaxi</a>',
    "{AIRALO_LINK}": '<a href="https://www.airalo.com/">Airalo</a>',
}


def _load_raw_routes() -> List[Dict[str, Any]]:
    cards = []
    if not ROUTES_DIR.exists():
        return cards
    for path in sorted(ROUTES_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
        raw["_file"] = path.name
        cards.append(raw)
    return cards


def substitute_placeholders(text: str) -> str:
    for token, replacement in PLACEHOLDER_LINKS.items():
        text = text.replace(token, replacement)
    return text


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
    return {
        "id": _route_id(raw),
        "parse_mode": raw.get("parse_mode") or "HTML",
        "text": substitute_placeholders(raw.get("text") or ""),
        "reply_markup": raw.get("reply_markup") or {"inline_keyboard": []},
        "callback_replies": replies,
    }


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


def tickets_url(route: Dict[str, Any]) -> Optional[str]:
    for row in route.get("reply_markup", {}).get("inline_keyboard") or []:
        for button in row:
            url = button.get("url") or ""
            if "aviasales" in url:
                return url
    return None


def section_buttons(route: Dict[str, Any]) -> List[Dict[str, str]]:
    buttons = []
    for row in route.get("reply_markup", {}).get("inline_keyboard") or []:
        for button in row:
            if button.get("callback_data"):
                buttons.append({"text": button.get("text") or "", "callback_data": button["callback_data"]})
    return buttons
