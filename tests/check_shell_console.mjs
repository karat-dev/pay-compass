import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const base = process.argv[2];
const chromeBin = process.argv[3];
const problems = [];

function note(text) {
  const value = String(text || "");
  if (!value) return;
  if (/telegram\.org|favicon|Failed to load resource/i.test(value)) return;
  problems.push(value);
}

function cdp(ws) {
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
    if (msg.method === "Runtime.exceptionThrown") {
      const details = msg.params && msg.params.exceptionDetails;
      note(details && (details.exception && details.exception.description || details.text));
    }
    if (msg.method === "Runtime.consoleAPICalled" && msg.params && msg.params.type === "error") {
      note((msg.params.args || []).map((item) => item.value || item.description || "").join(" "));
    }
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(JSON.stringify(msg.error)));
      else resolve(msg.result || {});
    }
  });
  return {
    send(method, params = {}) {
      const next = ++id;
      ws.send(JSON.stringify({ id: next, method, params }));
      return new Promise((resolve, reject) => pending.set(next, { resolve, reject }));
    },
  };
}

async function evaluate(client, expression) {
  const probe = await client.send("Runtime.evaluate", { expression, returnByValue: true });
  if (probe.exceptionDetails) {
    const details = probe.exceptionDetails;
    throw new Error(details.exception && details.exception.description || details.text || expression);
  }
  return probe.result && probe.result.value;
}

async function assertNoOverflow(client, label) {
  const measured = await evaluate(client, `(() => {
    const doc = document.documentElement;
    return { scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth };
  })()`);
  if (!measured || measured.scrollWidth > measured.clientWidth + 1) {
    throw new Error(`horizontal overflow on ${label} ${JSON.stringify(measured)}`);
  }
}

