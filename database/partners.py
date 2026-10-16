"""Travelpayouts partner links. URLs are built from config/partners.json, not from the UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
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


def partner_href(partner_id: str, *, project_id: Optional[str] = None) -> Optional[str]:
    """Return a live partner URL, or None while a config placeholder is still in place."""
    data = load_partner_config()
    partner = data["partners"][partner_id]
    template = str(partner.get("url_template") or "")
    status = partner.get("status")
    if status == "placeholder" or "PLACEHOLDER" in template:
        return None
    if status not in {"ready", "needs_project_id"}:
        return None
    project = str(data.get("project_id") or "") if project_id is None else project_id
    if "{project_id}" in template and not project.isdigit():
        return None
    destination = quote(str(partner.get("destination") or ""), safe="")
    url = template.format(marker=data["marker"], project_id=project, destination=destination)
    if not url.startswith("https://") or "PLACEHOLDER" in url:
        return None
    return url


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
            replacements[token] = f'<a href="{safe}">{label}</a>'
        else:
            replacements[token] = label
    return replacements
