"""Topic groups and the card summary are built from fact data, not a fixed topic list."""

import json
import subprocess

from database.knowledge_base import COUNTRIES_KNOWLEDGE_BASE, load_trust_config
from database.miniapp_catalog import derive_short_label, get_catalog, public_short_label

ROOT_SCRIPT = r"""
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const catalog = JSON.parse(Buffer.concat(chunks).toString("utf8"));
globalThis.location = { hash: "#/guide/china/8_tax_free", search: "", hostname: "127.0.0.1" };
globalThis.document = { documentElement: { dataset: {}, style: {} }, querySelector() { return null; } };

const {
  cardSummary,
  groupDomIdForFact,
  readExpanded,
  sectionTopicGroups,
  summaryPlain,
  topicGroups,
  writeExpanded,
} = await import("./miniapp/js/ui.js");
const { render } = await import("./miniapp/js/screens.js");

const facts = [
  { id: "a", text: "ВТБ: один", zone: "green", date: "01.01.2024", short_label: "ВТБ" },
  { id: "b", text: "ВТБ: два", zone: "yellow", date: "02.03.2026", short_label: "лимит" },
  { id: "c", text: "Наличные в кассе", zone: "green", date: "03.01.2026", short_label: "наличные", topic: "Касса" },
];
const limits = { prefixMax: catalog.summary.prefix_max_chars, minFacts: catalog.summary.min_facts, catalog };
const split = topicGroups(facts, { ...limits, fallbackId: "all", fallbackTitle: "Оплата" });
const together = topicGroups(facts, { ...limits, minFacts: catalog.summary.min_facts + catalog.summary.min_facts, fallbackId: "all", fallbackTitle: "Оплата" });
const summary = cardSummary(split.map((group) => ({ ...group, domId: `card:${group.id}` })), catalog.summary.preview_items);
const short = cardSummary(split, 1);
const whole = cardSummary(split, null);

const storage = {
  value: "",
  getItem() { return this.value; },
  setItem(_key, value) { this.value = value; },
};
writeExpanded(storage, { groups: { "card:all": true }, facts: {}, summaries: {} });
const restored = readExpanded(storage);
const broken = readExpanded({ getItem() { return "{"; } });

const china = catalog.countries.find((country) => country.slug === "china");
const taxFree = china.sections.find((section) => section.key === "8_tax_free");
const groups = sectionTopicGroups(taxFree, catalog, false);
const plain = summaryPlain(groups, catalog.summary.preview_items);
const expandedId = groups[0] && `china/8_tax_free:${groups[0].id}`;
const collapsed = render({
  catalog,
  introSeen: true,
  unverified: {},
  progress: {},
  openRoute: "",
  trip: null,
  profile: { favorite_countries: [], bank_id: "tbank", departure_city_id: "mow" },
  draft: {},
  cursor: {},
  sheet: null,
  openGroups: {},
  openFacts: {},
  openSummaries: {},
});
const expanded = render({
  catalog,
  introSeen: true,
  unverified: {},
  progress: {},
  openRoute: "",
  trip: null,
  profile: { favorite_countries: [], bank_id: "tbank", departure_city_id: "mow" },
  draft: {},
  cursor: {},
  sheet: null,
  openGroups: expandedId ? { [expandedId]: true } : {},
  openFacts: groups[0] && groups[0].facts[0] ? { [groups[0].facts[0].id]: true } : {},
  openSummaries: {},
});

process.stdout.write(JSON.stringify({
  split: split.map((group) => ({ id: group.id, title: group.title, ids: group.facts.map((fact) => fact.id) })),
  together: together.map((group) => ({ id: group.id, title: group.title, ids: group.facts.map((fact) => fact.id) })),
  summary,
  short,
  wholeMore: whole.more,
  restored,
  broken,
  plain,
  expandedId,
  firstLabel: groups[0] && groups[0].facts[0] && groups[0].facts[0].short_label,
  collapsed,
  expanded,
  located: groupDomIdForFact(taxFree, groups[0].facts[0].id, catalog, "china/8_tax_free"),
}));

location.hash = "#/trip";
const route = catalog.routes.find((item) => item.id === "mow_hkg_via_pek");
const transfer = route.sections.find((section) => section.id === "route:mow_hkg_via_pek:transfer");
const tripState = {
  catalog,
  introSeen: true,
  unverified: {},
  progress: {},
  openRoute: transfer.id,
  trip: {
    destination_slug: "hong_kong",
    departure_city_id: "mow",
    depart_date: "2026-11-12",
    return_date: "2026-11-20",
  },
  profile: { favorite_countries: [], bank_id: "tbank", departure_city_id: "mow", citizenship: "ru" },
  draft: {},
  cursor: {},
  sheet: null,
  openGroups: {},
  openFacts: {},
  openSummaries: {},
};
const routeCollapsed = render(tripState);
const leadGroups = topicGroups(route.lead_facts || [], {
  ...limits,
  fallbackId: "all",
  fallbackTitle: route.title,
});
const transferGroups = topicGroups(transfer.facts || [], {
  ...limits,
  fallbackId: "all",
  fallbackTitle: transfer.title,
});
const transferOpenId = transferGroups[0] && `${transfer.id}:${transferGroups[0].id}`;
const routeExpanded = render({
  ...tripState,
  openGroups: transferOpenId ? { [transferOpenId]: true } : {},
});
process.stdout.write("\n" + JSON.stringify({
  routeCollapsed,
  routeExpanded,
  transferOpenId,
  leadTitle: leadGroups[0] && leadGroups[0].title,
  transferTitle: transferGroups[0] && transferGroups[0].title,
}));
"""


