"""Route cards compute numbers from measurements. Zones are not stored."""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fact_check_report as report  # noqa: E402
from database.knowledge_base import TRUST_CONFIG, is_gap  # noqa: E402
from database.route_model import (  # noqa: E402
    MODEL_DIR,
    allowance_fact,
    build_routes,
    gap_texts,
    measurement_fact,
)
from database.routes import get_route, load_routes  # noqa: E402
from database.trust_zones import resolve_zone  # noqa: E402

AS_OF = date(2026, 10, 18)


def test_route_score_uses_the_guide_formula():
    assert report.resolve_zone is resolve_zone
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    fact = measurement_fact("china_visa_free_days", measurements["china_visa_free_days"], rules, AS_OF)
    assert fact["volatility_class"] == rules["engine_volatility"]["statute"]
    link = measurement_fact("pvg_sha_link_minutes", measurements["pvg_sha_link_minutes"], rules, AS_OF)
    fare = measurement_fact("pek_express_cny", measurements["pek_express_cny"], rules, AS_OF)
    interval = measurement_fact("pek_express_interval", measurements["pek_express_interval"], rules, AS_OF)
    classes = TRUST_CONFIG["volatility"]["classes"]
    measures = TRUST_CONFIG["volatility"]["transfer_measures"]
    assert link["volatility_class"] == measures["travel_time"]
    assert fare["volatility_class"] == interval["volatility_class"] == measures["price_schedule"]
    assert classes[measures["travel_time"]]["fresh_days"] == classes["slow"]["fresh_days"]
    assert classes[measures["travel_time"]]["green_max_days"] == classes["slow"]["green_max_days"]
    assert classes[measures["travel_time"]]["window_days"] == classes["slow"]["window_days"]
    assert classes[measures["price_schedule"]]["fresh_days"] == classes["medium"]["fresh_days"]
    assert classes[measures["price_schedule"]]["green_max_days"] == classes["medium"]["green_max_days"]
    assert classes[measures["price_schedule"]]["window_days"] == classes["medium"]["window_days"]
    probed = {
        "text": fact["text"],
        "status": "unconfirmed",
        "fact_type": "fact",
        "source_kind": fact["source_kind"],
        "agreement": fact["agreement"],
        "date_verified": fact["date_verified"],
        "volatility_class": fact["volatility_class"],
        "reports": fact.get("reports") or 0,
    }
    resolved = resolve_zone(probed, config=TRUST_CONFIG, as_of=AS_OF, forecast=False)
    assert resolved["age_days"] == (AS_OF - date(2026, 5, 20)).days
    assert resolved["score_breakdown"] == {"source": 50, "freshness": 0, "agreement": 20}
    assert fact["score_breakdown"] == resolved["score_breakdown"]
    assert fact["zone"] == resolved["zone"] == "yellow"
    assert fact["score"] == resolved["score"] == 70
    assert "zone" not in measurements["china_visa_free_days"]


def test_templates_do_not_type_the_numbers():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    routes = json.loads((MODEL_DIR / "routes.json").read_text(encoding="utf-8"))
    for measurement in measurements.values():
        assert not re.search(r"\d", measurement.get("template") or "")
        assert not re.search(r"\d", measurement.get("text") or "")
    for name, formula in rules["formulas"].items():
        assert not re.search(r"\d", formula), name
    assert "zone" not in json.dumps(routes)
    assert "765617" not in json.dumps(routes)
    assert "umnyturizm.example" not in json.dumps(measurements)


def test_changing_a_measurement_changes_the_sentence():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    edited = json.loads(json.dumps(measurements))
    edited["china_visa_free_days"]["value"] = 45
    fact = measurement_fact("china_visa_free_days", edited["china_visa_free_days"], rules, AS_OF)
    assert "45 дней" in fact["text"]
    assert "30 дней" not in fact["text"]


