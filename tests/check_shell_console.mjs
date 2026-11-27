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
  if (problems.length) throw new Error(problems.join("\n"));
  console.log(JSON.stringify({ ok: true, ...measured }));
  ws.close();
} finally {
  chrome.kill();
  await new Promise((resolve) => chrome.once("exit", resolve));
  await rm(profile, { recursive: true, force: true }).catch(() => {});
}
