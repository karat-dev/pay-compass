/** Boots the Mini App shell: tabs, inner screens, support toast, on-device personal data. */

import { programById } from "./loyalty_catalog.js";
import { PERSONAL_SECTIONS, createPersonalStore } from "./personal_store.js";
import {
  bookingName,
  cycleSetting,
  filterLatinInput,
  readLoyaltyCard,
  readPassport,
  revokedPersonal,
  todayIso,
  toggleNameOrder,
} from "./profile_flow.js";
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
  let keepDraft = false;
  if (document.body) document.body.classList.add("ut-shell");
  prepareTelegram();

  function draw(scroll) {
    state.route = parseShellRoute(location.hash);
    if (document.documentElement) {
      document.documentElement.dataset.utTheme = state.settings.theme === "Тёмная" ? "dark" : "light";
    }
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
      keepDraft = false;
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
    if (field.dataset.shellField === "latin") {
      const next = filterLatinInput(field.value);
      if (next !== field.value) {
        const end = field.selectionEnd;
        field.value = next;
        if (field.setSelectionRange && end != null) field.setSelectionRange(Math.min(next.length, end), Math.min(next.length, end));
      }
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

  root.addEventListener("change", (event) => {
    const field = event.target;
    if (!field || (field.name !== "citizenship" && field.name !== "programId")) return;
    syncDrafts();
    draw(false);
  });

  root.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form || !form.dataset) return;
    if (form.dataset.shellForm === "passport") {
      event.preventDefault();
      savePassport(form);
      return;
    }
    if (form.dataset.shellForm === "loyalty-add") {
      event.preventDefault();
      saveLoyalty(form);
      return;
    }
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
    state.loyaltyOpenId = "";
    state.alliance = "";
    if (!keepDraft) {
      state.passportDraft = null;
      state.loyaltyDraft = null;
      state.editingId = "";
    }
    keepDraft = false;
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

  function namedValues(form) {
    const values = {};
    for (const field of form.elements) {
      if (!field.name) continue;
      values[field.name] = field.type === "checkbox" ? Boolean(field.checked) : field.value;
    }
    return values;
  }

  function syncDrafts() {
    const passport = root.querySelector("[data-shell-form='passport']");
    if (passport) {
      const errors = (state.passportDraft && state.passportDraft.errors) || {};
      state.passportDraft = { ...namedValues(passport), errors };
    }
    const loyalty = root.querySelector("[data-shell-form='loyalty-add']");
    if (loyalty) {
      const errors = (state.loyaltyDraft && state.loyaltyDraft.errors) || {};
      state.loyaltyDraft = { ...namedValues(loyalty), errors };
    }
  }

  function rememberConsent() {
    if (state.settings.consentAt) return Promise.resolve();
    state.settings = { ...state.settings, consentAt: todayIso() };
    return store.write("settings", state.settings);
  }

  async function copyText(text) {
    const value = String(text || "");
    try {
      if (value && navigator.clipboard && navigator.clipboard.writeText) await navigator.clipboard.writeText(value);
    } catch {
      /* the value stays on this device */
    }
    state.notice = value ? "Скопировано на этом устройстве." : "Нечего копировать.";
    draw(false);
  }

  function savePassport(form) {
    const values = namedValues(form);
    const parsed = readPassport(values, { today: todayIso(), needConsent: !state.settings.consentAt });
    if (parsed.errors) {
      state.passportDraft = { ...values, errors: parsed.errors };
      state.notice = "";
      draw(false);
      return;
    }
    state.passport = parsed.passport;
    state.passportDraft = null;
    store.write("passport", state.passport).then(() => rememberConsent()).then(() => {
      go("/profile", "Паспорт сохранён на этом устройстве.");
    }).catch(() => {
      state.notice = "Не удалось сохранить данные на этом устройстве. Обновите страницу.";
      draw(false);
    });
  }

  function saveLoyalty(form) {
    const values = namedValues(form);
    const program = values.programId && values.programId !== "custom" ? programById(values.programId) : null;
    const parsed = readLoyaltyCard(values, {
      program,
      existing: state.loyalty,
      editingId: state.editingId,
      needConsent: !state.settings.consentAt,
    });
    if (parsed.errors) {
      state.loyaltyDraft = { ...values, errors: parsed.errors };
      state.notice = "";
      draw(false);
      return;
    }
    const card = { ...parsed.card, id: state.editingId || `card-${Date.now().toString(36)}` };
    state.loyalty = state.editingId
      ? state.loyalty.map((item) => (item.id === card.id ? card : item))
      : state.loyalty.concat(card);
    state.loyaltyDraft = null;
    state.editingId = "";
    store.write("loyalty", state.loyalty).then(() => rememberConsent()).then(() => {
      go("/loyalty", "Карта сохранена на этом устройстве.");
    }).catch(() => {
      state.notice = "Не удалось сохранить данные на этом устройстве. Обновите страницу.";
      draw(false);
    });
  }

  async function handle(el) {
    syncDrafts();
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
        const next = revokedPersonal(state);
        await clearSections(["passport", "payments", "loyalty"]);
        state.passport = next.passport;
        state.payments = next.payments;
        state.loyalty = next.loyalty;
        state.trips = next.trips;
        state.settings = next.settings;
        await store.write("settings", state.settings);
        state.sheet = "";
        state.passportDraft = null;
        state.loyaltyDraft = null;
        state.editingId = "";
        go("/profile", "Согласие отозвано. Поездки остаются на этом устройстве.");
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
      return;
    }
    if (action === "setting") {
      const key = el.dataset.key || "";
      const next = cycleSetting(state.settings, key);
      if (key === "language" && next.language === state.settings.language) {
        state.notice = "Сейчас доступен русский язык.";
      }
      state.settings = next;
      await store.write("settings", state.settings);
      draw(false);
      return;
    }
    if (action === "alliance") {
      const id = el.dataset.id || "";
      state.alliance = state.alliance === id ? "" : id;
      draw(false);
      return;
    }
    if (action === "loyalty-open") {
      const id = el.dataset.id || "";
      const cards = state.loyalty || [];
      const current = !state.loyaltyOpenId && cards.length ? cards[cards.length - 1].id : state.loyaltyOpenId;
      const open = current === "none" ? "" : current;
      state.loyaltyOpenId = open === id ? "none" : id;
      draw(false);
      return;
    }
    if (action === "loyalty-edit") {
      const card = state.loyalty.find((item) => item.id === el.dataset.id);
      if (!card) return;
      state.editingId = card.id;
      state.loyaltyDraft = {
        programId: card.programId || "",
        custom: card.programId === "custom" ? (card.program || "") : "",
        number: card.number || "",
        title: card.title && card.title !== card.program ? card.title : "",
        given: card.given || "",
        surname: card.surname || "",
        note: card.note || "",
        consent: true,
        errors: {},
      };
      keepDraft = true;
      go("/loyalty/add");
      return;
    }
    if (action === "loyalty-delete") {
      state.loyalty = state.loyalty.filter((item) => item.id !== el.dataset.id);
      state.loyaltyOpenId = "";
      await store.write("loyalty", state.loyalty);
      state.notice = "Карта удалена с этого устройства.";
      draw(false);
      return;
    }
    if (action === "passport-clear") {
      await store.remove("passport");
      state.passport = null;
      state.passportDraft = null;
      go("/profile", "Данные паспорта удалены с этого устройства.");
      return;
    }
    if (action === "name-order") {
      state.settings = toggleNameOrder(state.settings);
      await store.write("settings", state.settings);
      draw(false);
      return;
    }
    if (action === "copy-field") {
      const field = root.querySelector(`[name="${el.dataset.copyFrom || ""}"]`);
      await copyText(field ? field.value : "");
      return;
    }
    if (action === "copy-card" || action === "copy-name") {
      const card = state.loyalty.find((item) => item.id === el.dataset.id);
      if (!card) return;
      if (action === "copy-card") {
        await copyText(card.number || "");
        return;
      }
      const part = el.dataset.part || "full";
      const text = part === "given" ? card.given : part === "surname" ? card.surname : bookingName(card.given, card.surname, state.settings.nameOrder);
      await copyText(text);
    }
  }

  const next = location.hash.startsWith("#/") ? location.hash : "#/home";
  if (location.hash !== next) location.hash = next;
  else draw(false);
}
