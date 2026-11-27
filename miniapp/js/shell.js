/** Boots the Mini App shell: tabs, inner screens, support toast, on-device personal data. */

import { PERSONAL_SECTIONS, createPersonalStore } from "./personal_store.js";
import { backTarget, parseShellRoute, readTripForm } from "./shell_router.js";
import { DEMO_TRIP, defaultSettings, renderShell } from "./shell_screens.js";

function outsideTelegram() {
  const tg = globalThis.Telegram && globalThis.Telegram.WebApp;
  const init = tg && typeof tg.initData === "string" ? tg.initData : "";
  return !init;
}

function telegram() {
  return (globalThis.Telegram && globalThis.Telegram.WebApp) || null;
}

export async function startShell(root) {
  const outside = outsideTelegram();
  const store = createPersonalStore();
  const tripsRaw = await store.read("trips");
  let trips = Array.isArray(tripsRaw) ? tripsRaw : null;
  if (outside && trips == null) {
    trips = [{ ...DEMO_TRIP }];
    await store.write("trips", trips);
  }
  if (!Array.isArray(trips)) trips = [];
  const settingsRaw = await store.read("settings");
  const passport = await store.read("passport");
  const loyaltyRaw = await store.read("loyalty");
  const paymentsRaw = await store.read("payments");
  const state = {
    route: parseShellRoute(location.hash),
    trips,
    settings: { ...defaultSettings(), ...(settingsRaw && typeof settingsRaw === "object" ? settingsRaw : {}) },
    passport: passport && typeof passport === "object" ? passport : null,
    loyalty: Array.isArray(loyaltyRaw) ? loyaltyRaw : [],
    payments: Array.isArray(paymentsRaw) ? paymentsRaw : [],
    query: "",
    outside,
    supportOpen: false,
    supportReported: false,
    sheet: "",
    promoOpen: false,
    payGroup: "system",
    notice: "",
    focusSearch: false,
  };
  let keepNotice = false;
  if (document.body) document.body.classList.add("ut-shell");
  prepareTelegram();

  function draw(scroll) {
    state.route = parseShellRoute(location.hash);
    root.innerHTML = renderShell(state);
    syncBack();
    if (scroll) window.scrollTo(0, 0);
    if (state.focusSearch) {
      const field = root.querySelector("[data-shell-field='search']");
      if (field) {
        field.focus();
        const pos = field.value.length;
        if (field.setSelectionRange) field.setSelectionRange(pos, pos);
      }
      state.focusSearch = false;
    }
  }

  function go(path, notice) {
    if (notice) {
      state.notice = notice;
      keepNotice = true;
    }
    const clean = path.startsWith("/") ? path : `/${path}`;
    const next = `#${clean}`;
    if (location.hash === next) {
      keepNotice = false;
      draw(false);
      return;
    }
    location.hash = next;
  }

  function syncBack() {
    const back = telegram() && telegram().BackButton;
    if (!back) return;
    if (state.sheet || state.supportOpen || backTarget(state.route)) {
      if (back.show) back.show();
    } else if (back.hide) back.hide();
  }

  function prepareTelegram() {
    const tg = telegram();
    if (!tg) return;
    try { if (tg.ready) tg.ready(); } catch { /* desktop preview */ }
    try { if (tg.expand) tg.expand(); } catch { /* desktop preview */ }
    try { if (tg.setHeaderColor) tg.setHeaderColor("#eef2ff"); } catch { /* desktop preview */ }
    try { if (tg.setBackgroundColor) tg.setBackgroundColor("#eef2ff"); } catch { /* desktop preview */ }
    const back = tg.BackButton;
    if (back && back.onClick) {
      back.onClick(() => {
        if (state.sheet) {
          state.sheet = "";
          draw(false);
          return;
        }
        if (state.supportOpen) {
          state.supportOpen = false;
          state.supportReported = false;
          draw(false);
          return;
        }
        const target = backTarget(state.route);
        if (target) go(target);
      });
    }
  }

  async function clearSections(sections) {
    await Promise.all(sections.map((section) => store.remove(section)));
  }

  root.addEventListener("click", (event) => {
    const el = event.target.closest("[data-shell]");
    if (!el || !root.contains(el)) return;
    if (el.dataset.shellField) return;
    event.preventDefault();
    handle(el).catch(() => {
      state.notice = "Не удалось сохранить данные на этом устройстве. Обновите страницу.";
      draw(false);
    });
  });

  root.addEventListener("input", (event) => {
    const field = event.target;
    if (!field || field.dataset.shellField !== "search") return;
    state.query = field.value;
    state.focusSearch = true;
    draw(false);
  });

  root.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form || form.dataset.shellForm !== "trip") return;
    event.preventDefault();
    const parsed = readTripForm({
      origin: form.origin && form.origin.value,
      destination: form.destination && form.destination.value,
      depart: form.depart && form.depart.value,
      ret: form.ret && form.ret.value,
    });
    if (parsed.error) {
      state.notice = parsed.error;
      draw(false);
      return;
    }
    state.trips = [parsed.trip];
    store.write("trips", state.trips).then(() => {
      go("/home", "Поездка сохранена на этом устройстве.");
    }).catch(() => {
      state.notice = "Не удалось сохранить данные на этом устройстве. Обновите страницу.";
      draw(false);
    });
  });

  window.addEventListener("hashchange", () => {
    state.query = "";
    state.supportOpen = false;
    state.supportReported = false;
    state.sheet = "";
    if (!keepNotice) state.notice = "";
    keepNotice = false;
    draw(true);
  });

  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (state.sheet) {
      state.sheet = "";
      draw(false);
      return;
    }
    if (state.supportOpen) {
      state.supportOpen = false;
      state.supportReported = false;
      draw(false);
    }
  });

  async function handle(el) {
    const action = el.dataset.shell;
    if (action === "route") {
      go(el.dataset.path || "/home");
      return;
    }
    if (action === "back") {
      const target = backTarget(state.route);
      if (target) go(target);
      return;
    }
    if (action === "demo") {
      state.trips = el.dataset.mode === "empty" ? [] : [{ ...DEMO_TRIP }];
      await store.write("trips", state.trips);
      state.notice = "";
      draw(false);
      return;
    }
    if (action === "support") {
      state.supportOpen = true;
      state.supportReported = false;
      state.sheet = "";
      draw(false);
      return;
    }
    if (action === "support-close") {
      state.supportOpen = false;
      state.supportReported = false;
      draw(false);
      return;
    }
    if (action === "support-report") {
      state.supportReported = true;
      draw(false);
      return;
    }
    if (action === "sos") {
      state.sheet = "sos";
      state.supportOpen = false;
      draw(false);
      return;
    }
    if (action === "sheet-close") {
      state.sheet = "";
      draw(false);
      return;
    }
    if (action === "revoke") {
      state.sheet = state.settings.consentAt ? "revoke" : "";
      state.notice = state.settings.consentAt ? "" : "Согласие ещё не дано. Мы спросим его, когда вы добавите паспорт или способы оплаты.";
      draw(false);
      return;
    }
    if (action === "delete") {
      state.sheet = "delete";
      draw(false);
      return;
    }
    if (action === "sheet-ok") {
      if (state.sheet === "delete") {
        await clearSections(PERSONAL_SECTIONS);
        state.trips = [];
        state.passport = null;
        state.loyalty = [];
        state.payments = [];
        state.settings = defaultSettings();
        state.sheet = "";
        go("/home", "Данные на этом устройстве удалены.");
        return;
      }
      if (state.sheet === "revoke") {
        await clearSections(["passport", "payments", "loyalty"]);
        state.passport = null;
        state.payments = [];
        state.loyalty = [];
        state.settings = { ...state.settings, consentAt: "" };
        await store.write("settings", state.settings);
        state.sheet = "";
        state.notice = "Согласие отозвано. Поездки остаются на этом устройстве.";
        draw(false);
        return;
      }
      state.sheet = "";
      draw(false);
      return;
    }
    if (action === "promo") {
      state.promoOpen = !state.promoOpen;
      draw(false);
      return;
    }
    if (action === "pay-group") {
      state.payGroup = el.dataset.group || "system";
      draw(false);
      return;
    }
    if (action === "save-trip") {
      await store.write("trips", state.trips);
      state.notice = "Поездка сохранена на этом устройстве.";
      draw(false);
      return;
    }
    if (action === "soon") {
      state.notice = el.dataset.text || "Этот раздел подключим следующим шагом.";
      draw(false);
    }
  }

  const next = location.hash.startsWith("#/") ? location.hash : "#/home";
  if (location.hash !== next) location.hash = next;
  else draw(false);
}
