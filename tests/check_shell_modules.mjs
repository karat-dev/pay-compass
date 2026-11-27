import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createPersonalStore, createMemoryBackend, PERSONAL_SECTIONS } from "../miniapp/js/personal_store.js";
import { parseShellRoute, backTarget, readTripForm } from "../miniapp/js/shell_router.js";
import { renderShell, shellState, formatStay, DEMO_TRIP } from "../miniapp/js/shell_screens.js";

const banned = ["supabase", "/api/", "OAG", "CAAC"];
for (const name of ["personal_store.js", "shell.js", "shell_screens.js", "shell_router.js"]) {
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

console.log("shell modules ok");
