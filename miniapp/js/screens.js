import {
  countryBySlug,
  daysUntil,
  esc,
  factMeta,
  formatDay,
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
    onboarding: "Умный туризм",
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
  const nested = !["trip", "guide", "sos", "profile", "onboarding"].includes(screen.name);
  const back = nested
    ? `<button type="button" class="icon-btn" data-action="back" aria-label="Назад">${icon("back")}</button>`
    : "";
  const search = screen.name === "onboarding" || screen.name === "search"
    ? ""
    : `<button type="button" class="icon-btn" data-action="search" aria-label="Поиск">${icon("search")}</button>`;
  if (screen.name === "search") {
    return `<header class="header">
      <button type="button" class="icon-btn" data-action="back" aria-label="Назад">${icon("back")}</button>
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

function onboarding(state) {
  const step = state.step || 0;
  const draft = state.draft;
  let body = "";
  if (step === 0) {
    body = `<p class="eyebrow">Шаг 1 из 3</p>
      <h2>Какой банк берёте в поездку?</h2>
      <p class="lead">Подскажем QR и переводы, которые относятся к нему. Номер карты не нужен.</p>
      <div class="stack">${state.catalog.banks.map((bank) => choice("bank", bank.id, bank.label, draft.bank_id === bank.id)).join("")}</div>`;
  } else if (step === 1) {
    body = `<p class="eyebrow">Шаг 2 из 3</p>
      <h2>Откуда вылет?</h2>
      <p class="lead">Город нужен для чек-листа и ссылки на билеты.</p>
      <div class="stack">${state.catalog.cities.map((city) => choice("city", city.id, city.name, draft.departure_city_id === city.id, city.iata)).join("")}</div>`;
  } else {
    body = `<p class="eyebrow">Шаг 3 из 3</p>
      <h2>Куда и когда?</h2>
      <p class="lead">Соберём чек-лист по стране. Разбор маршрута с ценами билетов не показываем.</p>
      <div class="stack">${state.catalog.countries.map((country) => {
        const place = splitName(country.name);
        return choice("country", country.slug, place.title, draft.destination_slug === country.slug, place.flag);
      }).join("")}</div>
      <div class="dates">
        <label>Вылет<input id="depart-date" type="date" value="${esc(draft.depart_date || "")}" data-field="depart_date"></label>
        <label>Обратно<input id="return-date" type="date" value="${esc(draft.return_date || "")}" data-field="return_date"></label>
      </div>
      <button type="button" class="consent${draft.consent ? " is-on" : ""}" data-action="consent" aria-pressed="${draft.consent ? "true" : "false"}">
        <span class="tick">${draft.consent ? icon("check") : ""}</span>
        <span>Согласен на обработку Telegram ID, банка, города вылета и поездки. Паспорт и карту не спрашиваем.</span>
      </button>
      <button type="button" class="text-btn" data-action="privacy">Политика конфиденциальности</button>`;
  }
  const ready = step === 0 ? draft.bank_id : step === 1 ? draft.departure_city_id : (draft.destination_slug && draft.depart_date && draft.consent);
  return `<section class="screen onboard">
    ${body}
    ${state.message ? `<p class="form-error">${esc(state.message)}</p>` : ""}
    <div class="onboard-actions">
      ${step > 0 ? `<button type="button" class="ghost" data-action="onboard-back">Назад</button>` : ""}
      <button type="button" class="primary${ready ? "" : " is-off"}" data-action="onboard-next" ${ready ? "" : "disabled"}>${step === 2 ? "Открыть поездку" : "Дальше"}</button>
    </div>
  </section>`;
}

function tripScreen(state) {
  const trip = state.trip;
  const city = state.catalog.cities.find((item) => item.id === (trip && trip.departure_city_id)) || state.catalog.cities[0];
  const country = countryBySlug(state.catalog, trip && trip.destination_slug);
  const place = country ? splitName(country.name) : { title: "Страна не выбрана", flag: "" };
  const until = trip && daysUntil(trip.depart_date);
  const nights = trip && nightsBetween(trip.depart_date, trip.return_date);
  let when = "Даты не указаны";
  if (trip && trip.depart_date) {
    when = formatDay(trip.depart_date);
    if (trip.return_date) when += ` — ${formatDay(trip.return_date)}`;
    if (nights) when += ` · ${nights} дн.`;
  }
  let countdown = "";
  if (until === 0) countdown = "Вылет сегодня";
  else if (until > 0) countdown = `До вылета ${until} дн.`;
  else if (until < 0) countdown = "Дата вылета уже прошла";
  const route = state.catalog.routes[0];
  const matches = trip && trip.departure_city_id === "mow" && trip.destination_slug === "hong_kong";
  return `<section class="screen">
    <article class="hero-trip">
      <p class="eyebrow">${esc(countdown || "Ваша поездка")}</p>
      <h2>${esc(city ? city.name : "Город")} → ${esc(place.title)} ${place.flag ? esc(place.flag) : ""}</h2>
      <p class="lead">${esc(when)}</p>
      <button type="button" class="text-btn" data-action="edit-trip">Изменить поездку</button>
    </article>
    ${routeCard(state, route, matches)}
    ${checklist(state, country)}
  </section>`;
}

function routeCard(state, route, matches) {
  if (!route) return "";
  const note = matches
    ? ""
    : `<p class="hint">Подробный разбор пока есть только для Москва → Гонконг через Пекин. Чек-лист ниже — по вашей стране.</p>`;
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
  const links = current
    ? current.links.filter((link) => !link.placeholder).map((link) => `<a href="${esc(link.url)}" data-action="link" data-url="${esc(link.url)}">${esc(link.label)}</a>`).join("")
    : "";
  const url = ticketsUrl(route, state.trip && state.trip.depart_date);
  return `<article class="ticket">
    <p class="eyebrow">Разбор маршрута</p>
    <h2>${esc(route.title)}</h2>
    <p class="iata">MOW · PEK · HKG</p>
    <div class="ticket-rule"></div>
    ${route.summary.map((paragraph) => `<p class="ticket-copy">${esc(paragraph)}</p>`).join("")}
    <div class="airline-row">${names}</div>
    ${placeholder}
    <a class="primary tickets" href="${esc(url)}" data-action="link" data-url="${esc(url)}">Найти билеты</a>
    <div class="chip-row">${chips}</div>
    ${current ? `<div class="route-copy"><p>${esc(current.text)}</p>${links ? `<p class="source">${links}</p>` : ""}</div>` : ""}
    ${note}
  </article>`;
}

function checklist(state, country) {
  if (!country) return "";
  const section = sectionOf(country, "1_checklist");
  if (!section) return "";
  if (!section.applicable) {
    return `<section class="block"><h2>Чек-лист до вылета</h2><p>${esc(section.note || "Раздел не применим.")}</p></section>`;
  }
  const show = Boolean(state.unverified.checklist);
  const facts = section.facts || [];
  const tasks = visibleFacts(facts.filter((fact) => !fact.gap), show);
  const gaps = facts.filter((fact) => fact.gap);
  const done = tasks.filter((fact) => state.progress[fact.id] && state.progress[fact.id].completed).length;
  const rows = tasks.map((fact) => {
    const checked = Boolean(state.progress[fact.id] && state.progress[fact.id].completed);
    return `<div class="check${checked ? " is-done" : ""}">
      <button type="button" class="tick" data-action="check" data-id="${esc(fact.id)}" aria-pressed="${checked ? "true" : "false"}" aria-label="Отметить пункт">${checked ? icon("check") : ""}</button>
      <div class="check-body">${factCard(fact)}</div>
    </div>`;
  }).join("");
  const toggle = hasHidden(facts)
    ? `<button type="button" class="ghost wide" data-action="unverified" data-scope="checklist">${show ? "Скрыть непроверенное" : "Показать непроверенное"}</button>`
    : "";
  return `<section class="block">
    <div class="block-head">
      <h2>Чек-лист до вылета</h2>
      <p class="hint">${done} из ${tasks.length}</p>
    </div>
    ${rows || `<p class="hint">В зелёной и жёлтой зоне пунктов нет.</p>`}
    ${gaps.map((fact) => factCard(fact)).join("")}
    ${toggle}
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
      <span>
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
  if (!section.applicable) {
    return `<section class="screen"><h2>${esc(section.title)}</h2><p class="lead">Раздел не применим: ${esc(section.note || "")}</p></section>`;
  }
  const pools = [{ title: "", facts: section.facts || [], note: "" }].concat(
    (section.subsections || []).map((sub) => ({
      title: sub.title,
      facts: sub.applicable ? (sub.facts || []) : [],
      note: sub.applicable ? "" : (sub.note || "Не применимо."),
    })),
  );
  const hidden = pools.some((pool) => hasHidden(pool.facts));
  const blocks = pools.map((pool) => {
    const facts = visibleFacts(pool.facts, show);
    const title = pool.title ? `<h3>${esc(pool.title)}</h3>` : "";
    if (pool.note) return `${title}<p class="hint">${esc(pool.note)}</p>`;
    if (!facts.length && !pool.title) {
      const subsections = section.subsections || [];
      const nested = subsections.some((sub) => visibleFacts(sub.facts || [], show).length || sub.note);
      if (nested) return "";
      return `<p class="hint">${show ? "Дополнительных непроверенных фактов нет." : "В зелёной и жёлтой зоне фактов нет."}</p>`;
    }
    if (!facts.length) return `${title}<p class="hint">${show ? "Дополнительных непроверенных фактов нет." : "В зелёной и жёлтой зоне фактов нет."}</p>`;
    return `${title}${facts.map(factCard).join("")}`;
  }).join("");
  const guides = (section.instructions || []).map((id) => instructionTeaser(state, country.slug, id)).join("");
  const toggle = hidden
    ? `<button type="button" class="ghost wide" data-action="unverified" data-scope="${esc(scope)}">${show ? "Скрыть непроверенное" : "Показать непроверенное"}</button>`
    : "";
  return `<section class="screen">
    <p class="eyebrow">${esc(splitName(country.name).title)}</p>
    <h2>${esc(section.title)}</h2>
    ${toggle}
    ${blocks}
    ${guides}
  </section>`;
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
  const profile = state.profile;
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
    <button type="button" class="text-btn" data-action="privacy">Политика конфиденциальности</button>
    <p class="hint">Удалить данные можно командой /delete_me в чате с ботом.</p>
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
    <div class="dates">
      <label>Вылет<input id="depart-date" type="date" value="${esc(draft.depart_date || "")}" data-field="depart_date"></label>
      <label>Обратно<input id="return-date" type="date" value="${esc(draft.return_date || "")}" data-field="return_date"></label>
    </div>
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
  else if (state.failed) body = `<section class="screen"><h2>Справочник не открылся</h2><p class="lead">${esc(state.failed)}</p></section>`;
  else if (screen.name === "onboarding") body = onboarding(state);
  else if (screen.name === "trip") body = tripScreen(state);
  else if (screen.name === "trip-edit") body = tripEdit(state);
  else if (screen.name === "guide") body = guideHome(state);
  else if (screen.name === "country") body = countryScreen(state, screen);
  else if (screen.name === "section") body = sectionScreen(state, screen);
  else if (screen.name === "instruction") body = instructionScreen(state, screen);
  else if (screen.name === "sos") body = sosScreen(state);
  else if (screen.name === "profile") body = profileScreen(state);
  else if (screen.name === "search") body = searchScreen(state);
  const showNav = state.catalog && screen.name !== "onboarding";
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
