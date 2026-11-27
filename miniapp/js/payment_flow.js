/** Payment methods, local experience and country match. Values stay on the device. */

import {
  countryByName,
  countryFlag,
  PAYMENT_CATALOG,
  systemLabel,
} from "./payment_catalog.js";

export const TITLE_LIMIT = 30;

export const PAYMENT_KINDS = [
  { id: "card", label: "Карта" },
  { id: "app", label: "Платёжное приложение" },
  { id: "cash", label: "Наличные" },
];

export const CARD_FORMATS = [
  { id: "physical", label: "Физическая" },
  { id: "virtual", label: "Виртуальная" },
  { id: "both", label: "Оба" },
];

export const FORMAT_DETAIL = {
  physical: "физическая",
  virtual: "виртуальная",
  both: "оба формата",
};

export const GROUP_MODES = [
  { id: "system", label: "По платёжной системе" },
  { id: "country", label: "По стране выпуска" },
  { id: "bank", label: "По банку" },
];

export const FILTER_MODES = [
  { id: "all", label: "все" },
  { id: "card", label: "карты" },
  { id: "app", label: "приложения" },
  { id: "cash", label: "наличные" },
];

export const SORT_MODES = [
  { id: "added", label: "по добавлению" },
  { id: "title", label: "по названию" },
  { id: "country", label: "по стране" },
];

export const MATCH_CHANNELS = [
  ["shops", "Магазины"],
  ["online", "Онлайн"],
  ["atm", "Банкоматы"],
];

export const MATCH_LABELS = {
  known: "есть сведения",
  partial: "работает не везде, по отзывам",
  unverified: "не сверено",
};

const FORBIDDEN_KEYS = ["number", "pan", "card", "cardNumber", "expiry", "exp", "cvv", "cvc"];

export function nextMode(list, current) {
  const index = list.findIndex((item) => item.id === current);
  const next = list[(index < 0 ? 0 : index + 1) % list.length];
  return next ? next.id : list[0].id;
}

export function modeLabel(list, id) {
  const found = list.find((item) => item.id === id);
  return found ? found.label : list[0].label;
}

function clean(value, max) {
  return String(value || "").trim().slice(0, max);
}

export function readPaymentMethod(fields, options = {}) {
  const raw = fields || {};
  const errors = {};
  const kind = PAYMENT_KINDS.some((item) => item.id === raw.kind) ? raw.kind : "";
  if (!kind) errors.kind = "Выберите тип способа.";
  let system = kind === "cash" ? "cash" : clean(raw.system, 40);
  const systemCustom = clean(raw.systemCustom, 40);
  if (!system) errors.system = "Выберите платёжную систему.";
  else if (system === "other" && !systemCustom) errors.system = "Выберите платёжную систему.";
  else if (system !== "other" && system !== "cash" && !systemLabel(system)) errors.system = "Выберите платёжную систему.";
  const titleRaw = String(raw.title || "");
  if ([...titleRaw].length > TITLE_LIMIT) errors.title = "Название — до 30 символов.";
  const country = clean(raw.country, 60);
  let countryIso = clean(raw.countryIso, 2).toUpperCase();
  if (!countryIso && country) {
    const known = countryByName(country);
    if (known) countryIso = known.iso;
  }
  if (kind === "card" && !country) errors.country = "Укажите страну выпуска.";
  const bank = clean(raw.bank, 40);
  const format = kind === "card" && CARD_FORMATS.some((item) => item.id === raw.format) ? raw.format : "";
  if (kind === "card" && !format) errors.format = "Выберите формат карты.";
  if (options.needConsent && !raw.consent) errors.consent = "Подтвердите хранение только на этом устройстве.";
  if (Object.keys(errors).length) return { errors };
  const label = system === "other" ? systemCustom : systemLabel(system);
  return {
    method: {
      kind,
      system,
      systemLabel: label,
      country,
      countryIso,
      bank,
      title: clean(titleRaw, TITLE_LIMIT) || label,
      format,
    },
  };
}

