"""Travelpayouts partner links. URLs are built from config/partners.json, not from the UI."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "partners.json"


def load_partner_config() -> Dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if str(data.get("marker") or "") == "":
        raise RuntimeError("config/partners.json is missing marker")
    return data


def marker() -> str:
    return str(load_partner_config()["marker"])


def disclosure() -> str:
    text = str(load_partner_config().get("disclosure") or "").strip()
    return text or "партнёрская ссылка"


def _live_https(url: str) -> Optional[str]:
    if not url.startswith("https://") or "PLACEHOLDER" in url:
        return None
    return url


def partner_href(partner_id: str, *, project_id: Optional[str] = None) -> Optional[str]:
    """Return a live partner URL, or None while a config placeholder is still in place.

    A ready-made ``url`` is returned unchanged, query string included. That keeps
    the ``erid`` ad-marking token intact. ``url_template`` is filled only when
    no ready link is set.
    """
    data = load_partner_config()
    partner = data["partners"][partner_id]
    status = partner.get("status")
    if status == "placeholder":
        return None
    ready = str(partner.get("url") or "").strip()
    if ready:
        if status != "ready":
            return None
        return _live_https(ready)
    template = str(partner.get("url_template") or "")
    if "PLACEHOLDER" in template or status not in {"ready", "needs_project_id"}:
        return None
    project = str(data.get("project_id") or "") if project_id is None else project_id
    if "{project_id}" in template and not project.isdigit():
        return None
    destination = quote(str(partner.get("destination") or ""), safe="")
    url = template.format(marker=data["marker"], project_id=project, destination=destination)
    return _live_https(url)


def link_replacements() -> Dict[str, str]:
    """Token → HTML anchor, or the partner label when the URL is still a placeholder."""
    data = load_partner_config()
    replacements: Dict[str, str] = {}
    for partner_id, partner in data["partners"].items():
        token = partner["token"]
        label = partner["label"]
        href = partner_href(partner_id)
        if href:
            safe = href.replace("&", "&amp;").replace('"', "%22")
            replacements[token] = f'<a href="{safe}">{html.escape(label)}</a>'
        else:
            replacements[token] = html.escape(label)
    return replacements


def public_offers() -> List[Dict[str, str]]:
    """Live partner links safe to show in the Mini App catalog."""
    data = load_partner_config()
    offers: List[Dict[str, str]] = []
    for partner_id, partner in data["partners"].items():
        href = partner_href(partner_id)
        if not href:
            continue
        offers.append({
            "id": partner_id,
            "placement": str(partner.get("placement") or ""),
            "label": str(partner["label"]),
            "url": href,
        })
    return offers


def _offers_for(placement: str) -> List[Dict[str, str]]:
    return [offer for offer in public_offers() if offer["placement"] == placement]


def checklist_offer_text() -> str:
    offers = _offers_for("checklist")
    if not offers:
        return ""
    lines = [f"{offer['label']}: {offer['url']}" for offer in offers]
    lines.append(disclosure())
    return "\n".join(lines)


def checklist_offer_html() -> str:
    offers = _offers_for("checklist")
    if not offers:
        return ""
    anchors = []
    for offer in offers:
        safe = offer["url"].replace("&", "&amp;").replace('"', "%22")
        anchors.append(f'<a href="{safe}">{html.escape(offer["label"])}</a>')
    return " · ".join(anchors) + f"\n<i>{html.escape(disclosure())}</i>"
