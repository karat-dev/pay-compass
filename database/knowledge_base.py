"""
Detailed expert knowledge base for Turkey and priority countries.
Contains factual data, exact rules, deep verified links, Google Maps filters,
QR-code payment guides, tipping rules, customs limits, and Social Proof.

Forum posts are not part of user-facing country copy. Curated Turkey notes that
came from forums stay in community_insights for internal reading; render paths
for travelers skip that block.
"""

from typing import Dict, Any, List, Optional

TURKEY_DATA: Dict[str, Any] = {
    "name": "Турция 🇹🇷",
    "slug": "turkey",
    "headline": "Статус на сегодня: UnionPay РФ работает в банкоматах госбанков (0% комиссии). Запущена оплата по QR (TR QR) через Сбер, ВТБ и МТС Банк. Наличные $ — строго синие.",
    
    # 1. Maps & Navigation (Google Maps with pre-applied filters)
    "maps": {
        "vakifbank_atms": "https://www.google.com/maps/search/VakifBank+ATM/",
        "ziraat_atms": "https://www.google.com/maps/search/Ziraat+Bankasi+ATM/",
        "halkbank_atms": "https://www.google.com/maps/search/Halkbank+ATM/",
        "grand_bazaar_exchange": "https://www.google.com/maps/search/Grand+Bazaar+Doviz+Istanbul/",
        "ptt_post_offices": "https://www.google.com/maps/search/PTT+Posta+Istanbul/"
    },

    # 2. Currency & Cash Rules
    "currency_info": {
        "official_currency": "Турецкая лира (TRY, ₺)",
        "cash_rubles": "❌ Обмен наличных рублей крайне невыгоден: спред в обменниках достигает 20-30%. Везите наличную валюту или переводите через Золотую Корону / СБП.",
        "usd_eur_rules": (
            "💵 **Правило долларов в Турции:**\n"
            "• **Брать строго 'синие' купюры $100** нового образца (выпуск с 2013 года).\n"
            "• **'Белые' доллары (1996–2006 гг.):** в большинстве обменников либо отказываются принимать, "
            "либо взимают скрытую комиссию 5–10% за 'ветхость'.\n"
            "• Купюры должны быть идеальными: без штампов, надрывов, жирных пятен и заломов.\n"
            "• В аэропортах Стамбула (IST/SAW) и Антальи курс занижен на 15–20%. "
            "Меняйте там не более $20–30 на первый транспорт/Havaist, остальное — в городе."
        ),
        "best_exchangers": (
            "📍 **Где лучший курс обмена (Döviz Bürosu):**\n"
            "• **Стамбул**: Гранд-Базар (район Kapalıçarşı), Сиркеджи (Sirkeci), Лалели (Laleli). Курс максимально близок к биржевому.\n"
            "• **Избегайте**: обменников на улице Истикляль (Istiklal), возле Голубой мечети и на рецепциях отелей — спред до 10-15%."
        ),
        "source_url": "https://cbr.ru/crosscut/lawacts/file/5923"
    },

    # 3. Cards & ATMs (with DCC trap)
    "cards_and_atms": {
        "dcc_trap": (
            "🚨 **ГЛАВНАЯ ЛОВУШКА БАНКОМАТОВ — DCC (двойная конвертация):**\n"
            "Когда турецкий банкомат или POS-терминал видит иностранную карту, он услужливо предлагает списать сумму "
            "в валюте вашей карты (рублях или долларах) по собственному курсу банка (+8–12% потерь).\n"
            "👉 **ПРАВИЛО:** ВСЕГДА нажимайте кнопку **'Continue without conversion' (Списать в турецких лирах / TRY)**."
        ),
        "unionpay_status": [
            {
                "bank": "VakıfBank 🟢 (Госбанк)",
                "status": "✅ Работает отлично",
                "fee": "0% со стороны турецкого банка",
                "tips": "Снятие лир без комиссии турецкого банкомата с карт РСХБ и Газпромбанк UnionPay. Лимит: до 4000-5000 ₺ за операцию.",
                "source": "https://www.vakifbank.com.tr/Default.aspx?pageID=605",
                "map_url": "https://www.google.com/maps/search/VakifBank+ATM/",
                "verified_at": "13.09.2026",
                "confidence": 0.98
            },
            {
                "bank": "Ziraat Bankası 🔴 (Госбанк)",
                "status": "✅ Работает отлично",
                "fee": "0% со стороны турецкого банка",
                "tips": "Крупнейшая государственная сеть банкоматов. Доступны лиры почти в любой деревне.",
                "source": "https://www.ziraatbank.com.tr/en/our-bank/info-bank/atms",
                "map_url": "https://www.google.com/maps/search/Ziraat+Bankasi+ATM/",
                "verified_at": "13.09.2026",
                "confidence": 0.98
            },
            {
                "bank": "Halkbank 🔵 (Госбанк)",
                "status": "✅ Работает стабильно",
                "fee": "0% со стороны турецкого банка",
                "tips": "Выдача лир без комиссии. В туристических локациях иногда заканчивается наличность к вечеру.",
                "source": "https://www.halkbank.com.tr/en/individual-banking/other/branch-and-atm-locator.html",
                "map_url": "https://www.google.com/maps/search/Halkbank+ATM/",
                "verified_at": "12.09.2026",
                "confidence": 0.96
            },
            {
                "bank": "İşbank / DenizBank / Akbank / Garanti BBVA (Частные банки)",
                "status": "⚠️ Не рекомендуется",
                "fee": "Комиссия 6–8% (Direct Access Fee) либо отказ",
                "tips": "Берут высокую собственную комиссию (Direct Access Fee) либо отклоняют карты банков РФ.",
                "source": "https://www.denizbank.com/en",
                "map_url": "https://www.google.com/maps/search/Garanti+ATM/",
                "verified_at": "11.09.2026",
                "confidence": 0.92
            }
        ]
    },

    # 4. QR-Code Payments (TR QR / Karekod by Russian Banks)
    "qr_payments": {
        "headline": "📱 **Оплата по QR-кодам (TR QR / Karekod) картами РФ**",
        "description": (
            "С марта 2025 года российские банки запустили прямую оплату в Турции через национальную систему **TR QR (Karekod)**. "
            "Деньги списываются прямо с вашего рублевого счета или карт любых систем (включая МИР, Visa и Mastercard банков РФ)!"
        ),
        "supported_banks": [
            {
                "bank": "ВТБ (ВТБ Онлайн)",
                "how": "В приложении 'ВТБ Онлайн' нажать 'Оплата по QR' ➔ навести на QR-код терминала или предчека (Karekod) ➔ подтвердить.",
                "limits": "От 10 ₽ до 350 000 ₽ за одну операцию. Комиссия 0%, курс конвертации показывается на экране перед списанием.",
                "places": "LC Waikiki, DeFacto, Koton, сетевые рестораны, супермаркеты, аптеки с терминалами Vakıf/Ziraat.",
                "source_url": "https://www.vtb.ru/personal/perevody-i-platezhi/po-qr-kodu/"
            },
            {
                "bank": "МТС Банк / Приложение 'Мой МТС'",
                "how": "В приложении 'Мой МТС' (или МТС Банк) открыть вкладку 'Деньги' ➔ 'Оплата по QR-коду' ➔ отсканировать TR QR.",
                "limits": "Списание со счета абонента или с карты любого банка РФ. Без комиссии. Динамический курс (+2-3% к бирже).",
                "places": "Более 50 000 торговых точек в Турции, принимающих национальный TR QR.",
                "source_url": "https://moskva.mts.ru/about/media-centr/soobshheniya-kompanii/novosti-mts-v-rossii-i-mire/2025-03-12/mts-zapustila-v-mobilnom-prilozhenii-oplatu-po-qr-kodu-v-turcii"
            },
            {
                "bank": "Сбер (СберБанк Онлайн)",
                "how": "В приложении 'СберБанк Онлайн' открыть сканер QR ➔ отсканировать Karekod на кассе ➔ подтвердить списание в рублях.",
                "limits": "Конвертация на стороне турецкого банка-партнера без комиссии за перевод.",
                "places": "Торговые точки с поддержкой QR от турецких эквайеров.",
                "source_url": "https://www.sberbank.ru/ru/person/payments/qr"
            }
        ],
        "important_tips": (
            "💡 **Как оплатить на кассе:**\n"
            "1. Скажите кассиру волшебное слово: **'Karekod ile ödemek istiyorum'** (Хочу оплатить по QR-коду).\n"
            "2. Кассир выведет динамический QR-код на экран терминала или распечатает чек с кодом.\n"
            "3. Отсканируйте код в приложении вашего банка и подтвердите оплату (нужен мобильный интернет!)."
        )
    },

    # 5. Transfers & Digital Cards (KoronaPay, Ininal, Letim)
    "transfers_and_digital": {
        "koronapay": (
            "📲 **Золотая Корона (KoronaPay):**\n"
            "• **Как работает:** Отправляете перевод с неподсанкционной карты РФ (Озон Банк, Райффайзен, Яндекс Пэй) "
            "самому себе в приложении Короны с выдачей наличными (USD или TRY).\n"
            "• **Где получать:** Отделения турецкой почты **PTT** (желтые вывески) или пункты **PayCell / BPN**.\n"
            "• **Что нужно для получения:** Загранпаспорт + номер перевода (MTCN) + фраза: 'Korona transferi almak istiyorum'.\n"
            "• **Нюанс:** В PTT выдача долларов зависит от остатка в кассе, лиры выдают гарантированно."
        ),
        "ininal_letim": (
            "💳 **Предоплаченные турецкие карты (Ininal / Letim):**\n"
            "• **Ininal:** Физическая карта покупается в магазинах Migros/D&R за 50-70 ₺. Активируется в приложении по загранпаспорту. "
            "Пополняется через 'Золотую Корону' прямо в лирах. Лимит базового тарифа — 2750 ₺/мес (до 500 000 ₺ с верификацией).\n"
            "• **Letim:** Электронный кошелек с пополнением через СБП с российских банков. Оплата в магазинах по QR-коду Troy."
        ),
        "source_url": "https://koronapay.com/transfers/turkey/"
    },

    # 6. Lifehacks, Tips, Customs, NFC & Crypto
    "lifehacks": {
        "tipping": (
            "🛎 **Чаевые в Турции (Bahşiş):**\n"
            "• **Рестораны и кафе:** 5–10% от чека наличными. В туристических местах Стамбула в чек иногда уже включен 'Kuşver' (сервисный сбор 10%) — проверяйте строку 'Servis bedeli'. Если включен, доплачивать не нужно.\n"
            "• **Отели:** Носильщику — 20–50 ₺ (или $1-2) за чемодан; горничной — 50–100 ₺ за несколько дней (оставлять строго на подушке, иначе не возьмут).\n"
            "• **Такси:** Чаевые не приняты, но счет обычно округляют в большую сторону (например, со 185 ₺ до 200 ₺)."
        ),
        "bargaining": (
            "🤝 **Культура торга:**\n"
            "• **Где торговаться ОБЯЗАТЕЛЬНО:** Гранд-Базар, Египетский базар, частные лавки сувениров, кожи, золота и уличные рынки. Первоначальную цену можно сбить на 30–50%.\n"
            "• **Где торговаться НЕЛЬЗЯ:** Супермаркеты (BIM, Migros, Carrefour), аптеки (Eczane), торговые центры (Cevahir, Mall of Istanbul), рестораны с меню."
        ),
        "nfc_apple_pay": (
            "📱 **Apple Pay, Google Pay и Бесконтактная оплата:**\n"
            "• Российские карты в Apple Pay / Google Pay заблокированы глобально.\n"
            "• Карты UnionPay РФ привязать к Apple Pay нельзя (работает только физический пластик).\n"
            "• **Лайфхак для Android:** Карты UnionPay некоторых банков (например, Газпромбанк) можно привязать к сервису **Huawei Pay** или сервису Mir Pay (только внутри РФ)."
        ),
        "customs_rules": (
            "🛃 **Ввоз и вывоз денег (Таможенные лимиты):**\n"
            "• **Вывоз из РФ:** Строго до $10 000 (или эквивалент) наличными на одного человека (включая детей). Свыше $10 000 вывозить запрещено указом Президента РФ.\n"
            "• **Ввоз в Турцию:** Сумма наличной валюты на ввоз НЕ ограничена. Но суммы свыше $5 000 или эквивалент рекомендуется задекларировать, если планируете вывозить их обратно.\n"
            "• **Вывоз лир из Турции:** Разрешено вывозить до 25 000 турецких лир без декларации."
        ),
        "crypto_rules": (
            "🪙 **Криптовалюта в Турции:**\n"
            "• Прямая оплата товаров и услуг криптовалютой в Турции законодательно запрещена ЦБ Турции (TCMB).\n"
            "• Однако физический обмен USDT на наличные USD/TRY абсолютно легален через лицензированные офисы `NakitCoins` и криптообменники в районах Кадыкёй и Фатих."
        )
    },

    # 7. Scams & Warnings
    "scams_and_warnings": [
        {
            "title": "Фейковые крипто-курьеры в Стамбуле и Анталье",
            "desc": (
                "Схема в русскоязычных Telegram-чатах: предлагают встретиться и обменять USDT на наличные доллары "
                "с курьером. Курьер выдает фальшивые стодолларовые банкноты или забирает перевод до передачи денег и скрывается."
            ),
            "protection": "Обменивайте крипту строго в физических лицензированных крипто-офисах (Döviz / Crypto Shop) с проверкой купюр на детекторе.",
            "source": "https://t.me/travel_payments_news"
        },
        {
            "title": "Ловушка такси и 'похожих купюр'",
            "desc": (
                "Водитель желтого такси при оплате купюрой в 200 ₺ делает вид, что уронил ее или что вы дали 20 ₺, "
                "требуя доплатить. Либо заявляет, что сдачи нет."
            ),
            "protection": "Используйте приложение BiTaksi или Uber (привязав иностранную/виртуальную карту), либо отдавайте точную сумму под расчет, четко озвучивая номинал купюры вслух.",
            "source": "https://turkey.mid.ru"
        }
    ],

    # 8. Internal verification notes. Not rendered to travelers (see forum_section_text).
    "community_insights": {
        "internal_only": True,
        "headline": "💬 **Сводка реального опыта путешественников (Форум Винского)**",
        "description": "Анализ сообщений из веток 'Банковские карты и наличные в Турции'. Собраны только повторяющиеся, подтвержденные данные без рекламы посредников.",
        "verified_period": "Сентябрь 2026",
        "key_takeaways": [
            {
                "topic": "Банкоматы и карты UnionPay",
                "consensus": "✅ 85% успешных операций в банкоматах VakıfBank и Ziraat Bankası",
                "details": (
                    "• Опыт подтверждает: рублевые карты UnionPay (РСХБ, АТБ) стабильно выдают наличные лиры в банкоматах государственных банков.\n"
                    "• Обязательное условие: на этапе предложения конвертации выбирать отказ ('Without conversion' / списание в TRY).\n"
                    "• В курортных поселках банкоматы Ziraat иногда исчерпывают запас наличных к вечеру воскресенья — снимайте деньги заранее в первой половине дня."
                ),
                "date_verified": "12.09.2026",
                "confidence": 0.94
            },
            {
                "topic": "Наличная валюта и обменники",
                "consensus": "⚠️ Строгий отбор стодолларовых купюр",
                "details": (
                    "• Участники форума фиксируют: обменники в Стамбуле и Анталье поголовно отказываются от долларов 'старого образца' (белые, до 2006 года) или срезают курс на 5-10%.\n"
                    "• Купюры с микронадрывами или чернильными штампами кассиры не принимают даже с дисконтом.\n"
                    "• Лучший спред стабильно в районе Гранд-Базара (улица Mahmudpaşa и Sirkeci) — разница с аэропортом составляет до 15% в пользу туриста."
                ),
                "date_verified": "11.09.2026",
                "confidence": 0.98
            },
            {
                "topic": "Золотая Корона (KoronaPay) в отделениях PTT",
                "consensus": "✅ Надежный способ получения наличных лир и долларов",
                "details": (
                    "• Переводы через Корону с неподсанкционных банков РФ приходят мгновенно.\n"
                    "• В центральных отделениях турецкой почты (PTT) доллары выдают новыми купюрами без комиссий при наличии запаса в кассе.\n"
                    "• Если в небольшом отделении закончились доллары, оператор сразу предлагает выдать сумму в лирах по официальному курсу системы."
                ),
                "date_verified": "10.09.2026",
                "confidence": 0.92
            },
            {
                "topic": "Оплата по QR (Karekod) в супермаркетах",
                "consensus": "✅ Работает в сетевых магазинах через ВТБ и МТС",
                "details": (
                    "• В магазинах LC Waikiki, Koton, DeFacto и крупных аптеках оплата по TR QR через приложение банка РФ проходит успешно.\n"
                    "• Важно иметь стабильный мобильный интернет на смартфоне для подтверждения push-уведомления."
                ),
                "date_verified": "13.09.2026",
                "confidence": 0.90
            }
        ]
    }
}

