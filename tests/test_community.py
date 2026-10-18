"""Community v1: config, zones, badge, moderation, antifraud, photos."""

import copy
import io
import json
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest
from PIL import Image

from database.community import (
    ConfigError,
    antifraud_flags,
    apply_community_state,
    apply_owner_action,
    community_badge,
    confirmation_items,
    count_refutes,
    estimate_tg_age_days,
    helped_count,
    plan_intake,
    recheck_award,
    require_community,
    sort_by_badge,
)
from database.community_photo import consume_upload, redact_bytes
from database.community_service import decide, list_queue, submit_review
from database.community_store import FileCommunityStore, set_community_store
from database.config_error import ConfigError as ConfigErrorFromModule
from database.knowledge_base import load_trust_config
from database.miniapp_catalog import find_fact, get_catalog, source_facts_by_id
from database.trust_zones import confirmation_stats, resolve_zone

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 18)
NEW_MODULES = (
    "database/community.py",
    "database/community_photo.py",
    "database/community_store.py",
    "database/community_service.py",
)


def _config():
    return load_trust_config()


def _green_class(config):
    for name, spec in config["volatility"]["classes"].items():
        if spec.get("green_max_days") is not None:
            return name
    raise AssertionError("нет класса с зелёным окном")


def _fact(**overrides):
    base = {
        "text": "Тестовый факт сообщества",
        "zone": "red",
        "status": "unconfirmed",
        "source": None,
        "source_kind": "traveler",
        "reports": 1,
        "agreement": "agree",
        "fact_type": "fact",
        "date_verified": "2026-10-10",
        "verified_by_us": False,
        "refuted": False,
        "owner_approved": True,
    }
    base.update(overrides)
    return base


def _review(user, result="success", **extra):
    row = {
        "id": extra.pop("id", "r-" + str(user)),
        "user_id": user,
        "status": "approved",
        "result": result,
        "trip_date_end": "2026-10-10",
        "trip_date_start": "2026-10-01",
        "created_at": "2026-10-10T00:00:00+00:00",
        "moderated_at": "2026-10-11T00:00:00+00:00",
        "photo_path": None,
        "photo_redaction_status": None,
        "country": "china",
        "fact_id": "fact-1",
    }
    row.update(extra)
    return row


def _link(review, verdict="confirms", counted=True, **extra):
    row = {
        "id": "l-" + review["id"],
        "review_id": review["id"],
        "fact_id": "fact-1",
        "user_id": review["user_id"],
        "verdict": verdict,
        "counted": counted,
        "weight": 1,
    }
    row.update(extra)
    return row


def _visible_fact():
    for country in get_catalog()["countries"]:
        for section in country["sections"]:
            for fact in section["facts"]:
                if fact.get("topic") and not fact.get("hidden") and source_facts_by_id().get(fact["id"]):
                    return fact
    raise AssertionError("нет видимого факта")


def _payload(fact, **extra):
    community = _config()["community"]
    topic = fact["topic"]
    body = {
        "consent": True,
        "country": fact["country_slug"],
        "city": "Пекин",
        "trip_date_start": "2026-10-01",
        "trip_date_end": "2026-10-10",
        "topic": topic,
        "fact_id": fact["id"],
        "action_text": "Оплатил в кафе",
        "result": "success",
        "citizenship": community["citizenships"][0]["code"],
        "changed": False,
    }
    if topic in community["payment_method_topics"]:
        body["payment_method"] = community["payment_methods"][0]["code"]
    body.update(extra)
    return body


def test_missing_community_key_is_a_config_error():
    config = _config()
    require_community(config)
    broken = copy.deepcopy(config)
    del broken["community"]["min_refutes_to_downgrade"]
    with pytest.raises(ConfigError):
        require_community(broken)
    assert ConfigError is ConfigErrorFromModule


def test_new_modules_have_no_threshold_literals():
    number = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
    for rel in NEW_MODULES:
        for index, line in enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), start=1):
            code = re.sub(r'(""".*?"""|\'\'\'.*?\'\'\'|".*?"|\'.*?\')', '""', line)
            for match in number.finditer(code):
                assert match.group(0) in {"0", "1"}, f"{rel}:{index} {line.strip()}"