def test_airport_change_allowance_is_a_sum_or_a_gap():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    transfer = {
        "text": "переезд",
        "zone": "yellow",
        "score": 70,
        "value": 40,
        "date_verified": "2026-06-04",
        "fact_type": "fact",
        "type": "fact",
    }
    connection = {
        "text": "стыковка",
        "zone": "green",
        "score": 100,
        "value": 80,
        "date_verified": "2026-10-01",
        "fact_type": "fact",
        "type": "fact",
    }
    spec = {"id": "sample", "pair": "PVG и SHA", "inputs": ["transfer", "connection"]}
    advice = allowance_fact(spec, {"transfer": transfer, "connection": connection}, rules, AS_OF)
    assert advice["value"] == 120
    assert "120 минут" in advice["text"]
    assert advice["zone"] == "yellow"
    assert advice["type"] == "advice"
    missing = allowance_fact(spec, {"transfer": transfer}, rules, AS_OF)
    assert is_gap(missing)
    assert not re.search(r"\d", missing["text"])


def test_published_routes_match_trips_and_list_gaps():
    routes = load_routes()
    assert set(routes) == {"mow_hkg_via_pek", "mow_china", "mow_thailand"}
    assert get_route("mow_china")["destination_slug"] == "china"
    assert get_route("mow_thailand")["destination_slug"] == "thailand"
    china_urls = " ".join(link["url"] for link in get_route("mow_china")["ticket_links"])
    assert "BJS" in china_urls and "SHA" in china_urls and "HKG" not in china_urls
    thai_urls = " ".join(link["url"] for link in get_route("mow_thailand")["ticket_links"])
    assert "BKK" in thai_urls and "HKT" in thai_urls
    gaps = gap_texts(build_routes())
    assert any("PEK и PKX" in text for text in gaps)
    assert any("PVG и SHA" in text for text in gaps)
    assert any("BKK и DMK" in text for text in gaps)
    assert any("Багаж на раздельных билетах" in text for text in gaps)
    assert any("авиакомпании" in text.lower() for text in gaps)
    assert all("4–5" not in text and "1,5" not in text for text in gaps)


def test_every_measurement_has_a_volatility_class_and_no_typed_number():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    classes = set(rules["volatility_classes"])
    for measurement_id, measurement in measurements.items():
        assert measurement.get("volatility") in classes, measurement_id
        if measurement.get("gap"):
            assert is_gap(measurement_fact(measurement_id, measurement, rules, AS_OF))
            continue
        assert measurement.get("source")
        assert measurement.get("source_date")
        fact = measurement_fact(measurement_id, measurement, rules, AS_OF)
        assert fact["volatility_label"] == rules["volatility_classes"][measurement["volatility"]]
        assert not re.search(r"\d", measurement.get("template") or "")


def test_sourced_amounts_come_from_data_and_large_ones_are_grouped():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    cash = measurement_fact("china_rmb_cash_cny", measurements["china_rmb_cash_cny"], rules, AS_OF)
    assert "20 000 юаней" in cash["text"]
    assert cash["zone"] == "yellow"
    assert cash["score"] == 70
    edited = json.loads(json.dumps(measurements))
    edited["china_rmb_cash_cny"]["value"] = 30000
    changed = measurement_fact("china_rmb_cash_cny", edited["china_rmb_cash_cny"], rules, AS_OF)
    assert "30 000 юаней" in changed["text"]
    express = measurement_fact("pek_express_cny", measurements["pek_express_cny"], rules, AS_OF)
    assert "PEK → город: 25 юаней" in express["text"]
    assert express["zone"] == "green"
    overstay = measurement_fact("china_overstay_fine", measurements["china_overstay_fine"], rules, AS_OF)
    assert "500 юаней" in overstay["text"]
    assert "10 000 юаней" in overstay["text"]
    assert "от 5 до 15 дней" in overstay["text"]


