"""TBC Georgia cards keep the July visit and add the 2026-10-18 sources.

Zones are whatever resolve_zone returns. The ten visit cards start from the
lowest zone, so yellow appears only after the fresh-confirmation rule and
green only after an official confirmation. The deposit note is a separate
fact: its zone is the score of its own source.
"""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fact_check_report as report  # noqa: E402
from database.knowledge_base import INSTRUCTIONS, load_trust_config  # noqa: E402
from database.trust_zones import (  # noqa: E402
    confirmation_stats,
    lowest_zone,
    ranked_zones,
    resolve_zone,
)

AS_OF = date(2026, 10, 18)
CONFIG = load_trust_config()
LANGUAGE = "Обычно говорят по-грузински и по-английски; по-русски — не везде, держите переводчик."
DEPOSIT = "По отдельным отзывам (29.09.2026), перед выдачей пластика нужно внести деньги на счёт."
NEEDED = CONFIG["upgrade"]["yellow_min_independent_confirmations"]

CARDS = {
    1: "План: в первый день купить SIM Magti",
    2: LANGUAGE,
    3: "Карта TBC работает везде, где платили (Грузия).",
    4: "TBC Bank: карту Visa выпускают гражданину РФ",
    5: "Обслуживание 10 GEL в месяц.",
    6: "Карта TBC оформляется сразу мультивалютной",
    7: "Поставить приложение-переводчик. " + LANGUAGE,
    8: "Прийти в отделение TBC с SIM в телефоне",
    9: "Заполнить анкету (сотрудники помогают)",
    10: "пластик, не забранный за 3 месяца, уничтожают.",
}
CONTEXTS = {
    1: {"section_key": "1_checklist", "subsection": None, "instruction_id": None},
    2: {"section_key": "1_checklist", "subsection": None, "instruction_id": None},
    3: {"section_key": "2_pay_on_site", "subsection": None, "instruction_id": None},
    4: {"section_key": "3_local_wallets_cards", "subsection": "local_card", "instruction_id": None},
    5: {"section_key": "3_local_wallets_cards", "subsection": "local_card", "instruction_id": None},
    6: {"section_key": "3_local_wallets_cards", "subsection": "local_card", "instruction_id": None},
    7: {"section_key": "3_local_wallets_cards", "subsection": None, "instruction_id": "tbc_georgia"},
    8: {"section_key": "3_local_wallets_cards", "subsection": None, "instruction_id": "tbc_georgia"},
    9: {"section_key": "3_local_wallets_cards", "subsection": None, "instruction_id": "tbc_georgia"},
    10: {"section_key": "3_local_wallets_cards", "subsection": None, "instruction_id": "tbc_georgia"},
}


def _bundle():
    return json.loads((ROOT / "database" / "data" / "countries.json").read_text(encoding="utf-8"))


def _walk(bundle):
    georgia = bundle["countries"]["georgia"]["sections"]
    for key, section in georgia.items():
        ctx = {"section_key": key, "subsection": None, "instruction_id": None}
        for fact in section.get("facts") or []:
            yield fact, ctx
        for name, facts in (section.get("subsections") or {}).items():
            ctx = {"section_key": key, "subsection": name, "instruction_id": None}
            for fact in facts:
                yield fact, ctx
    ctx = {"section_key": "3_local_wallets_cards", "subsection": None, "instruction_id": "tbc_georgia"}
    for fact in bundle["instructions"]["tbc_georgia"]["steps"]:
        yield fact, ctx


def _cards(bundle):
    found = {}
    for fact, ctx in _walk(bundle):
        text = fact.get("text") or ""
        matches = [number for number, needle in CARDS.items() if needle in text]
        if 2 in matches and 7 in matches:
            matches.remove(2)
        if not matches:
            continue
        assert len(matches) == 1, text
        number = matches[0]
        assert number not in found, number
        assert ctx == CONTEXTS[number]
        found[number] = fact
    assert set(found) == set(CARDS)
    return found


def _live(fact, ctx, zone=None):
    probe = json.loads(json.dumps(fact))
    if zone is not None:
        probe["zone"] = zone
    return resolve_zone(probe, config=CONFIG, as_of=AS_OF, **ctx)