def test_reviews_never_turn_a_fact_green():
    config = _config()
    community = config["community"]
    reviews = []
    links = []
    for index in range(12):
        review = _review(1000 + index, id=f"g-{index}")
        review["photo_path"] = "kept.jpg"
        review["photo_redaction_status"] = community["photo"]["clean_status"]
        reviews.append(review)
        links.append(_link(review, weight=community["weights"]["photo_multiplier"]))
    items = confirmation_items(links, reviews, config, fact_id="fact-1")
    fact = _fact(reports=30, confirmations=items, owner_approved=True)
    resolved = resolve_zone(fact, config=config, as_of=AS_OF)
    assert resolved["zone"] != config["upgrade"]["green_zone"]
    assert resolved["owner_prompt"] is None


def test_official_and_verified_by_us_can_still_be_green():
    config = _config()
    official = _fact(
        zone="yellow",
        source_kind="official",
        source="https://www.rshb.ru/tariffs",
        reports=0,
        official_confirmed=True,
        agreement="agree",
        volatility_class=_green_class(config),
        owner_approved=False,
    )
    official.pop("owner_approved")
    shown = resolve_zone(official, config=config, as_of=AS_OF)
    assert shown["zone"] == config["upgrade"]["green_zone"]
    own = _fact(
        zone="green",
        source_kind="media",
        source="https://example.test/story",
        reports=0,
        verified_by_us=True,
        agreement="agree",
        volatility_class=_green_class(config),
        date_verified=AS_OF.isoformat(),
    )
    own.pop("owner_approved", None)
    verified = resolve_zone(own, config=config, as_of=AS_OF)
    assert verified["zone"] == config["verified_by_us_zone"]


def test_yellow_uses_weight_and_same_author_does_not_sum():
    config = _config()
    needed = config["upgrade"]["yellow_min_independent_confirmations"]
    partial = config["community"]["partial_vote_weight"]
    full = config["community"]["full_vote_weight"]
    reviews = [_review(index, result="partial", id=f"p-{index}") for index in range(int(needed / partial))]
    links = [_link(review, verdict="partial", weight=partial) for review in reviews]
    items = confirmation_items(links, reviews, config, fact_id="fact-1")
    stats = confirmation_stats(_fact(confirmations=items, reports=0, source_kind="media"), AS_OF, 30, config)
    assert stats["fresh_weight"] >= needed
    short = confirmation_items(links[:-1], reviews[:-1], config, fact_id="fact-1")
    short_stats = confirmation_stats(_fact(confirmations=short, reports=0, source_kind="media"), AS_OF, 30, config)
    assert short_stats["fresh_weight"] < needed
    same = [
        _review(7, result="success", id="a", trip_date_end="2026-10-01"),
        _review(7, result="success", id="b", trip_date_end="2026-10-08"),
    ]
    same_links = [_link(row) for row in same]
    folded = confirmation_items(same_links, same, config, fact_id="fact-1")
    folded_stats = confirmation_stats(_fact(confirmations=folded, reports=0), AS_OF, 30, config)
    assert folded_stats["fresh_weight"] == full
    assert folded_stats["fresh_count"] == 1