DATE_VERIFIED = "13.10.2026"

ALLOWED_FACT_STATUSES = (
    "подтверждено",
    "не подтверждено",
    "устарело",
    "под вопросом",
)

RSHB_UNIONPAY_PDF = (
    "https://www.rshb.ru/ (PDF «Информация о доступности сети приёма карт UnionPay в мире»)"
)
ATB_UNIONPAY_URL = "https://www.atb.su/atb-karta-unionpay-lp-6/"
RSHB_UNIONPAY_CASH_URL = "https://www.rshb.ru/natural/debetcards/unionpay-cash"


def make_fact(
    text: str,
    status: str,
    source: Optional[str] = None,
    source_type: Optional[str] = None,
    title: Optional[str] = None,
    section: str = "cards",
) -> Dict[str, Any]:
    if status not in ALLOWED_FACT_STATUSES:
        raise ValueError(f"Unexpected fact status: {status}")
    return {
        "title": title or text,
        "text": text,
        "status": status,
        "date_verified": DATE_VERIFIED,
        "source": source,
        "source_type": source_type,
        "section": section,
    }


def format_fact(fact: Dict[str, Any]) -> str:
    """Traveler-facing fact: original wording, status, check date, source."""
    source = fact.get("source")
    source_type = fact.get("source_type")
    if source:
        source_line = f"Источник: {source}."
    elif source_type:
        source_line = f"Официальной ссылки нет ({source_type})."
    else:
        source_line = "Официальной ссылки нет."
    return (
        f"{fact['text']}\n"
        f"Статус: {fact['status']}. Проверено: {fact.get('date_verified') or DATE_VERIFIED}. {source_line}"
    )