def test_airline_connection_advice_is_not_added_into_the_allowance():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    advice = measurement_fact("ceair_pvg_sha_minutes", measurements["ceair_pvg_sha_minutes"], rules, AS_OF)
    assert advice["value"] == 210
    assert "210 минут" in advice["text"]
    assert advice["zone"] == "yellow"
    routes = build_routes()
    china = next(card for card in routes if card["id"] == "mow_china")
    allowance = next(fact for fact in china["lead_facts"] if fact.get("rule_id") == "pvg_sha_allowance")
    assert is_gap(allowance)
    assert not re.search(r"\d", allowance["text"])
    shuttle = measurement_fact("bkk_dmk_shuttle_minutes", measurements["bkk_dmk_shuttle_minutes"], rules, AS_OF)
    assert shuttle["date_verified"] == "2023-07-11"
    assert shuttle["zone"] == "yellow"
    assert not shuttle.get("date_estimated")
    interval = measurements["bkk_dmk_interval"]
    assert interval["volatility"] == "conflict"
    urls = {item["url"] for item in interval["sources_checked"]}
    assert "https://suvarnabhumi.airportthai.co.th/service/transportation/detail/1093" in urls
    assert "https://thailand.go.th/public/issue-focus-detail/001_01_090" in urls


def test_map_estimates_render_from_slots_and_stay_out_of_the_allowance_until_enabled():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    drive = measurement_fact("bkk_dmk_drive_2300", measurements["bkk_dmk_drive_2300"], rules, AS_OF)
    assert drive["volatility_class"] == TRUST_CONFIG["volatility"]["transfer_measures"]["travel_time"]
    assert drive["source_kind"] == TRUST_CONFIG["source_kinds"]["map_estimate"]
    assert drive["zone"] == "yellow"
    assert drive["score_breakdown"]["source"] == TRUST_CONFIG["source_points"]["map_estimate"]
    cards = build_routes()
    thailand = next(card for card in cards if card["id"] == "mow_thailand")
    outbound = next(fact for fact in thailand["lead_facts"] if fact.get("rule_id") == "bkk_dmk_driving")
    assert outbound["text"].startswith("На машине, BKK → DMK:")
    assert "ночью: от 30 до 55 минут" in outbound["text"]
    assert "в 18:00: от 50 до 130 минут" in outbound["text"]
    china = next(card for card in cards if card["id"] == "mow_china")
    pek = next(fact for fact in china["lead_facts"] if fact.get("rule_id") == "pek_pkx_driving")
    pvg = next(fact for fact in china["lead_facts"] if fact.get("rule_id") == "pvg_sha_driving")
    assert "85 минут" in pek["text"]
    assert "без диапазона по пробкам" in pek["text"]
    assert "от 85" not in pek["text"]
    assert "55 минут" in pvg["text"] and "65 минут" in pvg["text"]
    assert "без диапазона по пробкам" in pvg["text"]
    allowance = next(fact for fact in thailand["lead_facts"] if fact.get("rule_id") == "bkk_dmk_allowance")
    assert is_gap(allowance)
    assert "130" not in allowance["text"]
    gaps = gap_texts(cards)
    assert any("Google Maps" in text and "PEK" in text for text in gaps)
    assert any("Google Maps" in text and "PVG" in text for text in gaps)
    assert any("Тариф такси из BKK" in text for text in gaps)
    assert any("Ночной проезд" in text for text in gaps)
    surcharge = measurement_fact("bkk_taxi_airport_surcharge", measurements["bkk_taxi_airport_surcharge"], rules, AS_OF)
    assert "50 батов" in surcharge["text"]
    assert surcharge["volatility_class"] == TRUST_CONFIG["volatility"]["transfer_measures"]["price_schedule"]
    flag = TRUST_CONFIG.setdefault("route_rules", {})
    previous = flag.get("allow_map_estimate_in_allowance")
    flag["allow_map_estimate_in_allowance"] = True
    try:
        still_gap = build_routes()
        thai_gap = next(
            fact
            for card in still_gap if card["id"] == "mow_thailand"
            for fact in card["lead_facts"]
            if fact.get("rule_id") == "bkk_dmk_allowance"
        )
        assert is_gap(thai_gap)
        edited = json.loads(json.dumps(measurements))
        edited["bkk_dmk_mct"] = {
            "kind": "value",
            "value": 40,
            "unit": "minutes",
            "template": "Стыковка: {value} {unit_label}.",
            "source": "https://example.com/mct",
            "source_kind": "official",
            "source_date": "2026-10-18",
            "agreement": "agree",
            "volatility": "operator",
        }
        advised = build_routes(measurements=edited)
        advice = next(
            fact
            for card in advised if card["id"] == "mow_thailand"
            for fact in card["lead_facts"]
            if fact.get("rule_id") == "bkk_dmk_allowance"
        )
        assert advice["value"] == 170
        assert "170 минут" in advice["text"]
        assert advice["type"] == "advice"
    finally:
        flag["allow_map_estimate_in_allowance"] = previous