def test_downgrade_waits_for_the_threshold_and_official_conflict_does_not_drop():
    config = _config()
    community = config["community"]
    window = config["volatility"]["classes"]["bank_procedure"]["fresh_days"]
    minimum = community["min_refutes_to_downgrade"]
    reviews = []
    links = []
    for index in range(minimum - 1):
        review = _review(200 + index, result="fail", id=f"d-{index}")
        reviews.append(review)
        links.append(_link(review, verdict="refutes"))
    held = apply_community_state(
        _fact(), links, reviews, config, fact_id="fact-1", as_of=AS_OF, window_days=window
    )
    assert held["downgraded"] is False
    assert held["conflict"] is False
    last = _review(299, result="fail", id="d-last")
    reviews.append(last)
    links.append(_link(last, verdict="refutes"))
    dropped = apply_community_state(
        _fact(), links, reviews, config, fact_id="fact-1", as_of=AS_OF, window_days=window
    )
    flag = community["downgrade"]["flag_by_method"][community["downgrade"]["method"]]
    assert dropped["downgraded"] is True
    assert dropped["fact"][flag] is True
    zone = resolve_zone(dropped["fact"], config=config, as_of=AS_OF)
    assert zone["zone"] == config["refuted_zone"]
    stale = _review(201, result="fail", id="stale", trip_date_end=(AS_OF - timedelta(days=window + 1)).isoformat())
    assert count_refutes(
        [_link(stale, verdict="refutes")],
        [stale],
        config,
        fact_id="fact-1",
        as_of=AS_OF,
        window_days=window,
    ) == 0
    official = _fact(
        source_kind="official",
        source="https://www.rshb.ru/tariffs",
        official_confirmed=True,
        date_verified=AS_OF.isoformat(),
        volatility_class=_green_class(config),
        zone="green",
    )
    blocked = apply_community_state(
        official, links, reviews, config, fact_id="fact-1", as_of=AS_OF, window_days=window
    )
    assert blocked["downgraded"] is False
    assert blocked["conflict"] is True
    assert blocked["fact"].get(flag) is not True
    assert blocked["disputes"][0]["trigger"] == community["moderation"]["trigger_codes"]["official_conflict"]
    kept = resolve_zone(blocked["fact"], config=config, as_of=AS_OF)
    assert kept["zone"] == config["upgrade"]["green_zone"]
    assert config["early_warning"]["reasons"]["conflict"] in (kept["at_risk_reason"] or "")


def test_badge_levels_sort_inside_the_zone_and_do_not_move_it():
    config = _config()
    community = config["community"]
    window = config["volatility"]["classes"]["medium"]["fresh_days"]
    one = _review(1, id="b1")
    badge = community_badge([_link(one)], [one], config, fact_id="fact-1", as_of=AS_OF, window_days=window)
    assert badge["label"] == community["badge"]["label"]
    assert badge["caption"] == community["badge"]["caption"]
    assert badge["code"] == community["badge"]["levels"][0]["code"]
    many_reviews = [_review(index, id=f"m-{index}") for index in range(3)]
    many = community_badge(
        [_link(row) for row in many_reviews],
        many_reviews,
        config,
        fact_id="fact-1",
        as_of=AS_OF,
        window_days=window,
    )
    assert many["strength"] > badge["strength"]
    refute = _review(9, result="fail", id="ref")
    confirm = _review(8, id="ok")
    blocked = community_badge(
        [_link(confirm), _link(refute, verdict="refutes"), _link(_review(10, result="fail", id="ref2"), verdict="refutes")],
        [confirm, refute, _review(10, result="fail", id="ref2")],
        config,
        fact_id="fact-1",
        as_of=AS_OF,
        window_days=window,
    )
    assert blocked is None
    green = _fact(
        zone="green",
        source_kind="official",
        source="https://www.rshb.ru/tariffs",
        official_confirmed=True,
        reports=0,
        volatility_class=_green_class(config),
        date_verified=AS_OF.isoformat(),
    )
    before = resolve_zone(green, config=config, as_of=AS_OF)["zone"]
    card = dict(green)
    card["community_badge"] = badge
    assert resolve_zone(card, config=config, as_of=AS_OF)["zone"] == before
    ordered = sort_by_badge([
        {"id": "plain", "community_badge": None},
        {"id": "strong", "community_badge": many},
        {"id": "base", "community_badge": badge},
    ])
    assert [item["id"] for item in ordered] == ["strong", "base", "plain"]