def format_source_link(
    source: Optional[str],
    source_type: Optional[str] = None,
    link_label: str = "Источник",
) -> str:
    """Markdown link when the source starts with http; otherwise an honest gap."""
    if isinstance(source, str) and source.startswith("http"):
        url = source.split()[0]
        note = source[len(url):].strip()
        line = f"[{link_label}]({url})"
        if note:
            line = f"{line} {note}"
        return line
    if source:
        return str(source)
    if source_type:
        return f"официальной ссылки нет ({source_type})"
    return "официальной ссылки нет"


def forum_section_text(country: Optional[Dict[str, Any]] = None) -> str:
    """Policy line only. Does not quote forum posts or internal takeaways."""
    del country
    return (
        "💬 **Форумы**\n\n"
        "Сообщения с форумов используются только для внутренней сверки и в справочнике не цитируются. "
        "Сырые посты Forum AWD в тексты для путешественников не попадают.\n\n"
        "Факты в остальных разделах подписаны статусом проверки. "
        "«Не подтверждено», «устарело» и «под вопросом» так и показаны."
    )


def common_payment_facts() -> List[Dict[str, Any]]:
    """Facts that apply to China, Hong Kong, Thailand and the UAE."""
    return [
        make_fact(
            "Российские Visa и Mastercard за рубежом не работают.",
            "подтверждено",
            source_type="общеизвестно/СМИ",
            title="Visa и Mastercard банков РФ",
        ),
        make_fact(
            "UnionPay АТБ: открытие 6 000 ₽ (570 ¥) при заявке на сайте; обслуживание 0 ₽ при тратах или остатке от 30 000 ₽ в месяц, иначе 399 ₽; снятие за рубежом 1,5% + 250 ₽ (рублёвый счёт) или 2,5% + 22 ¥ (юаневый).",
            "подтверждено",
            source=ATB_UNIONPAY_URL,
            source_type="official",
            title="UnionPay АТБ: тариф",
        ),
        make_fact(
            "UnionPay РСХБ: первая рублёвая карта бесплатно, следующие 4 500 ₽, валютная 380 ¥; снятие за рубежом 2%, минимум 299 ₽ (рублёвый счёт).",
            "подтверждено",
            source=RSHB_UNIONPAY_CASH_URL,
            source_type="official",
            title="UnionPay РСХБ: тариф",
        ),
        make_fact(
            "Лимит UnionPay для карт российских банков: снятие не более 50 000 ¥ в день и 500 000 ¥ в год на карту.",
            "подтверждено",
            source=RSHB_UNIONPAY_PDF,
            source_type="official",
            title="Лимит снятия UnionPay",
        ),
        make_fact(
            "Китай, Гонконг, Таиланд и ОАЭ не входят в список стран с ограничениями UnionPay для российских карт. Это не гарантия: конкретный банк или терминал может отказать.",
            "подтверждено",
            source=RSHB_UNIONPAY_PDF,
            source_type="official",
            title="Страны без ограничений UnionPay",
        ),
        make_fact(
            "Курсовую наценку банки не публикуют — реальный курс виден только после операции.",
            "подтверждено",
            source_type="наблюдение",
            title="Курсовая наценка",
        ),
        make_fact(
            "Карта «Мир» в этих странах не работает.",
            "не подтверждено",
            source_type="СМИ, есть противоречия",
            title="Карта «Мир»",
        ),
    ]


