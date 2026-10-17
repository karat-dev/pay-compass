import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const base = process.argv[2];
const chromeBin = process.argv[3];

function cdp(ws) {
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
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

const profile = await mkdtemp(join(tmpdir(), "country-width-"));
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
  await client.send("Network.enable");
  await client.send("Network.setCacheDisabled", { cacheDisabled: true });
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 320,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await client.send("Page.navigate", { url: `${base}/miniapp/?preview=country&theme=dark` });
  const started = Date.now();
  let ready = false;
  while (Date.now() - started < 12000) {
    const probe = await client.send("Runtime.evaluate", {
      expression: `document.querySelector("[data-ready='1']") ? "ready" : ""`,
      returnByValue: true,
    });
    if (probe.result && probe.result.value === "ready") {
      ready = true;
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  if (!ready) throw new Error("country preview did not render");
  await client.send("Runtime.evaluate", { expression: `location.hash = "#/guide/georgia"` });
  await new Promise((resolve) => setTimeout(resolve, 80));
  const measured = await client.send("Runtime.evaluate", {
    expression: `(() => {
      const doc = document.documentElement;
      const title = [...document.querySelectorAll(".section-tile strong")].find((node) => node.textContent.includes("Мошенничество"));
      const box = title ? title.getBoundingClientRect() : null;
      return {
        screen: document.querySelector("[data-screen]")?.dataset.screen || "",
        clientWidth: doc.clientWidth,
        scrollWidth: doc.scrollWidth,
        titleRight: box ? box.right : null,
      };
    })()`,
    returnByValue: true,
  });
  const value = measured.result.value;
  console.log(JSON.stringify(value));
  if (!value || value.screen !== "country" || value.scrollWidth > value.clientWidth + 1) {
    process.exitCode = 1;
  }
  if (!value || value.titleRight == null || value.titleRight > value.clientWidth + 1) {
    process.exitCode = 1;
  }
  ws.close();
} finally {
  chrome.kill();
  await new Promise((resolve) => chrome.once("exit", resolve));
  await rm(profile, { recursive: true, force: true }).catch(() => {});
}