def test_moderation_modes_and_idea_without_a_fact():
    config = _config()
    community = config["community"]
    idea = plan_intake(has_fact=False, flags=[], spike=False, official_conflict=False, config=config)
    assert idea["status"] == community["statuses"]["idea"]
    assert idea["counted"] is False
    assert idea["queue"][0]["kind"] == community["queue"]["kinds"]["idea"]
    disputes = copy.deepcopy(config)
    disputes["community"]["moderation"]["mode"] = community["moderation"]["disputes_only_mode"]
    clean = plan_intake(has_fact=True, flags=[], spike=False, official_conflict=False, config=disputes)
    assert clean["counted"] is True
    assert clean["queue"] == []
    fraud = plan_intake(
        has_fact=True,
        flags=[community["antifraud"]["flag_names"]["young"]],
        spike=False,
        official_conflict=False,
        config=disputes,
    )
    assert fraud["counted"] is False
    assert fraud["queue"][0]["trigger"] == community["moderation"]["trigger_codes"]["fraud_suspected"]
    spike = plan_intake(has_fact=True, flags=[], spike=True, official_conflict=False, config=disputes)
    conflict = plan_intake(has_fact=True, flags=[], spike=False, official_conflict=True, config=disputes)
    triggers = {item["trigger"] for item in spike["queue"] + conflict["queue"]}
    assert community["moderation"]["trigger_codes"]["refute_spike"] in triggers
    assert community["moderation"]["trigger_codes"]["official_conflict"] in triggers
    waiting = plan_intake(has_fact=True, flags=[], spike=False, official_conflict=False, config=config)
    assert waiting["status"] == community["statuses"]["pending"]
    assert waiting["counted"] is False


def test_antifraud_replacement_young_account_and_limits(tmp_path):
    config = _config()
    rules = config["community"]["antifraud"]
    names = rules["flag_names"]
    unknown = antifraud_flags(
        _review(None), [], config, as_of=AS_OF, age_days=None, window_days=None
    )
    assert names["age_unknown"] in unknown
    latest = max(rules["tg_id_anchors"], key=lambda row: row["telegram_id"])
    young_day = date.fromisoformat(latest["on"]) + timedelta(days=rules["min_tg_account_age_days"] - 1)
    age = estimate_tg_age_days(latest["telegram_id"], config, young_day)
    assert age is not None and age < rules["min_tg_account_age_days"]
    young = antifraud_flags(
        _review(latest["telegram_id"]), [], config, as_of=young_day, age_days=age, window_days=None
    )
    assert names["young"] in young
    history = []
    for index in range(rules["max_reviews_per_day"]):
        history.append(_review(3, id=f"day-{index}", created_at=AS_OF.isoformat(), fact_id="other"))
    daily = antifraud_flags(
        _review(3, id="new"), history, config, as_of=AS_OF, age_days=rules["min_tg_account_age_days"], window_days=None
    )
    assert names["daily"] in daily
    window = config["volatility"]["classes"]["medium"]["fresh_days"]
    same_fact = []
    for index in range(rules["max_reviews_per_fact_window"]):
        same_fact.append(_review(4, id=f"fact-{index}", created_at=AS_OF.isoformat(), fact_id="fact-1"))
    limited = antifraud_flags(
        _review(4, id="more"), same_fact, config, as_of=AS_OF, age_days=rules["min_tg_account_age_days"], window_days=window
    )
    assert names["fact_window"] in limited
    low = rules["outlier_check"]["min_samples"]
    samples = [low for _ in range(rules["outlier_check"]["min_samples"])]
    outlier = antifraud_flags(
        _review(5, amount=samples[0] * rules["outlier_check"]["amount_ratio"] + samples[0]),
        [],
        config,
        as_of=AS_OF,
        age_days=rules["min_tg_account_age_days"],
        window_days=window,
        amount_samples=samples,
    )
    assert names["amount"] in outlier
    fact = _visible_fact()
    store = FileCommunityStore(tmp_path / "community.json", tmp_path / "photos")
    set_community_store(store)
    try:
        open_mode = copy.deepcopy(config)
        open_mode["community"]["moderation"]["mode"] = config["community"]["moderation"]["disputes_only_mode"]
        user = 100000000
        first = submit_review(user_id=user, init_data="dev:100000000", payload=_payload(fact), config=open_mode, as_of=AS_OF, store=store)
        assert first["counted"] is True
        overlap = _payload(
            fact,
            country=next(slug for slug in ("china", "georgia") if slug != fact["country_slug"]),
            city="Другой",
        )
        second = submit_review(user_id=user, init_data="dev:100000000", payload=overlap, config=open_mode, as_of=AS_OF, store=store)
        assert second["counted"] is False
        counted = [link for link in store.snapshot()["links"] if link.get("counted") and link.get("fact_id") == fact["id"]]
        assert len(counted) == 1
        assert counted[0]["review_id"] != second["id"]
    finally:
        set_community_store(None)


