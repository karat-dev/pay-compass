import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  LOYALTY_ALLIANCES,
  LOYALTY_CHECKED,
  LOYALTY_PROGRAMS,
  allianceIdFromSource,
  filterLoyalty,
  programTag,
  trustZone,
} from "../miniapp/js/loyalty_catalog.js";
import { createPersonalStore, createMemoryBackend, PERSONAL_SECTIONS } from "../miniapp/js/personal_store.js";
import {
  cardsWord,
  cycleSetting,
  readLoyaltyCard,
  readPassport,
  revokedPersonal,
} from "../miniapp/js/profile_flow.js";
import { parseShellRoute, backTarget, readTripForm, readTripEdit } from "../miniapp/js/shell_router.js";
import { renderShell, shellState, formatStay, DEMO_TRIP } from "../miniapp/js/shell_screens.js";
import {
  applyChecks,
  assessFlightRows,
  checklistCaption,
  tripChecks,
} from "../miniapp/js/trip_flow.js";

const banned = ["supabase", "/api/", "OAG", "CAAC"];
for (const name of ["personal_store.js", "shell.js", "shell_screens.js", "shell_router.js", "trip_flow.js", "profile_flow.js", "loyalty_catalog.js"]) {
  const text = readFileSync(new URL(`../miniapp/js/${name}`, import.meta.url), "utf8");
  for (const word of banned) assert.equal(text.includes(word), false, `${name} contains ${word}`);
  assert.equal(/fetch\s*\(/.test(text), false, `${name} fetches`);
}

assert.deepEqual(parseShellRoute(""), { name: "home", tab: "home", inner: false, slug: "" });
assert.deepEqual(parseShellRoute("#/trip"), { name: "trip", tab: "trip", inner: false, slug: "" });
assert.equal(parseShellRoute("#/pay").inner, true);
assert.equal(parseShellRoute("#/pay").tab, "profile");
assert.equal(parseShellRoute("#/settings").name, "settings");
assert.equal(parseShellRoute("#/guide/china").name, "country");
assert.equal(parseShellRoute("#/guide/china").slug, "china");
assert.equal(backTarget(parseShellRoute("#/settings")), "/profile");
assert.equal(backTarget(parseShellRoute("#/pay")), "/profile");
assert.equal(backTarget(parseShellRoute("#/guide/china")), "/guide");
assert.equal(backTarget(parseShellRoute("#/home")), "");
assert.equal(parseShellRoute("#/unknown").name, "home");

assert.equal(formatStay("2026-12-12", "2026-12-20"), "12–20 декабря 2026");
assert.match(formatStay("2026-12-12", "2027-01-05"), /2026/);
assert.match(formatStay("2026-12-12", "2027-01-05"), /2027/);
assert.equal(formatStay("", ""), "Даты не указаны");

const bad = readTripForm({ origin: "Москва", destination: "", depart: "", ret: "" });
assert.match(bad.error, /даты/);
const early = readTripForm({ destination: "Шанхай", depart: "2026-12-20", ret: "2026-12-12" });
assert.match(early.error, /раньше/);
const saved = readTripForm({ origin: "Москва", destination: "Шанхай", depart: "2026-12-12", ret: "2026-12-20" });
assert.equal(saved.trip.destination, "Шанхай");
assert.match(saved.trip.depart, /^\d{4}-\d{2}-\d{2}$/);

const home = renderShell(shellState({
  route: parseShellRoute("#/home"),
  trips: [DEMO_TRIP],
  outside: true,
}));
assert.match(home, /Москва → Шанхай/);
assert.match(home, /12–20 декабря 2026/);
assert.match(home, /2 из 6/);
assert.match(home, /ut-support-mark">\?</);
assert.match(home, /Главная/);
assert.match(home, /Поездка/);
assert.match(home, /Справочник/);
assert.match(home, /Профиль/);
assert.match(home, /Шанхай, 12–20 декабря 2026/);

const empty = renderShell(shellState({
  route: parseShellRoute("#/home"),
  trips: [],
  outside: true,
}));
assert.match(empty, /Пока нет поездки/);
assert.match(empty, /Добавить поездку/);
assert.equal(empty.includes("Москва → Шанхай"), false);

const toast = renderShell(shellState({
  route: parseShellRoute("#/home"),
  trips: [DEMO_TRIP],
  supportOpen: true,
}));
assert.match(toast, /Скриншот сохранён/);
assert.match(toast, /Что-то не так на экране\?/);
assert.match(toast, /Сообщить о проблеме/);
assert.equal(toast.includes("ut-support-mark"), false);

const pay = renderShell(shellState({
  route: parseShellRoute("#/pay"),
  payments: [{ title: "Мир", detail: "Россия · физическая", bank: "Сбер", pan: "4111" }],
}));
for (const word of ["Сбер", "Тинькофф", "Т-Банк", "Альфа", "ВТБ", "OAG", "CAAC", "4111"]) {
  assert.equal(pay.includes(word), false, word);
}
assert.match(pay, /Мир/);
assert.match(pay, /Россия/);
assert.match(pay, /По платёжной системе/);

const guide = renderShell(shellState({ route: parseShellRoute("#/guide") }));
assert.match(guide, /официальный источник/);
assert.match(guide, /неофициальный \/ свой замер \/ ещё не сверено/);
assert.match(guide, /риск/);
assert.match(guide, /ut-dot-green/);
assert.match(guide, /ut-dot-yellow/);
assert.match(guide, /ut-dot-red/);

const profile = renderShell(shellState({
  route: parseShellRoute("#/profile"),
  passport: { citizenship: "РФ", expires: "2031-08-15", number: "4510 123456" },
}));
assert.match(profile, /15\.08\.2031/);
assert.equal(profile.includes("4510"), false);
assert.equal(profile.includes("123456"), false);

const settings = renderShell(shellState({ route: parseShellRoute("#/settings") }));
assert.match(settings, /Настройки/);
assert.match(settings, /Отозвать согласие/);
assert.match(settings, /data-shell="back"/);

const hostile = renderShell(shellState({
  route: { name: "country", tab: "guide", inner: true, slug: `"><img` },
  trips: [{ ...DEMO_TRIP, destination: "<script>" }],
}));
assert.equal(hostile.includes("<img"), false);
assert.equal(hostile.includes("<script>"), false);

const local = createMemoryBackend();
const cloud = {
  fail: false,
  data: {},
  getItem(key, cb) {
    if (this.fail) cb("down");
    else cb(null, Object.prototype.hasOwnProperty.call(this.data, key) ? this.data[key] : null);
  },
  setItem(key, value, cb) {
    if (this.fail) cb("down");
    else {
      this.data[key] = value;
      cb(null);
    }
  },
  removeItem(key, cb) {
    delete this.data[key];
    cb(null);
  },
};
const store = createPersonalStore({ cloud, local });
assert.equal(store.kind, "cloud");
await store.write("trips", [DEMO_TRIP]);
assert.match(cloud.data["ut.personal.trips"], /Шанхай/);
const readBack = await store.read("trips");
assert.equal(readBack[0].destination, "Шанхай");
cloud.fail = true;
await store.write("settings", { language: "Русский" });
const settingsRow = await store.read("settings");
assert.equal(settingsRow.language, "Русский");
cloud.fail = false;
await store.remove("trips");
assert.equal(await store.read("trips"), null);
assert.equal(await store.read("settings").then((row) => row.language), "Русский");
assert.equal(PERSONAL_SECTIONS.includes("passport"), true);
await assert.rejects(() => createPersonalStore({ local: createMemoryBackend(), cloud: null }).read("secret"));

assert.deepEqual(parseShellRoute("#/trip"), { name: "trip", tab: "trip", inner: false, slug: "" });
assert.equal(parseShellRoute("#/trip/flight-add").name, "flight-add");
assert.equal(parseShellRoute("#/trip/flight-add").inner, true);
assert.equal(parseShellRoute("#/trip/flight-add").tab, "trip");
assert.equal(parseShellRoute("#/trip/edit").name, "trip-edit");
assert.equal(parseShellRoute("#/trip/pay").name, "trip-pay");
assert.equal(parseShellRoute("#/trip/transport").name, "trip-transport");
assert.equal(parseShellRoute("#/trip/checklist").name, "trip-checklist");
assert.equal(backTarget(parseShellRoute("#/trip/flight-add")), "/trip");
assert.equal(backTarget(parseShellRoute("#/trip/pay")), "/trip");
assert.equal(backTarget(parseShellRoute("#/trip/transport")), "/trip");
assert.equal(backTarget(parseShellRoute("#/trip/checklist")), "/trip");
assert.equal(backTarget(parseShellRoute("#/trip/edit")), "/trip");
assert.equal(backTarget(parseShellRoute("#/trip")), "");

const stay = "12–20 декабря 2026";
const baseTrip = { ...DEMO_TRIP, checks: ["entry", "docs"], flights: [] };
function flightHtml(draft, flights) {
  return renderShell(shellState({
    route: parseShellRoute("#/trip/flight-add"),
    trips: [{ ...baseTrip, flights: flights || [] }],
    flightDraft: draft,
  }));
}

const emptyFlight = flightHtml([
  { number: "", date: "", legId: "" },
  { number: "", date: "", legId: "" },
]);
assert.match(emptyFlight, /Формат номера: SU 204/);
assert.match(emptyFlight, /К поездке Москва → Шанхай, 12–20 декабря 2026/);
assert.match(emptyFlight, /is-idle/);
assert.equal(emptyFlight.includes("Неверный формат"), false);
assert.equal(emptyFlight.includes("Укажите дату вылета"), false);

const badNumber = assessFlightRows([{ number: "СУ 204", date: "12.12.2026", legId: "" }], baseTrip, stay);
assert.equal(badNumber.canSave, false);
assert.equal(badNumber.rows[0].formatError, true);
const badNumberHtml = flightHtml([{ number: "СУ 204", date: "12.12.2026", legId: "" }]);
assert.match(badNumberHtml, /Неверный формат\. Пример: SU 204/);
assert.match(badNumberHtml, /is-bad/);
assert.match(badNumberHtml, /is-idle/);
assert.equal(badNumberHtml.includes("<img"), false);

const missingDate = assessFlightRows([{ number: "SU 204", date: "", legId: "" }], baseTrip, stay);
assert.equal(missingDate.canSave, false);
assert.equal(missingDate.rows[0].dateError, true);
assert.match(flightHtml([{ number: "SU 204", date: "", legId: "" }]), /Укажите дату вылета/);

const unknown = assessFlightRows([{ number: "mu510", date: "12.12.2026", legId: "" }], baseTrip, stay);
assert.equal(unknown.canSave, true);
assert.equal(unknown.rows[0].unverified, true);
assert.equal(unknown.rows[0].number, "MU 510");
assert.equal(unknown.ready[0].from, "");
assert.equal(unknown.ready[0].sample, false);
const unknownHtml = flightHtml([{ number: "MU 510", date: "12.12.2026", legId: "" }]);
assert.match(unknownHtml, /сведения не сверены/);
assert.match(unknownHtml, /ut-dot-yellow/);
assert.equal(unknownHtml.includes("is-idle"), false);
assert.equal(unknownHtml.includes("OAG"), false);

const outside = assessFlightRows([{ number: "MU 510", date: "21.12.2026", legId: "" }], baseTrip, stay);
assert.equal(outside.canSave, true);
assert.equal(outside.rows[0].outside, true);
assert.match(flightHtml([{ number: "MU 510", date: "21.12.2026", legId: "" }]), /Дата вне поездки 12–20 декабря 2026\. Сохранить можно\./);

const legs = assessFlightRows([{ number: "SU 204", date: "12.12.2026", legId: "kzn-sha" }], baseTrip, stay);
assert.equal(legs.canSave, true);
assert.equal(legs.rows[0].legs.length, 2);
assert.equal(legs.ready[0].from, "Казань");
assert.equal(legs.ready[0].to, "Шанхай");
assert.equal(legs.ready[0].sample, true);
const legsHtml = flightHtml([{ number: "SU 204", date: "12.12.2026", legId: "kzn-sha" }]);
assert.match(legsHtml, /Пример, не расписание/);
assert.match(legsHtml, /Москва — Казань/);
assert.match(legsHtml, /Казань — Шанхай/);
assert.equal(legsHtml.includes("is-idle"), false);

const otherDay = assessFlightRows([{ number: "SU 204", date: "13.12.2026", legId: "" }], baseTrip, stay);
assert.equal(otherDay.rows[0].duplicate, false);
assert.equal(otherDay.rows[0].legs.length, 0);
assert.equal(otherDay.canSave, true);

const savedFlight = { id: "flt-1", number: "SU 204", date: "2026-12-12", from: "Казань", to: "Шанхай", sample: true };
const duplicate = assessFlightRows(
  [{ number: "SU 204", date: "12.12.2026", legId: "" }],
  { ...baseTrip, flights: [savedFlight] },
  stay,
);
assert.equal(duplicate.canSave, true);
assert.equal(duplicate.rows[0].duplicate, true);
const duplicateHtml = flightHtml([{ number: "SU 204", date: "12.12.2026", legId: "" }], [savedFlight]);
assert.match(duplicateHtml, /Этот рейс уже есть в поездке/);
assert.equal(duplicateHtml.includes("is-idle"), false);
const sameNumberOtherDate = assessFlightRows(
  [{ number: "SU 204", date: "13.12.2026", legId: "" }],
  { ...baseTrip, flights: [savedFlight] },
  stay,
);
assert.equal(sameNumberOtherDate.rows[0].duplicate, false);
assert.equal(sameNumberOtherDate.canSave, true);

const edited = readTripEdit({
  origin: "Москва",
  destination: "Пекин",
  country: "Китай",
  depart: "2026-12-12",
  ret: "2026-12-20",
}, { ...baseTrip, flights: [savedFlight], checks: ["entry", "docs"] });
assert.equal(edited.trip.destination, "Пекин");
assert.equal(edited.trip.country, "Китай");
assert.equal(edited.trip.flights[0].id, "flt-1");
assert.deepEqual(edited.trip.checks, ["entry", "docs"]);

const marked = applyChecks(baseTrip, ["entry", "docs", "insurance"]);
assert.equal(marked.stepsDone, 3);
assert.equal(checklistCaption(marked), "Шаг 4 из 6: оплата");
const progressStore = createPersonalStore({ local: createMemoryBackend(), cloud: null });
await progressStore.write("trips", [marked]);
const storedTrips = await progressStore.read("trips");
assert.deepEqual(tripChecks(storedTrips[0]), ["entry", "docs", "insurance"]);
const homeProgress = renderShell(shellState({
  route: parseShellRoute("#/home"),
  trips: storedTrips,
}));
const tripProgress = renderShell(shellState({
  route: parseShellRoute("#/trip"),
  trips: storedTrips,
}));
assert.match(homeProgress, /3 из 6/);
assert.match(tripProgress, /3 из 6/);
assert.match(tripProgress, /SU 204|Добавьте рейс|Шаг 4 из 6/);
assert.match(tripProgress, /data-path="\/trip\/pay"/);
assert.match(tripProgress, /data-path="\/trip\/transport"/);
assert.match(tripProgress, /data-path="\/guide\/china"/);

const withFlight = [{ ...marked, flights: [savedFlight] }];
await progressStore.write("trips", withFlight);
const viewed = renderShell(shellState({
  route: parseShellRoute("#/trip"),
  trips: await progressStore.read("trips"),
}));
assert.match(viewed, /SU 204 · 12\.12\.2026/);
assert.match(viewed, /Казань — Шанхай/);
assert.match(viewed, /Пример, не расписание/);
assert.match(viewed, /Удалить/);
assert.match(viewed, /сведения не сверены/);
const removed = withFlight[0].flights.filter((item) => item.id !== "flt-1");
await progressStore.write("trips", [{ ...withFlight[0], flights: removed }]);
const afterDelete = renderShell(shellState({
  route: parseShellRoute("#/trip"),
  trips: await progressStore.read("trips"),
}));
assert.equal(afterDelete.includes("SU 204 · 12.12.2026"), false);

const paySlot = renderShell(shellState({
  route: parseShellRoute("#/trip/pay"),
  trips: [baseTrip],
}));
assert.match(paySlot, /data-slot="trip-pay"/);
assert.match(paySlot, /Москва · Шанхай · Китай/);
assert.match(paySlot, /12–20 декабря 2026/);
assert.match(paySlot, /data-shell="back"/);
for (const word of ["Сбер", "Тинькофф", "Т-Банк", "Альфа", "ВТБ", "OAG", "CAAC"]) {
  assert.equal(paySlot.includes(word), false, word);
}

const emptyTrip = renderShell(shellState({
  route: parseShellRoute("#/trip"),
  trips: [],
  outside: true,
}));
assert.match(emptyTrip, /Пока нет поездки/);
assert.match(emptyTrip, /Сохранить поездку/);
assert.match(emptyTrip, /Нет поездок/);

const hostileTrip = renderShell(shellState({
  route: parseShellRoute("#/trip"),
  trips: [{ ...DEMO_TRIP, destination: "<script>", country: "<img>", flights: [{ id: "x", number: "MU 1", date: "2026-12-12", from: "<img src=x>", to: "Шанхай" }] }],
}));
assert.equal(hostileTrip.includes("<script>"), false);
assert.equal(hostileTrip.includes("<img"), false);

const beforeProfile = renderShell(shellState({ route: parseShellRoute("#/profile") }));
assert.match(beforeProfile, /Добавить паспорт/);
assert.match(beforeProfile, /Добавить способы оплаты/);
assert.match(beforeProfile, /Добавить номера программ/);
assert.equal(beforeProfile.includes("15.08.2031"), false);

const counted = renderShell(shellState({
  route: parseShellRoute("#/profile"),
  passport: { citizenship: "РФ", expires: "2031-08-15", given: "IVAN", surname: "IVANOV" },
  loyalty: [
    { id: "1", program: "Miles&Smiles", number: "9988777390", allianceId: "star" },
    { id: "2", program: "Privilege Club", number: "1122331564", allianceId: "one" },
  ],
}));
assert.match(counted, /2 карты/);
assert.match(counted, /номера ваших программ/);
assert.equal(counted.includes("9988777390"), false);
assert.equal(counted.includes("1122331564"), false);
assert.equal(cardsWord(1), "1 карта");
assert.equal(cardsWord(5), "5 карт");

const emptyPassport = readPassport({ citizenship: "РФ", given: "", surname: "", expires: "" }, { today: "2026-11-27", needConsent: true });
assert.match(emptyPassport.errors.given, /латиницей/);
assert.match(emptyPassport.errors.expires, /годом/);
assert.match(emptyPassport.errors.consent, /устройстве/);
const cyrillic = readPassport({ citizenship: "РФ", given: "Иван", surname: "IVANOV", expires: "2031-08-15", consent: true }, { today: "2026-11-27" });
assert.match(cyrillic.errors.given, /латиница/);
const expired = readPassport({ citizenship: "РФ", given: "IVAN", surname: "IVANOV", expires: "2020-01-01", consent: true }, { today: "2026-11-27" });
assert.match(expired.errors.expires, /прошёл/);
const passportOk = readPassport({
  citizenship: "Другое",
  citizenshipOther: "Армения",
  given: "ivan",
  surname: "ivanov",
  number: "4510 123456",
  expires: "2031-08-15",
  consent: true,
}, { today: "2026-11-27", needConsent: true });
assert.equal(passportOk.passport.citizenship, "Армения");
assert.equal(passportOk.passport.given, "IVAN");
assert.equal(passportOk.passport.number, "4510 123456");

const passportScreen = renderShell(shellState({
  route: parseShellRoute("#/passport"),
  passportDraft: {
    citizenship: "РФ",
    given: "<img>",
    surname: "",
    number: "",
    expires: "",
    errors: { given: "Укажите имя латиницей.", surname: "<script>" },
  },
}));
assert.match(passportScreen, /Укажите имя латиницей/);
assert.match(passportScreen, /is-bad/);
assert.match(passportScreen, /ut-err/);
assert.equal(passportScreen.includes("<img>"), false);
assert.equal(passportScreen.includes("<script>"), false);
assert.match(passportScreen, /data-slot="passport"/);
assert.match(passportScreen, /data-shell="back"/);

const kept = revokedPersonal({
  trips: [DEMO_TRIP],
  passport: { citizenship: "РФ" },
  loyalty: [{ id: "1", number: "9988777390" }],
  payments: [{ title: "Мир" }],
  settings: { language: "Русский", consentAt: "2026-11-01", nameOrder: "family" },
});
assert.equal(kept.passport, null);
assert.deepEqual(kept.loyalty, []);
assert.deepEqual(kept.payments, []);
assert.equal(kept.trips[0].destination, "Шанхай");
assert.equal(kept.settings.consentAt, "");
assert.equal(kept.settings.language, "Русский");
assert.equal(kept.settings.nameOrder, "family");
const revokeSheet = renderShell(shellState({
  route: parseShellRoute("#/settings"),
  sheet: "revoke",
  settings: { consentAt: "2026-11-01" },
}));
assert.match(revokeSheet, /Отозвать согласие\?/);
assert.match(revokeSheet, /Достижения и поездки сохранятся/);
assert.equal(cycleSetting({ currency: "Рубли" }, "currency").currency, "Доллары США");
assert.equal(cycleSetting({ notifications: "Выключены" }, "notifications").notifications.includes("Выключены"), false);

const loyaltyJson = JSON.parse(readFileSync(new URL("../database/data/loyalty_programs.json", import.meta.url), "utf8"));
assert.equal(loyaltyJson.alliances.length, 4);
assert.equal(LOYALTY_ALLIANCES.length, 4);
assert.equal(loyaltyJson.programs.length, 16);
assert.equal(LOYALTY_PROGRAMS.length, 16);
for (const source of loyaltyJson.alliances) {
  const id = source.name === "Без альянса" ? "out" : allianceIdFromSource(source.name);
  const row = LOYALTY_ALLIANCES.find((item) => item.id === id);
  assert.equal(row.name, source.name);
  assert.deepEqual(row.members, source.our_members);
}
for (const source of loyaltyJson.programs) {
  const row = LOYALTY_PROGRAMS.find((item) => item.iata === source.iata);
  assert.ok(row, source.iata);
  assert.equal(row.airline, source.airline);
  assert.equal(row.program, source.program);
  assert.equal(row.allianceId, allianceIdFromSource(source.alliance));
  assert.equal(row.zone, trustZone(source));
  assert.equal(row.tag, programTag(source));
  assert.equal(source.checked, LOYALTY_CHECKED);
}
assert.equal(LOYALTY_PROGRAMS.filter((item) => item.zone === "green").length > 0, true);
assert.equal(LOYALTY_PROGRAMS.some((item) => item.zone === "red"), false);

const found = renderShell(shellState({
  route: parseShellRoute("#/guide/airlines"),
  query: "Turkish",
}));
assert.match(found, /Miles&amp;Smiles/);
assert.match(found, /ut-dot-yellow/);
assert.match(found, /официальный источник/);
assert.equal(found.includes("Pegasus"), false);
assert.equal(parseShellRoute("#/guide/airlines").name, "loyalty-ref");
assert.equal(parseShellRoute("#/guide/airlines").tab, "guide");
assert.equal(backTarget(parseShellRoute("#/guide/airlines")), "/guide");
const green = renderShell(shellState({
  route: parseShellRoute("#/guide/airlines"),
  query: "Qatar",
}));
assert.match(green, /Privilege Club/);
assert.match(green, /ut-dot-green/);
const sky = renderShell(shellState({
  route: parseShellRoute("#/guide/airlines"),
  alliance: "sky",
}));
assert.match(sky, /Аэрофлот Бонус/);
assert.match(sky, /членство приостановлено с 2022/);
assert.equal(sky.includes("Miles&amp;Smiles"), false);
assert.equal(filterLoyalty("нет такой", "").length, 0);

const card = readLoyaltyCard({
  programId: "turkish-airlines",
  number: "9988 7773 90",
  given: "ivan",
  surname: "ivanov",
  note: "золото",
  consent: true,
}, {
  program: LOYALTY_PROGRAMS.find((item) => item.id === "turkish-airlines"),
  existing: [],
  needConsent: true,
});
assert.equal(card.card.number, "9988777390");
assert.equal(card.card.given, "IVAN");
assert.equal(card.card.allianceId, "star");
const clash = readLoyaltyCard({ programId: "air-china", number: "12345678", consent: true }, {
  program: LOYALTY_PROGRAMS.find((item) => item.id === "air-china"),
  existing: [{ id: "old", allianceId: "star" }],
});
assert.match(clash.errors.program, /альянс/);
const custom = readLoyaltyCard({ programId: "custom", custom: "", number: "" }, { needConsent: false });
assert.match(custom.errors.custom, /название/);
assert.match(custom.errors.number, /номер/i);

const wallet = renderShell(shellState({
  route: parseShellRoute("#/loyalty"),
  loyalty: [card.card],
  passport: { given: "IVAN", surname: "IVANOV", citizenship: "РФ", expires: "2031-08-15" },
}));
assert.match(wallet, /•••• 7390/);
assert.match(wallet, /IVAN IVANOV/);
assert.match(wallet, /Удалить/);
assert.match(wallet, /Что такое альянс/);
assert.equal(wallet.includes("9988777390"), false);
assert.match(wallet, /data-slot="loyalty"/);
assert.equal(parseShellRoute("#/loyalty/add").name, "loyalty-add");
assert.equal(backTarget(parseShellRoute("#/loyalty/add")), "/loyalty");
const addForm = renderShell(shellState({
  route: parseShellRoute("#/loyalty/add"),
  loyaltyDraft: { programId: "", number: "", errors: { program: "Выберите программу.", number: "Введите номер карты полностью." } },
}));
assert.match(addForm, /Выберите программу/);
assert.match(addForm, /Введите номер карты полностью/);
assert.match(addForm, /Своя программа/);
assert.match(addForm, /is-bad/);

console.log("shell modules ok");