def _run(catalog):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", ROOT_SCRIPT],
        input=json.dumps(catalog),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    country, route = result.stdout.split("\n", 1)
    return json.loads(country), json.loads(route)


def test_short_label_comes_from_the_fact_text_or_a_grounded_field():
    summary = load_trust_config()["display"]["summary"]
    assert public_short_label({"text": "ВТБ: оплата по QR в Китае"}) == "ВТБ"
    assert public_short_label({
        "text": "С 1 июля 2026 бумажные бланки. 10 000 юаней — только порог.",
        "short_label": "порог",
    }) == "порог"
    invented = public_short_label({"text": "Ставка возврата 11%.", "short_label": "секретная ставка 99"})
    assert invented != "секретная ставка 99"
    assert "99" not in invented
    clipped = derive_short_label(
        "Наличными юанями до лимита без двоеточия и без короткой шапки в начале строки совсем.",
        max_chars=summary["label_max_chars"],
        prefix_max=summary["prefix_max_chars"],
    )
    assert len(clipped) <= summary["label_max_chars"]
    assert "Наличными" in clipped

    catalog = get_catalog()
    assert catalog["summary"] == {
        "preview_items": summary["preview_items"],
        "label_max_chars": summary["label_max_chars"],
        "prefix_max_chars": summary["prefix_max_chars"],
        "min_facts": summary["min_facts"],
    }
    pools = []
    for country in catalog["countries"]:
        for section in country["sections"]:
            pools.append(section["facts"])
            pools.extend(sub["facts"] for sub in section["subsections"])
    for route in catalog["routes"]:
        pools.append(route.get("lead_facts") or [])
        pools.extend(section.get("facts") or [] for section in route["sections"])
    for facts in pools:
        for fact in facts:
            assert fact["short_label"]
            assert fact["short_label"].casefold() in " ".join(fact["text"].split()).casefold()
            for number in __import__("re").findall(r"\d+", fact["short_label"]):
                assert number in fact["text"]

    china = COUNTRIES_KNOWLEDGE_BASE["china"]["sections"]["8_tax_free"]["facts"]
    stored = next(fact for fact in china if fact.get("short_label") == "порог")
    published = next(
        fact for fact in next(
            section for section in next(country for country in catalog["countries"] if country["slug"] == "china")["sections"]
            if section["key"] == "8_tax_free"
        )["facts"]
        if fact["text"] == stored["text"]
    )
    assert published["short_label"] == "порог"
    assert "score" not in published


