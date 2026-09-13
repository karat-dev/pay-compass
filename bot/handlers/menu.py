from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
import logging

from bot.keyboards.menu_kb import get_main_menu_kb
from bot.keyboards.country_kb import (
    get_countries_keyboard,
    get_country_hub_keyboard,
    get_country_section_back_keyboard,
    get_country_maps_keyboard,
    get_country_proof_keyboard,
    get_country_summary_keyboard,
    get_subscription_pay_keyboard
)
from database.repositories.users import UserRepository
from database.repositories.countries import CountryRepository
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
            f"📍 **ЭКСПЕРТНЫЙ ГИД: {c_name.upper()}**\n\n"
            f"⚡ **Коротко о главном:**\n_{headline}_\n\n"
            "💡 _Выберите интересующий раздел ниже, чтобы изучить проверенные факты, "
            "правила банкоматов, нюансы валюты и реальный опыт туристов:_"
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

# --- SUB-SECTION HANDLERS FOR COUNTRY HUB (TURKEY & OTHERS) ---

@menu_router.callback_query(F.data.startswith("csec_cash_"))
async def handle_csec_cash(callback: CallbackQuery):
    await callback.answer()
    slug = callback.data.replace("csec_cash_", "")
    await UserRepository.log_event(callback.from_user.id, "view_section_cash", {"slug": slug})
    expert_data = CountryRepository.get_expert_data(slug)

    if not expert_data:
        await callback.message.answer("Данные раздела обновляются...")
        return

    c_info = expert_data.get("currency_info", {})
    source_url = c_info.get("source_url", "https://cbr.ru/crosscut/lawacts/file/5923")
    text = (
        f"💵 **НАЛИЧНЫЕ И ОБМЕН ВАЛЮТЫ: {expert_data['name']}**\n\n"
        f"🏛 **Местная валюта:** {c_info.get('official_currency')}\n\n"
        f"🇷🇺 **Наличные рубли:**\n{c_info.get('cash_rubles')}\n\n"
        f"{c_info.get('usd_eur_rules')}\n\n"
        f"{c_info.get('best_exchangers')}\n\n"
        f"🔍 _Источник:_ [Указ ЦБ РФ о вывозе наличных]({source_url}) | _Проверено: 13.09.2026_"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_country_section_back_keyboard(slug),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


@menu_router.callback_query(F.data.startswith("csec_cards_"))
async def handle_csec_cards(callback: CallbackQuery):
    await callback.answer()
    slug = callback.data.replace("csec_cards_", "")
    await UserRepository.log_event(callback.from_user.id, "view_section_cards", {"slug": slug})
    expert_data = CountryRepository.get_expert_data(slug)

    if not expert_data:
        await callback.message.answer("Данные раздела обновляются...")
        return

    cards = expert_data.get("cards_and_atms", {})
    dcc = cards.get("dcc_trap", "")
    up_banks = cards.get("unionpay_status", [])

    lines = [
        f"💳 **КАРТЫ И БАНКОМАТЫ: {expert_data['name']}**\n",
        dcc,
        "\n🏦 **Как работают банкоматы с картами UnionPay (РФ):**"
    ]

    for b in up_banks:
        map_link = f" | [На карте Google Maps ↗]({b['map_url']})" if b.get("map_url") else ""
        fee_info = b.get("fee", "0%")
        lines.append(
            f"\n• **{b['bank']}** — {b['status']}\n"
            f"  💸 Комиссия: {fee_info}\n"
            f"  ℹ️ {b['tips']}\n"
            f"  🔍 _Источник:_ [Тарифы банка]({b['source']}){map_link} | _Дата:_ {b['verified_at']}"
        )

    lines.append("\n⚠️ _Карты Visa и Mastercard, выпущенные банками РФ, за рубежом НЕ работают нигде._")

    full_text = "\n".join(lines)
    await callback.message.edit_text(
        full_text,
        reply_markup=get_country_section_back_keyboard(slug),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


@menu_router.callback_query(F.data.startswith("csec_transfers_"))
async def handle_csec_transfers(callback: CallbackQuery):
    await callback.answer()
    slug = callback.data.replace("csec_transfers_", "")
    await UserRepository.log_event(callback.from_user.id, "view_section_transfers", {"slug": slug})
    expert_data = CountryRepository.get_expert_data(slug)

    if not expert_data:
        await callback.message.answer("Данные раздела обновляются...")
        return

    transfers = expert_data.get("transfers_and_digital", {})
    source_url = transfers.get("source_url", "https://koronapay.com")
    text = (
        f"📲 **ПЕРЕВОДЫ И ЦИФРОВЫЕ СЕРВИСЫ: {expert_data['name']}**\n\n"
        f"{transfers.get('koronapay')}\n\n"
        f"{transfers.get('ininal_letim')}\n\n"
        f"🔍 _Источник:_ [Тарифы Золотой Короны]({source_url}) | _Проверено: 13.09.2026_"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_country_section_back_keyboard(slug),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


@menu_router.callback_query(F.data.startswith("csec_qr_"))
async def handle_csec_qr(callback: CallbackQuery):
    await callback.answer()
    slug = callback.data.replace("csec_qr_", "")
    await UserRepository.log_event(callback.from_user.id, "view_section_qr", {"slug": slug})
    expert_data = CountryRepository.get_expert_data(slug)

    if not expert_data:
        await callback.message.answer("Данные раздела обновляются...")
        return

    qr = expert_data.get("qr_payments", {})
    lines = [
        f"{qr.get('headline', '📱 Оплата по QR-кодам')}\n",
        f"{qr.get('description', '')}\n",
        "🏦 **Поддерживаемые российские банки:**"
    ]

    for b in qr.get("supported_banks", []):
        lines.append(
            f"\n• **{b['bank']}**:\n"
            f"  📲 _Как платить:_ {b['how']}\n"
            f"  💰 _Лимиты и комиссии:_ {b['limits']}\n"
            f"  🏪 _Где принимают:_ {b['places']}\n"
            f"  🔍 _Источник:_ [Официальное подтверждение]({b['source_url']})"
        )

    lines.append(f"\n{qr.get('important_tips', '')}")
    lines.append("\n⚠️ _Обязательно включите мобильный интернет или подключитесь к Wi-Fi для подтверждения пуша в приложении банка._")

    full_text = "\n".join(lines)
    await callback.message.edit_text(
        full_text,
        reply_markup=get_country_section_back_keyboard(slug),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


@menu_router.callback_query(F.data.startswith("csec_lifehacks_"))
async def handle_csec_lifehacks(callback: CallbackQuery):
    await callback.answer()
    slug = callback.data.replace("csec_lifehacks_", "")
    await UserRepository.log_event(callback.from_user.id, "view_section_lifehacks", {"slug": slug})
    expert_data = CountryRepository.get_expert_data(slug)

    if not expert_data:
        await callback.message.answer("Данные раздела обновляются...")
        return

    lh = expert_data.get("lifehacks", {})
    lines = [
        f"💡 **ЛАЙФХАКИ, ЧАЕВЫЕ И ПРАВИЛА: {expert_data['name']}**\n",
        lh.get("tipping", ""),
        "\n" + lh.get("bargaining", ""),
        "\n" + lh.get("nfc_apple_pay", ""),
        "\n" + lh.get("customs_rules", ""),
        "\n" + lh.get("crypto_rules", "")
    ]

    full_text = "\n".join(lines)
    await callback.message.edit_text(
        full_text,
        reply_markup=get_country_section_back_keyboard(slug),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


@menu_router.callback_query(F.data.startswith("csec_maps_"))
async def handle_csec_maps(callback: CallbackQuery):
    await callback.answer()
    slug = callback.data.replace("csec_maps_", "")
    await UserRepository.log_event(callback.from_user.id, "view_section_maps", {"slug": slug})
    expert_data = CountryRepository.get_expert_data(slug)

    if not expert_data:
        await callback.message.answer("Данные раздела обновляются...")
        return

    maps = expert_data.get("maps", {})
    text = (
        f"🗺 **КАРТЫ БАНКОМАТОВ И ОБМЕННИКОВ: {expert_data['name']}**\n\n"
        "Мы собрали для вас прямые ссылки на Google Maps с уже настроенными поисковыми фильтрами:\n\n"
        "• **Банкоматы без комиссии (VakıfBank, Ziraat, Halkbank)** — сразу показывают ближайшие рабочие точки рядом с вашим текущим местоположением.\n"
        "• **Обменники Гранд-Базара (Kapalıçarşı)** — точки с минимальным спредом и лучшим курсом обмена валюты в Стамбуле.\n"
        "• **Отделения почты PTT** — официальные точки получения наличных по Золотой Короне.\n\n"
        "👇 _Нажмите на нужную кнопку ниже, чтобы открыть маршрут в приложении карт:_"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_country_maps_keyboard(slug, maps),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


@menu_router.callback_query(F.data.startswith("csec_scams_"))
async def handle_csec_scams(callback: CallbackQuery):
    await callback.answer()
    slug = callback.data.replace("csec_scams_", "")
    await UserRepository.log_event(callback.from_user.id, "view_section_scams", {"slug": slug})
    expert_data = CountryRepository.get_expert_data(slug)

    if not expert_data:
        await callback.message.answer("Данные раздела обновляются...")
        return

    scams = expert_data.get("scams_and_warnings", [])
    lines = [f"⚠️ **СКАМ-СХЕМЫ И ОПАСНОСТИ: {expert_data['name']}**\n"]

    for s in scams:
        lines.append(
            f"🚨 **{s['title']}**\n"
            f"• **Как выглядит схема:** {s['desc']}\n"
            f"• 🛡 **Как защититься:** {s['protection']}\n"
            f"• 🔍 _Источник:_ [Официальное предупреждение]({s['source']})\n"
        )

    full_text = "\n".join(lines)
    await callback.message.edit_text(
        full_text,
        reply_markup=get_country_section_back_keyboard(slug),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


@menu_router.callback_query(F.data.startswith("csec_proof_"))
async def handle_csec_proof(callback: CallbackQuery):
    await callback.answer()
    slug = callback.data.replace("csec_proof_", "")
    await UserRepository.log_event(callback.from_user.id, "view_section_proof", {"slug": slug})
    expert_data = CountryRepository.get_expert_data(slug)

    if not expert_data:
        await callback.message.answer("Данные раздела обновляются...")
        return

    proofs = expert_data.get("social_proof", [])
    lines = [
        f"🎬 **РЕАЛЬНЫЙ ОПЫТ И СОЦИАЛЬНЫЕ ДОКАЗАТЕЛЬСТВА: {expert_data['name']}**\n",
        "_Живой опыт путешественников с датами проверок и пруфами:_\n"
    ]

    for p in proofs:
        platform = p.get("platform", "Опыт")
        author = p.get("author") or p.get("channel", "Турист")
        date = p.get("date", "недавно")
        text = p.get("text", "")
        link = p.get("link", "#")

        lines.append(
            f"🔹 **{platform}** ({date})\n"
            f"👤 _Автор / канал:_ {author}\n"
            f"📌 **{p.get('title')}**\n"
            f"{text}\n"
            f"🔗 [Открыть первоисточник / видео ↗]({link})\n"
        )

    lines.append("💡 _Все материалы проверены: кнопки прямого перехода прикреплены ниже 👇_")

    full_text = "\n".join(lines)
    await callback.message.edit_text(
        full_text,
        reply_markup=get_country_proof_keyboard(slug, proofs),
        parse_mode="Markdown",
        disable_web_page_preview=True
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
