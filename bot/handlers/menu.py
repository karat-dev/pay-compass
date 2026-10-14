from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import logging

from bot.keyboards.menu_kb import get_main_menu_kb
from bot.keyboards.country_kb import (
    get_countries_keyboard,
    get_country_hub_keyboard,
    get_country_section_back_keyboard,
    get_country_summary_keyboard,
    get_instruction_nav_keyboard,
    get_section_nav_keyboard,
    get_subscription_pay_keyboard
)
from database.repositories.users import UserRepository
from database.repositories.countries import CountryRepository
from database.knowledge_base import (
    COUNTRIES_KNOWLEDGE_BASE,
    INSTRUCTIONS,
    NUMBER_BY_SECTION,
    SECTION_BY_NUMBER,
    forum_section_text,
    instruction_has_unverified,
    instruction_html_pages,
    section_html_pages,
)
from texts.onboarding import STEP_5_TEXT
from config.settings import settings

logger = logging.getLogger(__name__)
menu_router = Router(name="main_menu")

@menu_router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(STEP_5_TEXT, reply_markup=get_main_menu_kb())

@menu_router.callback_query(F.data == "menu_select_country")
async def handle_select_country(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    await UserRepository.log_event(user_id, "select_country_clicked")

    countries = await CountryRepository.get_all_countries()
    text = (
        "🌍 **Выберите страну для получения верифицированной сводки:**\n\n"
        "🆓 _Напоминаем: в бесплатном тарифе доступна 1 страна в 7 дней с проверенными фактами и источниками._"
    )
    await callback.message.edit_text(text, reply_markup=get_countries_keyboard(countries), parse_mode="Markdown")

@menu_router.callback_query(F.data.startswith("country_"))
async def handle_country_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    slug = callback.data.replace("country_", "")
    
    country = await CountryRepository.get_country_by_slug(slug)
    if not country:
        await callback.message.answer("Страна не найдена.")
        return

    user = await UserRepository.get_user(user_id) or {}
    is_premium = user.get("subscription_status") == "premium" or UserRepository.is_admin(user_id)
    if UserRepository.is_admin(user_id):
        try:
            await UserRepository.reset_country_limits(user_id)
        except Exception:
            pass

    country_id = str(country.get("id") or slug)
    access = await CountryRepository.check_user_access(user_id, country_id, is_premium)

    if not access["allowed"]:
        expires_at = access.get("expires_at", "скоро")
        await UserRepository.log_event(user_id, "free_limit_hit", {"slug": slug})
        text = (
            "🔒 **Лимит бесплатного тарифа**\n\n"
            "Вы уже открыли 1 бесплатную страну на этой неделе.\n"
            f"Следующая бесплатная страна станет доступна после: `{expires_at[:10]}`.\n\n"
            "⭐ **Оформите подписку**, чтобы разблокировать все страны без ограничений и получать оперативные алерты!"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_subscription_pay_keyboard(settings.STARS_PRICE_90_DAYS),
            parse_mode="Markdown"
        )
        return

    # User has access: show summary / interactive hub
    await UserRepository.log_event(user_id, "view_country_summary", {"slug": slug})
    expert_data = CountryRepository.get_expert_data(slug)

    if expert_data:
        # High-value interactive Country Hub
        c_name = expert_data.get("name", slug.title())
        headline = expert_data.get("headline", "")
        
        hub_text = (
            f"📍 **Компас оплаты: {c_name}**\n\n"
            f"{headline}\n\n"
            "Восемь разделов ниже. В каждом по умолчанию зелёная и жёлтая зоны. "
            "Кнопка «Показать непроверенное» открывает красную и чёрную."
        )
        await callback.message.edit_text(
            hub_text,
            reply_markup=get_country_hub_keyboard(slug),
            parse_mode="Markdown"
        )
        return

    summary = await CountryRepository.get_country_summary(country_id, slug)

    lines = [
        f"📊 **СВОДКА: {country.get('name', slug).upper()}**\n",
        "💳 **Платежные методы и карты:**"
    ]

    for m in summary["methods"]:
        status = "✅ Работает" if m.get("works") else "❌ Не работает"
        lines.append(f"• **{m.get('name')}**: {status}")
        if m.get("commission") and m.get("commission") != "—":
            lines.append(f"  Комиссия: {m.get('commission')}")
        if m.get("limits") and m.get("limits") != "—":
            lines.append(f"  Лимиты: {m.get('limits')}")
        # MANDATORY VERIFICATION METADATA
        lines.append(
            f"  🔍 _Источник:_ [Ссылка]({m.get('source_url')}) | "
            f"_Проверено:_ {m.get('verified_at')} (уверенность: {int(float(m.get('confidence', 0.9))*100)}%)\n"
        )

    if summary["warnings"]:
        lines.append("⚠️ **Скам и схемы мошенничества:**")
        for w in summary["warnings"]:
            lines.append(f"• **{w.get('scam_type')}**: {w.get('description')}")
            lines.append(
                f"  🔍 _Источник:_ [Ссылка]({w.get('source_url')}) | "
                f"_Дата:_ {w.get('published_at')}\n"
            )

    lines.append("⚖️ _Информация носит справочный характер. Всегда проверяйте актуальность перед транзакцией._")
    
    full_text = "\n".join(lines)
    await callback.message.edit_text(
        full_text,
        reply_markup=get_country_summary_keyboard(slug),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

# --- 8-section country hub ---

_LEGACY_SECTIONS = {
    "cash": "4",
    "cards": "2",
    "qr": "2",
    "transfers": "3",
    "lifehacks": "1",
    "maps": "5",
    "scams": "7",
}


def _section_page(data: str) -> int:
    if data.startswith("csep_") or data.startswith("cunp_"):
        return int(data.rsplit("_", 1)[-1])
    return 0


def _parse_section_callback(data: str):
    if data.startswith("cunp_") or data.startswith("csep_"):
        show_unverified = data.startswith("cunp_")
        number, rest = data[5:].split("_", 1)
        slug, _page = rest.rsplit("_", 1)
        return slug, number, show_unverified
    if data.startswith("cunv_"):
        number, slug = data[len("cunv_"):].split("_", 1)
        return slug, number, True
    if data.startswith("csec_"):
        rest = data[len("csec_"):]
        for name, number in _LEGACY_SECTIONS.items():
            prefix = name + "_"
            if rest.startswith(prefix):
                return rest[len(prefix):], number, False
        number, slug = rest.split("_", 1)
        if number.isdigit():
            return slug, number, False
    return None


def _instruction_page(data: str) -> int:
    if data.startswith("cipg_") or data.startswith("cipu_"):
        return int(data.rsplit("_", 1)[-1])
    return 0


def _parse_instruction_callback(data: str):
    if data.startswith("cipg_") or data.startswith("cipu_"):
        show_unverified = data.startswith("cipu_")
        body, _page = data[5:].rsplit("_", 1)
        data = ("cinu_" if show_unverified else "cins_") + body
    show_unverified = data.startswith("cinu_")
    if not (data.startswith("cins_") or show_unverified):
        return None
    body = data[5:]
    # Longest slug first so hong_kong is not cut at a shorter suffix.
    for slug in sorted(COUNTRIES_KNOWLEDGE_BASE, key=len, reverse=True):
        suffix = "_" + slug
        if body.endswith(suffix):
            return body[: -len(suffix)], slug, show_unverified
    return None


async def _show_section(callback: CallbackQuery, slug: str, number: str, show_unverified: bool):
    await callback.answer()
    expert_data = CountryRepository.get_expert_data(slug)
    if not expert_data or number not in SECTION_BY_NUMBER:
        await callback.message.answer("Данные раздела обновляются...")
        return
    section_key = SECTION_BY_NUMBER[number]
    await UserRepository.log_event(
        callback.from_user.id,
        "view_country_section",
        {"slug": slug, "section": section_key, "unverified": show_unverified},
    )
    pages = section_html_pages(expert_data, section_key, show_unverified=show_unverified)
    page = min(_section_page(callback.data), max(len(pages) - 1, 0))
    await callback.message.edit_text(
        pages[page],
        reply_markup=get_section_nav_keyboard(
            slug,
            number,
            show_unverified=show_unverified,
            page=page,
            page_count=len(pages),
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@menu_router.callback_query(
    F.data.startswith("cunv_")
    | F.data.startswith("cunp_")
    | F.data.startswith("csep_")
    | F.data.startswith("csec_1_")
    | F.data.startswith("csec_2_")
    | F.data.startswith("csec_3_")
    | F.data.startswith("csec_4_")
    | F.data.startswith("csec_5_")
    | F.data.startswith("csec_6_")
    | F.data.startswith("csec_7_")
    | F.data.startswith("csec_8_")
    | F.data.startswith("csec_cash_")
    | F.data.startswith("csec_cards_")
    | F.data.startswith("csec_qr_")
    | F.data.startswith("csec_transfers_")
    | F.data.startswith("csec_lifehacks_")
    | F.data.startswith("csec_maps_")
    | F.data.startswith("csec_scams_")
)
async def handle_country_section(callback: CallbackQuery):
    parsed = _parse_section_callback(callback.data)
    if not parsed:
        await callback.answer()
        return
    slug, number, show_unverified = parsed
    await _show_section(callback, slug, number, show_unverified)


@menu_router.callback_query(
    F.data.startswith("cins_")
    | F.data.startswith("cinu_")
    | F.data.startswith("cipg_")
    | F.data.startswith("cipu_")
)
async def handle_country_instruction(callback: CallbackQuery):
    parsed = _parse_instruction_callback(callback.data)
    if not parsed:
        await callback.answer()
        return
    instruction_id, slug, show_unverified = parsed
    await callback.answer()
    if instruction_id not in INSTRUCTIONS:
        await callback.message.answer("Инструкция обновляется...")
        return
    section_key = INSTRUCTIONS[instruction_id].get("section") or "2_pay_on_site"
    number = NUMBER_BY_SECTION.get(section_key, "2")
    await UserRepository.log_event(
        callback.from_user.id,
        "view_country_instruction",
        {"slug": slug, "instruction": instruction_id, "unverified": show_unverified},
    )
    pages = instruction_html_pages(instruction_id, show_unverified=show_unverified)
    page = min(_instruction_page(callback.data), max(len(pages) - 1, 0))
    await callback.message.edit_text(
        pages[page],
        reply_markup=get_instruction_nav_keyboard(
            slug,
            instruction_id,
            number,
            show_unverified=show_unverified,
            has_unverified=instruction_has_unverified(instruction_id),
            page=page,
            page_count=len(pages),
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@menu_router.callback_query(F.data.startswith("csec_forum_") | F.data.startswith("csec_proof_"))
async def handle_csec_forum(callback: CallbackQuery):
    await callback.answer()
    slug = callback.data.replace("csec_forum_", "").replace("csec_proof_", "")
    await UserRepository.log_event(callback.from_user.id, "view_section_forum_insights", {"slug": slug})
    full_text = forum_section_text()
    await callback.message.edit_text(
        full_text,
        reply_markup=get_country_section_back_keyboard(slug),
        disable_web_page_preview=True,
    )


@menu_router.callback_query(F.data == "menu_scam_warnings")
async def handle_scam_warnings(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    await UserRepository.log_event(user_id, "view_scam_warnings")

    text = (
        "⚠️ **ПРЕДУПРЕЖДЕНИЯ О МОШЕННИЧЕСТВЕ ЗА РУБЕЖОМ**\n\n"
        "1. **Схемы с криптообменниками в Telegram:**\n"
        "Предложения обменять наличные доллары или местную валюту с переводом на карты РФ через 'курьера'. Высокий риск потери средств.\n"
        "🔍 _Источник: МВД РФ, ФинЦЕРТ Банка России | Проверено: 12.09.2026_\n\n"
        "2. **Виртуальные карты от ботов без лицензий:**\n"
        "Массовые блокировки эмитентами карт из США и ЕС без возврата остатка средств на балансе.\n"
        "🔍 _Источник: Banki.ru | Проверено: 10.09.2026_\n\n"
        "⭐ _Подписчикам доступны мгновенные алерты о новых схемах за последние 7 дней._"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_subscription_pay_keyboard(settings.STARS_PRICE_90_DAYS),
        parse_mode="Markdown"
    )

@menu_router.callback_query(F.data == "menu_about_project")
async def handle_about_project(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    await UserRepository.log_event(user_id, "view_about_project")

    text = (
        "ℹ️ **О ПРОЕКТЕ**\n\n"
        "Мы — независимый справочник по платежам за границей для российских путешественников.\n\n"
        "🛡 **Наши принципы:**\n"
        "• Мы НЕ выпускаем и НЕ продаем виртуальные карты.\n"
        "• Мы НЕ берем проценты с ваших платежей и переводов.\n"
        "• Каждый факт привязан к источнику, дате проверки и коэффициенту достоверности.\n\n"
        "📬 Контакты и поддержка: @travel_support_bot"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_country_summary_keyboard("turkey"),
        parse_mode="Markdown"
    )

@menu_router.callback_query(F.data.startswith("report_error_"))
async def handle_report_error(callback: CallbackQuery):
    await callback.answer("Спасибо! Ваше сообщение передано на проверку модераторам.", show_alert=True)
    slug = callback.data.replace("report_error_", "")
    await UserRepository.log_event(callback.from_user.id, "error_reported", {"slug": slug})
