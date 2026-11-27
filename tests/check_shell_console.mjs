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
