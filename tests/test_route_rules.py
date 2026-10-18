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
from database.trust_score import freshness_points, score_fact, source_points  # noqa: E402

AS_OF = date(2026, 10, 18)


def test_route_score_uses_the_guide_formula():
    assert report.freshness_points is freshness_points
    assert report.source_points is source_points
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
    fact = measurement_fact("china_visa_free_days", measurements["china_visa_free_days"], rules, AS_OF)
    scored = score_fact(fact, TRUST_CONFIG, AS_OF)
    assert scored["age_days"] == (AS_OF - date(2026, 5, 20)).days
    assert scored["score_breakdown"] == {"source": 50, "freshness": 0, "agreement": 20}
    assert fact["zone"] == "yellow"
    assert fact["score"] == 70
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


def test_unknown_volatility_is_rejected_and_notes_stay_out_of_the_catalog():
    rules = json.loads((MODEL_DIR / "rules.json").read_text(encoding="utf-8"))
    measurements = json.loads((MODEL_DIR / "measurements.json").read_text(encoding="utf-8"))
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
