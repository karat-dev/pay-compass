from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.knowledge_base import (
    COUNTRIES_KNOWLEDGE_BASE,
    INSTRUCTION_LABELS,
    SECTION_ORDER,
    instructions_for_section,
    section_has_unverified,
)

def get_countries_keyboard(countries: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Country buttons, including guides that exist only in the knowledge base."""
    by_slug: Dict[str, Dict[str, Any]] = {}
    for c in countries:
        slug = c.get("slug")
        if slug:
            by_slug[slug] = c

    ordered: List[Dict[str, Any]] = []
    for slug, data in COUNTRIES_KNOWLEDGE_BASE.items():
        existing = by_slug.pop(slug, None)
        if existing:
            ordered.append(existing)
        else:
            ordered.append({"slug": slug, "name": data.get("name") or slug})
    ordered.extend(by_slug.values())

    buttons = []
    # 2 buttons per row
    row = []
    for c in ordered:
        slug = c.get("slug") or "unknown"
        name = c.get("name") or "Страна"
        row.append(InlineKeyboardButton(text=f"{name}", callback_data=f"country_{slug}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="« Назад в главное меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

_SECTION_BUTTONS = (
    ("1", "✅ До поездки"),
    ("2", "💳 Оплата на месте"),
    ("3", "👛 Кошельки и карты"),
    ("4", "💵 Наличные и обмен"),
    ("5", "🏧 Банкоматы"),
    ("6", "🚇 Транспорт"),
    ("7", "⚠️ Риски и блокировка"),
    ("8", "🧾 Tax free"),
)

def get_country_hub_keyboard(country_slug: str) -> InlineKeyboardMarkup:
    """Eight sections from the country schema. Forum reports have no button."""
    if len(_SECTION_BUTTONS) != len(SECTION_ORDER):
        raise RuntimeError("Hub buttons must follow the 8-section schema.")
    rows = []
    pair = []
    for number, label in _SECTION_BUTTONS:
        pair.append(InlineKeyboardButton(text=label, callback_data=f"csec_{number}_{country_slug}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.extend([
        [
            InlineKeyboardButton(text="🚨 Сообщить об ошибке", callback_data=f"report_error_{country_slug}"),
            InlineKeyboardButton(text="⭐ О подписке", callback_data="menu_subscription_info")
        ],
        [
            InlineKeyboardButton(text="« К списку стран", callback_data="menu_select_country"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _page_row(prefix: str, owner: str, page: int, page_count: int):
    if page_count <= 1:
        return None
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(
            text=f"← {page}/{page_count}",
            callback_data=f"{prefix}_{owner}_{page - 1}",
        ))
    if page + 1 < page_count:
        row.append(InlineKeyboardButton(
            text=f"{page + 2}/{page_count} →",
            callback_data=f"{prefix}_{owner}_{page + 1}",
        ))
    return row


def get_section_nav_keyboard(
    country_slug: str,
    section_number: str,
    *,
    show_unverified: bool = False,
    page: int = 0,
    page_count: int = 1,
) -> InlineKeyboardMarkup:
    """Back navigation plus 'Показать непроверенное' when the section has such facts."""
    data = COUNTRIES_KNOWLEDGE_BASE.get(country_slug) or {}
    section_key = SECTION_ORDER[int(section_number) - 1][0]
    buttons = []
    page_prefix = "cunp" if show_unverified else "csep"
    page_row = _page_row(page_prefix, f"{section_number}_{country_slug}", page, page_count)
    if page_row:
        buttons.append(page_row)
    if section_has_unverified(data, section_key):
        if show_unverified:
            buttons.append([InlineKeyboardButton(
                text="Скрыть непроверенное",
                callback_data=f"csec_{section_number}_{country_slug}",
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text="Показать непроверенное",
                callback_data=f"cunv_{section_number}_{country_slug}",
            )])
    for instruction_id in instructions_for_section(data, section_key):
        label = INSTRUCTION_LABELS.get(instruction_id, "📋 Инструкция")
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=f"cins_{instruction_id}_{country_slug}",
        )])
    buttons.append([InlineKeyboardButton(text="« Назад в хаб страны", callback_data=f"country_{country_slug}")])
    buttons.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_instruction_nav_keyboard(
    country_slug: str,
    instruction_id: str,
    section_number: str,
    *,
    show_unverified: bool,
    has_unverified: bool,
    page: int = 0,
    page_count: int = 1,
) -> InlineKeyboardMarkup:
    buttons = []
    page_prefix = "cipu" if show_unverified else "cipg"
    page_row = _page_row(page_prefix, f"{instruction_id}_{country_slug}", page, page_count)
    if page_row:
        buttons.append(page_row)
    if has_unverified:
        if show_unverified:
            buttons.append([InlineKeyboardButton(
                text="Скрыть непроверенное",
                callback_data=f"cins_{instruction_id}_{country_slug}",
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text="Показать непроверенное",
                callback_data=f"cinu_{instruction_id}_{country_slug}",
            )])
    buttons.append([InlineKeyboardButton(
        text="« Назад в раздел",
        callback_data=f"csec_{section_number}_{country_slug}",
    )])
    buttons.append([InlineKeyboardButton(text="« Назад в хаб страны", callback_data=f"country_{country_slug}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_country_maps_keyboard(country_slug: str, maps_data: Dict[str, str]) -> InlineKeyboardMarkup:
    """Keyboard with direct external Google Maps links with applied filters."""
    buttons = []
    if maps_data.get("vakifbank_atms"):
        buttons.append([InlineKeyboardButton(text="📍 Банкоматы VakıfBank на Google Maps ↗", url=maps_data["vakifbank_atms"])])
    if maps_data.get("ziraat_atms"):
        buttons.append([InlineKeyboardButton(text="📍 Банкоматы Ziraat Bankası на Google Maps ↗", url=maps_data["ziraat_atms"])])
    if maps_data.get("halkbank_atms"):
        buttons.append([InlineKeyboardButton(text="📍 Банкоматы Halkbank на Google Maps ↗", url=maps_data["halkbank_atms"])])
    if maps_data.get("grand_bazaar_exchange"):
        buttons.append([InlineKeyboardButton(text="📍 Обменники Гранд-Базара (лучший курс) ↗", url=maps_data["grand_bazaar_exchange"])])
    if maps_data.get("ptt_post_offices"):
        buttons.append([InlineKeyboardButton(text="📍 Отделения почты PTT (выдача Короны) ↗", url=maps_data["ptt_post_offices"])])
    
    buttons.append([InlineKeyboardButton(text="« Назад в хаб страны", callback_data=f"country_{country_slug}")])
    buttons.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_country_section_back_keyboard(country_slug: str) -> InlineKeyboardMarkup:
    """Navigation keyboard to return from a specific country sub-section to the country hub."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Назад в хаб страны", callback_data=f"country_{country_slug}")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")]
    ])

def get_country_proof_keyboard(country_slug: str, proofs: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Keyboard with direct external buttons for Social Proof videos and reports."""
    buttons = []
    for p in proofs:
        title = p.get("title", "Открыть пруф")
        link = p.get("link", "#")
        platform = p.get("platform", "").split()[0]
        btn_text = f"🔗 {platform}: {title[:32]}... ↗"
        buttons.append([InlineKeyboardButton(text=btn_text, url=link)])

    buttons.append([InlineKeyboardButton(text="« Назад в хаб страны", callback_data=f"country_{country_slug}")])
    buttons.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")])
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