def _card_row(fact: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "bank": fact["title"],
        "status": fact["status"],
        "fee": "—",
        "tips": format_fact(fact),
        "source": fact.get("source") or "",
        "source_type": fact.get("source_type") or "",
        "map_url": "",
        "verified_at": fact["date_verified"],
        "date_verified": fact["date_verified"],
    }


def _qr_row(fact: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "bank": fact["title"],
        "status": fact["status"],
        "how": format_fact(fact),
        "limits": f"Статус: {fact['status']}. Проверено: {fact['date_verified']}.",
        "places": fact.get("source_type") or "—",
        "source_url": fact.get("source") or "",
        "source_type": fact.get("source_type") or "",
    }


def build_country_data(
    *,
    name: str,
    slug: str,
    headline: str,
    official_currency: str,
    cash_rubles: str,
    usd_eur_rules: str,
    best_exchangers: str,
    source_url: Optional[str],
    source_label: str,
    setup_steps: List[str],
    how_to_pay: List[str],
    facts: List[Dict[str, Any]],
    open_questions: List[str],
    risks: List[Dict[str, str]],
    hub_labels: Dict[str, str],
    maps_intro: str,
    qr_headline: str,
    qr_description: str,
) -> Dict[str, Any]:
    card_facts = [f for f in facts if f["section"] == "cards"]
    qr_facts = [f for f in facts if f["section"] == "qr"]
    transfer_facts = [f for f in facts if f["section"] == "transfers"]

    transfer_parts = [format_fact(f) for f in transfer_facts]
    if open_questions:
        lines = "\n".join(f"• {q}" for q in open_questions)
        transfer_parts.append(
            "Открытые вопросы. В источнике у них нет статуса "
            "«подтверждено», «не подтверждено», «устарело» или «под вопросом»:\n"
            + lines
        )

    setup = "\n".join(f"{i}. {step}" for i, step in enumerate(setup_steps, 1))
    pay = "\n".join(f"• {step}" for step in how_to_pay)
    practical = (
        f"**Что сделать до поездки**\n{setup}\n\n"
        f"**Как платить на месте**\n{pay}\n\n"
        "Это шаги из памятки, не отдельные факты со статусом проверки."
    )

    return {
        "name": name,
        "slug": slug,
        "headline": headline,
        "date_verified": DATE_VERIFIED,
        "hub_labels": hub_labels,
        "maps": {},
        "maps_intro": maps_intro,
        "currency_info": {
            "official_currency": official_currency,
            "cash_rubles": cash_rubles,
            "usd_eur_rules": usd_eur_rules,
            "best_exchangers": best_exchangers,
            "source_url": source_url,
            "source_label": source_label,
            "date_verified": DATE_VERIFIED,
        },
        "cards_and_atms": {
            "dcc_trap": (
                f"Сверка фактов: {DATE_VERIFIED}. У каждого факта указан статус. "
                "«Не подтверждено», «устарело» и «под вопросом» нельзя читать как проверенное правило."
            ),
            "section_title": "Факты по картам, лимитам и комиссиям:",
            "unionpay_status": [_card_row(f) for f in card_facts],
        },
        "qr_payments": {
            "headline": qr_headline,
            "description": qr_description,
            "supported_banks": [_qr_row(f) for f in qr_facts],
            "important_tips": (
                "Если статус факта не «подтверждено», не делайте этот способ единственным."
            ),
        },
        "transfers_and_digital": {
            "koronapay": "\n\n".join(transfer_parts) if transfer_parts else "Отдельных фактов по переводам в памятке нет.",
            "ininal_letim": "",
            "source_url": source_url,
            "source_label": source_label,
            "date_verified": DATE_VERIFIED,
        },
        "lifehacks": {
            "practical": practical,
            "tipping": "",
            "bargaining": "",
            "nfc_apple_pay": "",
            "customs_rules": "",
            "crypto_rules": "",
        },
        "scams_and_warnings": [
            {
                "title": risk["title"],
                "desc": risk["text"],
                "protection": risk["protection"],
                "source": risk.get("source") or "",
                "source_type": "памятка, отдельный статус проверки не указан",
            }
            for risk in risks
        ],
        "community_insights": {
            "internal_only": True,
            "key_takeaways": [],
            "description": "Форумы только для внутренней сверки, пользователям не цитируются.",
        },
        "facts": facts,
    }