def test_topics_follow_data_and_the_summary_limit_comes_from_config():
    painted, route = _run(get_catalog())
    assert [group["title"] for group in painted["split"]] == ["Касса", "ВТБ"]
    assert painted["split"][1]["ids"] == ["a", "b"]
    assert [group["title"] for group in painted["together"]] == ["Касса", "Оплата"]
    assert len(painted["short"]["shown"]) == 1
    assert painted["short"]["more"] == 2
    assert painted["wholeMore"] == 0
    assert painted["restored"]["groups"] == {"card:all": True}
    assert painted["broken"] == {"groups": {}, "facts": {}, "summaries": {}}
    assert painted["plain"].startswith("Tax free:")
    assert "покупки от ¥200" in painted["plain"]
    assert "ещё" in painted["plain"]
    assert painted["located"] == painted["expandedId"]
    collapsed = painted["collapsed"]
    expanded = painted["expanded"]
    assert 'class="fact-group-body" hidden' in collapsed
    assert 'aria-expanded="false"' in collapsed
    assert f'data-group="{painted["expandedId"]}"' in expanded
    assert 'aria-expanded="true"' in expanded
    assert 'class="fact-details" hidden' in collapsed
    assert 'class="fact-details"' in expanded
    assert "Сообщить о неточности" in expanded
    assert "data-action=\"summary-item\"" in collapsed
    assert "data-zone=\"green\"" in collapsed

    ticket = route["routeCollapsed"].split('<article class="ticket">', 1)[1].split("</article>", 1)[0]
    assert "<article class=\"fact" not in ticket
    assert 'class="card-summary"' in ticket
    assert 'class="fact-group-body" hidden' in ticket
    assert route["leadTitle"]
    assert route["transferTitle"] in ticket
    copy = route["routeCollapsed"].split('<div class="route-copy">', 1)[1]
    assert "PEK → город" in copy
    assert "Компас оплаты" not in copy
    assert f'data-group="{route["transferOpenId"]}"' in route["routeExpanded"]
    opened = route["routeExpanded"].split(f'data-group="{route["transferOpenId"]}"', 1)[1]
    assert 'aria-expanded="true"' in opened
    assert 'class="fact-key"' in opened