def test_owner_grab_quotes_are_green_and_checked_against_the_evening_map():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    price_class = TRUST_CONFIG["volatility"]["transfer_measures"]["price_schedule"]
    time_class = TRUST_CONFIG["volatility"]["transfer_measures"]["travel_time"]
    justgrab = measurement_fact("bkk_dmk_grab_justgrab", measurements["bkk_dmk_grab_justgrab"], rules, AS_OF)
    assert justgrab["volatility_class"] == price_class
    assert justgrab["verified_by_us"] is True
    assert justgrab["source_kind"] == TRUST_CONFIG["source_kinds"]["internal"]
    assert justgrab["zone"] == TRUST_CONFIG["verified_by_us_zone"]
    assert "JustGrab" in justgrab["text"] and "652 бата" in justgrab["text"]
    assert "не поездка" in justgrab["text"]
    assert justgrab["source"] == "owner Grab screenshots 2026-10-18"
    taxi = measurement_fact("bkk_dmk_grab_taxi", measurements["bkk_dmk_grab_taxi"], rules, AS_OF)
    assert "от 567 до 851 бат" in taxi["text"]
    van = measurement_fact("dmk_bkk_grab_van", measurements["dmk_bkk_grab_van"], rules, AS_OF)
    assert "1 038 батов" in van["text"] and "10 мест" in van["text"]
    standard = measurement_fact("dmk_bkk_grab_standard", measurements["dmk_bkk_grab_standard"], rules, AS_OF)
    assert "623 бата" in standard["text"] and "8 минут" in standard["text"]
    route = measurement_fact("bkk_dmk_grab_route_tolls", measurements["bkk_dmk_grab_route_tolls"], rules, AS_OF)
    assert route["volatility_class"] == time_class
    assert route["zone"] == TRUST_CONFIG["verified_by_us_zone"]
    assert "52 минуты" in route["text"] and "50,2 км" in route["text"]
    cards = build_routes()
    thailand = next(card for card in cards if card["id"] == "mow_thailand")
    connection = thailand["section_facts"]["route:mow_thailand:connection"]
    outbound = next(fact for fact in connection if fact.get("rule_id") == "bkk_dmk_grab_time_check")
    inbound = next(fact for fact in connection if fact.get("rule_id") == "dmk_bkk_grab_time_check")
    assert "воскресный вечер" in outbound["text"]
    assert "не целиком внутри диапазона карты (в 18:00)" in outbound["text"]
    assert "внутри диапазона карты (ночью)" in outbound["text"]
    assert "не целиком" not in inbound["text"]
    assert "внутри диапазона карты (в 18:00)" in inbound["text"]
    assert "внутри диапазона карты (ночью)" in inbound["text"]
    assert outbound["zone"] == "yellow"
    transfer = thailand["section_facts"]["route:mow_thailand:transfer"]
    names = " ".join(fact["text"] for fact in transfer)
    assert "названия тарифов" in names
    assert "Floor 1" in names and "Exit 14" in names
    assert any(fact["text"].startswith("Тариф такси из BKK") for fact in transfer)


def test_unknown_volatility_is_rejected_and_notes_stay_out_of_the_catalog():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    broken = json.loads(json.dumps(measurements["pek_express_cny"]))
    broken["transfer_measure"] = "guess"
    try:
        measurement_fact("pek_express_cny", broken, rules, AS_OF)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown transfer measure was accepted")
    broken = json.loads(json.dumps(measurements["pek_express_cny"]))
    broken["volatility"] = "guess"
    try:
        measurement_fact("pek_express_cny", broken, rules, AS_OF)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown volatility was accepted")
    from database.miniapp_catalog import get_catalog

    catalog = json.dumps(get_catalog(), ensure_ascii=False)
    assert "sources_checked" not in catalog
    assert "20 000 юаней" in catalog
    assert "до 12 часов" in catalog
    assert "umnyturizm.example" not in catalog
