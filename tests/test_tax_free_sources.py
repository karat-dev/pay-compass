"""Tax-free facts follow the 2026-10-18 sources. Zones come from the trust formula."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from database.fact_score import (
    georgia_refund_rate,
    georgia_refund_text,
    georgia_shelf_refund_rate,
    percent_text,
    score_fact,
)
from database.knowledge_base import COUNTRIES_KNOWLEDGE_BASE, load_trust_config, normalize_fact
from database.trust_zones import resolve_zone

AS_OF = date(2026, 10, 18)
CHECK = "2026-10-18"
OWNER = "Возврат на карту российского банка не оформить — выбирайте наличные или карту иностранного банка"
CONFIG = load_trust_config()
ROOT = Path(__file__).resolve().parents[1]


def _tax(slug):
    return COUNTRIES_KNOWLEDGE_BASE[slug]["sections"]["8_tax_free"]["facts"]


def _raw_tax(slug):
    bundle = json.loads((ROOT / "database" / "data" / "countries.json").read_text(encoding="utf-8"))
    return bundle["countries"][slug]["sections"]["8_tax_free"]["facts"]


def test_owner_statement_replaces_probably_impossible_and_leaves_manual_checks():
    for slug in ("china", "thailand", "uae", "turkey", "georgia"):
        matches = [fact for fact in _raw_tax(slug) if fact["text"] == OWNER]
        assert len(matches) == 1, slug
        fact = matches[0]
        assert fact["needs_owner_check"] is False
        assert fact["verified_by_us"] is False
        assert fact["own_experience_unconfirmed"] is True
        assert fact["refresh_search"] is True
        assert fact["source_type"] == "заявление владельца"
        assert fact["source"] is None
        assert fact["date_verified"] == CHECK
        scored = score_fact(fact, CONFIG, AS_OF)
        live = resolve_zone(fact, config=CONFIG, as_of=AS_OF, section_key="8_tax_free")
        assert fact["zone"] == scored["zone"] == live["zone"]
        assert fact["score"] == scored["score"] == live["score"]
        assert fact["zone"] == "yellow"
    joined = "\n".join(fact["text"] for slug in ("china", "thailand", "uae", "turkey", "georgia") for fact in _raw_tax(slug))
    assert "вероятно" not in joined
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import fact_check_report as report

    built = report.build_report(as_of=AS_OF, check_http=False)
    manual = [fact["text"] for fact in built["facts"] if "needs_owner_check" in fact["flags"]]
    assert OWNER not in "\n".join(manual)
    refresh = [
        fact
        for fact in built["facts"]
        if fact["suggested_action"] == "refresh_search" and fact["text"] == OWNER
    ]
    assert len(refresh) == 5
    assert {fact["country"] for fact in refresh} == {"china", "thailand", "uae", "turkey", "georgia"}


def test_thailand_uses_the_current_revenue_department_pages():
    facts = _raw_tax("thailand")
    minimum = next(fact for fact in facts if fact["text"].startswith("VAT Refund"))
    assert "2 000 THB" in minimum["text"]
    assert "5 000" not in minimum["text"]
    assert minimum["source"] == "https://vrtweb2.rd.go.th/81.html"
    assert minimum["checked_at"] == CHECK
    cash = next(fact for fact in facts if "30 000 THB" in fact["text"] and "Alipay" not in fact["text"])
    assert "пересказ" not in json.dumps(cash, ensure_ascii=False)
    assert cash["source"] == "https://vrtmap.rd.go.th/gps/rd/lang/en/id_article_16.aspx"
    assert cash["source_type"] == "official"
    cards = next(fact for fact in facts if "Visa, Mastercard, Diners" in fact["text"])
    for name in ("Visa", "Mastercard", "Diners", "JCB", "Alipay", "WeChat"):
        assert name in cards["text"]
    assert "UnionPay" in cards["text"] and "Мир" in cards["text"]
    assert cards["source"] == "https://vrtweb2.rd.go.th/69.html"


def test_china_splits_the_paper_form_rule_from_the_spot_check_and_adds_bank_of_china():
    facts = _raw_tax("china")
    policy = next(fact for fact in facts if "бумажные бланки" in fact["text"])
    assert "при любой сумме" in policy["text"]
    assert "10 000" in policy["text"]
    assert "выборочно" in policy["text"]
    assert policy["source"] == "https://www.chinatax.gov.cn/eng/c101269/c5250095/content.html"
    kiosk = next(fact for fact in facts if "Bank of China" in fact["text"])
    for name in ("UnionPay", "Alipay", "WeChat"):
        assert name in kiosk["text"]
    assert kiosk["source_type"] == "operator"
    assert kiosk["checked_at"] == CHECK
    gap = next(fact for fact in facts if "Хунцяо" in fact["text"])
    assert gap["fact_type"] == "gap"
    assert gap["zone"] == "gap"
    assert "не исследовано" in gap["text"]
    assert gap["source"] is None


def test_georgia_refund_share_is_computed_from_the_revenue_service_rule():
    rule = CONFIG["tax_free_rules"]["georgia_refund"]
    vat = Decimal(rule["vat_of_price_ex_vat"])
    service = Decimal(rule["service_fee_of_price_ex_vat"])
    bank = Decimal(rule["bank_fee_of_remainder"])
    ex_vat = (vat - service) * (Decimal(1) - bank)
    shelf = ex_vat / (Decimal(1) + vat)
    assert georgia_refund_rate(CONFIG) == ex_vat
    assert georgia_shelf_refund_rate(CONFIG) == shelf
    places = int(rule["result_decimal_places"])
    shelf_text = percent_text(shelf, places)
    ex_text = percent_text(ex_vat, places)
    assert shelf_text == "11,5"
    assert ex_text == "13,6"
    source = (ROOT / "database" / "fact_score.py").read_text(encoding="utf-8")
    assert "11,5" not in source
    assert "13,6" not in source
    expected = georgia_refund_text(CONFIG)
    assert f"≈{shelf_text}% от цены на ценнике" in expected
    assert f"≈{ex_text}% от цены без НДС" in expected
    assert expected.index("ценнике") < expected.index("от цены без НДС")
    assert "13,5" not in expected
    facts = _raw_tax("georgia")
    refund = next(fact for fact in facts if fact["text"] == expected)
    assert refund["source"] == "https://www.rs.ge/Media/Default/Images/CustomsBrochures/TAX%20FREE.pdf"
    assert refund["source_type"] == "official"
    assert refund["date_verified"] == CHECK
    shops = next(fact for fact in facts if "200 GEL" in fact["text"])
    assert shops["source"] == "https://matsne.gov.ge/en/document/view/1043717"
    assert "mstore.ge" not in json.dumps(facts, ensure_ascii=False)
    assert "blogspot" not in json.dumps(facts, ensure_ascii=False)
    missing = next(fact for fact in facts if "Кутаиси" in fact["text"])
    assert missing["zone"] == "gap"
    assert missing["source"] is None
    assert "не исследовано" in missing["text"]


def test_tax_free_zones_match_the_formula_and_sourced_facts_have_a_check_date():
    for slug, country in COUNTRIES_KNOWLEDGE_BASE.items():
        for raw, shown in zip(_raw_tax(slug), country["sections"]["8_tax_free"]["facts"]):
            if raw["fact_type"] == "gap":
                assert shown["zone"] == "gap"
                assert "не исследовано" in shown["text"]
                continue
            assert raw["source_type"]
            assert raw.get("date_verified") or raw.get("checked_at")
            if raw.get("source_kind") != "internal":
                assert raw["source"]
            scored = score_fact(raw, CONFIG, AS_OF)
            live = resolve_zone(raw, config=CONFIG, as_of=AS_OF, section_key="8_tax_free")
            shown_on_date = normalize_fact(raw, section_key="8_tax_free", as_of=AS_OF)
            assert raw["zone"] == scored["zone"] == live["zone"] == shown_on_date["zone"]
            assert raw["score"] == scored["score"] == live["score"]
            assert raw["score_breakdown"] == scored["score_breakdown"] == live["score_breakdown"]
            assert shown["zone"] == live["zone"]
