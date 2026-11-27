/** Payment facts for the Mini App. China block stays in step with database/data/countries.json.
 *  Public copy names a payment system and an issuing country only — never a bank.
 */

const COUNTRY_ROWS = `
RU Россия
BY Беларусь
KZ Казахстан
UZ Узбекистан
AZ Азербайджан
AM Армения
KG Киргизия
TJ Таджикистан
TM Туркменистан
MD Молдова
GE Грузия
CN Китай
HK Гонконг
MO Макао
TW Тайвань
JP Япония
KR Южная Корея
MN Монголия
TH Таиланд
VN Вьетнам
LA Лаос
KH Камбоджа
MM Мьянма
MY Малайзия
SG Сингапур
ID Индонезия
PH Филиппины
IN Индия
LK Шри-Ланка
NP Непал
MV Мальдивы
AE ОАЭ
SA Саудовская Аравия
QA Катар
BH Бахрейн
KW Кувейт
OM Оман
IL Израиль
JO Иордания
EG Египет
TR Турция
CY Кипр
GR Греция
DE Германия
FR Франция
IT Италия
ES Испания
PT Португалия
NL Нидерланды
BE Бельгия
LU Люксембург
CH Швейцария
AT Австрия
CZ Чехия
PL Польша
HU Венгрия
SK Словакия
SI Словения
HR Хорватия
RS Сербия
ME Черногория
BA Босния и Герцеговина
BG Болгария
RO Румыния
SE Швеция
NO Норвегия
FI Финляндия
DK Дания
IS Исландия
IE Ирландия
GB Великобритания
EE Эстония
LV Латвия
LT Литва
US США
CA Канада
MX Мексика
BR Бразилия
AR Аргентина
CL Чили
PE Перу
CO Колумбия
CU Куба
ZA ЮАР
MA Марокко
TN Тунис
KE Кения
TZ Танзания
AU Австралия
NZ Новая Зеландия
FJ Фиджи
`.trim().split("\n");

export const COUNTRIES = COUNTRY_ROWS.map((line) => ({
  iso: line.slice(0, 2),
  name: line.slice(3),
}));

export const PAYMENT_SYSTEMS = {
  visa: "Visa",
  mastercard: "Mastercard",
  mir: "Мир",
  unionpay: "UnionPay",
  alipay: "Alipay",
  wechat: "WeChat Pay",
  cash: "Наличные",
};

export const CARD_SYSTEMS = ["visa", "mastercard", "mir", "unionpay", "other"];
export const APP_SYSTEMS = ["alipay", "wechat", "other"];

/** Checked date of the China payment facts in countries.json (2026-10-13). */
export const PAYMENT_CHECKED = "2026-10-13";

export const CHINA_RULES = [
  {
    system: "unionpay",
    kind: "card",
    issuer: "RU",
    channels: { shops: "partial", online: "unverified", atm: "partial" },
  },
  {
    system: "alipay",
    kind: "app",
    issuer: "*",
    channels: { shops: "known", online: "known", atm: "unverified" },
  },
  {
    system: "wechat",
    kind: "app",
    issuer: "*",
    channels: { shops: "known", online: "known", atm: "unverified" },
  },
];

export const CHINA_GUIDE = {
  checked: PAYMENT_CHECKED,
  payChips: ["Alipay", "WeChat Pay", "Карта при терминале", "Наличные юани"],
  payText: "Обычно в приложении. Карта — если виден логотип сети. Иностранная карта может не подойти — держите запасной способ.",
  payNote: "Приём не везде. Лимиты и комиссию смотрите при оплате.",
  cashText: "В банкоматах с логотипом вашей сети можно снять наличные. Свои лимиты могут быть у банкомата и у банка-эмитента. Курс в банкомате и в обменном пункте может отличаться.",
  cashGap: "Где выгоднее менять наличные, в наших сведениях ещё не собрано.",
  backup: "Не полагайтесь на один способ: карта, приложение и немного наличных закрывают разные ситуации.",
  before: "Привяжите карту и сделайте тестовую оплату до вылета.",
  disclaimer: "Не сверено — не значит, что способ не работает. Имеющиеся сведения не гарантируют приём везде и не проверяют конкретную карту или банк.",
};

