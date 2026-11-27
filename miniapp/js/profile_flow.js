/** Passport and miles-wallet checks. Values stay in personal storage on the device. */

export const CITIZENSHIPS = ["РФ", "Беларусь", "Казахстан"];

const SETTING_CYCLES = {
  language: ["Русский"],
  currency: ["Рубли", "Доллары США", "Евро"],
  theme: ["Обычная", "Тёмная"],
  notifications: [
    "Изменились правила въезда · пришлём уведомление",
    "Выключены",
  ],
};

export function filterLatinInput(value) {
  return String(value || "").replace(/[^A-Za-z '\-]/g, "").toUpperCase();
}

export function todayIso(now = new Date()) {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function isIsoDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 2000 || year > 2100 || month < 1 || month > 12 || day < 1) return false;
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

function cleanLatin(value) {
  return filterLatinInput(value).replace(/\s+/g, " ").trim();
}

function latinOk(value) {
  return /^[A-Z]+(?:[ '\-][A-Z]+)*$/.test(value);
}

function readLatin(rawValue, emptyMessage) {
  const raw = String(rawValue || "");
  if (/[^A-Za-z '\-]/.test(raw)) return { error: "Только латиница, как в загранпаспорте." };
  const value = cleanLatin(raw);
  if (!value) return { error: emptyMessage };
  if (!latinOk(value)) return { error: "Только латиница, как в загранпаспорте." };
  return { value };
}

export function citizenshipChoice(value) {
  const text = String(value || "").trim();
  if (CITIZENSHIPS.includes(text)) return { choice: text, other: "" };
  if (!text) return { choice: "РФ", other: "" };
  return { choice: "Другое", other: text };
}

export function readPassport(fields, options = {}) {
  const raw = fields || {};
  const choice = String(raw.citizenship || "").trim();
  const other = String(raw.citizenshipOther || "").trim();
  const citizenship = choice === "Другое" ? other : choice;
  const givenField = readLatin(raw.given, "Укажите имя латиницей.");
  const surnameField = readLatin(raw.surname, "Укажите фамилию латиницей.");
  const given = givenField.value || "";
  const surname = surnameField.value || "";
  const number = String(raw.number || "").trim();
  const expires = String(raw.expires || "").trim();
  const errors = {};
  if (!citizenship) errors.citizenship = "Укажите гражданство.";
  else if (citizenship.length > 40) errors.citizenship = "Слишком длинное название гражданства.";
  if (givenField.error) errors.given = givenField.error;
  if (surnameField.error) errors.surname = surnameField.error;
  if (number && !/^[0-9A-Za-z][0-9A-Za-z -]{3,23}$/.test(number)) {
    errors.number = "Номер: от 4 до 24 символов, буквы и цифры.";
  }
  if (!expires) errors.expires = "Укажите дату окончания с годом.";
  else if (!isIsoDate(expires)) errors.expires = "Укажите дату окончания с годом.";
  else if (options.today && expires < options.today) errors.expires = "Срок действия уже прошёл.";
  if (options.needConsent && !raw.consent) errors.consent = "Подтвердите хранение только на этом устройстве.";
  if (Object.keys(errors).length) return { errors };
  return { passport: { citizenship, given, surname, number, expires } };
}

export function passportFit(expires, tripEnd, destination, stayText) {
  if (!isIsoDate(expires) || !isIsoDate(tripEnd)) return null;
  if (expires >= tripEnd) return { ok: true, text: `Подходит для поездки в ${destination}, ${stayText}` };
  return { ok: false, text: `Срок заканчивается раньше конца поездки (${stayText}). Сохранить можно.` };
}

export function maskCard(number) {
  const raw = String(number || "").replace(/\s+/g, "");
  if (raw.length < 4) return "";
  return `•••• ${raw.slice(-4)}`;
}

export function cardLooksTypical(number) {
  const raw = String(number || "").replace(/\s+/g, "");
  return /^[0-9]{8,16}$/.test(raw);
}

export function cardsWord(count) {
  const value = Math.abs(Number(count) || 0);
  const mod100 = value % 100;
  const mod10 = value % 10;
  if (mod100 > 10 && mod100 < 20) return `${value} карт`;
  if (mod10 === 1) return `${value} карта`;
  if (mod10 >= 2 && mod10 <= 4) return `${value} карты`;
  return `${value} карт`;
}

export function bookingName(given, surname, order) {
  const first = cleanLatin(given);
  const last = cleanLatin(surname);
  if (!first && !last) return "";
  if (order === "family") return `${last} ${first}`.trim();
  return `${first} ${last}`.trim();
}

export function cycleSetting(settings, key) {
  const list = SETTING_CYCLES[key];
  const current = { ...(settings || {}) };
  if (!list) return current;
  const index = list.indexOf(current[key]);
  const next = list[index < 0 ? 0 : (index + 1) % list.length];
  return { ...current, [key]: next };
}

export function toggleNameOrder(settings) {
  const current = { ...(settings || {}) };
  return { ...current, nameOrder: current.nameOrder === "family" ? "given" : "family" };
}

export function readLoyaltyCard(fields, options = {}) {
  const raw = fields || {};
  const programId = String(raw.programId || "").trim();
  const custom = String(raw.custom || "").trim().slice(0, 60);
  const number = String(raw.number || "").replace(/\s+/g, "");
  const title = String(raw.title || "").trim().slice(0, 40);
  const givenField = String(raw.given || "").trim() ? readLatin(raw.given, "Укажите имя латиницей.") : { value: "" };
  const surnameField = String(raw.surname || "").trim() ? readLatin(raw.surname, "Укажите фамилию латиницей.") : { value: "" };
  const given = givenField.value || "";
  const surname = surnameField.value || "";
  const note = String(raw.note || "").trim().slice(0, 80);
  const program = options.program || null;
  const errors = {};
  if (!programId) errors.program = "Выберите программу.";
  else if (programId !== "custom" && !program) errors.program = "Выберите программу из справочника.";
  if (programId === "custom" && !custom) errors.custom = "Укажите название своей программы.";
  if (!number) errors.number = "Введите номер карты полностью.";
  else if (number.length < 4 || number.length > 24 || !/^[0-9A-Za-z]+$/.test(number)) {
    errors.number = "Номер карты: от 4 до 24 букв или цифр.";
  }
  if (givenField.error) errors.given = givenField.error;
  if (surnameField.error) errors.surname = surnameField.error;
  const allianceId = program ? program.allianceId : "out";
  if (!errors.program && ["star", "sky", "one"].includes(allianceId)) {
    const clash = (options.existing || []).some((card) => card && card.allianceId === allianceId && card.id !== options.editingId);
    if (clash) errors.program = "Для этого альянса карта уже есть. Одна карта на альянс.";
  }
  if (options.needConsent && !raw.consent) errors.consent = "Подтвердите хранение только на этом устройстве.";
  if (Object.keys(errors).length) return { errors };
  const programName = program ? program.program : custom;
  return {
    card: {
      programId,
      airline: program ? program.airline : "",
      program: programName,
      allianceId,
      zone: program && program.zone === "green" ? "green" : "yellow",
      title: title || programName,
      number,
      given,
      surname,
      note,
    },
  };
}

export function revokedPersonal(current) {
  const source = current || {};
  return {
    passport: null,
    loyalty: [],
    payments: [],
    trips: Array.isArray(source.trips) ? source.trips : [],
    settings: { ...(source.settings || {}), consentAt: "" },
  };
}