_STATUS_INTRO = (
    "Ниже только то, что есть в памятке на 13.10.2026. "
    "Отдельной проверенной точки на карте в источниках нет, поэтому кнопок с «лучшими» банкоматами нет."
)

CHINA_DATA: Dict[str, Any] = build_country_data(
    name="Китай 🇨🇳",
    slug="china",
    headline=(
        "Главный способ оплаты — QR (Alipay/WeChat). Надёжнее всего иметь 2–3 способа: "
        "пополненный кошелёк, карту UnionPay и наличные юани. Сверка: 13.10.2026."
    ),
    official_currency="Китайский юань (CNY, ¥)",
    cash_rubles=(
        "На первый день в памятке советуют взять ¥300–500 наличными. "
        "Это шаг подготовки, не тариф со статусом проверки. "
        "Обмен наличных рублей в источниках отдельно не описан."
    ),
    usd_eur_rules="Наличные юани — запасной вариант (такси, рынки), если QR и карта не проходят.",
    best_exchangers=(
        "Список проверенных обменников в источниках по Китаю не указан. "
        "Случайный обменник не стоит считать подтверждённым способом."
    ),
    source_url="https://www.vtb.ru/personal/platezhi-i-perevody/perevody-v-kitaj/",
    source_label="ВТБ: переводы в Китай",
    setup_steps=[
        "Установить Alipay (международную версию) и/или WeChat, зарегистрироваться по номеру +7, пройти верификацию по загранпаспорту — ещё дома.",
        "Выбрать способ пополнения кошелька из России (ниже) и сделать пробное пополнение на небольшую сумму до вылета.",
        "Оформить UnionPay АТБ или РСХБ как запасной вариант (карту выпускают не мгновенно — закладывайте время).",
        "Купить eSIM или местную SIM: по отзывам, приложения оплаты в российском роуминге по мобильному интернету работают плохо.",
        "Взять ¥300–500 наличными на первый день.",
    ],
    how_to_pay=[
        "В магазине: показать свой QR в Alipay/WeChat или отсканировать QR продавца.",
        "Где QR не проходит — карта UnionPay в терминале.",
        "Наличные — запасной вариант (такси, рынки).",
    ],
    facts=common_payment_facts() + [
        make_fact(
            "ВТБ: перевод в Китай по номеру телефона на популярные кошельки — комиссия от 0%, курс банка.",
            "подтверждено",
            source="https://www.vtb.ru/personal/platezhi-i-perevody/perevody-v-kitaj/",
            source_type="official",
            title="ВТБ → кошельки Китая",
            section="qr",
        ),
        make_fact(
            "ВТБ: работает ли зачисление на кошелёк, зарегистрированный на российский номер.",
            "устарело",
            source_type="отзывы 2025",
            title="ВТБ: кошелёк на российском номере",
            section="qr",
        ),
        make_fact(
            "МТС («Мой МТС»): пополнение WeChat и Alipay без комиссии, курс внутри приложения, 1 100 – 400 000 ₽ за перевод.",
            "подтверждено",
            source="https://media.mts.ru/technologies/213834-kak-popolnit-wechat-i-alipay-iz-rossii",
            source_type="official",
            title="МТС → WeChat и Alipay",
            section="qr",
        ),
        make_fact(
            "Т-Банк: перевод на Alipay/WeChat по номеру — источники расходятся (только китайские номера или и +7).",
            "не подтверждено",
            source_type="СМИ",
            title="Т-Банк → Alipay/WeChat",
            section="qr",
        ),
        make_fact(
            "Сбер: перевод по номеру — бывают зависания и возвраты.",
            "не подтверждено",
            source_type="СМИ",
            title="Сбер → перевод по номеру",
            section="qr",
        ),
        make_fact(
            "Посредники (обменники в Telegram): курс хуже на 2–4%, высокий риск мошенничества и блокировки вашей карты по 115-ФЗ. Не рекомендуем.",
            "не подтверждено",
            source_type="заинтересованные источники",
            title="Посредники в Telegram",
            section="qr",
        ),
        make_fact(
            "Оплата с иностранной карты, привязанной к Alipay/WeChat: 0% до ¥200, выше — 3% со всей суммы.",
            "подтверждено",
            source="https://24isfc.casconf.cn/static/1697415579046121472/pages/file/a7dca5ed9d2146ae9317b79e296117dc.pdf",
            source_type="official",
            title="Комиссия Alipay/WeChat с иностранной карты",
        ),
        make_fact(
            "Лимиты Alipay для иностранцев: источники расходятся.",
            "не подтверждено",
            source="https://24isfc.casconf.cn/static/1697415579046121472/pages/file/a7dca5ed9d2146ae9317b79e296117dc.pdf",
            source_type="official",
            title="Лимиты Alipay для иностранцев",
        ),
        make_fact(
            "РСХБ официально: QR-оплата в Китае через приложение Nihao China, регистрация по российскому номеру.",
            "подтверждено",
            source="https://www.rshb.ru/natural/debetcards/unionpay-china",
            source_type="official",
            title="Nihao China (РСХБ, официально)",
        ),
        make_fact(
            "Nihao China с картой РСХБ на практике: QR открывается только по Wi‑Fi, пополнение Tour Wallet сбоит (октябрь 2026).",
            "подтверждено",
            source_type="отзывы путешественников",
            title="Nihao China на практике",
        ),
        make_fact(
            "Карта АТБ привязывается к Alipay/WeChat.",
            "не подтверждено",
            source_type="1 отзыв",
            title="Привязка карты АТБ к Alipay/WeChat",
        ),
        make_fact(
            "Карта РСХБ привязывается к Alipay/WeChat — данные противоречат друг другу.",
            "не подтверждено",
            source_type="СМИ/отзывы",
            title="Привязка карты РСХБ к Alipay/WeChat",
        ),
    ],
    open_questions=[
        "Корона Pay в Китай — источники расходятся.",
        "Реальная курсовая наценка ВТБ/МТС — нужен тестовый перевод.",
    ],
    risks=[
        {
            "title": "Остаток на кошельке",
            "text": "Вывести остаток с кошелька на российскую карту официального способа нет — пополняйте только запланированные траты плюс 10–15% запаса.",
            "protection": "Пополняйте только запланированные траты плюс 10–15% запаса.",
        },
        {
            "title": "Tour Pass и TourCard",
            "text": "Tour Pass/TourCard в Alipay пополняется только иностранной картой; возврат — через сервис, курсовые потери на вас.",
            "protection": "Не считайте этот баланс запасным: возврат идёт через сервис, курсовые потери на вас.",
        },
        {
            "title": "Один способ оплаты",
            "text": "Одна карта или один кошелёк — точка отказа. Имейте минимум два способа плюс наличные.",
            "protection": "Имейте минимум два способа плюс наличные.",
        },
        {
            "title": "Обменники и предоплата незнакомцу",
            "text": "Обменники и «предоплата незнакомцу» — главный риск потери денег.",
            "protection": "Не отправляйте предоплату незнакомцу.",
        },
    ],
    hub_labels={"qr": "📱 QR и пополнение", "transfers": "📲 Открытые вопросы"},
    maps_intro=_STATUS_INTRO,
    qr_headline="📱 **QR и пополнение Alipay / WeChat**",
    qr_description=(
        "Пополнение кошелька из России и оплата своим QR. У каждого способа свой статус на 13.10.2026."
    ),
)

