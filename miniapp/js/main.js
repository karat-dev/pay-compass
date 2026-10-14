import { render, parseRoute } from "./screens.js";
import {
  applyTheme,
  countryBySlug,
  isLocalHost,
  mapStart,
  sectionOf,
  stepPosition,
  visibleFacts,
  visibleSteps,
} from "./ui.js";

const state = {
  catalog: null,
  profile: null,
  trip: null,
  progress: {},
  draft: {
    bank_id: "",
    departure_city_id: "",
    destination_slug: "",
    depart_date: "",
    return_date: "",
    consent: false,
  },
  step: 0,
  unverified: {},
  cursor: {},
  openRoute: "",
  query: "",
  sheet: null,
  reportComment: "",
  toast: "",
  message: "",
  failed: "",
  preview: false,
  returnTo: "/trip",
  after: "/trip",
  saveTimer: 0,
  toastTimer: 0,
  scrolledFact: "",
};

const app = document.getElementById("app");

function initData() {
  const tg = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
  if (tg) return tg;
  if (isLocalHost()) return "dev:1001";
  return "";
}

async function getJSON(path) {
  const response = await fetch(path, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Не удалось загрузить данные.");
  return payload;
}

async function postJSON(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData(),
    },
    body: JSON.stringify(body || {}),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Не удалось сохранить.");
  return payload;
}

function showToast(text) {
  state.toast = text;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => {
    state.toast = "";
    draw();
  }, 2400);
}

function applySession(session) {
  state.profile = session.profile;
  state.trip = session.trip;
  state.progress = {};
  for (const item of session.progress || []) state.progress[item.item_id] = item;
  if (state.profile) {
    state.draft.bank_id = state.profile.bank_id || "";
    state.draft.departure_city_id = state.profile.departure_city_id || "";
  }
  if (state.trip) {
    state.draft.destination_slug = state.trip.destination_slug || "";
    state.draft.depart_date = state.trip.depart_date || "";
    state.draft.return_date = state.trip.return_date || "";
  }
}

function findFact(id) {
  const catalog = state.catalog;
  if (!catalog || !id) return null;
  for (const country of catalog.countries) {
    for (const section of country.sections) {
      for (const fact of section.facts) if (fact.id === id) return fact;
      for (const sub of section.subsections || []) {
        for (const fact of sub.facts) if (fact.id === id) return fact;
      }
    }
  }
  for (const instruction of Object.values(catalog.instructions)) {
    for (const step of instruction.steps) if (step.id === id) return step;
  }
  return null;
}

function parentHash(screen) {
  if (screen.name === "search") return state.returnTo || "/trip";
  if (screen.name === "trip-edit") return "/trip";
  if (screen.name === "country") return "/guide";
  if (screen.name === "section") return `/guide/${screen.slug}`;
  if (screen.name === "instruction") {
    const instruction = state.catalog.instructions[screen.instructionId];
    if (instruction && instruction.section) return `/guide/${screen.slug}/${instruction.section}`;
    return `/guide/${screen.slug}`;
  }
  return "/trip";
}

function navigate(hash) {
  const path = hash.startsWith("/") ? hash : `/${hash}`;
  const next = `#${path}`;
  if (location.hash === next) draw();
  else location.hash = next;
}

function readDates() {
  const depart = document.getElementById("depart-date");
  const back = document.getElementById("return-date");
  if (depart) state.draft.depart_date = depart.value;
  if (back) state.draft.return_date = back.value;
}

function completed() {
  return Boolean(state.profile && state.profile.onboarding_completed);
}

function guard() {
  const screen = parseRoute(location.hash);
  if (state.failed || !state.catalog) return;
  if (!completed() && screen.name !== "onboarding") {
    navigate("/onboarding");
    return;
  }
  if (completed() && screen.name === "onboarding" && !state.preview) {
    navigate(state.after || "/trip");
  }
}

