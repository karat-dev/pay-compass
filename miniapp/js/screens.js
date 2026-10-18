import { backPlan, routeForTrip, searchTicketsUrl, tripCountdown, tripWhen } from "./flow.js";
import {
  countryBySlug,
  daysUntil,
  esc,
  factMeta,
  formatDay,
  groupFacts,
  hasHidden,
  icon,
  nightsBetween,
  parseRoute,
  searchRows,
  sectionOf,
  splitName,
  stepPosition,
  ruCount,
  ticketsUrl,
  visibleFacts,
  visibleSteps,
  zoneName,
} from "./ui.js";

const ORDER_HINT = "Сначала подтверждённые, внутри группы — более свежая проверка выше.";

function factCard(fact) {
  const zone = fact.gap ? "gap" : (fact.zone || "yellow");
  const source = fact.source_url
    ? `<a class="source-link" href="${esc(fact.source_url)}" data-action="link" data-url="${esc(fact.source_url)}">Источник</a>`
    : `<span>Официальной ссылки нет.</span>`;
  return `<article class="fact${fact.hidden ? " is-unverified" : ""}${fact.gap ? " is-gap" : ""}" data-zone="${esc(zone)}" data-fact-id="${esc(fact.id)}">
    <div class="fact-top">
      <span class="zone-dot" aria-hidden="true"></span>
      <span class="zone-name">${esc(zoneName(zone))}</span>
      <span class="fact-meta">${esc(factMeta(fact))}</span>
    </div>
    <p class="fact-text">${esc(fact.text)}</p>
    <p class="source">${source}</p>
    <button type="button" class="text-btn" data-action="report" data-id="${esc(fact.id)}">Сообщить о неточности</button>
  </article>`;
}

function choice(group, id, label, on, extra = "") {
  return `<button type="button" class="choice${on ? " is-on" : ""}" data-action="choice" data-group="${esc(group)}" data-id="${esc(id)}" aria-pressed="${on ? "true" : "false"}">
    <span>${esc(label)}</span>${extra ? `<span class="choice-extra">${extra}</span>` : ""}${on ? icon("check") : ""}
  </button>`;
}

function navigationPlan(state, screen) {
  let instructionIndex = 0;
  let instructionSection = "";
  if (screen.name === "instruction" && state.catalog) {
    const instruction = state.catalog.instructions[screen.instructionId];
    instructionSection = (instruction && instruction.section) || "";
    const scope = `instruction:${instruction && instruction.id}`;
    const steps = visibleSteps(instruction, Boolean(state.unverified && state.unverified[scope]));
    instructionIndex = stepPosition(steps, state.progress || {}, state.cursor && instruction && state.cursor[instruction.id]);
  }
  return backPlan({
    screen: Object.assign({}, screen, { instructionSection }),
    stackDepth: state.stackDepth == null ? 1 : state.stackDepth,
    introSeen: Boolean(state.introSeen),
    introStep: state.introStep || 0,
    pickStep: state.step || 0,
    instructionIndex,
    openRoute: state.openRoute || "",
    sheet: Boolean(state.sheet),
    returnTo: state.returnTo || "",
  });
}

function backButton() {
  return `<button type="button" class="icon-btn" data-action="back" aria-label="Назад">${icon("back")}</button>`;
}

function header(state, screen) {
  const titles = {
    trip: "Поездка",
    "trip-edit": "Поездка",
    guide: "Справочник",
    country: "Страна",
    section: "Раздел",
    instruction: "Инструкция",
    sos: "SOS",
    profile: "Профиль",
    search: "Поиск",
    intro: "Умный туризм",
    pick: "Подбор под поездку",
  };
  let title = titles[screen.name] || "Умный туризм";
  if (screen.name === "country") {
    const country = countryBySlug(state.catalog, screen.slug);
    title = country ? splitName(country.name).title : title;
  }
  if (screen.name === "section") {
    const section = sectionOf(countryBySlug(state.catalog, screen.slug), screen.sectionKey);
    title = section ? section.short_title : title;
  }
  if (screen.name === "instruction") {
    const instruction = state.catalog.instructions[screen.instructionId];
    title = instruction ? instruction.service : title;
  }
  const back = navigationPlan(state, screen).type === "none" ? "" : backButton();
  const search = screen.name === "intro" || screen.name === "pick" || screen.name === "search"
    ? ""
    : `<button type="button" class="icon-btn" data-action="search" aria-label="Поиск">${icon("search")}</button>`;
  if (screen.name === "search") {
    return `<header class="header">
      ${back || backButton()}
      <input id="search-input" class="search-input" type="search" placeholder="Факт, страна или раздел" value="${esc(state.query)}" autocomplete="off">
    </header>`;
  }
  return `<header class="header">
    ${back}
    <h1 class="header-title">${esc(title)}</h1>
    ${search}
  </header>`;
}