HONG_KONG_DATA: Dict[str, Any] = build_country_data(
    name="Гонконг 🇭🇰",
    slug="hong_kong",
    headline=(
        "Нужны HKD наличными и Octopus для транспорта. "
        "Российские UnionPay в магазинах работают нестабильно. Сверка: 13.10.2026."
    ),
    official_currency="Гонконгский доллар (HKD)",
    cash_rubles=(
        "Возьмите USD, CNY или HKD наличными. Это шаг подготовки из памятки, не тариф со статусом."
    ),
    usd_eur_rules=(
        "Транспорт, 7‑Eleven и кафе в памятке закрывают картой Octopus. "
        "Остальное — наличные HKD. Карта UnionPay в первую очередь для снятия наличных, не для магазинов."
    ),
    best_exchangers="Отдельный список обменников в источниках по Гонконгу не указан.",
    source_url="https://www.octopus.com.hk/",
    source_label="Octopus",
    setup_steps=[
        "Взять USD/CNY или HKD наличными.",
        "Оформить UnionPay АТБ/РСХБ для снятия наличных.",
        "В аэропорту купить Tourist Octopus.",
    ],
    how_to_pay=[
        "Транспорт, 7‑Eleven, кафе — Octopus.",
        "Остальное — наличные HKD.",
        "Карта UnionPay — в первую очередь для снятия наличных.",
    ],
    facts=common_payment_facts() + [
        make_fact(
            "Tourist Octopus — HK$39, без залога; пополнение наличными в 7‑Eleven, Circle K, на транспорте; можно пополнить через Weixin Pay.",
            "подтверждено",
            source="https://www.octopus.com.hk/",
            source_type="official",
            title="Tourist Octopus",
            section="qr",
        ),
        make_fact(
            "Карта РСХБ: снятие в аэропорту проходит, в магазинах и ресторанах часто отклоняется (сентябрь 2026).",
            "не подтверждено",
            source_type="1 отзыв",
            title="Карта РСХБ в магазинах Гонконга",
        ),
        make_fact(
            "UnionPay АТБ в банкоматах BoC/BoCom/HSBC.",
            "не подтверждено",
            source_type="СМИ",
            title="UnionPay АТБ в банкоматах BoC/BoCom/HSBC",
        ),
        make_fact(
            "Alipay/AlipayHK с российской картой не работает.",
            "не подтверждено",
            source_type="1 отзыв",
            title="Alipay и AlipayHK с российской картой",
        ),
    ],
    open_questions=["Комиссии гонконгских банкоматов для UnionPay."],
    risks=[
        {
            "title": "Оплата российской картой в магазинах",
            "text": "Не рассчитывайте платить российской картой в магазинах — имейте наличные.",
            "protection": "Держите наличные HKD. Карту не считайте основным способом в магазине.",
        },
        {
            "title": "Цифровой Octopus на iPhone",
            "text": "Цифровой Octopus в iPhone пополняется только иностранной картой.",
            "protection": "Для туристической карты закладывайте пополнение наличными, как в факте про Tourist Octopus.",
        },
    ],
    hub_labels={"qr": "📱 Octopus", "transfers": "📲 Что неясно"},
    maps_intro=_STATUS_INTRO,
    qr_headline="📱 **Octopus**",
    qr_description="Факт по Tourist Octopus со статусом проверки. Это не гарантия, что российская карта пройдёт в магазине.",
)