function syncDeepFact() {
  const screen = parseRoute(location.hash);
  const fact = screen.params.get("fact");
  if (!fact || state.scrolledFact === `${location.hash}`) return;
  if (screen.name === "instruction") {
    const instruction = state.catalog.instructions[screen.instructionId];
    if (!instruction) return;
    const hidden = (instruction.steps || []).some((step) => step.id === fact && step.hidden);
    if (hidden) state.unverified[`instruction:${instruction.id}`] = true;
    const steps = visibleSteps(instruction, Boolean(state.unverified[`instruction:${instruction.id}`]));
    const index = steps.findIndex((step) => step.id === fact);
    if (index >= 0) state.cursor[instruction.id] = index;
  }
  if (screen.name === "section") {
    const country = countryBySlug(state.catalog, screen.slug);
    const section = sectionOf(country, screen.sectionKey);
    const pools = section ? [section.facts || []].concat((section.subsections || []).map((sub) => sub.facts || [])) : [];
    const hidden = pools.some((pool) => pool.some((item) => item.id === fact && item.hidden));
    if (hidden) state.unverified[`${screen.slug}/${screen.sectionKey}`] = true;
  }
}

function draw() {
  const active = document.activeElement;
  const searching = active && active.id === "search-input";
  const selection = searching ? [active.selectionStart, active.selectionEnd] : null;
  app.innerHTML = render(state);
  const input = document.getElementById("search-input");
  if (input && (searching || parseRoute(location.hash).name === "search")) {
    input.focus();
    if (searching && selection) input.setSelectionRange(selection[0], selection[1]);
  }
  const screen = parseRoute(location.hash);
  const fact = screen.params.get("fact");
  if (fact && state.scrolledFact !== location.hash) {
    const node = document.querySelector(`[data-fact-id="${CSS.escape(fact)}"]`);
    if (node) node.scrollIntoView({ block: "center" });
    state.scrolledFact = location.hash;
  }
}

function seedPreview(name) {
  state.preview = true;
  state.profile = {
    bank_id: "tbank",
    departure_city_id: "mow",
    favorite_countries: ["china", "hong_kong"],
    notify_checklist: true,
    notify_trip: true,
    notify_alerts: false,
    consent_given: true,
    onboarding_completed: name !== "onboarding",
  };
  state.trip = {
    destination_slug: "hong_kong",
    departure_city_id: "mow",
    depart_date: "2026-11-12",
    return_date: "2026-11-20",
  };
  state.draft = {
    bank_id: "tbank",
    departure_city_id: "mow",
    destination_slug: "hong_kong",
    depart_date: "2026-11-12",
    return_date: "2026-11-20",
    consent: false,
  };
  state.step = 0;
  if (name === "instruction") {
    visibleSteps(state.catalog.instructions.wechat_pay, false).slice(0, 2).forEach((step) => {
      state.progress[step.id] = { completed: true, kind: "step", instruction_id: "wechat_pay" };
    });
  }
  if (name === "trip") {
    const section = sectionOf(countryBySlug(state.catalog, "hong_kong"), "1_checklist");
    visibleFacts((section && section.facts) || [], false).filter((fact) => !fact.gap).slice(0, 2).forEach((fact) => {
      state.progress[fact.id] = { completed: true, kind: "checklist" };
    });
  }
}

function previewTarget(name) {
  return {
    onboarding: "/onboarding",
    trip: "/trip",
    country: "/guide/china",
    section: "/guide/china/3_local_wallets_cards",
    instruction: "/guide/china/i/wechat_pay",
    profile: "/profile",
  }[name] || "/trip";
}

async function saveProgress(id, completedFlag, kind, instructionId) {
  state.progress[id] = {
    ...(state.progress[id] || {}),
    item_id: id,
    completed: completedFlag,
    kind,
    instruction_id: instructionId,
  };
  draw();
  if (state.preview) return;
  try {
    const payload = await postJSON("/api/miniapp/progress", {
      item_id: id,
      completed: completedFlag,
      kind,
    });
    state.progress[id] = payload.progress;
  } catch (error) {
    showToast(error.message);
    draw();
  }
}

function queueProfileSave() {
  if (state.preview) return;
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(async () => {
    try {
      const payload = await postJSON("/api/miniapp/profile", {
        ...state.profile,
        consent_given: true,
        onboarding_completed: true,
      });
      state.profile = payload.profile;
      showToast("Сохранили");
      draw();
    } catch (error) {
      state.message = error.message;
      draw();
    }
  }, 250);
}