def test_visit_cards_take_the_zone_the_upgrade_rule_returns():
    bundle = _bundle()
    floor = lowest_zone(CONFIG)
    green = CONFIG["upgrade"]["green_zone"]
    yellow = CONFIG["upgrade"]["yellow_zone"]
    for number, fact in _cards(bundle).items():
        ctx = CONTEXTS[number]
        shown = _live(fact, ctx)
        assert fact["zone"] == shown["zone"]
        assert fact["score"] == shown["score"]
        assert fact["owner_approved"] is False
        fresh = shown["confirmations"]["fresh_count"]
        owner_checked = (
            fact.get("verified_by_us") is True
            and shown["age_days"] is not None
            and shown["age_days"] <= CONFIG["volatility"]["classes"][shown["volatility_class"]]["green_max_days"]
        )
        if not owner_checked:
            assert fact["zone"] == _live(fact, ctx, floor)["zone"]
        if owner_checked:
            assert fact["date_verified"] == "2026-10-18"
            assert fact["zone"] == green
        elif fact["official_confirmed"] is True:
            assert fact["zone"] == green
            assert fact["source_kind"] == "official"
            assert report.is_official_publisher(fact["source"])
        elif fresh >= NEEDED:
            assert fact["zone"] == yellow
            assert fact["zone"] != green
        else:
            assert fact["zone"] == floor
        for item in fact["confirmations"]:
            assert item["url"].startswith("https://")
            assert item["type"] in ("official", "independent")
            assert item["verdict"] in ("confirms", "partial", "contradicts")
            assert "date" in item


def test_partial_and_contradicting_sources_do_not_count_as_confirmations():
    bundle = _bundle()
    cards = _cards(bundle)
    plan = cards[1]
    window = CONFIG["volatility"]["classes"]["medium"]["fresh_days"]
    stats = confirmation_stats(plan, AS_OF, window, CONFIG)
    assert stats["fresh_count"] == 2
    assert stats["fresh_count"] < NEEDED
    assert any(item["verdict"] == "partial" and item["date"] >= "2026-09-18" for item in plan["confirmations"])
    fee = cards[5]
    expatden = next(item for item in fee["confirmations"] if "expatden.com" in item["url"])
    assert expatden["verdict"] == "contradicts"
    assert "2 GEL" in expatden["note"]
    fee_stats = confirmation_stats(fee, AS_OF, window, CONFIG)
    assert fee_stats["fresh_count"] == 2


def test_language_cards_use_the_softer_sentence():
    raw = (ROOT / "database" / "data" / "countries.json").read_text(encoding="utf-8")
    assert "по-русски не отвечают" not in raw
    cards = _cards(_bundle())
    assert cards[2]["text"] == LANGUAGE
    assert cards[7]["text"] == "Поставить приложение-переводчик. " + LANGUAGE
    for number in (2, 7):
        for host in ("madloba.info", "t-j.ru"):
            item = next(row for row in cards[number]["confirmations"] if host in row["url"])
            assert item["verdict"] == "partial"
            assert "по-русски — не везде" in item["note"]


def test_research_counts_of_three_stay_outside_the_medium_window():
    """The research 90-day count is not the medium-class window of 30 days.

    Cards 1, 2, 7 and 9 each have three confirms inside that research cutoff.
    Only dates on or after 2026-09-18 count. Partial and contradicting rows
    never count. Same Yandex host with a different person stays independent.
    A date_estimated flag does not drop a parseable date. Cards 3 and 6 stay
    on the July observation.
    """
    cards = _cards(_bundle())
    window = CONFIG["volatility"]["classes"]["medium"]["fresh_days"]
    assert window == 30
    expected = {1: 2, 2: 1, 7: 1, 9: 1}
    floor = lowest_zone(CONFIG)
    for number, fresh in expected.items():
        fact = cards[number]
        stats = confirmation_stats(fact, AS_OF, window, CONFIG)
        assert stats["fresh_count"] == fresh
        assert fact["zone"] == floor
        confirms = [item for item in fact["confirmations"] if item["verdict"] == "confirms"]
        assert len(confirms) >= 3
        outside = [
            item for item in confirms
            if item.get("date") and item["date"] < "2026-09-18"
        ]
        assert outside
        assert len({item.get("person") or item["outlet"] for item in confirms}) == len(confirms)
    assert cards[3]["zone"] == floor
    assert cards[3]["verified_by_us"] is True
    assert cards[3]["date_verified"] == "2026-07-16"
    assert cards[6]["zone"] == floor
    assert cards[6]["verified_by_us"] is False
    assert cards[6]["own_date"] == "2026-07-16"


def test_monthly_fee_has_no_hardcoded_ruble_figure():
    cards = _cards(_bundle())
    assert "₽" not in cards[5]["text"]
    assert "300" not in cards[5]["text"]
    config = json.loads((ROOT / "config" / "trust_config.json").read_text(encoding="utf-8"))
    assert "gel" not in json.dumps(config).lower()
    source = (ROOT / "database" / "fact_score.py").read_text(encoding="utf-8")
    assert "300" not in source
    assert "GEL" not in source