function nav(screen) {
  const items = [
    ["trip", "Поездка", "trip"],
    ["guide", "Справочник", "guide"],
    ["sos", "SOS", "sos"],
    ["profile", "Профиль", "profile"],
  ];
  return `<nav class="nav" aria-label="Разделы">${items.map(([tab, label, glyph]) => {
    const current = screen.tab === tab;
    return `<button type="button" data-action="tab" data-tab="${tab}" ${current ? 'aria-current="page"' : ""}>
      ${icon(glyph)}<span>${label}</span>
    </button>`;
  }).join("")}</nav>`;
}

function introDots(step) {
  return `<p class="intro-dots" aria-hidden="true">${[0, 1, 2, 3].map((index) => `<span class="${index === step ? "is-on" : ""}"></span>`).join("")}</p>`;
}

function zoneMarks(zones) {
  return `<span class="zone-marks" aria-hidden="true">${zones.map((zone) => `<span class="zone-dot" data-zone="${esc(zone)}"></span>`).join("")}</span>`;
}

function introScreen(state) {
  const step = state.introStep || 0;
  let body = "";
  if (step === 0) {
    body = `<h2>Платите за границей без сюрпризов</h2>
      <p class="lead">Подскажем, как платить в стране поездки именно вам: что работает с вашим банком, где нужна зарубежная карта или наличные, как перевести деньги. У каждого факта — дата проверки и источник.</p>`;
  } else if (step === 1) {
    body = `<h2>Мы честно показываем, насколько уверены</h2>
      <ul class="intro-zones">
        <li>${zoneMarks(["green"])}<span>Зелёный — подтверждено официальным источником или нашим личным опытом, проверено недавно.</span></li>
        <li>${zoneMarks(["yellow"])}<span>Жёлтый — скорее всего верно, но источник слабее или проверка давняя.</span></li>
        <li>${zoneMarks(["red", "black"])}<span>Красный и чёрный — мало подтверждений, устарело или опровергнуто. Скрыты, открываются кнопкой «Показать непроверенное».</span></li>
      </ul>
      <p class="intro-fine">Рядом с каждым фактом — дата проверки. Где данных нет, честно пишем «не исследовано».</p>`;
  } else if (step === 2) {
    body = `<h2>Всё к поездке в одном месте</h2>
      <ul class="intro-list">
        <li>Чек-лист: что сделать до вылета и на месте</li>
        <li>Связь: eSIM, чтобы интернет был сразу после посадки</li>
        <li>Страховка и трансфер из аэропорта</li>
        <li class="intro-soon">SOS: что делать, если не прошла карта, задержали рейс или потерялся багаж <span class="soon">скоро</span></li>
      </ul>
      <p class="intro-fine">Ссылки на eSIM, страховку и трансфер — партнёрские.</p>`;
  } else {
    body = `<h2>Без лишнего</h2>
      <p class="lead">Храним только Telegram ID и настройки. Заметили ошибку — нажмите „Сообщить о неточности“, мы исправим.</p>
      <div class="onboard-actions intro-actions">
        <button type="button" class="primary" data-action="intro-pick">Подобрать под поездку</button>
        <button type="button" class="ghost" data-action="intro-skip">Пропустить</button>
      </div>`;
  }
  const forward = step < 3
    ? `<div class="onboard-actions"><button type="button" class="primary" data-action="intro-next">Дальше</button></div>`
    : "";
  return `<section class="screen onboard">${introDots(step)}${body}${forward}</section>`;
}

function dateFields(draft) {
  return `<div class="dates">
      <label>Вылет<span class="hint"> необязательно</span><input id="depart-date" type="date" value="${esc(draft.depart_date || "")}" data-field="depart_date"></label>
      <label>Обратно<span class="hint"> необязательно</span><input id="return-date" type="date" value="${esc(draft.return_date || "")}" data-field="return_date"></label>
    </div>
    <p class="hint">Пустая дата так и остаётся пустой: в карточке будет «Дата не выбрана», без «Вылет сегодня».</p>`;
}