THAILAND_DATA: Dict[str, Any] = build_country_data(
    name="Таиланд 🇹🇭",
    slug="thailand",
    headline=(
        "Основа — наличные бат. UnionPay РСХБ принимают не везде. Сверка: 13.10.2026."
    ),
    official_currency="Тайский бат (THB)",
    cash_rubles="Основа оплаты в памятке — наличные бат. Обмен наличных рублей отдельно не описан.",
    usd_eur_rules=(
        "Возьмите USD или EUR новыми купюрами для обмена. "
        "Крупные сети можно пробовать картой UnionPay и держать наличные на случай отказа. "
        "Рынки, такси и мелкие кафе — наличные."
    ),
    best_exchangers=(
        "Курс и условия обменников в источниках не зафиксированы. "
        "Это открытый вопрос, без статуса «подтверждено» или «не подтверждено»."
    ),
    source_url="https://www.true.th/en/help/mobile/setting/faq-mobile-banking-authen",
    source_label="True: мобильный банк и SIM",
    setup_steps=[
        "Оформить UnionPay РСХБ или АТБ.",
        "Взять USD/EUR наличными новыми купюрами для обмена.",
    ],
    how_to_pay=[
        "Крупные сети — попробовать карту UnionPay, держать наличные на случай отказа.",
        "Рынки, такси, мелкие кафе — наличные.",
    ],
    facts=common_payment_facts() + [
        make_fact(
            "UnionPay РСХБ принимают в части сетей: Big C — да, Makro — нет (сентябрь–октябрь 2026).",
            "подтверждено",
            source_type="отзывы путешественников",
            title="UnionPay РСХБ: Big C и Makro",
        ),
        make_fact(
            "UnionPay АТБ в Таиланде.",
            "не подтверждено",
            source_type="отзывов нет",
            title="UnionPay АТБ в Таиланде",
        ),
        make_fact(
            "Банкоматы Bangkok Bank, Krungsri, SCB для UnionPay.",
            "устарело",
            source_type="нет отзывов >60 дней",
            title="Банкоматы Bangkok Bank, Krungsri, SCB",
        ),
        make_fact(
            "Банковское приложение в Таиланде привязано к SIM на имя клиента; при несовпадении мобильный банк приостанавливают.",
            "подтверждено",
            source="https://www.true.th/en/help/mobile/setting/faq-mobile-banking-authen",
            source_type="official",
            title="Мобильный банк и SIM",
        ),
        make_fact(
            "Комиссия тайского банкомата (~220–250 THB) поверх комиссии вашего банка.",
            "не подтверждено",
            source_type="СМИ",
            title="Комиссия тайского банкомата",
        ),
        make_fact(
            "ПОД ВОПРОСОМ: открытие местной карты туристом (Bangkok Bank, Kasikorn) — проверить на официальных страницах банков до запуска.",
            "под вопросом",
            title="Местная карта туристу",
            section="transfers",
        ),
        make_fact(
            "ПОД ВОПРОСОМ: тестовый перевод/замер курса.",
            "под вопросом",
            title="Тестовый перевод и курс",
            section="transfers",
        ),
    ],
    open_questions=["Курс и условия обменников."],
    risks=[
        {
            "title": "Отказ карты",
            "text": "Карту могут не принять — держите наличные.",
            "protection": "Держите наличные баты. Не оставляйте карту единственным способом.",
        },
        {
            "title": "Местная карта через посредника",
            "text": "Открыть местную карту туристу сейчас, по имеющимся данным, почти невозможно: банки требуют долгосрочную визу. Посредникам «под ключ» не доверяйте.",
            "protection": "Не платите посредникам «под ключ». Открытие карты туристом само по себе под вопросом — смотрите этот статус в разделе переводов.",
        },
    ],
    hub_labels={"qr": "📱 Оплата по QR", "transfers": "📲 Под вопросом"},
    maps_intro=_STATUS_INTRO,
    qr_headline="📱 **Оплата по QR**",
    qr_description=(
        "Отдельных фактов по QR-оплате в памятке по Таиланду нет. "
        "Факты по картам и банкоматам — в разделе карт, каждый со своим статусом."
    ),
)