async function exerciseTrip(client) {
  await evaluate(client, `document.querySelector("[data-path='/trip/checklist']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='trip-checklist']") ? "ok" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='check'][data-id='insurance']").click()`);
  await waitFor(client, `document.body.innerText.includes("3 из 6") ? "ok" : ""`);
  const stored = await evaluate(client, `(() => {
    const trips = JSON.parse(localStorage.getItem("ut.personal.trips") || "[]");
    const trip = trips[0] || {};
    return { steps: trip.stepsDone, checks: trip.checks || [] };
  })()`);
  if (!stored || stored.steps !== 3 || !stored.checks.includes("insurance")) {
    throw new Error(`checklist was not stored ${JSON.stringify(stored)}`);
  }
  await evaluate(client, `document.querySelector("[data-shell='back']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='trip']") ? "ok" : ""`);
  await evaluate(client, `document.querySelector(".ut-nav [data-path='/home']").click()`);
  await waitFor(client, `document.body.innerText.includes("3 из 6") ? "home" : ""`);
  await evaluate(client, `document.querySelector(".ut-nav [data-path='/trip']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='trip']") ? "ok" : ""`);
  await assertNoOverflow(client, "trip");
  await evaluate(client, `document.querySelector("[data-path='/trip/flight-add']").click()`);
  await waitFor(client, `document.body.innerText.includes("Формат номера: SU 204") ? "empty" : ""`);
  await assertNoOverflow(client, "flight-add");

  const typeFlight = (number, date) => `(() => {
    const num = document.querySelector("[data-shell-field='flight-number'][data-index='0']");
    num.value = ${JSON.stringify(number)};
    num.dispatchEvent(new Event("input", { bubbles: true }));
    const date = document.querySelector("[data-shell-field='flight-date'][data-index='0']");
    date.value = ${JSON.stringify(date)};
    date.dispatchEvent(new Event("input", { bubbles: true }));
    const save = document.querySelector("[data-shell='flight-save']");
    return save && save.classList.contains("is-idle") ? "idle" : "ready";
  })()`;

  const blocked = await evaluate(client, typeFlight("СУ 204", "12.12.2026"));
  if (blocked !== "idle") throw new Error(`bad flight number can be saved (${blocked})`);
  await waitFor(client, `document.body.innerText.includes("Неверный формат. Пример: SU 204") ? "bad" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='flight-save']").click()`);
  if (await evaluate(client, `document.querySelector("[data-shell-screen='flight-add']") ? "stay" : ""`) !== "stay") {
    throw new Error("invalid flight number left the form");
  }

  const noDate = await evaluate(client, typeFlight("SU 204", ""));
  if (noDate !== "idle") throw new Error("missing date can be saved");
  await waitFor(client, `document.body.innerText.includes("Укажите дату вылета") ? "date" : ""`);

  const unknown = await evaluate(client, typeFlight("MU 510", "12.12.2026"));
  if (unknown !== "ready") throw new Error("unknown flight is blocked");
  await waitFor(client, `document.body.innerText.includes("сведения не сверены") ? "open" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='flight-save']").click()`);
  await waitFor(client, `document.body.innerText.includes("MU 510") && document.querySelector("[data-shell-screen='trip']") ? "saved" : ""`);
  await evaluate(client, `document.querySelector("[data-flight-number='MU 510'] [data-shell='flight-delete']").click()`);
  await waitFor(client, `document.querySelector("[data-flight-number='MU 510']") ? "" : "gone"`);

  await evaluate(client, `document.querySelector("[data-path='/trip/flight-add']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='flight-add']") ? "ok" : ""`);
  const outside = await evaluate(client, typeFlight("MU 510", "21.12.2026"));
  if (outside !== "ready") throw new Error("date outside the trip is blocked");
  await waitFor(client, `document.body.innerText.includes("Дата вне поездки 12–20 декабря 2026. Сохранить можно.") ? "out" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='flight-save']").click()`);
  await waitFor(client, `document.body.innerText.includes("21.12.2026") ? "saved" : ""`);
  await evaluate(client, `document.querySelector("[data-flight-number='MU 510'] [data-shell='flight-delete']").click()`);
  await waitFor(client, `document.querySelector("[data-flight-number='MU 510']") ? "" : "gone"`);

  await evaluate(client, `document.querySelector("[data-path='/trip/flight-add']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='flight-add']") ? "ok" : ""`);
  const legs = await evaluate(client, typeFlight("SU 204", "12.12.2026"));
  if (legs !== "ready") throw new Error("sample legs are blocked");
  await waitFor(client, `document.body.innerText.includes("Пример, не расписание") && document.body.innerText.includes("Казань — Шанхай") ? "legs" : ""`);
  await evaluate(client, `document.querySelector("[data-leg='kzn-sha']").click()`);
  await evaluate(client, `document.querySelector("[data-shell='flight-save']").click()`);
  await waitFor(client, `document.body.innerText.includes("Казань — Шанхай") && document.body.innerText.includes("Пример, не расписание") ? "saved" : ""`);

  await evaluate(client, `document.querySelector("[data-path='/trip/flight-add']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='flight-add']") ? "ok" : ""`);
  const duplicate = await evaluate(client, typeFlight("SU 204", "12.12.2026"));
  if (duplicate !== "ready") throw new Error("duplicate flight is blocked");
  await waitFor(client, `document.body.innerText.includes("Этот рейс уже есть в поездке") ? "dup" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='flight-save']").click()`);
  await waitFor(client, `document.querySelectorAll("[data-flight-number='SU 204'][data-flight-date='2026-12-12']").length === 2 ? "two" : ""`);

  await evaluate(client, `document.querySelector("[data-path='/trip/flight-add']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='flight-add']") ? "ok" : ""`);
  const otherDate = await evaluate(client, typeFlight("SU 204", "13.12.2026"));
  if (otherDate !== "ready") throw new Error("same number on another date is blocked");
  const warned = await evaluate(client, `document.body.innerText.includes("Этот рейс уже есть в поездке") ? "warn" : "clear"`);
  if (warned !== "clear") throw new Error("same number on another date shows a duplicate warning");
  await evaluate(client, `document.querySelector("[data-shell='flight-save']").click()`);
  await waitFor(client, `document.body.innerText.includes("13.12.2026") ? "saved" : ""`);

  await evaluate(client, `document.querySelector("[data-path='/trip/edit']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-form='trip-edit']") ? "edit" : ""`);
  await evaluate(client, `(() => {
    const form = document.querySelector("[data-shell-form='trip-edit']");
    form.destination.value = "Пекин";
    form.country.value = "Китай";
    form.requestSubmit();
    return "sent";
  })()`);
  await waitFor(client, `document.body.innerText.includes("Москва → Пекин") ? "edited" : ""`);
  await evaluate(client, `document.querySelector("[data-path='/trip/pay']").click()`);
  await waitFor(client, `document.querySelector("[data-slot='trip-pay']") ? "pay" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='back']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='trip']") ? "trip" : ""`);
  await evaluate(client, `document.querySelector("[data-path='/trip/transport']").click()`);
  await waitFor(client, `document.querySelector("[data-slot='trip-transport']") ? "transport" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='back']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='trip']") ? "trip" : ""`);
  await evaluate(client, `document.querySelector(".ut-nav [data-path='/home']").click()`);
  await waitFor(client, `document.body.innerText.includes("Москва → Пекин") && document.body.innerText.includes("3 из 6") ? "home" : ""`);
}