function pickScreen(state) {
  const step = state.step || 0;
  const draft = state.draft;
  let body = "";
  if (step === 0) {
    body = `<p class="eyebrow">Подбор под поездку · шаг 1 из 3</p>
      <h2>Какой банк берёте в поездку?</h2>
      <p class="lead">Подскажем QR и переводы, которые относятся к нему. Номер карты не нужен.</p>
      <div class="stack">${state.catalog.banks.map((bank) => choice("bank", bank.id, bank.label, draft.bank_id === bank.id)).join("")}</div>`;
  } else if (step === 1) {
    body = `<p class="eyebrow">Подбор под поездку · шаг 2 из 3</p>
      <h2>Откуда вылет?</h2>
      <p class="lead">Город нужен для чек-листа и ссылки на билеты.</p>
      <div class="stack">${state.catalog.cities.map((city) => choice("city", city.id, city.name, draft.departure_city_id === city.id, city.iata)).join("")}</div>`;
  } else {
    body = `<p class="eyebrow">Подбор под поездку · шаг 3 из 3</p>
      <h2>Куда и когда?</h2>
      <p class="lead">Страна собирает чек-лист. Дата вылета необязательна. Разбор маршрута с ценами билетов не показываем.</p>
      <div class="stack">${state.catalog.countries.map((country) => {
        const place = splitName(country.name);
        return choice("country", country.slug, place.title, draft.destination_slug === country.slug, place.flag);
      }).join("")}</div>
      ${dateFields(draft)}
      <button type="button" class="consent${draft.consent ? " is-on" : ""}" data-action="consent" aria-pressed="${draft.consent ? "true" : "false"}">
        <span class="tick">${draft.consent ? icon("check") : ""}</span>
        <span>Согласен на обработку Telegram ID и настроек: банк, город вылета, поездка. Имя, username и телефон не сохраняем.</span>
      </button>
      <button type="button" class="text-btn" data-action="privacy">Политика конфиденциальности</button>`;
  }
  const ready = step === 0 ? draft.bank_id : step === 1 ? draft.departure_city_id : (draft.destination_slug && draft.consent);
  return `<section class="screen onboard">
    ${body}
    ${state.message ? `<p class="form-error">${esc(state.message)}</p>` : ""}
    <div class="onboard-actions">
      ${step > 0 ? `<button type="button" class="ghost" data-action="pick-back">Назад</button>` : ""}
      <button type="button" class="primary${ready ? "" : " is-off"}" data-action="pick-next" ${ready ? "" : "disabled"}>${step === 2 ? "Сохранить" : "Дальше"}</button>
    </div>
  </section>`;
}

function tripScreen(state) {
  const trip = state.trip;
  if (!trip || !trip.destination_slug) {
    return `<section class="screen">
      <article class="hero-trip">
        <p class="eyebrow">Поездка</p>
        <h2>Подбор ещё не сделан</h2>
        <p class="lead">Банк, город вылета и страна. Дату можно не указывать — она сама не станет сегодняшней.</p>
        <button type="button" class="primary" data-action="start-pick">Подобрать под поездку</button>
      </article>
    </section>`;
  }
  const city = state.catalog.cities.find((item) => item.id === trip.departure_city_id);
  const country = countryBySlug(state.catalog, trip.destination_slug);
  const place = country ? splitName(country.name) : { title: "Страна", flag: "" };
  const nights = nightsBetween(trip.depart_date, trip.return_date);
  let when = tripWhen(trip.depart_date);
  if (trip.depart_date) {
    when = formatDay(trip.depart_date);
    if (trip.return_date) when += ` — ${formatDay(trip.return_date)}`;
    if (nights) when += ` · ${nights} дн.`;
  }
  const countdown = tripCountdown(daysUntil(trip.depart_date));
  const route = routeForTrip(state.catalog.routes, trip);
  const dateNote = trip.depart_date
    ? ""
    : `<p class="hint">Дата не выбрана — отсчёта до вылета нет. Чек-лист ниже без привязки ко дню.</p>`;
  return `<section class="screen">
    <article class="hero-trip">
      <p class="eyebrow">${esc(countdown || "Поездка")}</p>
      <h2>${esc(city ? city.name : "Город")} → ${esc(place.title)} ${place.flag ? esc(place.flag) : ""}</h2>
      <p class="lead">${esc(when)}</p>
      <button type="button" class="text-btn" data-action="edit-trip">Изменить поездку</button>
      <button type="button" class="text-btn" data-action="start-pick">Подобрать под поездку</button>
    </article>
    ${dateNote}
    ${route ? routeCard(state, route) : unmatchedRoute(state, trip)}
    ${checklist(state, country)}
  </section>`;
}