async function finishOnboarding() {
  readDates();
  if (!state.draft.depart_date) {
    state.message = "Укажите дату вылета.";
    draw();
    return;
  }
  if (!state.draft.consent) {
    state.message = "Нужно согласие на обработку данных.";
    draw();
    return;
  }
  const profile = {
    bank_id: state.draft.bank_id,
    departure_city_id: state.draft.departure_city_id,
    favorite_countries: [state.draft.destination_slug],
    notify_checklist: true,
    notify_trip: true,
    notify_alerts: false,
    consent_given: true,
    onboarding_completed: true,
  };
  const trip = {
    destination_slug: state.draft.destination_slug,
    departure_city_id: state.draft.departure_city_id,
    depart_date: state.draft.depart_date,
    return_date: state.draft.return_date || null,
  };
  if (state.preview) {
    state.profile = profile;
    state.trip = trip;
    navigate(state.after || "/trip");
    return;
  }
  try {
    const payload = await postJSON("/api/miniapp/onboarding", { profile, trip });
    state.profile = payload.profile;
    state.trip = payload.trip;
    state.message = "";
    navigate(state.after || "/trip");
  } catch (error) {
    state.message = error.message;
    draw();
  }
}

function openExternal(url) {
  if (!url || !/^https?:\/\//i.test(url)) return;
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg && tg.openLink) tg.openLink(url);
  else window.open(url, "_blank", "noopener");
}