def test_recheck_award_and_helped_counter():
    config = _config()
    spec = config["community"]["achievements"]["recheck_month"]
    previous = _review(5, id="old", trip_date_end="2026-09-01")
    gap = spec["recheck_min_days"]
    later_day = date.fromisoformat(previous["trip_date_end"]) + timedelta(days=gap)
    current = _review(5, id="new", trip_date_end=later_day.isoformat())
    links = [_link(previous), _link(current)]
    award = recheck_award(current, [previous, current], links, config, fact_id="fact-1")
    assert award["code"] == spec["code"]
    assert award["scope"] == "fact-1"
    again = recheck_award(current, [previous, current], links, config, fact_id="fact-1")
    assert again["review_id"] == award["review_id"]
    too_soon = _review(5, id="soon", trip_date_end=(date.fromisoformat(previous["trip_date_end"]) + timedelta(days=gap - 1)).isoformat())
    assert recheck_award(too_soon, [previous, too_soon], [_link(previous), _link(too_soon)], config, fact_id="fact-1") is None
    early = {"fact_id": "fact-1", "user_id": 8, "first_seen_at": "2026-10-10T00:00:00+00:00"}
    late = {"fact_id": "fact-1", "user_id": 8, "first_seen_at": "2026-10-12T00:00:00+00:00"}
    other = {"fact_id": "fact-2", "user_id": 8, "first_seen_at": "2026-10-12T00:00:00+00:00"}
    author = {"fact_id": "fact-1", "user_id": 5, "first_seen_at": "2026-10-12T00:00:00+00:00"}
    second_link = _link(current, fact_id="fact-2")
    helped = helped_count(
        5,
        [current],
        [_link(current), second_link],
        [early, late, other, author],
        config,
    )
    assert helped == 1


def test_photo_drops_the_original_exif_and_uncertain_frames(tmp_path):
    config = _config()
    image = Image.new("RGB", (64, 64), "white")
    exif = Image.Exif()
    exif[0x010E] = "passport"
    raw_path = tmp_path / "upload.jpg"
    image.save(raw_path, format="JPEG", exif=exif)
    result = consume_upload(raw_path, config, tmp_path / "kept", "shot")
    assert not raw_path.exists()
    assert result["publish"] is True
    saved = Image.open(io.BytesIO(result["image"]))
    assert 0x010E not in saved.getexif()
    strict = copy.deepcopy(config)
    photo = strict["community"]["photo"]
    photo["confidence_min"] = photo["detector_ran_confidence"] + photo["confidence_min"]
    original = tmp_path / "again.jpg"
    image.save(original, format="JPEG", exif=exif)
    rejected = consume_upload(original, strict, tmp_path / "kept", "nope")
    assert not original.exists()
    assert rejected["publish"] is False
    assert rejected["status"] == photo["review_status"]
    assert rejected["image"] is None
    assert not (tmp_path / "kept" / "nope.jpg").exists()