function unmatchedRoute(state, trip) {
  const city = state.catalog.cities.find((item) => item.id === trip.departure_city_id);
  const country = countryBySlug(state.catalog, trip.destination_slug);
  const url = searchTicketsUrl({
    origin: city && city.iata,
    destination: country && country.ticket_iata,
    depart: trip.depart_date,
    marker: state.catalog.tickets_marker,
  });
  const link = url
    ? `<a class="primary tickets" href="${esc(url)}" data-action="link" data-url="${esc(url)}">Найти билеты</a>`
    : "";
  return `<article class="ticket">
    <p class="eyebrow">Разбор маршрута</p>
    <h2>Разбор этого маршрута пока не готов</h2>
    <p class="lead">Чек-лист ниже — по стране поездки.</p>
    ${link}
  </article>`;
}

function routeCard(state, route) {
  if (!route) return "";
  const names = route.airlines.map((item) => `<span>${esc(item.name)}</span>`).join('<span class="dot">·</span>');
  const placeholder = route.airlines.some((item) => item.placeholder)
    ? `<p class="hint">Страницы авиакомпаний ещё не подключены — пока только названия.</p>`
    : "";
  const open = state.openRoute;
  const chips = route.sections.map((section) => {
    const on = open === section.id;
    return `<button type="button" class="chip${on ? " is-on" : ""}" data-action="route-section" data-id="${esc(section.id)}" aria-expanded="${on ? "true" : "false"}">${esc(section.title)}</button>`;
  }).join("");
  const current = route.sections.find((section) => section.id === open);
  const url = ticketsUrl(route, state.trip && state.trip.depart_date);
  const iata = route.iata ? `<p class="iata">${esc(route.iata)}</p>` : "";
  const link = url
    ? `<a class="primary tickets" href="${esc(url)}" data-action="link" data-url="${esc(url)}">Найти билеты</a>`
    : "";
  return `<article class="ticket">
    <p class="eyebrow">Разбор маршрута</p>
    <h2>${esc(route.title)}</h2>
    ${iata}
    <div class="ticket-rule"></div>
    ${route.summary.map((paragraph) => `<p class="ticket-copy">${esc(paragraph)}</p>`).join("")}
    <div class="airline-row">${names}</div>
    ${placeholder}
    ${link}
    <div class="chip-row">${chips}</div>
    ${current ? routeCopy(state, current) : ""}
  </article>`;
}

function partnerNote(state) {
  const note = state.catalog.partner_note || "";
  return note ? `<span class="partner-note">${esc(note)}</span>` : "";
}