export function presentPayment(item) {
  const source = item || {};
  const title = source.title || source.systemLabel || "Способ оплаты";
  if (source.detail && !source.system) return { title, detail: source.detail };
  const bits = [];
  if (source.kind === "app") bits.push("Платёжное приложение");
  else if (source.kind === "cash") bits.push("Наличные");
  if (source.country) {
    const flag = countryFlag(source.countryIso);
    bits.push(flag ? `${flag} ${source.country}` : source.country);
  }
  if (source.kind === "card" && FORMAT_DETAIL[source.format]) bits.push(FORMAT_DETAIL[source.format]);
  return { title, detail: bits.filter(Boolean).join(" · ") };
}

function groupTitle(item, mode) {
  if (mode === "country") return item.country || "Страна не указана";
  if (mode === "bank") return item.bank || "Без пометки о банке";
  return item.systemLabel || item.title || "Платёжная система не указана";
}

export function filterPayments(items, filter) {
  const list = Array.isArray(items) ? items : [];
  if (!filter || filter === "all") return list.slice();
  return list.filter((item) => item.kind === filter);
}

export function sortPayments(items, mode) {
  const copy = (Array.isArray(items) ? items : []).slice();
  if (mode === "title") {
    copy.sort((a, b) => String(a.title || "").localeCompare(String(b.title || ""), "ru"));
  } else if (mode === "country") {
    copy.sort((a, b) => String(a.country || "").localeCompare(String(b.country || ""), "ru"));
  }
  return copy;
}

export function groupPayments(items, mode) {
  const groups = [];
  const index = new Map();
  for (const item of items || []) {
    const title = groupTitle(item, mode);
    if (!index.has(title)) {
      index.set(title, groups.length);
      groups.push({ title, items: [] });
    }
    groups[index.get(title)].items.push(item);
  }
  return groups;
}

export function joinNames(names) {
  const list = (names || []).filter(Boolean);
  if (list.length <= 1) return list[0] || "";
  return `${list.slice(0, -1).join(", ")} и ${list[list.length - 1]}`;
}

export function matchMethod(method, slug) {
  const guide = PAYMENT_CATALOG[slug] || null;
  const rules = guide ? guide.rules : [];
  const source = method || {};
  const iso = source.countryIso || (countryByName(source.country) || {}).iso || "";
  const rule = rules.find((item) => {
    if (item.system !== source.system) return false;
    if (item.kind && item.kind !== source.kind) return false;
    if (item.issuer && item.issuer !== "*" && item.issuer !== iso) return false;
    return true;
  });
  const channels = {};
  for (const [id] of MATCH_CHANNELS) {
    channels[id] = rule && rule.channels && rule.channels[id] ? rule.channels[id] : "unverified";
  }
  return channels;
}

export function matchDot(status) {
  return status === "known" ? "green" : "yellow";
}

/** Local experience only. TODO: отправка анонимного опыта на сервер — отдельная задача. */
export function readExperience(fields) {
  const raw = fields || {};
  const fromList = Array.isArray(raw.channels) ? raw.channels : [];
  const countries = Array.isArray(raw.countries)
    ? raw.countries
    : String(raw.countries || "").split("|");
  const channels = MATCH_CHANNELS.map(([id]) => id).filter((id) => fromList.includes(id) || raw[`use_${id}`]);
  const result = raw.result === "ok" || raw.result === "fail" ? raw.result : "";
  const when = raw.when === "trip" || raw.when === "earlier" ? raw.when : "";
  return {
    experience: {
      countries: countries.map((item) => clean(item, 60)).filter(Boolean).slice(0, 12),
      comment: clean(raw.comment, 200),
      channels,
      result,
      when,
    },
  };
}

export function keptPaymentKeys(method) {
  const source = method || {};
  const copy = {};
  for (const key of Object.keys(source)) {
    if (FORBIDDEN_KEYS.includes(key)) continue;
    copy[key] = source[key];
  }
  return copy;
}