def test_deposit_before_plastic_is_its_own_fact():
    bundle = _bundle()
    hits = [(fact, ctx) for fact, ctx in _walk(bundle) if fact.get("text") == DEPOSIT]
    assert len(hits) == 2
    contexts = {tuple(sorted(ctx.items())) for _fact, ctx in hits}
    assert contexts == {
        tuple(sorted({"section_key": "1_checklist", "subsection": None, "instruction_id": None}.items())),
        tuple(sorted({"section_key": "3_local_wallets_cards", "subsection": None, "instruction_id": "tbc_georgia"}.items())),
    }
    top = ranked_zones(CONFIG)[-1]["name"]
    floor = lowest_zone(CONFIG)
    for fact, ctx in hits:
        assert fact["source_kind"] == "traveler"
        assert fact["reports"] == 1
        assert fact["official_confirmed"] is False
        assert fact["owner_approved"] is False
        assert len(fact["confirmations"]) == 1
        assert fact["confirmations"][0]["date"] == "2026-09-29"
        assert fact["confirmations"][0]["verdict"] == "confirms"
        shown = _live(fact, ctx)
        ceiling = _live(fact, ctx, top)
        held = _live(fact, ctx, floor)
        assert fact["zone"] == shown["zone"] == ceiling["zone"]
        assert held["zone"] == floor
        assert held["upgraded"] is False
        assert shown["confirmations"]["fresh_count"] < NEEDED


def test_owner_closed_the_fee_and_the_address_on_2026_10_18():
    cards = _cards(_bundle())
    fee = cards[5]
    branch = cards[8]
    assert fee["text"] == "Обслуживание 10 GEL в месяц. Отдельной платы за текущий счёт нет."
    assert fee["verified_by_us"] is True
    assert fee["date_verified"] == "2026-10-18"
    assert fee["decision_needed"] is None
    assert fee["agreement"] == "agree"
    assert "площадь Свободы, 7" in branch["text"]
    assert "18.10.2026" in branch["text"]
    assert "Rustaveli" not in branch["text"]
    assert branch["verified_by_us"] is True
    assert branch["date_verified"] == "2026-10-18"
    assert branch["decision_needed"] is None
    assert branch["agreement"] == "agree"
    bia = next(item for item in branch["confirmations"] if "bia.ge" in item["url"])
    assert "Rustaveli" in bia["note"]
    assert "площадь Свободы, 7" in bia["note"]
    form = cards[9]
    assert form["decision_needed"] is None
    assert "Платы за рассмотрение не было." in form["text"]
    built = report.build_report(as_of=AS_OF, check_http=False)
    rendered = report.render_text(built)
    section = rendered.split("\nНужно решение\n", 1)[1].split("\nСкоро съедут\n", 1)[0]
    for fact in (fee, branch, form):
        assert fact["text"] not in section
        row = next(item for item in built["facts"] if item["text"] == fact["text"])
        assert "decision_needed" not in row["flags"]
        assert row.get("at_risk_reason") is None or "противореч" not in row["at_risk_reason"]


def test_timing_conflict_stays_on_the_owner_decision_list():
    bundle = _bundle()
    cards = _cards(bundle)
    assert "Конфликт сроков" in cards[1]["decision_needed"]
    assert "Конфликт сроков" in cards[4]["decision_needed"]
    assert "следующий рабочий день" in cards[1]["text"]
    assert "следующий рабочий день" in cards[4]["text"]
    for number in (1, 4):
        assert cards[number]["agreement"] == "agree"
    built = report.build_report(as_of=AS_OF, check_http=False)
    rendered = report.render_text(built)
    section = rendered.split("\nНужно решение\n", 1)[1].split("\nСкоро съедут\n", 1)[0]
    for number in (1, 4):
        assert cards[number]["text"] in section
        match = next(fact for fact in built["facts"] if fact["text"] == cards[number]["text"])
        assert "decision_needed" in match["flags"]
        assert match["suggested_action"] == "owner_decision"
        assert cards[number]["decision_needed"] in match["reason"]


def test_instruction_keeps_the_translator_step_hidden_until_it_earns_a_zone():
    step = next(step for step in INSTRUCTIONS["tbc_georgia"]["steps"] if step["text"].startswith("Поставить приложение-переводчик"))
    assert step["zone"] != CONFIG["upgrade"]["yellow_zone"]
    assert step["zone"] != CONFIG["upgrade"]["green_zone"]