UAE_DATA: Dict[str, Any] = build_country_data(
    name="ОАЭ 🇦🇪",
    slug="uae",
    headline=(
        "Данных мало и они устарели. Рассчитывайте на наличные USD → AED. Сверка: 13.10.2026."
    ),
    official_currency="Дирхам ОАЭ (AED)",
    cash_rubles=(
        "Рассчитывайте на наличные: USD меняют на AED в городе. "
        "Свежих подтверждений по картам мало, часть фактов помечена «устарело» или «под вопросом»."
    ),
    usd_eur_rules=(
        "Карту UnionPay можно пробовать, но будьте готовы к отказу. "
        "Это ориентир из памятки, не гарантия приёма."
    ),
    best_exchangers=(
        "Спред обмена USD → AED вынесен отдельным фактом со статусом «не подтверждено» в разделе карт."
    ),
    source_url=None,
    source_label="ссылки у фактов, где они есть",
    setup_steps=[
        "Взять USD наличными.",
        "Оформить UnionPay РСХБ/АТБ как запасной вариант — без гарантий.",
    ],
    how_to_pay=[
        "Наличные AED (обмен USD в городе).",
        "Карта UnionPay — пробовать, но быть готовым к отказу.",
    ],
    facts=common_payment_facts() + [
        make_fact(
            "UnionPay РСХБ: терминалы ADCB, Emirates NBD, Magnati пропускают, Network/NeoPay отклоняют.",
            "устарело",
            source_type="нет отзывов >60 дней",
            title="Терминалы UnionPay РСХБ",
        ),
        make_fact(
            "Банкомат Mashreq без комиссии банкомата.",
            "не подтверждено",
            source_type="1 коммерческий источник",
            title="Банкомат Mashreq",
        ),
        make_fact(
            "Обмен USD → AED: спред ~0,5–1%.",
            "не подтверждено",
            source_type="1 источник",
            title="Обмен USD → AED",
        ),
        make_fact(
            "ПОД ВОПРОСОМ: все данные по ОАЭ — нужны свежие отчёты (≤30 дней) до запуска.",
            "под вопросом",
            title="Свежесть данных по ОАЭ",
            section="transfers",
        ),
    ],
    open_questions=[],
    risks=[
        {
            "title": "Нет свежих подтверждений по картам",
            "text": "Свежих подтверждений по картам нет — не полагайтесь на карту как на единственный способ.",
            "protection": "Держите наличные USD и AED. Карта — запасной вариант без гарантии.",
        },
    ],
    hub_labels={"qr": "📱 Карты и QR", "transfers": "📲 Под вопросом"},
    maps_intro=_STATUS_INTRO,
    qr_headline="📱 **QR в ОАЭ**",
    qr_description=(
        "Отдельных фактов по QR-оплате в памятке по ОАЭ нет. "
        "Смотрите карты и обмен: у части фактов статус «устарело», «не подтверждено» или «под вопросом»."
    ),
)


_USER_FACING_SKIP_KEYS = {"facts", "community_insights", "hub_labels"}


def render_user_facing(country: Dict[str, Any]) -> str:
    """Text the country screens actually draw, without the internal fact archive or forums."""
    parts: List[str] = []

    def walk(obj: Any, key: Optional[str] = None) -> None:
        if key in _USER_FACING_SKIP_KEYS:
            return
        if isinstance(obj, dict):
            if obj.get("internal_only"):
                return
            for child_key, child in obj.items():
                walk(child, child_key)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, str) and obj.strip():
            parts.append(obj)

    walk(country)
    return "\n".join(parts)


COUNTRIES_KNOWLEDGE_BASE = {
    "turkey": TURKEY_DATA,
    "china": CHINA_DATA,
    "hong_kong": HONG_KONG_DATA,
    "thailand": THAILAND_DATA,
    "uae": UAE_DATA,
}
