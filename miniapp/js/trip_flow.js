/** Trip checklist and flight drafts. Stored only inside the on-device trips record. */

export const TRIP_CHECKS = [
  { id: "entry", title: "Въезд" },
  { id: "docs", title: "Документы" },
  { id: "insurance", title: "Страховка" },
  { id: "pay", title: "Оплата" },
  { id: "link", title: "Связь" },
  { id: "transport", title: "Транспорт" },
];

const GUIDE_BY_NAME = {
  "китай": "china",
  "шанхай": "china",
  "пекин": "china",
  "таиланд": "thailand",
  "бангкок": "thailand",
  "турция": "turkey",
  "стамбул": "turkey",
  "оаэ": "uae",
  "дубай": "uae",
  "грузия": "georgia",
  "тбилиси": "georgia",
  "гонконг": "hong_kong",
  "россия": "russia",
};

/* One demo number and date, so the multi-leg choice is visibly an example. */
const SAMPLE_LEGS = {
  "SU 204|2026-12-12": [
    { id: "mow-kzn", from: "Москва", to: "Казань", sample: true },
    { id: "kzn-sha", from: "Казань", to: "Шанхай", sample: true },
  ],
};

const KNOWN_CHECKS = new Set(TRIP_CHECKS.map((item) => item.id));

export function tripChecks(trip) {
  if (trip && Array.isArray(trip.checks)) {
    const chosen = new Set(trip.checks.filter((id) => KNOWN_CHECKS.has(id)));
    return TRIP_CHECKS.map((item) => item.id).filter((id) => chosen.has(id));
  }
  const done = Math.max(0, Math.min(TRIP_CHECKS.length, Number(trip && trip.stepsDone) || 0));
  return TRIP_CHECKS.slice(0, done).map((item) => item.id);
}

export function checklistCaption(trip) {
  const checks = tripChecks(trip);
  const nextIndex = TRIP_CHECKS.findIndex((item) => !checks.includes(item.id));
  if (nextIndex < 0) return "Все 6 шагов отмечены";
  return `Шаг ${nextIndex + 1} из 6: ${TRIP_CHECKS[nextIndex].title.toLowerCase()}`;
}

export function applyChecks(trip, checks) {
  const ordered = tripChecks({ checks });
  return {
    ...trip,
    checks: ordered,
    stepsDone: ordered.length,
    stepsTotal: TRIP_CHECKS.length,
  };
}

export function guideSlugFor(trip) {
  if (!trip) return "";
  for (const name of [trip.country, trip.destination]) {
    const key = String(name || "").trim().toLowerCase();
    if (GUIDE_BY_NAME[key]) return GUIDE_BY_NAME[key];
  }
  return "";
}

export function normalizeFlightNumber(raw) {
  const text = String(raw || "").trim();
  if (!text) return { empty: true, valid: false, number: "" };
  const compact = text.toUpperCase().replace(/\s+/g, "");
  const match = /^([A-Z]{2})(\d{1,4}[A-Z]?)$/.exec(compact);
  if (!match) return { empty: false, valid: false, number: "" };
  return { empty: false, valid: true, number: `${match[1]} ${match[2]}` };
}

export function parseFlightDate(raw) {
  const text = String(raw || "").trim();
  if (!text) return "";
  let iso = "";
  const dotted = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(text);
  if (dotted) iso = `${dotted[3]}-${dotted[2]}-${dotted[1]}`;
  else if (/^\d{4}-\d{2}-\d{2}$/.test(text)) iso = text;
  else return "";
  const year = Number(iso.slice(0, 4));
  const month = Number(iso.slice(5, 7));
  const day = Number(iso.slice(8, 10));
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return "";
  return iso;
}

export function sampleLegsFor(number, iso) {
  const legs = SAMPLE_LEGS[`${number}|${iso}`];
  return legs ? legs.map((leg) => ({ ...leg })) : [];
}

function dateOutside(iso, trip) {
  if (!iso || !trip) return false;
  const depart = String(trip.depart || "");
  const ret = String(trip.ret || "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(depart) || !/^\d{4}-\d{2}-\d{2}$/.test(ret)) return false;
  return iso < depart || iso > ret;
}

function rowLabel(index) {
  if (index === 0) return "Туда";
  if (index === 1) return "Обратно";
  return `Рейс ${index + 1}`;
}

export function assessFlightRows(rows, trip, stayText) {
  const source = Array.isArray(rows) && rows.length
    ? rows
    : [{ number: "", date: "", legId: "" }, { number: "", date: "", legId: "" }];
  const existing = new Set(
    (trip && Array.isArray(trip.flights) ? trip.flights : []).map((item) => `${item.number}|${item.date}`),
  );
  const seen = new Set();
  let anyContent = false;
  const assessed = source.map((row, index) => {
    const numberInfo = normalizeFlightNumber(row && row.number);
    const dateRaw = String((row && row.date) || "");
    const iso = parseFlightDate(dateRaw);
    const dateTouched = dateRaw.trim() !== "";
    const content = !numberInfo.empty || dateTouched;
    if (content) anyContent = true;
    const formatError = (!numberInfo.empty && !numberInfo.valid) || (numberInfo.empty && dateTouched);
    const dateError = (numberInfo.valid && !iso) || (numberInfo.empty && dateTouched && !iso);
    const blocking = formatError || dateError;
    const legs = !blocking && numberInfo.valid && iso ? sampleLegsFor(numberInfo.number, iso) : [];
    let selectedLegId = "";
    if (legs.length) {
      const wanted = row && row.legId;
      selectedLegId = legs.some((leg) => leg.id === wanted) ? wanted : legs[0].id;
    }
    const key = `${numberInfo.number}|${iso}`;
    const duplicate = !blocking && numberInfo.valid && iso && (existing.has(key) || seen.has(key));
    if (!blocking && numberInfo.valid && iso) seen.add(key);
    return {
      index,
      label: rowLabel(index),
      numberRaw: String((row && row.number) || ""),
      dateRaw,
      number: numberInfo.number,
      iso,
      formatError,
      dateError,
      blocking,
      legs,
      selectedLegId,
      duplicate,
      outside: !blocking && dateOutside(iso, trip),
      unverified: !blocking && Boolean(numberInfo.valid && iso && !legs.length),
      empty: !content,
    };
  });
  const ready = [];
  for (const row of assessed) {
    if (row.empty || row.blocking) continue;
    const leg = row.legs.find((item) => item.id === row.selectedLegId) || null;
    ready.push({
      number: row.number,
      date: row.iso,
      from: leg ? leg.from : "",
      to: leg ? leg.to : "",
      sample: Boolean(leg && leg.sample),
      legId: leg ? leg.id : "",
    });
  }
  return {
    canSave: anyContent && assessed.every((row) => row.empty || !row.blocking) && ready.length > 0,
    rows: assessed,
    ready,
    empty: !anyContent,
    outsideText: stayText
      ? `Дата вне поездки ${stayText}. Сохранить можно.`
      : "Дата вне поездки. Сохранить можно.",
  };
}

export function flightsWord(count) {
  const n10 = count % 10;
  const n100 = count % 100;
  if (n10 === 1 && n100 !== 11) return "рейс";
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return "рейса";
  return "рейсов";
}
