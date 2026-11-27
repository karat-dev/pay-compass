/** Screen frames for the Mini App shell. Later steps fill elements marked data-slot. */

import {
  LOYALTY_CHECKED,
  LOYALTY_PROGRAMS,
  allianceLabel,
  allianceMembers,
  filterLoyalty,
  programById,
  programInitials,
} from "./loyalty_catalog.js";
import {
  CHINA_GUIDE,
  COUNTRIES,
  PAYMENT_CATALOG,
  countryFlag,
  searchCountries,
  systemLabel,
  systemsForKind,
} from "./payment_catalog.js";
import {
  CARD_FORMATS,
  FILTER_MODES,
  GROUP_MODES,
  MATCH_CHANNELS,
  MATCH_LABELS,
  PAYMENT_KINDS,
  SORT_MODES,
  filterPayments,
  groupPayments,
  joinNames,
  matchDot,
  matchMethod,
  modeLabel,
  presentPayment,
  sortPayments,
} from "./payment_flow.js";
import {
  CITIZENSHIPS,
  bookingName,
  cardLooksTypical,
  cardsWord,
  citizenshipChoice,
  maskCard,
  passportFit,
} from "./profile_flow.js";
import { esc } from "./ui.js";
import {
  TRIP_CHECKS,
  assessFlightRows,
  checklistCaption,
  flightsWord,
  guideSlugFor,
  tripChecks,
} from "./trip_flow.js";

export const DEMO_TRIP = {
  id: "demo-shanghai-2026",
  origin: "Москва",
  destination: "Шанхай",
  country: "Китай",
  depart: "2026-12-12",
  ret: "2026-12-20",
  stepsDone: 2,
  stepsTotal: 6,
  checks: ["entry", "docs"],
  flights: [],
};

const MONTHS = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

const POPULAR = [
  { slug: "china", flag: "🇨🇳", name: "Китай" },
  { slug: "thailand", flag: "🇹🇭", name: "Таиланд" },
  { slug: "turkey", flag: "🇹🇷", name: "Турция" },
  { slug: "uae", flag: "🇦🇪", name: "ОАЭ" },
  { slug: "georgia", flag: "🇬🇪", name: "Грузия" },
  { slug: "hong_kong", flag: "🇭🇰", name: "Гонконг" },
];

const GUIDE_REGIONS = [
  {
    title: "Страна вылета",
    open: true,
    items: [{ slug: "russia", flag: "🇷🇺", name: "Россия", zone: "yellow" }],
  },
  {
    title: "Ближний Восток · доступно 2 из 21",
    open: true,
    items: [
      { slug: "uae", flag: "🇦🇪", name: "ОАЭ", zone: "yellow" },
      { slug: "turkey", flag: "🇹🇷", name: "Турция", zone: "green" },
    ],
  },
  {
    title: "Восточная Азия · доступно 2 из 19",
    open: true,
    items: [
      { slug: "china", flag: "🇨🇳", name: "Китай", zone: "yellow", note: "Материковый" },
      { slug: "hong_kong", flag: "🇭🇰", name: "Гонконг", zone: "yellow" },
    ],
  },
  {
    title: "Европа и Кавказ · доступно 1 из 58",
    open: true,
    items: [{ slug: "georgia", flag: "🇬🇪", name: "Грузия", zone: "yellow" }],
  },
  {
    title: "Юго-Восточная Азия · доступно 1 из 11",
    open: true,
    items: [{ slug: "thailand", flag: "🇹🇭", name: "Таиланд", zone: "green" }],
  },
  { title: "Австралия и Океания · доступно 0 из 14", open: false, items: [] },
  { title: "Африка · доступно 0 из 60", open: false, items: [] },
  { title: "Карибы · доступно 0 из 16", open: false, items: [] },
  { title: "Северная Америка · доступно 0 из 5", open: false, items: [] },
  { title: "Центральная Азия · доступно 0 из 6", open: false, items: [] },
  { title: "Центральная Америка · доступно 0 из 7", open: false, items: [] },
  { title: "Южная Азия · доступно 0 из 9", open: false, items: [] },
  { title: "Южная Америка · доступно 0 из 12", open: false, items: [] },
];

const COUNTRY_TITLES = {
  russia: "Россия",
  uae: "ОАЭ",
  turkey: "Турция",
  china: "Китай",
  hong_kong: "Гонконг",
  georgia: "Грузия",
  thailand: "Таиланд",
  airlines: "Авиакомпании и мили",
};

const NAV = [
  ["home", "/home", "Главная", '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>'],
  ["trip", "/trip", "Поездка", '<path d="M2 16l20-6-20-6 4 6z"/><path d="M6 10h8"/>'],
  ["guide", "/guide", "Справочник", '<path d="M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z"/><path d="M20 4h-4a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h5z"/>'],
  ["profile", "/profile", "Профиль", '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>'],
];

function splitIso(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return { year, month, day };
}

export function formatStay(depart, ret) {
  const start = splitIso(depart);
  const end = splitIso(ret);
  if (!start) return "Даты не указаны";
  const startText = `${start.day} ${MONTHS[start.month - 1]} ${start.year}`;
  if (!end) return startText;
  if (start.year === end.year && start.month === end.month) {
    return `${start.day}–${end.day} ${MONTHS[start.month - 1]} ${start.year}`;
  }
  const endText = `${end.day} ${MONTHS[end.month - 1]} ${end.year}`;
  return `${startText} – ${endText}`;
}

export function formatDotDate(iso) {
  const parts = splitIso(iso);
  if (!parts) return "";
  const day = String(parts.day).padStart(2, "0");
  const month = String(parts.month).padStart(2, "0");
  return `${day}.${month}.${parts.year}`;
}

export function defaultSettings() {
  return {
    language: "Русский",
    currency: "Рубли",
    theme: "Обычная",
    notifications: "Изменились правила въезда · пришлём уведомление",
    consentAt: "",
    nameOrder: "given",
  };
}

export function shellState(extra = {}) {
  const route = extra.route || { name: "home", tab: "home", inner: false, slug: "" };
  return {
    trips: [],
    passport: null,
    loyalty: [],
    payments: [],
    query: "",
    outside: false,
    supportOpen: false,
    supportReported: false,
    sheet: "",
    promoOpen: false,
    payGroup: "system",
    payFilter: "all",
    paySort: "added",
    payOpenId: "",
    payDraft: null,
    payReturn: "",
    payExperienceId: "",
    payExperienceDraft: null,
    experienceOpen: false,
    notice: "",
    focusSearch: false,
    flightDraft: null,
    alliance: "",
    loyaltyOpenId: "",
    passportDraft: null,
    loyaltyDraft: null,
    editingId: "",
    ...extra,
    settings: { ...defaultSettings(), ...(extra.settings || {}) },
    route,
  };
}

function safeSlug(slug) {
  return /^[a-z0-9_-]{1,40}$/i.test(String(slug || "")) ? String(slug) : "";
}