def test_owner_queue_and_count_action(tmp_path, monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(settings, "MINIAPP_DEV_AUTH", True)
    fact = _visible_fact()
    store = FileCommunityStore(tmp_path / "community.json", tmp_path / "photos")
    set_community_store(store)
    config = _config()
    try:
        saved = submit_review(
            user_id=100000000,
            init_data="dev:100000000",
            payload=_payload(fact),
            config=config,
            as_of=AS_OF,
            store=store,
        )
        assert saved["status"] == config["community"]["statuses"]["pending"]
        with pytest.raises(PermissionError):
            list_queue(owner_id=100000000, config=config, store=store)
        queue = list_queue(owner_id=303653591, config=config, store=store)
        assert queue["items"]
        item = queue["items"][0]
        assert item["review"]["action_text"]
        decided = decide(
            owner_id=303653591,
            queue_id=item["id"],
            action=config["community"]["moderation"]["actions"]["count"],
            config=config,
            as_of=AS_OF,
            store=store,
        )
        assert decided["status"] == config["community"]["statuses"]["approved"]
        counted = [link for link in store.snapshot()["links"] if link.get("counted")]
        assert counted
        closed = apply_owner_action(
            store.snapshot()["reviews"][0],
            store.snapshot()["links"],
            config["community"]["moderation"]["actions"]["ignore"],
            config,
            now="2026-10-18T00:00:00+00:00",
        )
        assert closed["links"][0]["counted"] is False
    finally:
        set_community_store(None)


def test_screens_render_review_queue_and_badge_order():
    script = r"""
import { groupFacts } from "./miniapp/js/ui.js";
import { render } from "./miniapp/js/screens.js";
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const catalog = JSON.parse(Buffer.concat(chunks).toString("utf8"));
globalThis.location = { hash: "#/review", search: "", hostname: "127.0.0.1" };
globalThis.document = { documentElement: { dataset: {}, style: {} }, querySelector() { return null; } };
const facts = [
  { id: "plain-new", zone: "green", date: "02.10.2026" },
  { id: "plain-old", zone: "green", date: "01.01.2026" },
  { id: "strong", zone: "green", date: "01.01.2026", community_badge: { strength: 4, label: "Подтверждено сообществом", caption: "по отзывам путешественников" } },
  { id: "weak", zone: "green", date: "02.10.2026", community_badge: { strength: 1, label: "Подтверждено сообществом", caption: "по отзывам путешественников" } },
];
const order = groupFacts(facts, { zone_groups: [{ name: "green", title: "Подтверждено" }], missing_zone: "red" })[0].facts.map((fact) => fact.id);
const state = {
  catalog,
  profile: { citizenship: "ru", favorite_countries: [], bank_id: "", departure_city_id: "" },
  community: { is_owner: true, helped_text: "Помог 2", achievements: [{ title: "Проверено через месяц" }] },
  review: { country: "china", topic: "payment", consent: true, suggestions: [{ id: "f1", text: "Факт" }] },
  queue: [{ id: "q1", kind: "review", trigger: "fraud_suspected", verdict: "confirms", flags: ["tg_account_young"], fact_text: "Факт", review: { action_text: "Оплатил", country: "china", city: "Пекин", result: "success" }, actions: catalog.community.actions, verdicts: ["confirms"] }],
  message: "",
  unverified: {},
  progress: {},
  cursor: {},
  trip: null,
};
const review = render(state);
globalThis.location.hash = "#/moderation";
const queue = render(state);
const country = catalog.countries.find((item) => item.slug === "china");
const section = country.sections.find((item) => item.key === "2_pay_on_site");
const shown = section.facts.find((fact) => !fact.hidden) || section.facts[0];
shown.hidden = false;
shown.community_badge = { label: "Подтверждено сообществом", caption: "по отзывам путешественников", strength: 1 };
globalThis.location.hash = "#/guide/china/2_pay_on_site";
const card = render(state);
process.stdout.write(JSON.stringify({ order, review, queue, card }));
"""
    catalog = get_catalog()
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps(catalog),
        text=True,
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["order"] == ["strong", "weak", "plain-new", "plain-old"]
    assert "review-form" in payload["review"]
    assert "Оплатил в кафе" not in payload["review"]
    assert catalog["community"]["actions"]["submit"] in payload["review"]
    assert "moderation-queue" in payload["queue"]
    assert "Учесть" in payload["queue"]
    assert "community-badge" in payload["card"]
    assert "по отзывам путешественников" in payload["card"]