async function exerciseProfile(client) {
  await evaluate(client, `document.querySelector(".ut-nav [data-path='/profile']").click()`);
  await waitFor(client, `document.body.innerText.includes("Добавить паспорт") ? "before" : ""`);
  await assertNoOverflow(client, "profile-before");
  await evaluate(client, `document.querySelector("[data-path='/passport']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-form='passport']") ? "form" : ""`);
  await assertNoOverflow(client, "passport-empty");
  await evaluate(client, `document.querySelector("[data-shell-form='passport']").requestSubmit()`);
  await waitFor(client, `document.body.innerText.includes("Укажите имя латиницей.") ? "err" : ""`);
  await evaluate(client, `(() => {
    const form = document.querySelector("[data-shell-form='passport']");
    form.given.value = "Ivan";
    form.given.dispatchEvent(new Event("input", { bubbles: true }));
    form.surname.value = "Ivanov";
    form.surname.dispatchEvent(new Event("input", { bubbles: true }));
    form.number.value = "4510123456";
    form.expires.value = "2031-08-15";
    form.consent.checked = true;
    form.requestSubmit();
    return "sent";
  })()`);
  await waitFor(client, `document.body.innerText.includes("Гражданство РФ") && document.body.innerText.includes("15.08.2031") ? "saved" : ""`);
  if (await evaluate(client, `document.body.innerText.includes("4510123456") ? "leak" : "clean"`) !== "clean") {
    throw new Error("passport number is on the profile");
  }
  await assertNoOverflow(client, "profile-after");
  await evaluate(client, `document.querySelector("[data-path='/loyalty']").click()`);
  await waitFor(client, `document.querySelector("[data-slot='loyalty']") ? "wallet" : ""`);
  await evaluate(client, `document.querySelector("[data-path='/loyalty/add']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-form='loyalty-add']") ? "add" : ""`);
  await assertNoOverflow(client, "loyalty-add");
  await evaluate(client, `(() => {
    const form = document.querySelector("[data-shell-form='loyalty-add']");
    form.programId.value = "turkish-airlines";
    form.programId.dispatchEvent(new Event("change", { bubbles: true }));
    return "picked";
  })()`);
  await evaluate(client, `(() => {
    const form = document.querySelector("[data-shell-form='loyalty-add']");
    form.number.value = "9988777390";
    form.note.value = "золото";
    if (form.consent) form.consent.checked = true;
    form.requestSubmit();
    return "sent";
  })()`);
  await waitFor(client, `document.body.innerText.includes("•••• 7390") && document.querySelector("[data-shell-screen='loyalty']") ? "card" : ""`);
  if (await evaluate(client, `document.body.innerText.includes("9988777390") ? "leak" : "clean"`) !== "clean") {
    throw new Error("card number is visible in the wallet");
  }
  const storedCard = await evaluate(client, `(() => {
    const rows = JSON.parse(localStorage.getItem("ut.personal.loyalty") || "[]");
    return rows[0] && rows[0].number;
  })()`);
  if (storedCard !== "9988777390") throw new Error(`card was not stored on the device (${storedCard})`);
  await assertNoOverflow(client, "wallet");
  await evaluate(client, `document.querySelector("[data-shell='loyalty-delete']").click()`);
  await waitFor(client, `document.body.innerText.includes("Пока нет карт") ? "empty" : ""`);
  await evaluate(client, `document.querySelector("[data-path='/guide/airlines']").click()`);
  await waitFor(client, `document.body.innerText.includes("Авиакомпании и мили") && document.body.innerText.includes("Miles&Smiles") ? "ref" : ""`);
  await assertNoOverflow(client, "loyalty-ref");
  await evaluate(client, `(() => {
    const input = document.querySelector("[data-shell-field='search']");
    input.value = "Turkish";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    return "q";
  })()`);
  await waitFor(client, `document.body.innerText.includes("Miles&Smiles") && document.querySelector(".ut-result .ut-dot-yellow") && !document.body.innerText.includes("Pegasus") ? "hit" : ""`);
  await assertNoOverflow(client, "loyalty-search");
  await evaluate(client, `(() => {
    const input = document.querySelector("[data-shell-field='search']");
    input.value = "Qatar";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    return "q";
  })()`);
  await waitFor(client, `document.body.innerText.includes("Privilege Club") && document.querySelector(".ut-result .ut-dot-green") ? "green" : ""`);
  await evaluate(client, `(() => {
    const input = document.querySelector("[data-shell-field='search']");
    input.value = "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    document.querySelector("[data-shell='alliance'][data-id='sky']").click();
    return "sky";
  })()`);
  await waitFor(client, `document.body.innerText.includes("Аэрофлот Бонус") && !document.body.innerText.includes("Miles&Smiles") ? "sky" : ""`);
  await evaluate(client, `document.querySelector(".ut-nav [data-path='/profile']").click()`);
  await waitFor(client, `document.querySelector("[data-path='/settings']") ? "profile" : ""`);
  await evaluate(client, `document.querySelector("[data-path='/settings']").click()`);
  await waitFor(client, `document.querySelector("[data-key='currency']") ? "settings" : ""`);
  await assertNoOverflow(client, "settings");
  await evaluate(client, `document.querySelector("[data-key='currency']").click()`);
  await waitFor(client, `document.body.innerText.includes("Доллары США") ? "currency" : ""`);
  await evaluate(client, `document.querySelector("[data-key='notifications']").click()`);
  await waitFor(client, `document.body.innerText.includes("Выключены") ? "off" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='revoke']").click()`);
  await waitFor(client, `document.body.innerText.includes("Отозвать согласие?") ? "sheet" : ""`);
  await assertNoOverflow(client, "revoke");
  await evaluate(client, `document.querySelector("[data-shell='sheet-ok']").click()`);
  await waitFor(client, `document.body.innerText.includes("Добавить паспорт") && document.querySelector("[data-shell-screen='profile']") ? "revoked" : ""`);
  const after = await evaluate(client, `(() => {
    const trips = JSON.parse(localStorage.getItem("ut.personal.trips") || "[]");
    const settings = JSON.parse(localStorage.getItem("ut.personal.settings") || "{}");
    return {
      destination: trips[0] && trips[0].destination,
      passport: localStorage.getItem("ut.personal.passport"),
      loyalty: localStorage.getItem("ut.personal.loyalty"),
      consent: settings.consentAt || "",
    };
  })()`);
  if (!after || after.destination !== "Пекин" || after.passport || after.loyalty || after.consent) {
    throw new Error(`revoke did not clear personal data ${JSON.stringify(after)}`);
  }
  await assertNoOverflow(client, "profile-revoked");
}