app.addEventListener("click", (event) => {
  const el = event.target.closest("[data-action]");
  if (!el || el.hasAttribute("disabled")) return;
  const action = el.dataset.action;
  if (el.tagName === "A") event.preventDefault();
  if (action === "close-sheet") {
    if (el.classList.contains("sheet-back") && event.target.closest(".sheet")) return;
    state.sheet = null;
    draw();
    return;
  }
  if (action === "link") {
    openExternal(el.dataset.url || el.getAttribute("href"));
    return;
  }
  if (action === "tab") {
    navigate(`/${el.dataset.tab}`);
    return;
  }
  if (action === "back") {
    navigate(parentHash(parseRoute(location.hash)));
    return;
  }
  if (action === "search") {
    state.returnTo = location.hash.replace(/^#/, "") || "/trip";
    state.query = "";
    navigate("/search");
    return;
  }
  if (action === "choice") {
    const screen = parseRoute(location.hash);
    const target = screen.name === "profile" ? state.profile : state.draft;
    if (el.dataset.group === "bank") target.bank_id = el.dataset.id;
    if (el.dataset.group === "city") target.departure_city_id = el.dataset.id;
    if (el.dataset.group === "country") target.destination_slug = el.dataset.id;
    state.message = "";
    if (screen.name === "profile") queueProfileSave();
    draw();
    return;
  }
  if (action === "onboard-back") {
    state.step = Math.max(0, state.step - 1);
    state.message = "";
    draw();
    return;
  }
  if (action === "onboard-next") {
    readDates();
    if (state.step < 2) {
      state.step += 1;
      state.message = "";
      draw();
      return;
    }
    finishOnboarding();
    return;
  }
  if (action === "consent") {
    state.draft.consent = !state.draft.consent;
    state.message = "";
    draw();
    return;
  }
  if (action === "privacy") {
    state.sheet = { type: "privacy" };
    draw();
    return;
  }
  if (action === "edit-trip") {
    state.draft.destination_slug = state.trip.destination_slug;
    state.draft.depart_date = state.trip.depart_date || "";
    state.draft.return_date = state.trip.return_date || "";
    state.message = "";
    navigate("/trip/edit");
    return;
  }
  if (action === "save-trip") {
    readDates();
    const trip = {
      destination_slug: state.draft.destination_slug,
      departure_city_id: state.profile.departure_city_id,
      depart_date: state.draft.depart_date || null,
      return_date: state.draft.return_date || null,
    };
    if (state.preview) {
      state.trip = { ...state.trip, ...trip };
      navigate("/trip");
      return;
    }
    postJSON("/api/miniapp/trip", trip).then((payload) => {
      state.trip = payload.trip;
      navigate("/trip");
    }).catch((error) => {
      state.message = error.message;
      draw();
    });
    return;
  }
  if (action === "open-country") {
    navigate(`/guide/${el.dataset.slug}`);
    return;
  }
  if (action === "open-section") {
    navigate(`/guide/${el.dataset.slug}/${el.dataset.key}`);
    return;
  }
  if (action === "open-instruction") {
    navigate(`/guide/${el.dataset.slug}/i/${el.dataset.id}`);
    return;
  }
  if (action === "unverified") {
    state.unverified[el.dataset.scope] = !state.unverified[el.dataset.scope];
    draw();
    return;
  }
  if (action === "route-section") {
    state.openRoute = state.openRoute === el.dataset.id ? "" : el.dataset.id;
    draw();
    return;
  }
  if (action === "check") {
    const current = Boolean(state.progress[el.dataset.id] && state.progress[el.dataset.id].completed);
    saveProgress(el.dataset.id, !current, "checklist", null);
    return;
  }
  if (action === "step-done") {
    const current = Boolean(state.progress[el.dataset.id] && state.progress[el.dataset.id].completed);
    saveProgress(el.dataset.id, !current, "step", el.dataset.instruction);
    return;
  }
  if (action === "step-move") {
    const screen = parseRoute(location.hash);
    const instruction = state.catalog.instructions[screen.instructionId];
    const steps = visibleSteps(instruction, Boolean(state.unverified[`instruction:${instruction.id}`]));
    const index = stepPosition(steps, state.progress, state.cursor[instruction.id]);
    const next = Math.max(0, Math.min(steps.length - 1, index + Number(el.dataset.dir)));
    state.cursor[instruction.id] = next;
    draw();
    return;
  }
  if (action === "report") {
    state.sheet = { type: "report", fact: findFact(el.dataset.id) };
    state.reportComment = "";
    draw();
    return;
  }
  if (action === "submit-report") {
    const fact = state.sheet && state.sheet.fact;
    const field = document.getElementById("report-comment");
    const comment = field ? field.value : "";
    if (!fact) return;
    if (state.preview) {
      state.sheet = null;
      showToast("Сохранили. Проверим этот факт.");
      draw();
      return;
    }
    postJSON("/api/miniapp/report", { fact_id: fact.id, comment }).then(() => {
      state.sheet = null;
      showToast("Сохранили. Проверим этот факт.");
      draw();
    }).catch((error) => {
      showToast(error.message);
      draw();
    });
    return;
  }
  if (action === "fav") {
    const list = new Set(state.profile.favorite_countries || []);
    if (list.has(el.dataset.slug)) list.delete(el.dataset.slug);
    else list.add(el.dataset.slug);
    state.profile.favorite_countries = [...list];
    queueProfileSave();
    draw();
    return;
  }
  if (action === "notify") {
    const key = el.dataset.key;
    state.profile[key] = !state.profile[key];
    queueProfileSave();
    draw();
    return;
  }
  if (action === "open-result") {
    if (el.dataset.hidden === "1") {
      if (el.dataset.instruction) state.unverified[`instruction:${el.dataset.instruction}`] = true;
      if (el.dataset.key) state.unverified[`${el.dataset.slug}/${el.dataset.key}`] = true;
    }
    navigate(el.dataset.hash);
  }
});

app.addEventListener("input", (event) => {
  if (event.target.id === "search-input") {
    state.query = event.target.value;
    draw();
  }
});

app.addEventListener("change", (event) => {
  const field = event.target.dataset.field;
  if (field === "depart_date" || field === "return_date") {
    state.draft[field === "depart_date" ? "depart_date" : "return_date"] = event.target.value;
    state.message = "";
    draw();
  }
});

window.addEventListener("hashchange", () => {
  syncDeepFact();
  guard();
  draw();
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.sheet) {
    state.sheet = null;
    draw();
  }
});

async function boot() {
  applyTheme();
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    if (tg.ready) tg.ready();
    if (tg.expand) tg.expand();
    if (tg.onEvent) tg.onEvent("themeChanged", () => { applyTheme(); draw(); });
  }
  try {
    state.catalog = await getJSON("/api/catalog");
  } catch (error) {
    state.failed = "Не удалось загрузить справочник. Запустите python3 -m miniapp и обновите страницу.";
    draw();
    return;
  }
  const params = new URLSearchParams(location.search);
  const preview = params.get("preview");
  if (preview && isLocalHost()) {
    seedPreview(preview);
    navigate(previewTarget(preview));
    return;
  }
  try {
    applySession(await postJSON("/api/miniapp/session", {}));
  } catch (error) {
    state.failed = error.message;
    draw();
    return;
  }
  const start = mapStart(state.catalog, params.get("startapp") || params.get("tgWebAppStartParam") || "");
  if (start) state.after = start;
  if (!location.hash || location.hash === "#") {
    navigate(completed() ? (start || "/trip") : "/onboarding");
    return;
  }
  syncDeepFact();
  guard();
  draw();
}

boot();
