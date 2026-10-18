"""Bank-procedure facts use a 60-day class. Other medium facts stay medium."""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from database.knowledge_base import INSTRUCTION_SECTION, load_trust_config  # noqa: E402
from database.trust_zones import resolve_zone  # noqa: E402

AS_OF = date(2026, 10, 18)
CONFIG = load_trust_config()


def _bundle():
    return json.loads((ROOT / "database" / "data" / "countries.json").read_text(encoding="utf-8"))


def _walk(bundle):
    for slug, country in bundle["countries"].items():
        for key, section in country["sections"].items():
            for fact in section.get("facts") or []:
                yield slug, fact, {"section_key": key, "subsection": None, "instruction_id": None}
            for name, facts in (section.get("subsections") or {}).items():
                for fact in facts:
                    yield slug, fact, {"section_key": key, "subsection": name, "instruction_id": None}
    for instruction_id, instruction in bundle["instructions"].items():
        section_key = INSTRUCTION_SECTION.get(instruction_id)
        for fact in instruction.get("steps") or []:
            yield instruction_id, fact, {
                "section_key": section_key,
                "subsection": None,
                "instruction_id": instruction_id,
            }


def test_bank_procedure_windows_are_double_the_medium_class():
    classes = CONFIG["volatility"]["classes"]
    medium = classes["medium"]
    bank = classes["bank_procedure"]
    basis = CONFIG["volatility"]["class_basis"]["bank_procedure"]
    assert CONFIG["volatility"]["fact_field"] == "volatility_class"
    assert basis["proportion_of"] == "medium"
    assert basis["decision_date"] == "2026-10-18"
    for key in ("fresh_days", "green_max_days", "window_days"):
        assert bank[key] == 60
        assert bank[key] == medium[key] * basis[f"{key}_ratio"]


def test_only_facts_with_the_field_leave_medium():
    bundle = _bundle()
    stayed = []
    moved = []
    for _slug, fact, ctx in _walk(bundle):
        shown = resolve_zone(fact, config=CONFIG, as_of=AS_OF, **ctx)
        text = fact.get("text") or ""
        if fact.get("volatility_class") == "bank_procedure":
            assert shown["volatility_class"] == "bank_procedure", text
            moved.append(text)
            continue
        assert "volatility_class" not in fact, text
        stayed.append((text, shown["volatility_class"], fact.get("zone"), shown["zone"]))
    assert len(moved) == 36
    neighbors = {
        "SIM Magti: SIM/eSIM 10 GEL": "medium",
        "Российские карты в Грузии не работают совсем": "medium",
        "Карта TBC работает везде, где платили (Грузия).": "fast",
        "Тариф TBC Card: лимит трат": "medium",
        "Купить SIM Magti": "medium",
        "Добавить карту в Apple Pay": "medium",
        "Взять наличные USD/EUR на 2–3 дня": "medium",
    }
    found = set()
    for text, class_name, stored, live in stayed:
        for needle, expected in neighbors.items():
            if text.startswith(needle):
                assert class_name == expected, text
                assert live == stored, text
                found.add(needle)
    assert found == set(neighbors)