FRESH_CARDS_SCRIPT = r"""
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const catalog = JSON.parse(Buffer.concat(chunks).toString("utf8"));
globalThis.location = { hash: "#/guide/georgia/3_local_wallets_cards", search: "", hostname: "127.0.0.1" };
globalThis.document = { documentElement: { dataset: {}, style: {} }, querySelector() { return null; } };

const { sectionTopicGroups, topicGroups } = await import("./miniapp/js/ui.js");
const { render } = await import("./miniapp/js/screens.js");

function baseState(extra) {
  return {
    catalog,
    introSeen: true,
    unverified: {},
    progress: {},
    openRoute: "",
    trip: null,
    profile: { favorite_countries: [], bank_id: "tbank", departure_city_id: "mow", citizenship: "ru" },
    draft: {},
    cursor: {},
    sheet: null,
    openGroups: {},
    openFacts: {},
    openSummaries: {},
    ...extra,
  };
}

function groupChunks(html) {
  return html.split('<section class="fact-group"').slice(1).map((chunk) => chunk.split("</section>")[0]);
}

function groupName(chunk) {
  const match = chunk.match(/class="fact-group-name">([^<]*)</);
  return match ? match[1] : "";
}

const georgia = catalog.countries.find((country) => country.slug === "georgia");
const wallets = georgia.sections.find((section) => section.key === "3_local_wallets_cards");
const limits = { prefixMax: catalog.summary.prefix_max_chars, minFacts: catalog.summary.min_facts, catalog };
const cardGroups = sectionTopicGroups(wallets, catalog, false);
const tbcGroup = cardGroups.find((group) => group.facts.some((fact) => fact.text.startsWith("TBC Bank:")));
const georgiaCollapsed = render(baseState());
const georgiaExpanded = render(baseState({
  openGroups: tbcGroup ? { [`georgia/3_local_wallets_cards:${tbcGroup.id}`]: true } : {},
}));

location.hash = "#/trip";
const route = catalog.routes.find((item) => item.id === "mow_thailand");
const transfer = route.sections.find((section) => section.id === "route:mow_thailand:transfer");
const transferGroups = topicGroups(transfer.facts, { ...limits, fallbackId: "all", fallbackTitle: transfer.title });
const grabGroup = transferGroups.find((group) => group.facts.some((fact) => fact.text.includes("JustGrab") && fact.text.includes("652")));
const transferOpenId = grabGroup && `${transfer.id}:${grabGroup.id}`;
const trip = {
  destination_slug: "thailand",
  departure_city_id: "mow",
  depart_date: "2026-12-01",
  return_date: "2026-12-12",
};
const transferCollapsed = render(baseState({ trip, openRoute: transfer.id }));
const transferExpanded = render(baseState({
  trip,
  openRoute: transfer.id,
  openGroups: transferOpenId ? { [transferOpenId]: true } : {},
}));

process.stdout.write(JSON.stringify({
  tbcTitle: tbcGroup && tbcGroup.title,
  tbcId: tbcGroup && `georgia/3_local_wallets_cards:${tbcGroup.id}`,
  georgiaTitles: groupChunks(georgiaCollapsed).map(groupName),
  georgiaCollapsed,
  georgiaExpanded,
  grabTitle: grabGroup && grabGroup.title,
  transferOpenId,
  transferTitles: groupChunks(transferCollapsed).map(groupName),
  transferCollapsed,
  transferExpanded,
  grabTexts: (grabGroup && grabGroup.facts || []).map((fact) => fact.text),
}));
"""


def _fresh(catalog):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", FRESH_CARDS_SCRIPT],
        input=json.dumps(catalog),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _group_named(html, title):
    for chunk in html.split('<section class="fact-group"')[1:]:
        body = chunk.split("</section>", 1)[0]
        if f'class="fact-group-name">{title}<' in body:
            return body
    return ""


def test_georgia_tbc_and_bkk_dmk_grab_use_collapsed_groups():
    painted = _fresh(get_catalog())
    assert painted["tbcTitle"] == "Местная карта или счёт"
    assert "Риск" in painted["georgiaTitles"]
    tbc = _group_named(painted["georgiaCollapsed"], "Местная карта или счёт")
    assert tbc
    assert 'class="fact-group-body" hidden' in tbc
    assert "TBC Bank" in tbc
    assert "10 GEL" in tbc
    assert 'data-zone="green"' in tbc
    assert "Unired" not in painted["georgiaCollapsed"]
    opened = painted["georgiaExpanded"].split(f'data-group="{painted["tbcId"]}"', 1)[1]
    assert 'aria-expanded="true"' in opened
    assert "карту Visa выпускают" in opened
    assert 'class="fact-key"' in opened

    assert painted["grabTitle"] == "Трансфер"
    titles = painted["transferTitles"]
    assert titles[0] == "Москва → Таиланд", titles
    assert "Трансфер" in titles, titles
    assert titles.index("Трансфер") < titles.index("Чек-лист")
    transfer = _group_named(painted["transferCollapsed"], "Трансфер")
    assert 'class="fact-group-body" hidden' in transfer
    assert "JustGrab" in transfer and "652" in transfer
    assert "GrabCar" in transfer and "924" in transfer
    assert "1 038 батов" in transfer
    assert "Floor 1" in transfer
    assert "<article class=\"fact" not in painted["transferCollapsed"]
    expanded = painted["transferExpanded"].split(f'data-group="{painted["transferOpenId"]}"', 1)[1]
    assert 'aria-expanded="true"' in expanded
    assert "Котировка в Grab наличными, не поездка." in expanded
    assert "Компас оплаты" not in painted["transferCollapsed"].split('<div class="route-copy">', 1)[1]
