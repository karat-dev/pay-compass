from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_countries_keyboard(countries: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    # 2 buttons per row
    row = []
    for c in countries:
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

def get_country_hub_keyboard(country_slug: str) -> InlineKeyboardMarkup:
    """Interactive Hub keyboard for a country: detailed thematic sub-sections."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💵 Наличные и обмен ($)", callback_data=f"csec_cash_{country_slug}"),
            InlineKeyboardButton(text="💳 Карты и банкоматы", callback_data=f"csec_cards_{country_slug}")
        ],
        [
            InlineKeyboardButton(text="📱 Оплата по QR (Karekod)", callback_data=f"csec_qr_{country_slug}"),
            InlineKeyboardButton(text="📲 Золотая Корона", callback_data=f"csec_transfers_{country_slug}")
        ],
        [
            InlineKeyboardButton(text="💡 Лайфхаки, чаевые и лимиты", callback_data=f"csec_lifehacks_{country_slug}"),
            InlineKeyboardButton(text="🗺 Карты банкоматов и обменников", callback_data=f"csec_maps_{country_slug}")
        ],
        [
            InlineKeyboardButton(text="⚠️ Скам и ловушка DCC", callback_data=f"csec_scams_{country_slug}"),
            InlineKeyboardButton(text="🎬 Опыт туристов (Social Proof)", callback_data=f"csec_proof_{country_slug}")
        ],
        [
            InlineKeyboardButton(text="🚨 Сообщить об ошибке", callback_data=f"report_error_{country_slug}"),
            InlineKeyboardButton(text="⭐ О подписке", callback_data="menu_subscription_info")
        ],
        [
            InlineKeyboardButton(text="« К списку стран", callback_data="menu_select_country"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")
        ]
    ])

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