async function exercisePayments(client) {
  await evaluate(client, `document.querySelector(".ut-nav [data-path='/profile']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='profile']") ? "ok" : ""`);
  await evaluate(client, `document.querySelector("[data-path='/pay']").click()`);
  await waitFor(client, `document.querySelector("[data-slot='pay']") ? "pay" : ""`);
  await assertNoOverflow(client, "pay");
  await evaluate(client, `document.querySelector("[data-path='/pay/add']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-form='pay-add']") ? "add" : ""`);
  await assertNoOverflow(client, "pay-add");
  await evaluate(client, `document.querySelector("[data-shell-form='pay-add']").requestSubmit()`);
  await waitFor(client, `document.body.innerText.includes("Выберите платёжную систему.") ? "err" : ""`);
  await evaluate(client, `(() => {
    const form = document.querySelector("[data-shell-form='pay-add']");
    form.title.value = ${JSON.stringify("Я".repeat(31))};
    form.title.dispatchEvent(new Event("input", { bubbles: true }));
    return "title";
  })()`);
  await evaluate(client, `document.querySelector("[data-shell='pay-system'][data-id='unionpay']").click()`);
  await evaluate(client, `(() => {
    const form = document.querySelector("[data-shell-form='pay-add']");
    form.countryQuery.value = "Росс";
    form.countryQuery.dispatchEvent(new Event("input", { bubbles: true }));
    return "query";
  })()`);
  await waitFor(client, `document.querySelector("[data-shell='pay-country'][data-iso='RU']") ? "ru" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='pay-country'][data-iso='RU']").click()`);
  await evaluate(client, `document.querySelector("[data-shell-form='pay-add']").requestSubmit()`);
  await waitFor(client, `document.body.innerText.includes("до 30 символов") ? "long" : ""`);
  await evaluate(client, `(() => {
    const form = document.querySelector("[data-shell-form='pay-add']");
    form.title.value = "UnionPay РФ";
    form.title.dispatchEvent(new Event("input", { bubbles: true }));
    return "short";
  })()`);
  await evaluate(client, `(() => {
    const form = document.querySelector("[data-shell-form='pay-add']");
    if (form.consent) form.consent.checked = true;
    form.requestSubmit();
    return "sent";
  })()`);
  await waitFor(client, `document.querySelector("[data-slot='pay-experience-prompt']") ? "exp" : ""`);
  await assertNoOverflow(client, "experience");
  await evaluate(client, `document.querySelector("[data-shell='experience-skip']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-screen='pay']") && document.body.innerText.includes("UnionPay РФ") ? "list" : ""`);
  const skipped = await evaluate(client, `(() => {
    const rows = JSON.parse(localStorage.getItem("ut.personal.payments") || "[]");
    return rows[0] ? rows[0].experience : "missing";
  })()`);
  if (skipped) throw new Error(`skip wrote an experience ${JSON.stringify(skipped)}`);
  await evaluate(client, `document.querySelector("[data-path='/pay/add']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-form='pay-add']") ? "add2" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='pay-kind'][data-id='app']").click()`);
  await waitFor(client, `document.querySelector("[data-shell='pay-system'][data-id='alipay']") ? "ali" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='pay-system'][data-id='alipay']").click()`);
  await evaluate(client, `document.querySelector("[data-shell-form='pay-add']").requestSubmit()`);
  await waitFor(client, `document.querySelector("[data-slot='pay-experience-prompt']") ? "exp2" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='experience-open']").click()`);
  await waitFor(client, `document.querySelector("[data-shell-form='pay-experience']") ? "form" : ""`);
  await assertNoOverflow(client, "experience-form");
  await evaluate(client, `(() => {
    const form = document.querySelector("[data-shell-form='pay-experience']");
    form.countryQuery.value = "Герма";
    form.countryQuery.dispatchEvent(new Event("input", { bubbles: true }));
    form.comment.value = "личный комментарий";
    return "q";
  })()`);
  await waitFor(client, `document.querySelector("[data-shell='experience-country']") ? "de" : ""`);
  await evaluate(client, `document.querySelector("[data-shell='experience-country']").click()`);
  await evaluate(client, `document.querySelector("[data-shell='experience-channel'][data-id='shops']").click()`);
  await evaluate(client, `document.querySelector("[data-shell='experience-result'][data-id='ok']").click()`);
  await evaluate(client, `document.querySelector("[data-shell-form='pay-experience']").requestSubmit()`);
  await waitFor(client, `document.body.innerText.includes("Опыт сохранён на этом устройстве.") ? "saved" : ""`);
  const stored = await evaluate(client, `(() => {
    const rows = JSON.parse(localStorage.getItem("ut.personal.payments") || "[]");
    return rows.map((item) => ({
      system: item.system,
      experience: item.experience,
      pan: item.pan || "",
      cvv: item.cvv || "",
    }));
  })()`);
  const ali = (stored || []).find((item) => item.system === "alipay");
  const union = (stored || []).find((item) => item.system === "unionpay");
  if (!ali || !ali.experience || !ali.experience.countries.includes("Германия") || !ali.experience.channels.includes("shops")) {
    throw new Error(`experience was not stored locally ${JSON.stringify(stored)}`);
  }
  if (!union || union.experience) throw new Error("skipped method gained an experience");
  if ((stored || []).some((item) => item.pan || item.cvv)) throw new Error("card secrets were stored");
  await evaluate(client, `document.querySelector(".ut-nav [data-path='/trip']").click()`);
  await waitFor(client, `document.querySelector("[data-path='/trip/pay']") ? "trip" : ""`);
  await evaluate(client, `document.querySelector("[data-path='/trip/pay']").click()`);
  await waitFor(client, `document.body.innerText.includes("Чем платить") && document.body.innerText.includes("Выберите разделы и поездку") ? "pay" : ""`);
  await assertNoOverflow(client, "trip-pay");
  await evaluate(client, `document.querySelector("[data-path='/guide/china/pay']").click()`);
  await waitFor(client, `document.body.innerText.includes("работает не везде, по отзывам") && document.body.innerText.includes("есть сведения") && document.body.innerText.includes("не сверено") ? "match" : ""`);
  await assertNoOverflow(client, "country-pay");
}