export const PAYMENT_CATALOG = {
  china: { checked: PAYMENT_CHECKED, rules: CHINA_RULES, guide: CHINA_GUIDE },
};

const PAYMENT_SECTION_KEYS = ["2_pay_on_site", "3_local_wallets_cards", "4_cash_exchange", "5_atms"];

export function countryFlag(iso) {
  const code = String(iso || "").toUpperCase();
  if (!/^[A-Z]{2}$/.test(code)) return "";
  return String.fromCodePoint(...[...code].map((char) => 127397 + char.charCodeAt(0)));
}

export function countryByName(name) {
  const needle = String(name || "").trim().toLowerCase();
  if (!needle) return null;
  if (needle === "рф") return COUNTRIES.find((item) => item.iso === "RU") || null;
  return COUNTRIES.find((item) => item.name.toLowerCase() === needle) || null;
}

export function searchCountries(query) {
  const needle = String(query || "").trim().toLowerCase();
  if (needle.length < 2) return [];
  return COUNTRIES.filter((item) => item.name.toLowerCase().includes(needle)).slice(0, 6);
}

export function systemLabel(id, custom) {
  if (id === "other") return String(custom || "").trim();
  return PAYMENT_SYSTEMS[id] || "";
}

export function systemsForKind(kind) {
  if (kind === "app") return APP_SYSTEMS;
  if (kind === "cash") return ["cash"];
  return CARD_SYSTEMS;
}

function sectionFacts(sections) {
  const source = sections || {};
  const rows = [];
  for (const key of PAYMENT_SECTION_KEYS) {
    const section = source[key] || {};
    for (const fact of section.facts || []) rows.push(fact);
    const subs = section.subsections || {};
    for (const bucket of Object.values(subs)) {
      const list = Array.isArray(bucket) ? bucket : (bucket && bucket.facts) || [];
      for (const fact of list) rows.push(fact);
    }
  }
  return rows;
}

/** Public China coverage derived from the payment sections. Bank names stay out of the result. */
export function deriveChinaPayment(sections) {
  const facts = sectionFacts(sections).filter((fact) => fact && fact.fact_type === "fact" && fact.source_user_facing !== false);
  const dates = facts.map((fact) => fact.checked_at).filter(Boolean).sort();
  const checked = dates.length ? dates[dates.length - 1] : "";
  const unionFacts = facts.filter((fact) => /unionpay/i.test(fact.text || ""));
  const namesRussia = unionFacts.some((fact) => /РФ|росси/i.test(fact.text || ""));
  const shopsPartial = unionFacts.some((fact) => /терминал/i.test(fact.text || "") && fact.zone !== "green");
  const atmPartial = unionFacts.some((fact) => /снят/i.test(fact.text || "") && /РФ|росси/i.test(fact.text || ""));
  const rules = [];
  if (namesRussia && (shopsPartial || atmPartial)) {
    rules.push({
      system: "unionpay",
      kind: "card",
      issuer: "RU",
      channels: {
        shops: shopsPartial ? "partial" : "unverified",
        online: "unverified",
        atm: atmPartial ? "partial" : "unverified",
      },
    });
  }
  for (const [system, pattern] of [["alipay", /alipay/i], ["wechat", /wechat/i]]) {
    const named = facts.some((fact) => pattern.test(fact.text || "") && fact.source_kind === "official");
    if (!named) continue;
    rules.push({
      system,
      kind: "app",
      issuer: "*",
      channels: { shops: "known", online: "known", atm: "unverified" },
    });
  }
  return { checked, rules };
}