function liveLinks(links) {
  return (links || []).filter((link) => !link.placeholder && /^https:\/\//.test(link.url));
}

function routeCopy(state, current) {
  const note = state.catalog.partner_note || "";
  const links = liveLinks(current.links);
  const anchors = links.map((link) => `<a href="${esc(link.url)}" data-action="link" data-url="${esc(link.url)}">${esc(link.label)}</a>`).join("");
  let text = current.text || "";
  let tail = "";
  if (note && text.includes(note)) {
    const at = text.indexOf(note);
    tail = text.slice(at + note.length).trim();
    text = text.slice(0, at).trim();
  }
  const disclosure = links.some((link) => link.partner) ? `<p class="partner-line">${partnerNote(state)}</p>` : "";
  return `<div class="route-copy"><p>${esc(text)}</p>${anchors ? `<p class="source">${anchors}</p>` : ""}${disclosure}${tail ? `<p>${esc(tail)}</p>` : ""}</div>`;
}

function checklistOffers(state) {
  return (state.catalog.offers || []).filter((offer) => offer.placement === "checklist" && /^https:\/\//.test(offer.url || ""));
}

function checklistOfferRow(state) {
  const offers = checklistOffers(state);
  if (!offers.length) return "";
  const links = offers.map((offer) => `<a href="${esc(offer.url)}" data-action="link" data-url="${esc(offer.url)}">${esc(offer.label)}</a>`).join("");
  return `<div class="partner-row">${links}${partnerNote(state)}</div>`;
}

function groupTitle(group) {
  return `<p class="fact-group-title"><span class="zone-dot" data-zone="${esc(group.zone)}" aria-hidden="true"></span><span>${esc(group.title)}</span><span class="count">${group.facts.length}</span></p>`;
}

function factGroupHtml(facts, renderFact) {
  return groupFacts(facts).map((group) => `<div class="fact-group" data-zone="${esc(group.zone)}">${groupTitle(group)}${group.facts.map(renderFact).join("")}</div>`).join("");
}

function orderHint() {
  return `<p class="hint order-hint">${ORDER_HINT}</p>`;
}

function checklist(state, country) {
  if (!country) return "";
  const section = sectionOf(country, "1_checklist");
  if (!section) return "";
  const offer = checklistOfferRow(state);
  if (!section.applicable) {
    return `<section class="block"><h2>Чек-лист до вылета</h2><p>${esc(section.note || "Раздел не применим.")}</p>${offer}</section>`;
  }
  const show = Boolean(state.unverified.checklist);
  const facts = section.facts || [];
  const tasks = visibleFacts(facts.filter((fact) => !fact.gap), show);
  const done = tasks.filter((fact) => state.progress[fact.id] && state.progress[fact.id].completed).length;
  const checkRow = (fact) => {
    const checked = Boolean(state.progress[fact.id] && state.progress[fact.id].completed);
    return `<div class="check${checked ? " is-done" : ""}">
      <button type="button" class="tick" data-action="check" data-id="${esc(fact.id)}" aria-pressed="${checked ? "true" : "false"}" aria-label="Отметить пункт">${checked ? icon("check") : ""}</button>
      <div class="check-body">${factCard(fact)}</div>
    </div>`;
  };
  const visibleRows = factGroupHtml(
    visibleFacts(facts.filter((fact) => !fact.gap), false).concat(facts.filter((fact) => fact.gap)),
    (fact) => (fact.gap ? factCard(fact) : checkRow(fact)),
  );
  const hiddenRows = show ? factGroupHtml(facts.filter((fact) => !fact.gap && fact.hidden), checkRow) : "";
  const toggle = hasHidden(facts)
    ? `<button type="button" class="ghost wide" data-action="unverified" data-scope="checklist">${show ? "Скрыть непроверенное" : "Показать непроверенное"}</button>`
    : "";
  return `<section class="block">
    <div class="block-head">
      <h2>Чек-лист до вылета</h2>
      <p class="hint">${done} из ${tasks.length}</p>
    </div>
    ${visibleRows || hiddenRows ? orderHint() : ""}
    ${visibleRows || `<p class="hint">В зелёной и жёлтой зоне пунктов нет.</p>`}
    ${offer}
    ${toggle}
    ${hiddenRows}
  </section>`;
}

function guideHome(state) {
  const cards = state.catalog.countries.map((country) => {
    const place = splitName(country.name);
    const fav = (state.profile.favorite_countries || []).includes(country.slug);
    return `<button type="button" class="country-card" data-action="open-country" data-slug="${esc(country.slug)}">
      <span class="flag">${esc(place.flag)}</span>
      <span>
        <strong>${esc(place.title)}</strong>
        <span class="hint">${fav ? "В избранном · " : ""}8 разделов</span>
      </span>
    </button>`;
  }).join("");
  return `<section class="screen">
    <p class="lead">Шесть стран. В каждом разделе сначала зелёная и жёлтая зоны. Данные на ${esc(state.catalog.checked_label)}.</p>
    <div class="stack">${cards}</div>
  </section>`;
}

function countryScreen(state, screen) {
  const country = countryBySlug(state.catalog, screen.slug);
  if (!country) return missing();
  const place = splitName(country.name);
  const tiles = country.sections.map((section) => {
    const count = visibleFacts(section.facts, false).length
      + (section.subsections || []).reduce((sum, sub) => sum + visibleFacts(sub.facts, false).length, 0);
    const guideCount = (section.instructions || []).length;
    let meta = section.applicable ? ruCount(count, "факт", "факта", "фактов") : "не применимо";
    if (guideCount) meta += ` · ${ruCount(guideCount, "инструкция", "инструкции", "инструкций")}`;
    return `<button type="button" class="section-tile" data-action="open-section" data-slug="${esc(country.slug)}" data-key="${esc(section.key)}">
      <span class="section-index">${esc(section.key.slice(0, 1))}</span>
      <span class="section-copy">
        <strong>${esc(section.short_title)}</strong>
        <span class="hint">${esc(meta)}</span>
      </span>
    </button>`;
  }).join("");
  return `<section class="screen">
    <p class="eyebrow">${esc(place.flag)} ${esc(place.title)}</p>
    <p class="lead">${esc(country.headline)}</p>
    <div class="section-grid">${tiles}</div>
  </section>`;
}

function sectionScreen(state, screen) {
  const country = countryBySlug(state.catalog, screen.slug);
  const section = sectionOf(country, screen.sectionKey);
  if (!section) return missing();
  const scope = `${country.slug}/${section.key}`;
  const show = Boolean(state.unverified[scope]);
  const offer = section.key === "1_checklist" ? checklistOfferRow(state) : "";
  if (!section.applicable) {
    return `<section class="screen"><h2>${esc(section.title)}</h2><p class="lead">Раздел не применим: ${esc(section.note || "")}</p>${offer}</section>`;
  }
  const pools = [{ title: "", facts: section.facts || [], note: "" }].concat(
    (section.subsections || []).map((sub) => ({
      title: sub.title,
      facts: sub.applicable ? (sub.facts || []) : [],
      note: sub.applicable ? "" : (sub.note || "Не применимо."),
    })),
  );
  const hidden = pools.some((pool) => hasHidden(pool.facts));
  const visibleBlocks = pools.map((pool) => poolMarkup(pool)).join("");
  const hiddenBlocks = show ? pools.map((pool) => hiddenMarkup(pool)).join("") : "";
  const guides = (section.instructions || []).map((id) => instructionTeaser(state, country.slug, id)).join("");
  const toggle = hidden
    ? `<button type="button" class="ghost wide" data-action="unverified" data-scope="${esc(scope)}">${show ? "Скрыть непроверенное" : "Показать непроверенное"}</button>`
    : "";
  const anyFacts = pools.some((pool) => (pool.facts || []).some((fact) => show || !fact.hidden));
  const empty = visibleBlocks || hiddenBlocks
    ? ""
    : `<p class="hint">${show ? "Дополнительных непроверенных фактов нет." : "В зелёной и жёлтой зоне фактов нет."}</p>`;
  return `<section class="screen">
    <p class="eyebrow">${esc(splitName(country.name).title)}</p>
    <h2>${esc(section.title)}</h2>
    ${anyFacts ? orderHint() : ""}
    ${visibleBlocks}
    ${empty}
    ${offer}
    ${toggle}
    ${hiddenBlocks}
    <div class="instruction-block">${guides}</div>
  </section>`;
}

function poolMarkup(pool) {
  const title = pool.title ? `<h3>${esc(pool.title)}</h3>` : "";
  if (pool.note) return `${title}<p class="hint">${esc(pool.note)}</p>`;
  const facts = (pool.facts || []).filter((fact) => !fact.hidden);
  if (!facts.length) {
    if (!pool.title || (pool.facts || []).some((fact) => fact.hidden)) return "";
    return `${title}<p class="hint">В зелёной и жёлтой зоне фактов нет.</p>`;
  }
  return `${title}${factGroupHtml(facts, factCard)}`;
}

function hiddenMarkup(pool) {
  const facts = (pool.facts || []).filter((fact) => fact.hidden);
  if (!facts.length) return "";
  const title = pool.title ? `<h3>${esc(pool.title)}</h3>` : "";
  return `${title}${factGroupHtml(facts, factCard)}`;
}

function instructionTeaser(state, slug, id) {
  const instruction = state.catalog.instructions[id];
  if (!instruction) return "";
  const steps = visibleSteps(instruction, false);
  const done = steps.filter((step) => state.progress[step.id] && state.progress[step.id].completed).length;
  return `<button type="button" class="instruction-card" data-action="open-instruction" data-slug="${esc(slug)}" data-id="${esc(id)}">
    <span class="eyebrow">По шагам</span>
    <strong>${esc(instruction.service)}</strong>
    <span class="hint">${done ? `сделано ${done} из ${steps.length}` : ruCount(steps.length, "шаг", "шага", "шагов")}</span>
  </button>`;
}

function instructionScreen(state, screen) {
  const instruction = state.catalog.instructions[screen.instructionId];
  if (!instruction) return missing();
  const scope = `instruction:${instruction.id}`;
  const show = Boolean(state.unverified[scope]);
  const steps = visibleSteps(instruction, show);
  if (!steps.length) {
    return `<section class="screen"><h2>${esc(instruction.service)}</h2><p class="hint">В зелёной и жёлтой зоне шагов нет.</p>
      ${hasHidden(instruction.steps) ? `<button type="button" class="ghost wide" data-action="unverified" data-scope="${esc(scope)}">Показать непроверенное</button>` : ""}
    </section>`;
  }
  const index = stepPosition(steps, state.progress, state.cursor[instruction.id]);
  const step = steps[index];
  const done = steps.filter((item) => state.progress[item.id] && state.progress[item.id].completed).length;
  const checked = Boolean(state.progress[step.id] && state.progress[step.id].completed);
  const intro = index === 0 && instruction.intro ? `<p class="lead">${esc(instruction.intro)}</p>` : "";
  const prereq = index === 0 && instruction.prereq && instruction.prereq.length
    ? `<div class="note"><p class="eyebrow">До начала</p><ul>${instruction.prereq.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></div>`
    : "";
  const last = index === steps.length - 1;
  const footerBits = [];
  if (last && instruction.costs) footerBits.push(`<p><strong>Комиссия и курс.</strong> ${esc(instruction.costs)}</p>`);
  if (last && instruction.limits) footerBits.push(`<p><strong>Лимиты.</strong> ${esc(instruction.limits)}</p>`);
  if (last && instruction.risks && instruction.risks.length) {
    footerBits.push(`<p class="eyebrow">На что смотреть</p><ul>${instruction.risks.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`);
  }
  const width = Math.round(((index + 1) / steps.length) * 100);
  return `<section class="screen instruction">
    <p class="eyebrow">${esc(instruction.app || instruction.provider || "Инструкция")}</p>
    <div class="progress" aria-hidden="true"><span style="width:${width}%"></span></div>
    <p class="step-count">шаг ${index + 1} из ${steps.length}</p>
    <p class="hint">сделано ${done} из ${steps.length}</p>
    ${step.stage ? `<p class="stage">${esc(step.stage)}</p>` : ""}
    ${intro}
    ${prereq}
    ${factCard(step)}
    <button type="button" class="ghost wide" data-action="step-done" data-id="${esc(step.id)}" data-instruction="${esc(instruction.id)}" aria-pressed="${checked ? "true" : "false"}">${checked ? "Шаг сделан" : "Отметить шаг"}</button>
    ${hasHidden(instruction.steps) ? `<button type="button" class="text-btn" data-action="unverified" data-scope="${esc(scope)}">${show ? "Скрыть непроверенное" : "Показать непроверенное"}</button>` : ""}
    ${footerBits.length ? `<div class="note">${footerBits.join("")}</div>` : ""}
    <div class="step-nav">
      <button type="button" class="ghost" data-action="step-move" data-dir="-1" ${index === 0 ? "disabled" : ""}>Назад</button>
      <button type="button" class="primary" data-action="step-move" data-dir="1" ${last ? "disabled" : ""}>Дальше</button>
    </div>
  </section>`;
}

function sosScreen(state) {
  const country = state.trip && countryBySlug(state.catalog, state.trip.destination_slug);
  const slug = country ? country.slug : "china";
  return `<section class="screen sos">
    <p class="eyebrow">После запуска</p>
    <h2>SOS пока заглушка</h2>
    <p class="lead">Экстренные контакты и помощь на месте появятся отдельным обновлением. Если карта не проходит сейчас, откройте раздел про мошенничество и 115-ФЗ.</p>
    <button type="button" class="primary" data-action="open-section" data-slug="${esc(slug)}" data-key="7_risks">Мошенничество и 115-ФЗ</button>
  </section>`;
}

function profileScreen(state) {
  const profile = state.profile || {
    bank_id: "",
    departure_city_id: "",
    favorite_countries: [],
    notify_checklist: true,
    notify_trip: true,
    notify_alerts: false,
  };
  const banks = state.catalog.banks.map((bank) => choice("bank", bank.id, bank.label, profile.bank_id === bank.id)).join("");
  const cities = state.catalog.cities.map((city) => choice("city", city.id, city.name, profile.departure_city_id === city.id, city.iata)).join("");
  const favorites = state.catalog.countries.map((country) => {
    const place = splitName(country.name);
    const on = (profile.favorite_countries || []).includes(country.slug);
    return `<button type="button" class="choice${on ? " is-on" : ""}" data-action="fav" data-slug="${esc(country.slug)}" aria-pressed="${on ? "true" : "false"}"><span>${esc(place.flag)} ${esc(place.title)}</span>${on ? icon("check") : ""}</button>`;
  }).join("");
  const notifies = [
    ["notify_checklist", "Чек-лист до вылета"],
    ["notify_trip", "Напоминания о поездке"],
    ["notify_alerts", "Изменения по оплате"],
  ].map(([key, label]) => `<button type="button" class="choice${profile[key] ? " is-on" : ""}" data-action="notify" data-key="${key}" aria-pressed="${profile[key] ? "true" : "false"}"><span>${esc(label)}</span>${profile[key] ? icon("check") : ""}</button>`).join("");
  return `<section class="screen">
    <h2>Банк</h2>
    <div class="stack">${banks}</div>
    <h2>Город вылета</h2>
    <div class="stack">${cities}</div>
    <h2>Избранные страны</h2>
    <div class="stack">${favorites}</div>
    <h2>Уведомления</h2>
    <p class="hint">Бот пришлёт сообщение со ссылкой в приложение. Расписание уведомлений включим после запуска.</p>
    <div class="stack">${notifies}</div>
    <button type="button" class="ghost wide" data-action="replay-intro">Показать знакомство снова</button>
    <button type="button" class="text-btn" data-action="privacy">Политика конфиденциальности</button>
    <p class="hint">Храним только Telegram ID и настройки. Удаление — команда /delete_me в чате с ботом.</p>
    ${state.message ? `<p class="form-error">${esc(state.message)}</p>` : ""}
  </section>`;
}

function tripEdit(state) {
  const draft = state.draft;
  return `<section class="screen">
    <h2>Куда и когда</h2>
    <div class="stack">${state.catalog.countries.map((country) => {
      const place = splitName(country.name);
      return choice("country", country.slug, place.title, draft.destination_slug === country.slug, place.flag);
    }).join("")}</div>
    ${dateFields(draft)}
    ${state.message ? `<p class="form-error">${esc(state.message)}</p>` : ""}
    <button type="button" class="primary" data-action="save-trip">Сохранить</button>
  </section>`;
}

function searchScreen(state) {
  const query = (state.query || "").trim().toLowerCase();
  if (query.length < 2) {
    return `<section class="screen"><p class="lead">Ищите по фактам и разделам. Например, UnionPay, Tax free или банкомат.</p></section>`;
  }
  const rows = searchRows(state.catalog).filter((row) => row.haystack.toLowerCase().includes(query)).slice(0, 30);
  if (!rows.length) return `<section class="screen"><p class="lead">Ничего не нашли.</p></section>`;
  return `<section class="screen"><div class="stack">${rows.map((row) => `<button type="button" class="search-hit" data-action="open-result" data-hash="${esc(row.hash)}" data-hidden="${row.hidden ? "1" : ""}" data-slug="${esc(row.slug || "")}" data-key="${esc(row.sectionKey || "")}" data-instruction="${esc(row.instructionId || "")}">
    <strong>${esc(row.title)}</strong>
    <span class="hint">${esc(row.note)}${row.hidden ? " · непроверенное" : ""}</span>
  </button>`).join("")}</div></section>`;
}

function sheet(state) {
  if (!state.sheet) return "";
  if (state.sheet.type === "privacy") {
    return `<div class="sheet-back" data-action="close-sheet"><div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
      <h2 id="sheet-title">Политика конфиденциальности</h2>
      <pre class="policy">${esc(state.catalog.privacy || "")}</pre>
      <button type="button" class="primary" data-action="close-sheet">Закрыть</button>
    </div></div>`;
  }
  const fact = state.sheet.fact;
  return `<div class="sheet-back" data-action="close-sheet"><div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
    <h2 id="sheet-title">Сообщить о неточности</h2>
    <p class="hint">${esc(fact ? fact.text : "")}</p>
    <textarea id="report-comment" maxlength="1000" placeholder="Что не совпало с кассой, банком или сайтом">${esc(state.reportComment || "")}</textarea>
    <button type="button" class="primary" data-action="submit-report">Отправить</button>
    <button type="button" class="ghost wide" data-action="close-sheet">Отмена</button>
  </div></div>`;
}

function missing() {
  return `<section class="screen"><h2>Раздел не найден</h2><button type="button" class="primary" data-action="tab" data-tab="guide">К справочнику</button></section>`;
}

export function render(state) {
  const screen = parseRoute(location.hash);
  let body = "";
  if (!state.catalog) body = `<p class="boot">Открываем справочник…</p>`;
  else if (state.failed) {
    const title = state.failedTitle || "Не удалось открыть";
    body = `<section class="screen"><h2>${esc(title)}</h2><p class="lead">${esc(state.failed)}</p></section>`;
  }
  else if (screen.name === "intro") body = introScreen(state);
  else if (screen.name === "pick") body = pickScreen(state);
  else if (screen.name === "trip") body = tripScreen(state);
  else if (screen.name === "trip-edit") body = tripEdit(state);
  else if (screen.name === "guide") body = guideHome(state);
  else if (screen.name === "country") body = countryScreen(state, screen);
  else if (screen.name === "section") body = sectionScreen(state, screen);
  else if (screen.name === "instruction") body = instructionScreen(state, screen);
  else if (screen.name === "sos") body = sosScreen(state);
  else if (screen.name === "profile") body = profileScreen(state);
  else if (screen.name === "search") body = searchScreen(state);
  const showNav = state.catalog && screen.name !== "intro";
  const toast = state.toast ? `<p class="toast" role="status">${esc(state.toast)}</p>` : "";
  return `<div class="shell" data-ready="1" data-screen="${esc(screen.name)}">
    ${state.catalog ? header(state, screen) : ""}
    <main class="content">${body}</main>
    ${showNav ? nav(screen) : ""}
    ${state.catalog ? sheet(state) : ""}
    ${toast}
  </div>`;
}

export { parseRoute };