async function waitFor(client, expression) {
  const started = Date.now();
  while (Date.now() - started < 8000) {
    const probe = await client.send("Runtime.evaluate", { expression, returnByValue: true });
    if (probe.result && probe.result.value) return probe.result.value;
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  throw new Error(`timeout: ${expression}`);
}

const profile = await mkdtemp(join(tmpdir(), "shell-console-"));
const chrome = spawn(chromeBin, [
  "--headless=new",
  "--no-sandbox",
  "--disable-gpu",
  "--disable-dev-shm-usage",
  "--remote-debugging-port=0",
  `--user-data-dir=${profile}`,
], { stdio: ["ignore", "ignore", "pipe"] });

let stderr = "";
try {
  const port = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`devtools timeout\n${stderr}`)), 15000);
    chrome.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
      const match = stderr.match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)\//);
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
    chrome.on("exit", (code) => reject(new Error(`chrome exited ${code}\n${stderr}`)));
  });
  const created = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" });
  if (!created.ok) throw new Error(`json/new ${created.status}`);
  const tab = await created.json();
  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve);
    ws.addEventListener("error", () => reject(new Error("websocket failed")));
  });
  const client = cdp(ws);
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await client.send("Page.navigate", { url: `${base}/miniapp/#/home` });
  const home = await waitFor(client, `document.body && document.body.innerText.includes("Шанхай") ? "home" : ""`);
  if (home !== "home") throw new Error("home did not show the demo trip");
  await client.send("Runtime.evaluate", { expression: `document.querySelector("[data-mode='empty']").click()` });
  await waitFor(client, `document.body.innerText.includes("Пока нет поездки") ? "empty" : ""`);
  await client.send("Runtime.evaluate", { expression: `document.querySelector("[data-mode='trip']").click()` });
  await waitFor(client, `document.body.innerText.includes("Москва → Шанхай") ? "trip" : ""`);
  await client.send("Runtime.evaluate", { expression: `document.querySelector(".ut-nav [data-path='/trip']").click()` });
  await waitFor(client, `document.querySelector("[data-shell-screen='trip']") ? "ok" : ""`);
  await exerciseTrip(client);
  await client.send("Runtime.evaluate", { expression: `document.querySelector(".ut-nav [data-path='/guide']").click()` });
  await waitFor(client, `document.body.innerText.includes("официальный источник") ? "ok" : ""`);
  await client.send("Runtime.evaluate", { expression: `document.querySelector("[data-path='/guide/china']").click()` });
  await waitFor(client, `document.querySelector("[data-shell-screen='country']") ? "ok" : ""`);
  await client.send("Runtime.evaluate", { expression: `document.querySelector("[data-shell='back']").click()` });
  await waitFor(client, `document.querySelector("[data-shell-screen='guide']") ? "ok" : ""`);
  await client.send("Runtime.evaluate", { expression: `document.querySelector(".ut-nav [data-path='/profile']").click()` });
  await waitFor(client, `document.querySelector("[data-shell-screen='profile']") ? "ok" : ""`);
  await client.send("Runtime.evaluate", { expression: `document.querySelector("[data-path='/pay']").click()` });
  await waitFor(client, `document.body.innerText.includes("Мои способы оплаты") ? "ok" : ""`);
  await client.send("Runtime.evaluate", { expression: `document.querySelector("[data-shell='back']").click()` });
  await client.send("Runtime.evaluate", { expression: `document.querySelector("[data-path='/settings']").click()` });
  await waitFor(client, `document.querySelector("[data-shell-screen='settings']") ? "ok" : ""`);
  await client.send("Runtime.evaluate", { expression: `document.querySelector(".ut-support").click()` });
  await waitFor(client, `document.body.innerText.includes("Скриншот сохранён") ? "ok" : ""`);
  const hidden = await client.send("Runtime.evaluate", {
    expression: `document.querySelector(".ut-support") ? "shown" : "hidden"`,
    returnByValue: true,
  });
  if (!hidden.result || hidden.result.value !== "hidden") throw new Error("support button stays visible while the toast is open");
  await client.send("Runtime.evaluate", { expression: `document.querySelector("[data-shell='support-close']").click()` });
  await waitFor(client, `document.querySelector(".ut-support") ? "back" : ""`);
  const width = await client.send("Runtime.evaluate", {
    expression: `(() => {
      const doc = document.documentElement;
      const mark = document.querySelector(".ut-support-mark");
      const button = document.querySelector(".ut-support");
      const box = button.getBoundingClientRect();
      const glyph = mark.getBoundingClientRect();
      return {
        scrollWidth: doc.scrollWidth,
        clientWidth: doc.clientWidth,
        width: Math.round(box.width),
        height: Math.round(box.height),
        glyphCenter: Math.round(glyph.left + glyph.width / 2),
        buttonCenter: Math.round(box.left + box.width / 2),
      };
    })()`,
    returnByValue: true,
  });
  const measured = width.result && width.result.value;
  if (!measured || measured.scrollWidth > measured.clientWidth + 1) {
    throw new Error(`horizontal overflow ${JSON.stringify(measured)}`);
  }
  if (measured.width !== 48 || measured.height !== 48) {
    throw new Error(`support button size ${measured.width}x${measured.height}`);
  }
  if (Math.abs(measured.glyphCenter - measured.buttonCenter) > 1) {
    throw new Error(`question mark is off center ${JSON.stringify(measured)}`);
  }
  await exerciseProfile(client);
  await exercisePayments(client);
  if (problems.length) throw new Error(problems.join("\n"));
  console.log(JSON.stringify({ ok: true, ...measured }));
  ws.close();
} finally {
  chrome.kill();
  await new Promise((resolve) => chrome.once("exit", resolve));
  await rm(profile, { recursive: true, force: true }).catch(() => {});
}