function icon(paths) {
  return `<svg class="ut-ico" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}

function sosButton() {
  return `<button type="button" class="ut-sos" data-shell="sos">SOS</button>`;
}

function headerHome(state) {
  const theme = state.settings.theme || "Обычная";
  return `<header class="ut-header">
    <h1 class="ut-brand"><span aria-hidden="true">🧭</span> Умный туризм</h1>
    <div class="ut-header-tools">
      <button type="button" class="ut-theme" data-shell="route" data-path="/settings">Тема · ${esc(theme)} ▾</button>
      ${sosButton()}
    </div>
  </header>`;
}

function headerBar(title, inner) {
  const back = inner
    ? `<button type="button" class="ut-back" data-shell="back" aria-label="Назад">‹</button>`
    : "";
  return `<header class="ut-header">
    <h1 class="ut-h1">${back}${esc(title)}</h1>
    ${sosButton()}
  </header>`;
}

function searchField(placeholder, value) {
  return `<label class="ut-search">
    <span aria-hidden="true">🔍</span>
    <input data-shell-field="search" type="search" enterkeyhint="search" autocomplete="off" placeholder="${esc(placeholder)}" value="${esc(value || "")}">
  </label>`;
}

function legend() {
  return `<div class="ut-legend">
    <i class="ut-dot ut-dot-green" aria-hidden="true"></i><span>официальный источник</span>
    <i class="ut-dot ut-dot-yellow" aria-hidden="true"></i><span>неофициальный / свой замер / ещё не сверено</span>
    <i class="ut-dot ut-dot-red" aria-hidden="true"></i><span>риск</span>
  </div>`;
}

function row(title, detail, path, detailClass) {
  return `<button type="button" class="ut-row" data-shell="route" data-path="${esc(path)}">
    <span><span class="ut-row-title">${title}</span>${detail ? `<span class="${detailClass || "ut-row-text"}">${detail}</span>` : ""}</span>
    <span class="ut-chev" aria-hidden="true">›</span>
  </button>`;
}

function activeTrip(state) {
  return state.trips && state.trips.length ? state.trips[0] : null;
}

function matches(query, text) {
  if (!query) return true;
  return String(text || "").toLowerCase().includes(query.trim().toLowerCase());
}

function renderDemo(state) {
  const tripOn = state.trips.length === 1 && state.trips[0] && state.trips[0].id === DEMO_TRIP.id;
  const emptyOn = state.trips.length === 0;
  return `<div class="ut-demo">
    <span>Локальный просмотр</span>
    <button type="button" data-shell="demo" data-mode="trip" aria-pressed="${tripOn ? "true" : "false"}">Шанхай, 12–20 декабря 2026</button>
    <button type="button" data-shell="demo" data-mode="empty" aria-pressed="${emptyOn ? "true" : "false"}">Нет поездок</button>
  </div>`;
}

function renderHome(state) {
  const trip = activeTrip(state);
  const query = state.query || "";
  const countries = POPULAR.filter((item) => matches(query, item.name));
  const countryHtml = countries.map((item) => (
    `<button type="button" class="ut-country" data-shell="route" data-path="/guide/${item.slug}">
      <span class="ut-flag" aria-hidden="true">${item.flag}</span>
      <b>${esc(item.name)}</b>
    </button>`
  )).join("");
  const tripHtml = trip ? `<button type="button" class="ut-trip" data-shell="route" data-path="/trip">
      <span class="ut-trip-top"><b>${esc(trip.origin || "Москва")} → ${esc(trip.destination)}</b><span aria-hidden="true">✈️</span></span>
      <span class="ut-trip-dates">${esc(formatStay(trip.depart, trip.ret))}</span>
      <span class="ut-track" aria-hidden="true"><span style="width:${progressWidth(trip)}"></span></span>
      <span class="ut-trip-foot"><span>Подготовка: ${tripChecks(trip).length} из ${TRIP_CHECKS.length} шагов</span><span>открыть ›</span></span>
    </button>` : `<section class="ut-empty">
      <b>Пока нет поездки</b>
      <p>Добавьте направление — подскажем въезд, оплату, связь и транспорт</p>
      <button type="button" class="ut-primary" data-shell="route" data-path="/trip">Добавить поездку</button>
    </section>`;
  const promoCode = state.promoOpen
    ? `<p class="ut-code">Пример промокода: SHARJAH26</p><button type="button" class="ut-promo-btn" data-shell="promo">Скрыть промокод</button>`
    : `<button type="button" class="ut-promo-btn" data-shell="promo">Показать промокод</button>`;
  return `${headerHome(state)}
    ${searchField("Страна, город или тема: Alipay, eSIM…", query)}
    <section class="ut-promo" data-slot="home-promo">
      <div class="ut-promo-top"><span class="ut-partner">Партнёр</span><button type="button" class="ut-linkish" data-shell="soon" data-text="Список промокодов подключим следующим шагом.">Все промокоды ›</button></div>
      <div class="ut-promo-brand"><span>Я</span><span><b>Яндекс Путешествия</b><small>до 30 ноября 2026</small></span></div>
      <p class="ut-promo-value">−25%</p>
      <p class="ut-promo-line">На жильё в эмирате Шарджа</p>
      ${promoCode}
      <p class="ut-fine">Скидка до 3 000 ₽ · только первые 350 · сверено 01.11.2026<br>Шаблон баннера · тема «Обычная»</p>
    </section>
    <div data-slot="home-trip">${tripHtml}</div>
    <div class="ut-section-head"><b>Популярные страны и территории</b><button type="button" class="ut-linkish" data-shell="route" data-path="/guide">Все ›</button></div>
    <div class="ut-countries" data-slot="home-countries">${countryHtml || `<p class="ut-muted ut-pad">Ничего не нашли. Попробуйте другую страну или тему.</p>`}</div>
    <button type="button" class="ut-useful" data-shell="route" data-path="/guide">
      <b>Полезное перед поездкой</b>
      <span>eSIM, наличные, страховка — 5 советов</span>
    </button>
    <p class="ut-disclaimer">Пример. Промокод условный. Тема «Обычная» — шаблон; сезонные темы (Новый год, Хэллоуин, Масленица) подключаются отдельно.</p>`;
}

function progressWidth(trip) {
  const total = TRIP_CHECKS.length;
  const done = tripChecks(trip).length;
  if (!total) return "0%";
  return `${Math.max(0, Math.min(100, Math.round((done / total) * 100)))}%`;
}

function renderTrip(state) {
  const trip = activeTrip(state);
  if (!trip) {
    return `${headerBar("Поездка", false)}
      <section class="ut-empty" data-slot="trip-empty">
        <b>Пока нет поездки</b>
        <p>Добавьте направление и даты с годом. Поездка сохранится только на этом устройстве.</p>
      </section>
      <form class="ut-form" data-shell-form="trip" data-slot="trip-form">
        <label>Откуда<input name="origin" maxlength="40" autocomplete="off" value="Москва"></label>
        <label>Куда<input name="destination" maxlength="40" autocomplete="off" placeholder="Город"></label>
        <label>Страна<input name="country" maxlength="40" autocomplete="off" placeholder="Китай"></label>
        <label>Туда<input name="depart" type="date" autocomplete="off"></label>
        <label>Обратно<input name="ret" type="date" autocomplete="off"></label>
        <button type="submit" class="ut-primary">Сохранить поездку</button>
        <p class="ut-fine">Поездка хранится только у вас. Даты указывайте с годом.</p>
      </form>`;
  }
  const flights = Array.isArray(trip.flights) ? trip.flights : [];
  const slug = guideSlugFor(trip);
  const flightNote = flights.length ? "сведения не сверены" : "нужно действие";
  const flightDesc = flights.length
    ? `В поездке ${flights.length} ${flightsWord(flights.length)}`
    : "Добавьте рейс для проверки пересадок";
  const tiles = [
    ["#fff0e3", "🛂", "Въезд", "Условия въезда и проверка паспорта", "green", "сведения сверены 01.11.2026", slug ? `/guide/${slug}` : "/guide"],
    ["#edf0f6", "📋", "Чек-лист", checklistCaption(trip), "green", "сведения сверены 01.11.2026", "/trip/checklist"],
    ["#e8f1fa", "🛫", "Перелёт и пересадки", flightDesc, "yellow", flightNote, "/trip/flight-add"],
    ["#e9f2fc", "💳", "Оплата", "Что подготовить до вылета", "green", "сведения сверены 01.11.2026", "/trip/pay"],
    ["#f0ebfc", "📶", "Связь", "eSIM на даты поездки, ссылки партнёров", "green", "сведения сверены 01.11.2026", "/trip/checklist"],
    ["#f0f3e9", "🛡", "Страховка", "Подобрать полис на даты", "yellow", "нужно действие", "/trip/checklist"],
    ["#edf0f6", "🚕", "Транспорт", `${trip.destination} → центр, метро, такси`, "green", "сведения сверены 01.11.2026", "/trip/transport"],
  ];
  const cards = tiles.map(([bg, mark, title, desc, zone, note, path]) => (
    `<button type="button" class="ut-tile" style="background:${bg}" data-shell="route" data-path="${esc(path)}">
      <span class="ut-tile-icon" aria-hidden="true">${mark}</span>
      <b>${title}</b>
      <p>${esc(desc)}</p>
      <span class="ut-checked"><i class="ut-dot ut-dot-${zone}"></i>${esc(note)}</span>
    </button>`
  )).join("");
  const addLabel = flights.length ? "Добавить ещё рейс" : "+ Добавьте рейс, чтобы проверить пересадки";
  return `${headerBar("Поездка", false)}
    <p class="ut-lead">Шаги в порядке подготовки · пример</p>
    <section class="ut-trip ut-trip-static" data-slot="trip-summary">
      <span class="ut-trip-top"><b>${esc(trip.origin || "Москва")} → ${esc(trip.destination)}</b><span aria-hidden="true">✈️</span></span>
      <span class="ut-trip-dates">${esc(formatStay(trip.depart, trip.ret))}</span>
      <button type="button" class="ut-inline-link" data-shell="route" data-path="/trip/edit">Изменить город, страну и даты</button>
      <button type="button" class="ut-inline-link" data-shell="route" data-path="/trip/flight-add">${addLabel}</button>
      <span class="ut-track" aria-hidden="true"><span style="width:${progressWidth(trip)}"></span></span>
      <span class="ut-progress">Подготовка: ${tripChecks(trip).length} из ${TRIP_CHECKS.length} шагов</span>
    </section>
    ${renderFlightList(flights)}
    <button type="button" class="ut-primary ut-save" data-shell="save-trip">Сохранить поездку</button>
    <p class="ut-caption">Выберите разделы и поездку</p>
    <div class="ut-tiles" data-slot="trip-steps">${cards}</div>`;
}

function renderFlightList(flights) {
  if (!flights.length) return "";
  const items = flights.map((flight) => {
    const when = formatDotDate(flight.date) || String(flight.date || "");
    const route = flight.from && flight.to ? `${flight.from} — ${flight.to}` : "";
    const sample = flight.sample ? " Пример, не расписание." : "";
    return `<article class="ut-flight" data-flight-number="${esc(flight.number || "")}" data-flight-date="${esc(flight.date || "")}">
      <div>
        <b>${esc(flight.number || "Рейс")} · ${esc(when)}</b>
        ${route ? `<p>${esc(route)}</p>` : ""}
        <p class="ut-ver"><i class="ut-dot ut-dot-yellow"></i>сведения не сверены.${sample ? esc(sample) : ""}</p>
      </div>
      <button type="button" class="ut-flight-del" data-shell="flight-delete" data-id="${esc(flight.id || "")}">Удалить</button>
    </article>`;
  }).join("");
  return `<div class="ut-flight-list" data-slot="trip-flights">${items}</div>`;
}

function renderNeedTrip(title) {
  return `${headerBar(title, true)}
    <section class="ut-empty" data-slot="trip-empty">
      <b>Пока нет поездки</b>
      <p>Сначала сохраните направление и даты — затем можно добавить рейс и отметить шаги.</p>
      <button type="button" class="ut-primary" data-shell="route" data-path="/trip">Добавить поездку</button>
    </section>`;
}

function renderTripEdit(state) {
  const trip = activeTrip(state);
  if (!trip) return renderNeedTrip("Поездка");
  return `${headerBar("Поездка", true)}
    <p class="ut-lead">Город, страна и даты с годом хранятся только на этом устройстве.</p>
    <form class="ut-form" data-shell-form="trip-edit" data-slot="trip-edit">
      <label>Откуда<input name="origin" maxlength="40" autocomplete="off" value="${esc(trip.origin || "")}"></label>
      <label>Куда<input name="destination" maxlength="40" autocomplete="off" value="${esc(trip.destination || "")}"></label>
      <label>Страна<input name="country" maxlength="40" autocomplete="off" value="${esc(trip.country || "")}"></label>
      <label>Туда<input name="depart" type="date" autocomplete="off" value="${esc(trip.depart || "")}"></label>
      <label>Обратно<input name="ret" type="date" autocomplete="off" value="${esc(trip.ret || "")}"></label>
      <button type="submit" class="ut-primary">Сохранить поездку</button>
    </form>`;
}

function renderChecklist(state) {
  const trip = activeTrip(state);
  if (!trip) return renderNeedTrip("Чек-лист");
  const checks = new Set(tripChecks(trip));
  const items = TRIP_CHECKS.map((item) => {
    const on = checks.has(item.id);
    return `<button type="button" class="ut-check${on ? " is-on" : ""}" data-shell="check" data-id="${item.id}" aria-pressed="${on ? "true" : "false"}">
      <span class="ut-radio" aria-hidden="true"></span>
      <span><b>${esc(item.title)}</b><span class="ut-row-text">${on ? "Отмечено" : "Отметить"}</span></span>
    </button>`;
  }).join("");
  return `${headerBar("Чек-лист", true)}
    <p class="ut-lead">${esc(checklistCaption(trip))}. Подготовка: ${checks.size} из 6 шагов</p>
    <div data-slot="trip-checklist">${items}</div>`;
}

function checkedLine(zone, text) {
  return `<span class="ut-stamp"><i class="ut-dot ut-dot-${zone}"></i>${esc(text)}</span>`;
}

function renderTripPay(state) {
  const trip = activeTrip(state);
  if (!trip) return renderNeedTrip("Оплата");
  const place = [trip.origin || "Москва", trip.destination, trip.country].filter(Boolean).join(" · ");
  const slug = guideSlugFor(trip);
  const guide = slug && PAYMENT_CATALOG[slug] ? PAYMENT_CATALOG[slug].guide : null;
  const payments = Array.isArray(state.payments) ? state.payments : [];
  const names = joinNames(payments.map((item) => presentPayment(item).title));
  const countryName = (slug && COUNTRY_TITLES[slug]) || trip.country || "этой стране";
  const matchPath = slug ? `/guide/${slug}/pay` : "/pay";
  const mine = payments.length
    ? `<p class="ut-sub">В профиле сохранены ${esc(names)}. Сверка с ${esc(countryName)} ещё не сделана.</p>
       <button type="button" class="ut-secondary ut-inline-btn" data-shell="route" data-path="${esc(matchPath)}">Сверить с моими способами</button>
       <button type="button" class="ut-inline-link" data-shell="route" data-path="${esc(matchPath)}">Полное сравнение ›</button>`
    : `<p class="ut-sub">В профиле пока нет способов оплаты. Добавьте их — сверка покажет, какие подходят для этой страны.</p>
       <button type="button" class="ut-secondary ut-inline-btn" data-shell="pay-add-return" data-return="${esc(matchPath)}">Добавить способы оплаты</button>`;
  const payBlock = guide
    ? `<section class="ut-seg">
        <div class="ut-seg-head"><h2>💳 Чем платить</h2>${checkedLine("green", `проверено ${formatDotDate(guide.checked)}`)}</div>
        <div class="ut-chips ut-chips-tight">${guide.payChips.map((item) => `<span class="ut-chip">${esc(item)}</span>`).join("")}</div>
        <p class="ut-mark">Оплата в стране · не список приёма везде.</p>
        <p class="ut-sub">${esc(guide.payText)}</p>
        <p class="ut-note ut-note-tight">${esc(guide.payNote)}</p>
      </section>
      <section class="ut-seg">
        <div class="ut-seg-head"><h2>💰 Наличные и снятие</h2>${checkedLine("green", `проверено ${formatDotDate(guide.checked)}`)}</div>
        <p class="ut-sub">${esc(guide.cashText)}</p>
        <p class="ut-note ut-note-tight">${esc(guide.cashGap)}</p>
      </section>`
    : `<section class="ut-seg">
        <div class="ut-seg-head"><h2>💳 Чем платить</h2>${checkedLine("yellow", "сведения не сверены")}</div>
        <p class="ut-sub">Для этой страны в справочнике оплаты пока нет проверенных сведений. Держите запасной способ.</p>
      </section>`;
  return `${headerBar("Оплата", true)}
    <p class="ut-lead">${esc(place)} · ${esc(formatStay(trip.depart, trip.ret))}</p>
    <div data-slot="trip-pay">
      ${payBlock}
      <section class="ut-seg">
        <div class="ut-seg-head"><h2>🔗 Мои способы в этой стране</h2>${checkedLine("yellow", "нужно действие")}</div>
        ${mine}
      </section>
      <section class="ut-seg">
        <div class="ut-seg-head"><h2>⚠️ Запасной вариант</h2></div>
        <p class="ut-sub">${esc(guide ? guide.backup : "Не полагайтесь на один способ: карта, приложение и немного наличных закрывают разные ситуации.")}</p>
      </section>
      <section class="ut-seg">
        <div class="ut-seg-head"><h2>💡 До вылета</h2>${checkedLine("yellow", "нужно действие")}</div>
        <p class="ut-sub">${esc(guide ? guide.before : "Привяжите карту и сделайте тестовую оплату до вылета.")}</p>
      </section>
      <p class="ut-fine ut-foot">Это пример сведений, не подтверждение приёма.</p>
      <button type="button" class="ut-primary ut-save" data-shell="soon" data-text="Выберите разделы и поездку">Сохранить</button>
      <p class="ut-caption">Выберите разделы и поездку</p>
    </div>`;
}

function renderTripTransport(state) {
  const trip = activeTrip(state);
  if (!trip) return renderNeedTrip("Транспорт");
  const slug = guideSlugFor(trip);
  const path = slug ? `/guide/${slug}` : "/guide";
  const label = slug ? "Открыть в справочнике" : "Открыть справочник";
  return `${headerBar("Транспорт", true)}
    <p class="ut-lead">${esc(trip.destination || "Город")} → центр, метро, такси</p>
    <section class="ut-slot" data-slot="trip-transport">
      <p class="ut-lead">Как добраться по городу, смотрите в справочнике. Это не расписание рейсов.</p>
      <button type="button" class="ut-inline-link" data-shell="route" data-path="${esc(path)}">${label}</button>
    </section>`;
}

function flightRowHtml(row, assessed) {
  const hint = assessed.empty && row.index === 0
    ? `<p class="ut-hintline">Формат номера: SU 204</p>`
    : "";
  const errors = [
    row.formatError ? `<p class="ut-err">Неверный формат. Пример: SU 204</p>` : "",
    row.dateError ? `<p class="ut-err">Укажите дату вылета</p>` : "",
  ].join("");
  const legs = row.legs.length
    ? `<p class="ut-hintline">Несколько участков в этот день. Выберите «откуда — куда». Пример, не расписание.</p>${row.legs.map((leg) => (
      `<button type="button" class="ut-opt${leg.id === row.selectedLegId ? " is-on" : ""}" data-shell="flight-leg" data-index="${row.index}" data-leg="${esc(leg.id)}" aria-pressed="${leg.id === row.selectedLegId ? "true" : "false"}"><span class="ut-radio" aria-hidden="true"></span>${esc(leg.from)} — ${esc(leg.to)}</button>`
    )).join("")}`
    : "";
  const status = row.unverified ? `<p class="ut-ver"><i class="ut-dot ut-dot-yellow"></i>сведения не сверены</p>` : "";
  const outside = row.outside ? `<p class="ut-warnbox">${esc(assessed.outsideText)}</p>` : "";
  const duplicate = row.duplicate ? `<p class="ut-soft">Этот рейс уже есть в поездке</p>` : "";
  const drop = row.index > 1
    ? `<button type="button" class="ut-more" data-shell="flight-drop" data-index="${row.index}">Убрать</button>`
    : "";
  return `<section class="ut-seg" data-flight-row="${row.index}">
    <div class="ut-seg-title">${esc(row.label)}</div>
    <div class="ut-cols">
      <label>
        <span class="ut-lab">Номер рейса</span>
        <input class="ut-field${row.formatError ? " is-bad" : ""}" data-shell-field="flight-number" data-index="${row.index}" type="text" inputmode="text" autocomplete="off" maxlength="12" placeholder="SU 204" value="${esc(row.numberRaw)}">
      </label>
      <label>
        <span class="ut-lab">Дата вылета</span>
        <input class="ut-field${row.dateError ? " is-bad" : ""}" data-shell-field="flight-date" data-index="${row.index}" type="text" inputmode="numeric" autocomplete="off" maxlength="10" placeholder="ДД.ММ.ГГГГ" value="${esc(row.dateRaw)}">
      </label>
    </div>
    ${hint}${errors}${status}${outside}${legs}${duplicate}${drop}
  </section>`;
}

function renderFlightAdd(state) {
  const trip = activeTrip(state);
  if (!trip) return renderNeedTrip("Добавить рейс");
  if (!Array.isArray(state.flightDraft) || !state.flightDraft.length) {
    state.flightDraft = [{ number: "", date: "", legId: "" }, { number: "", date: "", legId: "" }];
  }
  const assessed = assessFlightRows(state.flightDraft, trip, formatStay(trip.depart, trip.ret));
  const rows = assessed.rows.map((row) => flightRowHtml(row, assessed)).join("");
  const idle = assessed.canSave ? "" : " is-idle";
  return `${headerBar("Добавить рейс", true)}
    <p class="ut-ctx">К поездке ${esc(trip.origin || "Москва")} → ${esc(trip.destination)}, ${esc(formatStay(trip.depart, trip.ret))}</p>
    <div data-slot="flight-add">${rows}</div>
    <button type="button" class="ut-more" data-shell="flight-add-row">+ Ещё рейс</button>
    <button type="button" class="ut-primary ut-save${idle}" data-shell="flight-save" aria-disabled="${assessed.canSave ? "false" : "true"}">Добавить к поездке</button>`;
}

function paymentView(item) {
  return presentPayment(item);
}

function renderPay(state) {
  const stored = Array.isArray(state.payments) ? state.payments : [];
  const filtered = sortPayments(filterPayments(stored, state.payFilter), state.paySort);
  const groups = groupPayments(filtered, state.payGroup || "system");
  const chips = GROUP_MODES.map((item) => (
    `<button type="button" class="ut-chip${state.payGroup === item.id ? " is-on" : ""}" data-shell="pay-group" data-group="${item.id}" aria-pressed="${state.payGroup === item.id ? "true" : "false"}">${item.label}</button>`
  )).join("");
  const body = stored.length
    ? groups.map((group) => {
      const rows = group.items.map((item, index) => payRow(state, item, index)).join("");
      return `<p class="ut-group-label">${esc(group.title)}</p><div class="ut-panel">${rows}</div>`;
    }).join("")
    : `<p class="ut-group-label">Сохранённые способы</p><div class="ut-panel"><p class="ut-pay-empty">Пока нет сохранённых способов. Добавьте карту, платёжное приложение или наличные — без номеров и сроков.</p></div>`;
  const emptyFilter = stored.length && !filtered.length
    ? `<p class="ut-fine">Нет способов в этом фильтре.</p>`
    : "";
  return `${headerBar("Мои способы оплаты", true)}
    <div data-slot="pay">
      <p class="ut-lead">Добавьте в общих чертах, чем вы пользуетесь: карты, платёжные приложения и наличные. Для выбранной страны покажем, какие из ваших способов, по нашим данным, подходят для оплаты и снятия наличных.</p>
      <p class="ut-note">Номера карт и другие платёжные реквизиты не нужны.</p>
      <p class="ut-label">Группировать</p>
      <div class="ut-chips">${chips}</div>
      <div class="ut-tools">
        <button type="button" data-shell="pay-filter">Фильтр · ${esc(modeLabel(FILTER_MODES, state.payFilter))} ▾</button>
        <button type="button" data-shell="pay-sort">Сортировка · ${esc(modeLabel(SORT_MODES, state.paySort))} ▾</button>
      </div>
      ${body}
      ${emptyFilter}
      <button type="button" class="ut-secondary" data-shell="route" data-path="/pay/add">+ Добавить способ оплаты</button>
      <p class="ut-fine ut-foot">Название — до 30 символов. Имеющиеся сведения не гарантируют приём везде.</p>
    </div>`;
}

function payRow(state, item, index) {
  const view = presentPayment(item);
  const id = item.id || `idx-${index}`;
  const open = state.payOpenId === id;
  const bank = open && item.bank ? `<p class="ut-mini">Ваша пометка: ${esc(item.bank)}</p>` : "";
  const full = open ? `<p class="ut-sub">${esc(view.detail)}</p>${bank}<button type="button" class="ut-flight-del" data-shell="pay-delete" data-id="${esc(id)}">Удалить</button>` : "";
  return `<div class="ut-pay-item${open ? " is-open" : ""}">
    <button type="button" class="ut-pay-open" data-shell="pay-open" data-id="${esc(id)}">
      <b>${esc(view.title)}</b>
      ${open ? "" : `<span>${esc(view.detail)}</span>`}
    </button>
    ${full}
  </div>`;
}

function renderGuide(state) {
  const query = state.query || "";
  const airlines = matches(query, "Авиакомпании и мили") ? row("✈️ Авиакомпании и мили", "Программы лояльности и кто летает", "/guide/airlines") : "";
  const regions = GUIDE_REGIONS.map((region) => {
    const items = region.items.filter((item) => matches(query, `${item.name} ${item.note || ""} ${region.title}`));
    if (query && !items.length && !matches(query, region.title)) return "";
    if (query && !items.length) return "";
    const body = items.map((item) => {
      const dot = `<i class="ut-dot ut-dot-${item.zone === "red" ? "red" : item.zone === "green" ? "green" : "yellow"}"></i>`;
      const note = item.note ? `<span class="ut-row-text">${esc(item.note)}</span>` : "";
      return `<button type="button" class="ut-row" data-shell="route" data-path="/guide/${item.slug}">
        <span><span class="ut-row-title">${item.flag} ${esc(item.name)}${dot}</span>${note}</span>
        <span class="ut-chev" aria-hidden="true">›</span>
      </button>`;
    }).join("");
    const open = region.open ? " open" : "";
    return `<details class="ut-fold"${open}>
      <summary><span>${esc(region.title)}</span><span class="ut-twist" aria-hidden="true"></span></summary>
      ${body}
    </details>`;
  }).join("");
  const empty = query && !airlines && !regions.trim()
    ? `<p class="ut-muted ut-pad">Ничего не нашли. Попробуйте другую страну или тему.</p>`
    : "";
  return `${headerBar("Справочник", false)}
    ${searchField("Страна, город или тема", query)}
    ${legend()}
    <div data-slot="guide">${airlines}${regions}${empty}</div>`;
}

function renderCountry(state) {
  const slug = safeSlug(state.route.slug);
  const title = COUNTRY_TITLES[slug] || "Страна";
  const matchPath = slug ? `/guide/${slug}/pay` : "/pay";
  return `${headerBar(title, true)}
    <section class="ut-slot" data-slot="country" data-slug="${esc(slug)}">
      ${legend()}
      <p class="ut-lead">Здесь появятся въезд, оплата, связь и транспорт. Сведения покажем с датой и годом.</p>
      <h2 class="ut-block-title">Подойдут ли ваши способы оплаты?</h2>
      <p class="ut-sub">Сопоставьте сохранённые способы с выбранной страной.</p>
      <button type="button" class="ut-primary ut-inline-btn" data-shell="route" data-path="${esc(matchPath)}">Сверить с моими способами</button>
    </section>`;
}

function renderCountryPay(state) {
  const slug = safeSlug(state.route.slug);
  const title = COUNTRY_TITLES[slug] || "Страна";
  const payments = Array.isArray(state.payments) ? state.payments : [];
  const guide = PAYMENT_CATALOG[slug] || null;
  const when = guide ? `по сведениям на ${formatDotDate(guide.checked)}` : "Сведений по оплате для этой страны пока нет. Статус — не сверено.";
  const backTo = `/guide/${slug}/pay`;
  if (!payments.length) {
    return `${headerBar(title, true)}
      <div data-slot="country-pay" data-slug="${esc(slug)}">
        <section class="ut-seg">
          <h2>Мои способы оплаты</h2>
          <p class="ut-sub">Добавьте свои способы оплаты — покажем, какие из них, по нашим данным, можно использовать в этой стране. Без номеров карт и платёжных реквизитов.</p>
          <button type="button" class="ut-primary ut-inline-btn" data-shell="pay-add-return" data-return="${esc(backTo)}">Добавить способы оплаты</button>
          <p class="ut-note ut-note-tight">После сохранения — возврат к сравнению с этой страной. Опыт можно пропустить.</p>
        </section>
        <p class="ut-fine ut-foot">Имеющиеся сведения не подтверждают приём везде.</p>
      </div>`;
  }
  const rows = payments.map((item) => {
    const view = presentPayment(item);
    const channels = matchMethod(item, slug);
    const lines = MATCH_CHANNELS.map(([id, label]) => {
      const status = channels[id];
      return `<div class="ut-match-row"><span>${label}</span><span class="ut-st"><i class="ut-dot ut-dot-${matchDot(status)}"></i>${esc(MATCH_LABELS[status] || MATCH_LABELS.unverified)}</span></div>`;
    }).join("");
    return `<h3 class="ut-match-name">${esc(view.title)}</h3>${lines}`;
  }).join(`<div class="ut-divider"></div>`);
  return `${headerBar(title, true)}
    <div data-slot="country-pay" data-slug="${esc(slug)}">
      <section class="ut-seg">
        <h2>Мои способы в этой стране</h2>
        <p class="ut-hintline">${esc(when)}</p>
        <div class="ut-divider"></div>
        ${rows}
        <p class="ut-note ut-note-tight">${esc(CHINA_GUIDE.disclaimer)}</p>
      </section>
      <p class="ut-fine ut-foot">Имеющиеся сведения не подтверждают приём везде.</p>
    </div>`;
}

function payFormState(state) {
  return {
    kind: "card",
    system: "",
    systemCustom: "",
    country: "",
    countryIso: "",
    countryQuery: "",
    bank: "",
    title: "",
    format: "physical",
    consent: false,
    errors: {},
    ...(state.payDraft || {}),
  };
}

function chipButton(action, id, label, on, extra) {
  const attrs = extra || "";
  return `<button type="button" class="ut-chip${on ? " is-on" : ""}" data-shell="${action}" data-id="${esc(id)}" aria-pressed="${on ? "true" : "false"}"${attrs}>${label}</button>`;
}

function renderPayAdd(state) {
  const values = payFormState(state);
  const errors = values.errors || {};
  const systems = systemsForKind(values.kind);
  const systemChips = systems.map((id) => chipButton(
    "pay-system",
    id,
    esc(id === "other" ? "Другая" : systemLabel(id)),
    values.system === id,
  )).join("");
  const kinds = PAYMENT_KINDS.map((item) => chipButton("pay-kind", item.id, esc(item.label), values.kind === item.id)).join("");
  const formats = values.kind === "card"
    ? `<p class="ut-label">Формат карты</p><div class="ut-chips">${CARD_FORMATS.map((item) => chipButton("pay-format", item.id, esc(item.label), values.format === item.id)).join("")}</div>${fieldError(errors, "format")}`
    : "";
  const custom = values.system === "other"
    ? `<label>Название платёжной системы<input name="systemCustom" maxlength="40" autocomplete="off" value="${esc(values.systemCustom || "")}" class="${badClass(errors, "system").trim()}"></label>`
    : `<input type="hidden" name="systemCustom" value="">`;
  const query = values.countryQuery || "";
  const suggestions = searchCountries(query).filter((item) => item.name !== values.country || query !== values.country);
  const suggestHtml = suggestions.map((item) => (
    `<button type="button" class="ut-suggest" data-shell="pay-country" data-country="${esc(item.name)}" data-iso="${esc(item.iso)}">+ ${countryFlag(item.iso)} ${esc(item.name)}</button>`
  )).join("");
  const customCountry = query.trim().length >= 2 && !COUNTRIES.some((item) => item.name.toLowerCase() === query.trim().toLowerCase())
    ? `<button type="button" class="ut-suggest" data-shell="pay-country" data-country="${esc(query.trim())}" data-iso="">Использовать «${esc(query.trim())}»</button>`
    : "";
  const count = [...String(values.title || "")].length;
  const consent = state.settings && state.settings.consentAt
    ? ""
    : `<label class="ut-check"><input type="checkbox" name="consent"${values.consent ? " checked" : ""}><span>Соглашаюсь хранить эти сведения только на этом устройстве. На сервер их не отправляем.</span></label>${fieldError(errors, "consent")}`;
  return `${headerBar("Добавить способ", true)}
    <p class="ut-step">1 · В ОБЩИХ ЧЕРТАХ</p>
    <form class="ut-form" data-shell-form="pay-add" data-slot="pay-add">
      <input type="hidden" name="kind" value="${esc(values.kind)}">
      <input type="hidden" name="system" value="${esc(values.system)}">
      <input type="hidden" name="format" value="${esc(values.format)}">
      <input type="hidden" name="country" value="${esc(values.country)}">
      <input type="hidden" name="countryIso" value="${esc(values.countryIso)}">
      <p class="ut-label">Тип</p>
      <div class="ut-chips">${kinds}</div>
      ${fieldError(errors, "kind")}
      <p class="ut-label">Платёжная система</p>
      <div class="ut-chips">${systemChips}</div>
      ${fieldError(errors, "system")}
      ${custom}
      <label>Страна выпуска${values.kind === "card" ? " <span class=\"ut-req\">*</span>" : ""}
        <input name="countryQuery" data-shell-field="pay-country" maxlength="60" autocomplete="off" placeholder="Любая страна · поиск" value="${esc(query)}" class="${badClass(errors, "country").trim()}">
      </label>
      ${suggestHtml}${customCountry}
      ${values.country ? `<p class="ut-mini">Выбрано: ${esc(values.country)}</p>` : ""}
      ${fieldError(errors, "country")}
      <label>Банк · необязательно<input name="bank" maxlength="40" autocomplete="off" placeholder="Название банка" value="${esc(values.bank || "")}"></label>
      <p class="ut-hintline">Личная пометка. В сведениях о стране банк не показываем.</p>
      <label>Своё название · необязательно<input name="title" data-shell-field="pay-title" maxlength="40" autocomplete="off" placeholder="Основная карта для путешествий" value="${esc(values.title || "")}" class="${badClass(errors, "title").trim()}"></label>
      <p class="ut-count${count > 30 ? " is-bad" : ""}">${count} / 30</p>
      ${fieldError(errors, "title")}
      <p class="ut-hintline">До 30 символов. В списке — максимум две строки; полное название — при открытии способа.</p>
      ${formats}
      <p class="ut-note ut-note-tight">Номер карты, срок действия и CVV не нужны.</p>
      ${consent}
      <button type="submit" class="ut-primary">Сохранить способ</button>
    </form>
    <p class="ut-fine ut-foot">Способ сохраняется независимо от того, поделитесь ли вы опытом. Если пришли из сравнения со страной — вернём к сравнению после сохранения.</p>`;
}

function experienceDraft(state) {
  return {
    countries: [],
    query: "",
    channels: [],
    result: "",
    when: "",
    ...(state.payExperienceDraft || {}),
  };
}

function renderPayExperience(state) {
  const draft = experienceDraft(state);
  const open = Boolean(state.experienceOpen);
  const picked = (draft.countries || []).map((name) => (
    `<button type="button" class="ut-chip is-on" data-shell="experience-country-remove" data-country="${esc(name)}">${esc(name)} ×</button>`
  )).join("");
  const suggestions = searchCountries(draft.query).filter((item) => !(draft.countries || []).includes(item.name));
  const suggestHtml = suggestions.map((item) => (
    `<button type="button" class="ut-suggest" data-shell="experience-country" data-country="${esc(item.name)}">+ ${esc(item.name)}</button>`
  )).join("");
  const custom = draft.query && draft.query.trim().length >= 2 && !suggestions.some((item) => item.name.toLowerCase() === draft.query.trim().toLowerCase())
    ? `<button type="button" class="ut-suggest" data-shell="experience-country" data-country="${esc(draft.query.trim())}">+ ${esc(draft.query.trim())}</button>`
    : "";
  const usage = [
    ["shops", "Магазины"],
    ["online", "Онлайн"],
    ["atm", "Банкоматы"],
  ].map(([id, label]) => chipButton("experience-channel", id, esc(label), (draft.channels || []).includes(id))).join("");
  const result = [["ok", "Получилось"], ["fail", "Не получилось"]].map(([id, label]) => (
    chipButton("experience-result", id, esc(label), draft.result === id)
  )).join("");
  const when = [["trip", "В этой поездке"], ["earlier", "Раньше"]].map(([id, label]) => (
    chipButton("experience-when", id, esc(label), draft.when === id)
  )).join("");
  const form = open
    ? `<section class="ut-seg">
        <h2>Где использовали?</h2>
        <p class="ut-hintline">Поиск по всем странам, не только из справочника.</p>
        <div class="ut-chips">${picked}</div>
        <form class="ut-form" data-shell-form="pay-experience" data-slot="pay-experience">
          <label>Страны · автодополнение<input name="countryQuery" data-shell-field="pay-exp-country" maxlength="60" autocomplete="off" value="${esc(draft.query || "")}"></label>
          ${suggestHtml}${custom}
          <label>Личный комментарий · необязательно<input name="comment" maxlength="200" autocomplete="off" placeholder="Например: ЕС / СНГ / Азия" value="${esc(draft.comment || "")}"></label>
          <p class="ut-hintline">Ваш комментарий, не подтверждение работы во всём регионе.</p>
          <p class="ut-label">Как использовали</p>
          <div class="ut-chips">${usage}</div>
          <p class="ut-label">Результат</p>
          <div class="ut-chips">${result}</div>
          <p class="ut-label">Когда · можно не указывать</p>
          <div class="ut-chips">${when}</div>
          <p class="ut-note ut-note-tight">Если результаты по странам различаются — отдельные сообщения. Опыт не подтверждает приём по всей стране.</p>
          <button type="submit" class="ut-primary">Поделиться опытом</button>
        </form>
        <button type="button" class="ut-skip" data-shell="experience-skip">Пропустить · способ сохранён</button>
      </section>`
    : "";
  return `${headerBar("Способ сохранён", true)}
    <p class="ut-step">2 · ТОЛЬКО ПО ЖЕЛАНИЮ</p>
    <section class="ut-seg ut-okbox" data-slot="pay-experience-prompt">
      <h2>Поделиться опытом?</h2>
      <p class="ut-sub">Способ уже сохранён.</p>
      <button type="button" class="ut-primary ut-inline-btn" data-shell="experience-open">Поделиться опытом</button>
      <button type="button" class="ut-skip" data-shell="experience-skip">Пропустить</button>
    </section>
    ${form}`;
}

function passportLine(passport) {
  const citizenship = passport.citizenship || "РФ";
  const till = formatDotDate(passport.expires);
  const tail = till ? ` · до ${till}` : "";
  return `Гражданство ${esc(citizenship)}${tail} · для правил въезда`;
}

function paymentSummary(payments) {
  return payments.map((item) => esc(paymentView(item).title)).filter(Boolean).join(" · ");
}

function renderProfile(state) {
  const passport = state.passport;
  const payments = Array.isArray(state.payments) ? state.payments : [];
  const loyalty = Array.isArray(state.loyalty) ? state.loyalty : [];
  const passportRow = passport
    ? row("🛂 Паспорт", passportLine(passport), "/passport")
    : row("🛂 Добавить паспорт", "При добавлении коротко спросим согласие на хранение", "/passport", "ut-hint");
  const payRow = payments.length
    ? row("💳 Мои способы оплаты", paymentSummary(payments), "/pay")
    : row("💳 Добавить способы оплаты", "При добавлении коротко спросим согласие на хранение", "/pay", "ut-hint");
  const loyaltyRow = loyalty.length
    ? row("✈️ Кошелёк миль", `${esc(cardsWord(loyalty.length))} · номера ваших программ`, "/loyalty")
    : row("✈️ Добавить номера программ", "При добавлении коротко спросим согласие на хранение", "/loyalty", "ut-hint");
  return `${headerBar("Профиль", false)}
    <div data-slot="profile">
      <button type="button" class="ut-replay" data-shell="soon" data-text="Короткий обзор возможностей подключим следующим шагом.">Посмотреть возможности</button>
      ${passportRow}
      ${payRow}
      ${row("📄 Отправлено в чат", "Китай от 1 ноября 2026 · прислать свежую версию", "/chat")}
      ${row("🧳 Мои поездки", "Оставить отзыв о памятке", "/trips", "ut-linkish-text")}
      ${loyaltyRow}
      ${passport
        ? row("🏆 Достижения", "Отзывы и находки — когда захотите", "/achievements")
        : row("🏆 Достижения", "Отзывы и находки — когда захотите. Часть наград пока недоступна без данных профиля", "/achievements", "ut-hint")}
      ${row("⚙️ Настройки", "Язык, валюта, уведомления", "/settings")}
    </div>`;
}

function renderSettings(state) {
  const consent = formatDotDate(state.settings.consentAt);
  const status = consent ? `Согласие дано ${esc(consent)}` : "Согласие ещё не дано";
  const setting = (title, value, key) => {
    const toggle = key === "theme" || key === "notifications";
    const on = key === "theme" ? value === "Тёмная" : value !== "Выключены";
    const mark = toggle
      ? `<span class="ut-switch${on ? " is-on" : ""}" aria-hidden="true"></span>`
      : `<span class="ut-chev" aria-hidden="true">›</span>`;
    const pressed = toggle ? ` aria-pressed="${on ? "true" : "false"}"` : "";
    return `<button type="button" class="ut-row" data-shell="setting" data-key="${esc(key)}"${pressed}>
      <span><span class="ut-row-title">${title}</span><span class="ut-row-text">${esc(value)}</span></span>
      ${mark}
    </button>`;
  };
  return `${headerBar("Настройки", true)}
    <div data-slot="settings">
      ${setting("🌐 Язык", state.settings.language, "language")}
      ${setting("💱 Валюта подсказок", state.settings.currency, "currency")}
      ${setting("🎨 Тема оформления", state.settings.theme, "theme")}
      ${setting("🔔 Уведомления", state.settings.notifications, "notifications")}
      ${row("📄 Отправлено в чат", "Китай от 1 ноября 2026 · прислать свежую версию", "/chat")}
      <section class="ut-privacy">
        <p class="ut-row-text">${status}</p>
        <button type="button" class="ut-privacy-btn" data-shell="revoke">Отозвать согласие</button>
        <p class="ut-hint">Отзыв остановит хранение и использование паспорта, способов оплаты и номеров программ. Поездки и памятки останутся. «Удалить мои данные» стирает всё.</p>
        <button type="button" class="ut-privacy-btn ut-danger" data-shell="delete">🗑 Удалить мои данные</button>
      </section>
    </div>`;
}

function renderFrame(title, slot, text) {
  return `${headerBar(title, true)}
    <section class="ut-slot" data-slot="${esc(slot)}"><p class="ut-lead">${text}</p></section>`;
}

function renderTrips(state) {
  const items = (state.trips || []).map((trip) => (
    `<button type="button" class="ut-row" data-shell="route" data-path="/trip">
      <span><span class="ut-row-title">${esc(trip.origin || "Москва")} → ${esc(trip.destination)}</span>
      <span class="ut-row-text">${esc(formatStay(trip.depart, trip.ret))}</span></span>
      <span class="ut-chev" aria-hidden="true">›</span>
    </button>`
  )).join("");
  const body = items || `<p class="ut-lead">Пока нет сохранённых поездок. Добавьте направление в разделе «Поездка».</p>`;
  return `${headerBar("Мои поездки", true)}<div data-slot="trips">${body}</div>`;
}

function fieldError(errors, key) {
  return errors && errors[key] ? `<p class="ut-err">${esc(errors[key])}</p>` : "";
}

function badClass(errors, key) {
  return errors && errors[key] ? " is-bad" : "";
}

function passportFormState(state) {
  if (state.passportDraft) return { consent: false, errors: {}, citizenshipOther: "", ...state.passportDraft };
  const saved = state.passport || {};
  const choice = citizenshipChoice(saved.citizenship || "РФ");
  return {
    citizenship: choice.choice,
    citizenshipOther: choice.other,
    given: saved.given || "",
    surname: saved.surname || "",
    number: saved.number || "",
    expires: saved.expires || "",
    consent: false,
    errors: {},
  };
}

function loyaltyFormState(state) {
  const passport = state.passport || {};
  if (state.loyaltyDraft) {
    return {
      programId: "",
      custom: "",
      number: "",
      title: "",
      given: passport.given || "",
      surname: passport.surname || "",
      note: "",
      consent: false,
      errors: {},
      ...state.loyaltyDraft,
    };
  }
  return {
    programId: "",
    custom: "",
    number: "",
    title: "",
    given: passport.given || "",
    surname: passport.surname || "",
    note: "",
    consent: false,
    errors: {},
  };
}

function renderPassport(state) {
  const values = passportFormState(state);
  const errors = values.errors || {};
  const options = CITIZENSHIPS.concat("Другое").map((item) => (
    `<option value="${esc(item)}"${values.citizenship === item ? " selected" : ""}>${esc(item)}</option>`
  )).join("");
  const other = values.citizenship === "Другое"
    ? `<label>Какое гражданство<input name="citizenshipOther" maxlength="40" autocomplete="off" value="${esc(values.citizenshipOther || "")}" class="${badClass(errors, "citizenship").trim()}"></label>${fieldError(errors, "citizenship")}`
    : `<input type="hidden" name="citizenshipOther" value="">`;
  const trip = activeTrip(state);
  const fit = !errors.expires && values.expires && trip
    ? passportFit(values.expires, trip.ret, trip.destination, formatStay(trip.depart, trip.ret))
    : null;
  const fitHtml = fit
    ? `<p class="${fit.ok ? "ut-status-ok" : "ut-warnbox"}">${esc(fit.text)}</p>`
    : "";
  const consent = state.settings && state.settings.consentAt
    ? ""
    : `<label class="ut-check"><input type="checkbox" name="consent"${values.consent ? " checked" : ""}><span>Соглашаюсь хранить эти сведения только на этом устройстве. На сервер их не отправляем.</span></label>${fieldError(errors, "consent")}`;
  const clear = state.passport
    ? `<button type="button" class="ut-flight-del ut-clear" data-shell="passport-clear">Удалить данные паспорта</button>`
    : "";
  return `${headerBar("Загранпаспорт", true)}
    <p class="ut-lead">Хранится только на этом устройстве и в Telegram. На сервер не отправляем.</p>
    <form class="ut-form" data-shell-form="passport" data-slot="passport">
      <label>Гражданство<select name="citizenship">${options}</select></label>
      ${other}
      <label>Действителен до<input name="expires" type="date" autocomplete="off" value="${esc(values.expires || "")}" class="${badClass(errors, "expires").trim()}"></label>
      ${fieldError(errors, "expires")}
      ${fitHtml}
      <label>Имя <button type="button" class="ut-inline-link" data-shell="copy-field" data-copy-from="given">Скопировать</button>
        <input name="given" data-shell-field="latin" maxlength="40" autocomplete="off" spellcheck="false" inputmode="latin" lang="en" aria-label="Имя латиницей" value="${esc(values.given || "")}" class="${badClass(errors, "given").trim()}"></label>
      ${fieldError(errors, "given")}
      <label>Фамилия <button type="button" class="ut-inline-link" data-shell="copy-field" data-copy-from="surname">Скопировать</button>
        <input name="surname" data-shell-field="latin" maxlength="40" autocomplete="off" spellcheck="false" inputmode="latin" lang="en" aria-label="Фамилия латиницей" value="${esc(values.surname || "")}" class="${badClass(errors, "surname").trim()}"></label>
      ${fieldError(errors, "surname")}
      <p class="ut-hintline">Как в загранпаспорте — подставим в карты лояльности. Только латиница.</p>
      <label>Номер и серия<input name="number" maxlength="24" autocomplete="off" placeholder="Необязательно" value="${esc(values.number || "")}" class="${badClass(errors, "number").trim()}"></label>
      ${fieldError(errors, "number")}
      <p class="ut-hintline">Необязательно. На профиле номер не показываем.</p>
      ${consent}
      <button type="submit" class="ut-primary">Сохранить</button>
    </form>
    ${clear}`;
}

function cardColor(card) {
  const known = programById(card.programId);
  return known && /^#[0-9A-Fa-f]{6}$/.test(known.color) ? known.color : "#3A4A68";
}

function cardInitials(card) {
  const known = programById(card.programId);
  if (known) return programInitials(known.iata);
  const letters = String(card.program || card.airline || "").replace(/[^A-Za-zА-Яа-яЁё]/g, "");
  return (letters.slice(0, 2) || "??").toUpperCase();
}

function renderWallet(state) {
  const cards = Array.isArray(state.loyalty) ? state.loyalty : [];
  let openId = state.loyaltyOpenId || "";
  if (!openId && cards.length) openId = cards[cards.length - 1].id;
  if (openId === "none") openId = "";
  const items = cards.map((card) => walletCard(state, card, card.id === openId)).join("");
  const empty = cards.length
    ? ""
    : `<p class="ut-lead">Пока нет карт. Добавьте программу — номер останется только на этом устройстве.</p>`;
  return `${headerBar("Кошелёк миль", true)}
    <p class="ut-wallet-hint">Одна карта на альянс: мили партнёров на неё. <button type="button" class="ut-inline-link" data-shell="route" data-path="/guide/airlines">Что такое альянс</button></p>
    <div data-slot="loyalty">${empty}<div class="ut-wstack">${items}</div></div>
    <button type="button" class="ut-primary ut-save" data-shell="route" data-path="/loyalty/add">Добавить программу</button>
    <p class="ut-lead">Доплаты на сайте авиакомпании могут требовать зарубежную карту — проверьте заранее.</p>`;
}

function walletCard(state, card, open) {
  const zone = card.zone === "green" ? "green" : "yellow";
  const mask = maskCard(card.number);
  const full = bookingName(card.given, card.surname, state.settings && state.settings.nameOrder);
  const names = full
    ? `<div class="ut-book">
        <p class="ut-book-title">Имя для бронирования</p>
        <p>Имя: ${esc(card.given || "")} <button type="button" class="ut-inline-link" data-shell="copy-name" data-id="${esc(card.id)}" data-part="given">Скопировать</button></p>
        <p>Фамилия: ${esc(card.surname || "")} <button type="button" class="ut-inline-link" data-shell="copy-name" data-id="${esc(card.id)}" data-part="surname">Скопировать</button></p>
        <p>Полностью: ${esc(full)} <button type="button" class="ut-inline-link" data-shell="name-order">Сменить порядок</button> <button type="button" class="ut-inline-link" data-shell="copy-name" data-id="${esc(card.id)}" data-part="full">Скопировать</button></p>
      </div>`
    : "";
  const warn = cardLooksTypical(card.number)
    ? ""
    : `<div class="ut-warnbox">Номер не похож на типовой для этой программы — проверьте. <button type="button" class="ut-inline-link" data-shell="loyalty-edit" data-id="${esc(card.id)}">Изменить</button></div>`;
  const note = card.note ? `<p class="ut-card-note">${esc(card.note)}</p>` : "";
  const body = open
    ? `<div class="ut-wcard-body">
        <p class="ut-mask">${esc(mask)}</p>
        ${names}
        ${note}
        ${warn}
        <div class="ut-wactions">
          <button type="button" class="ut-ghost" data-shell="copy-card" data-id="${esc(card.id)}">Скопировать номер</button>
          <button type="button" class="ut-flight-del" data-shell="loyalty-delete" data-id="${esc(card.id)}">Удалить</button>
        </div>
      </div>`
    : "";
  const peek = open ? "" : `<span class="ut-peek">${esc(mask)}</span>`;
  return `<article class="ut-wcard${open ? " is-open" : ""}" style="--ut-card:${cardColor(card)}">
    <button type="button" class="ut-wcard-toggle" data-shell="loyalty-open" data-id="${esc(card.id)}">
      <span class="ut-ini">${esc(cardInitials(card))}</span>
      <span class="ut-wcard-copy"><b>${esc(card.title || card.program || "Программа")}</b><span class="ut-al">${esc(allianceLabel(card.allianceId))} <i class="ut-dot ut-dot-${zone}" title="${zone === "green" ? "официальный источник" : "ещё не сверено"}"></i></span></span>
      ${peek}
    </button>
    ${body}
  </article>`;
}

function renderLoyaltyAdd(state) {
  const values = loyaltyFormState(state);
  const errors = values.errors || {};
  const editing = Boolean(state.editingId);
  const options = [`<option value=""${values.programId ? "" : " selected"}>Выберите программу</option>`]
    .concat(LOYALTY_PROGRAMS.map((item) => (
      `<option value="${esc(item.id)}"${values.programId === item.id ? " selected" : ""}>${esc(item.program)} · ${esc(item.airline)}</option>`
    )))
    .concat(`<option value="custom"${values.programId === "custom" ? " selected" : ""}>Своя программа</option>`)
    .join("");
  const custom = values.programId === "custom"
    ? `<label>Название своей программы <span class="ut-req">*</span><input name="custom" maxlength="60" autocomplete="off" value="${esc(values.custom || "")}" class="${badClass(errors, "custom").trim()}"></label>${fieldError(errors, "custom")}`
    : `<input type="hidden" name="custom" value="">`;
  const passport = state.passport || {};
  const fromPassport = (passport.given || passport.surname) && values.given === (passport.given || "") && values.surname === (passport.surname || "");
  const from = fromPassport ? `<p class="ut-mini">Подставлено из паспорта</p>` : "";
  const consent = state.settings && state.settings.consentAt
    ? ""
    : `<label class="ut-check"><input type="checkbox" name="consent"${values.consent ? " checked" : ""}><span>Соглашаюсь хранить номер карты только на этом устройстве. На сервер его не отправляем.</span></label>${fieldError(errors, "consent")}`;
  return `${headerBar(editing ? "Изменить программу" : "Добавить программу", true)}
    <form class="ut-form" data-shell-form="loyalty-add" data-slot="loyalty-add">
      <label>Программа <span class="ut-req">*</span><select name="programId" class="${badClass(errors, "program").trim()}">${options}</select></label>
      ${fieldError(errors, "program")}
      ${custom}
      <label>Номер карты <span class="ut-req">*</span><input name="number" maxlength="24" autocomplete="off" inputmode="text" placeholder="Введите номер полностью" value="${esc(values.number || "")}" class="${badClass(errors, "number").trim()}"></label>
      ${fieldError(errors, "number")}
      <p class="ut-hintline">Обязательное поле. Номер хранится целиком только у вас, чтобы его можно было скопировать.</p>
      <label>Название карты<input name="title" maxlength="40" autocomplete="off" placeholder="Если пусто — возьмём название программы" value="${esc(values.title || "")}"></label>
      <label>Статус или заметка<input name="note" maxlength="80" autocomplete="off" placeholder="Необязательно" value="${esc(values.note || "")}"></label>
      <div class="ut-cols">
        <label>Имя<input name="given" data-shell-field="latin" maxlength="40" autocomplete="off" spellcheck="false" inputmode="latin" lang="en" aria-label="Имя латиницей" value="${esc(values.given || "")}" class="${badClass(errors, "given").trim()}"></label>
        <label>Фамилия<input name="surname" data-shell-field="latin" maxlength="40" autocomplete="off" spellcheck="false" inputmode="latin" lang="en" aria-label="Фамилия латиницей" value="${esc(values.surname || "")}" class="${badClass(errors, "surname").trim()}"></label>
      </div>
      ${fieldError(errors, "given")}${fieldError(errors, "surname")}
      ${from}
      <p class="ut-hintline">Должно совпадать с именем в программе и в билете. Только латиница, как в загранпаспорте.</p>
      ${consent}
      <button type="submit" class="ut-primary">${editing ? "Сохранить" : "Добавить"}</button>
    </form>`;
}

function loyaltyHead(item) {
  const zone = item.zone === "green" ? "green" : "yellow";
  const tag = item.tag ? `<span class="ut-ytag">${esc(item.tag)}</span>` : "";
  const meaning = zone === "green" ? "официальный источник" : "ещё не сверено";
  return `<span class="ut-ini" style="background:${esc(item.color)}">${esc(programInitials(item.iata))}</span>
    <span class="ut-ref-copy"><b>${esc(item.airline)} <i class="ut-dot ut-dot-${zone}" title="${meaning}"></i></b><span>${esc(item.program)}</span>${tag}</span>`;
}

function renderLoyaltyRef(state) {
  const query = state.query || "";
  const alliance = state.alliance || "";
  const chips = [
    ["star", "Star Alliance"],
    ["sky", "SkyTeam"],
    ["one", "oneworld"],
    ["out", "Вне альянсов"],
  ].map(([id, label]) => {
    const on = alliance === id;
    return `<button type="button" class="ut-chip${on ? " is-on" : ""}" data-shell="alliance" data-id="${id}" aria-pressed="${on ? "true" : "false"}">${label}</button>`;
  }).join("");
  const hits = filterLoyalty(query, alliance);
  let body = "";
  if (query.trim()) {
    body = hits.length
      ? hits.map((item) => {
        const allied = item.allianceId === "star" || item.allianceId === "sky" || item.allianceId === "one";
        const members = allianceMembers(item.allianceId).join(", ");
        const claim = allied
          ? `<p class="ut-claim">Мили за перелёт можно копить на любую карту этого альянса</p><p>В наших данных в ${esc(allianceLabel(item.allianceId))}: ${esc(members)}. Начисление по тарифу не сверено — уточните в правилах программы.</p>`
          : `<p>Вне альянсов. Общей договорённости о милях в наших данных нет.</p>`;
        return `<article class="ut-result"><div class="ut-ref-row">${loyaltyHead(item)}<span class="ut-tag">${esc(allianceLabel(item.allianceId))}</span></div>${claim}<p>Сведения на ${esc(formatDotDate(LOYALTY_CHECKED))}</p></article>`;
      }).join("")
      : `<p class="ut-lead">Ничего не нашли. Проверьте название авиакомпании, программы или альянса.</p>`;
  } else {
    body = ["star", "sky", "one", "out"].map((id) => {
      if (alliance && alliance !== id) return "";
      const items = filterLoyalty("", id);
      if (!items.length) return "";
      return `<h2 class="ut-group">${esc(allianceLabel(id))}</h2><div class="ut-ref-list">${items.map((item) => `<div class="ut-ref-row">${loyaltyHead(item)}</div>`).join("")}</div>`;
    }).join("");
  }
  return `${headerBar("Авиакомпании и мили", true)}
    ${searchField("Авиакомпания или программа", query)}
    <div class="ut-chips">${chips}</div>
    <details class="ut-fold">
      <summary><span>Что такое альянс</span><span class="ut-twist" aria-hidden="true"></span></summary>
      <p class="ut-lead">Альянс — договорённость авиакомпаний о совместных полётах и милях. По нашим данным, мили за рейс участника часто можно начислить на карту любой программы этого альянса. Начисление зависит от тарифа; в альянс включаем только компании из наших сведений.</p>
    </details>
    ${legend()}
    <p class="ut-date">Справочник по данным на ${esc(formatDotDate(LOYALTY_CHECKED))}</p>
    <div data-slot="loyalty-ref">${body}</div>`;
}

function renderScreen(state) {
  const name = state.route.name;
  if (name === "home") return renderHome(state);
  if (name === "trip") return renderTrip(state);
  if (name === "flight-add") return renderFlightAdd(state);
  if (name === "trip-edit") return renderTripEdit(state);
  if (name === "trip-checklist") return renderChecklist(state);
  if (name === "trip-pay") return renderTripPay(state);
  if (name === "trip-transport") return renderTripTransport(state);
  if (name === "pay") return renderPay(state);
  if (name === "pay-add") return renderPayAdd(state);
  if (name === "pay-experience") return renderPayExperience(state);
  if (name === "country-pay") return renderCountryPay(state);
  if (name === "guide") return renderGuide(state);
  if (name === "country") return renderCountry(state);
  if (name === "profile") return renderProfile(state);
  if (name === "settings") return renderSettings(state);
  if (name === "trips") return renderTrips(state);
  if (name === "passport") return renderPassport(state);
  if (name === "loyalty") return renderWallet(state);
  if (name === "loyalty-add") return renderLoyaltyAdd(state);
  if (name === "loyalty-ref") return renderLoyaltyRef(state);
  if (name === "chat") {
    return renderFrame("Отправлено в чат", "chat", "Китай от 1 ноября 2026. Свежую версию памятки пришлём в чат следующим шагом.");
  }
  if (name === "achievements") {
    return renderFrame("Достижения", "achievements", "Отзывы и находки появятся здесь, когда вы захотите их добавить.");
  }
  return renderHome(state);
}

function renderNav(state) {
  const buttons = NAV.map(([id, path, label, paths]) => {
    const on = state.route.tab === id;
    return `<button type="button" class="ut-nav-btn${on ? " is-on" : ""}" data-shell="route" data-path="${path}"${on ? ` aria-current="page"` : ""}>
      ${icon(paths)}<span>${label}</span>
    </button>`;
  }).join("");
  return `<nav class="ut-nav" aria-label="Разделы">${buttons}</nav>`;
}

function renderSupport(state) {
  if (state.supportOpen || state.sheet) return "";
  return `<button type="button" class="ut-support" data-shell="support" aria-label="Поддержка"><span class="ut-support-mark">?</span></button>`;
}

function renderToast(state) {
  if (!state.supportOpen || state.sheet) return "";
  const sub = state.supportReported
    ? "Черновик обращения остаётся на вашем устройстве."
    : "Что-то не так на экране?";
  return `<div class="ut-toast" role="status">
    <span class="ut-toast-shot" aria-hidden="true"></span>
    <span class="ut-toast-copy"><b>Скриншот сохранён</b><span>${sub}</span></span>
    <button type="button" class="ut-toast-go" data-shell="support-report">Сообщить о проблеме</button>
    <button type="button" class="ut-toast-x" data-shell="support-close" aria-label="Закрыть">✕</button>
  </div>`;
}

function renderSheet(state) {
  if (!state.sheet) return "";
  if (state.sheet === "sos") {
    return `<div class="ut-dim" data-shell="sheet-close"></div>
      <div class="ut-sheet" role="dialog" aria-labelledby="ut-sheet-title">
        <h2 id="ut-sheet-title">Нужна помощь</h2>
        <p>Экстренные телефоны страны покажем в справочнике. Если помощь нужна сразу, обратитесь в местные службы.</p>
        <div class="ut-sheet-btns"><button type="button" class="ut-sheet-ok" data-shell="sheet-close">Закрыть</button></div>
      </div>`;
  }
  if (state.sheet === "delete") {
    return `<div class="ut-dim" data-shell="sheet-close"></div>
      <div class="ut-sheet" role="dialog" aria-labelledby="ut-sheet-title">
        <h2 id="ut-sheet-title">Удалить данные с этого устройства?</h2>
        <p>Сотрём поездки, паспорт, способы оплаты, карты лояльности и настройки из хранилища на вашей стороне.</p>
        <div class="ut-sheet-btns">
          <button type="button" class="ut-sheet-cancel" data-shell="sheet-close">Отмена</button>
          <button type="button" class="ut-sheet-ok" data-shell="sheet-ok">Удалить</button>
        </div>
      </div>`;
  }
  return `<div class="ut-dim" data-shell="sheet-close"></div>
    <div class="ut-sheet" role="dialog" aria-labelledby="ut-sheet-title">
      <h2 id="ut-sheet-title">Отозвать согласие?</h2>
      <p>Остановим хранение и использование паспорта, способов оплаты и номеров программ. Поездки и памятки останутся. Согласие можно дать снова при добавлении этих данных.</p>
      <p class="ut-keep">Достижения и поездки сохранятся</p>
      <div class="ut-sheet-btns">
        <button type="button" class="ut-sheet-cancel" data-shell="sheet-close">Отмена</button>
        <button type="button" class="ut-sheet-ok" data-shell="sheet-ok">Отозвать</button>
      </div>
    </div>`;
}

export function renderShell(state) {
  const notice = state.notice ? `<p class="ut-notice" role="status">${esc(state.notice)}</p>` : "";
  const demoScreens = state.route.name === "home" || state.route.name === "trip";
  const demo = state.outside && demoScreens ? renderDemo(state) : "";
  return `<div class="ut-app" data-shell-screen="${esc(state.route.name)}">
    <div class="ut-bubbles" aria-hidden="true"><span></span><span></span></div>
    ${demo}
    ${notice}
    <main class="ut-main">${renderScreen(state)}</main>
    ${renderSupport(state)}
    ${renderToast(state)}
    ${renderSheet(state)}
    ${renderNav(state)}
  </div>`;
}
