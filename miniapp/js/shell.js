/** Boots the Mini App shell: tabs, inner screens, support toast, on-device personal data. */

import { PERSONAL_SECTIONS, createPersonalStore } from "./personal_store.js";
import { applyChecks, assessFlightRows, tripChecks } from "./trip_flow.js";
import { backTarget, parseShellRoute, readTripEdit, readTripForm } from "./shell_router.js";
import { DEMO_TRIP, defaultSettings, formatStay, renderShell } from "./shell_screens.js";

function cloneDemo() {
  return {
    ...DEMO_TRIP,
    checks: Array.isArray(DEMO_TRIP.checks) ? [...DEMO_TRIP.checks] : [],
    flights: [],
  };
}

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
    trips = [cloneDemo()];
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
    flightDraft: null,
    flightFocus: null,
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
    if (state.flightFocus) {
      const focus = state.flightFocus;
      const field = root.querySelector(`[data-shell-field="${focus.field}"][data-index="${focus.index}"]`);
      if (field) {
        field.focus();
        if (field.setSelectionRange && focus.start != null && focus.end != null) {
          field.setSelectionRange(focus.start, focus.end);
        }
      }
      state.flightFocus = null;
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
    if (!field || !field.dataset) return;
    if (field.dataset.shellField === "search") {
      state.query = field.value;
      state.focusSearch = true;
      draw(false);
      return;
    }
    if (field.dataset.shellField !== "flight-number" && field.dataset.shellField !== "flight-date") return;
    const index = Number(field.dataset.index);
    if (!state.flightDraft || !state.flightDraft[index]) return;
    const key = field.dataset.shellField === "flight-number" ? "number" : "date";
    state.flightDraft[index] = { ...state.flightDraft[index], [key]: field.value, legId: "" };
    state.flightFocus = {
      index,
      field: field.dataset.shellField,
      start: field.selectionStart,
      end: field.selectionEnd,
    };
    draw(false);
  });

  root.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form || !form.dataset) return;
    if (form.dataset.shellForm === "trip") {
      event.preventDefault();
      const parsed = readTripForm({
        origin: form.origin && form.origin.value,
        destination: form.destination && form.destination.value,
        country: form.country && form.country.value,
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
      return;
    }
    if (form.dataset.shellForm !== "trip-edit") return;
    event.preventDefault();
    const current = state.trips[0];
    if (!current) return;
    const parsed = readTripEdit({
      origin: form.origin && form.origin.value,
      destination: form.destination && form.destination.value,
      country: form.country && form.country.value,
      depart: form.depart && form.depart.value,
      ret: form.ret && form.ret.value,
    }, current);
    if (parsed.error) {
      state.notice = parsed.error;
      draw(false);
      return;
    }
    state.trips = [parsed.trip, ...state.trips.slice(1)];
    store.write("trips", state.trips).then(() => {
      go("/trip", "Поездка сохранена на этом устройстве.");
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
    state.flightDraft = null;
    state.flightFocus = null;
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
      state.trips = el.dataset.mode === "empty" ? [] : [cloneDemo()];
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
    if (action === "check") {
      const trip = state.trips[0];
      if (!trip) return;
      const id = el.dataset.id || "";
      const current = tripChecks(trip);
      const next = current.includes(id) ? current.filter((item) => item !== id) : current.concat(id);
      state.trips = [applyChecks(trip, next), ...state.trips.slice(1)];
      await store.write("trips", state.trips);
      draw(false);
      return;
    }
    if (action === "flight-add-row") {
      const draft = Array.isArray(state.flightDraft) ? state.flightDraft : [];
      state.flightDraft = draft.concat([{ number: "", date: "", legId: "" }]);
      draw(false);
      return;
    }
    if (action === "flight-drop") {
      const index = Number(el.dataset.index);
      if (Array.isArray(state.flightDraft) && index > 1) {
        state.flightDraft = state.flightDraft.filter((_, item) => item !== index);
        draw(false);
      }
      return;
    }
    if (action === "flight-leg") {
      const index = Number(el.dataset.index);
      if (state.flightDraft && state.flightDraft[index]) {
        state.flightDraft[index] = { ...state.flightDraft[index], legId: el.dataset.leg || "" };
        draw(false);
      }
      return;
    }
    if (action === "flight-delete") {
      const trip = state.trips[0];
      if (!trip) return;
      const flights = (Array.isArray(trip.flights) ? trip.flights : []).filter((item) => item.id !== el.dataset.id);
      state.trips = [{ ...trip, flights }, ...state.trips.slice(1)];
      await store.write("trips", state.trips);
      state.notice = "Рейс удалён на этом устройстве.";
      draw(false);
      return;
    }
    if (action === "flight-save") {
      const trip = state.trips[0];
      if (!trip) return;
      const assessed = assessFlightRows(state.flightDraft, trip, formatStay(trip.depart, trip.ret));
      if (!assessed.canSave) return;
      const stamp = Date.now().toString(36);
      const added = assessed.ready.map((item, index) => ({
        ...item,
        id: `flt-${item.number.replace(/\s+/g, "")}-${item.date}-${item.legId || "open"}-${stamp}-${index}`,
      }));
      const flights = (Array.isArray(trip.flights) ? trip.flights : []).concat(added);
      state.trips = [{ ...trip, flights }, ...state.trips.slice(1)];
      await store.write("trips", state.trips);
      state.flightDraft = null;
      go("/trip", added.length > 1 ? "Рейсы сохранены на этом устройстве." : "Рейс сохранён на этом устройстве.");
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
