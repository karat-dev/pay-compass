import { afterPick, backPlan, beginIntroReplay, bootTarget, introExit } from "./flow.js";
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
  failedTitle: "",
  introSeen: false,
  introStep: 0,
  preview: false,
  returnTo: "/trip",
  after: "",
  saveTimer: 0,
  toastTimer: 0,
  scrolledFact: "",
};

const app = document.getElementById("app");

let cachedInitData = "";

function launchInitData() {
  const sources = [location.hash || "", location.search || ""];
  for (const source of sources) {
    const raw = source.charAt(0) === "#" || source.charAt(0) === "?" ? source.slice(1) : source;
    if (!raw || raw.charAt(0) === "/") continue;
    const value = new URLSearchParams(raw).get("tgWebAppData");
    if (value) return value;
  }
  return "";
}

function initData() {
  if (cachedInitData) return cachedInitData;
  const tg = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
  const value = tg || launchInitData() || (isLocalHost() ? "dev:1001" : "");
  if (value) cachedInitData = value;
  return value;
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

function emptyProfile(introSeen) {
  return {
    bank_id: "",
    departure_city_id: "",
    favorite_countries: [],
    notify_checklist: true,
    notify_trip: true,
    notify_alerts: false,
    consent_given: false,
    onboarding_completed: false,
    intro_seen: Boolean(introSeen),
    citizenship: "ru",
  };
}

function applySession(session) {
  state.introSeen = Boolean(session.intro_seen || (session.profile && session.profile.intro_seen));
  state.profile = session.profile || emptyProfile(state.introSeen);
  state.profile.intro_seen = state.introSeen;
  if (!state.profile.citizenship) state.profile.citizenship = "ru";
  state.trip = session.trip;
  state.progress = {};
  for (const item of session.progress || []) state.progress[item.item_id] = item;
  if (state.profile.bank_id) state.draft.bank_id = state.profile.bank_id;
  if (state.profile.departure_city_id) state.draft.departure_city_id = state.profile.departure_city_id;
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

const appStack = [];
let navLock = 0;

function pathFromHash(hash) {
  const clean = String(hash || "").replace(/^#/, "");
  if (!clean) return "/trip";
  return clean.startsWith("/") ? clean : `/${clean}`;
}

function currentPlan() {
  const screen = parseRoute(location.hash);
  let instructionIndex = 0;
  let instructionSection = "";
  if (screen.name === "instruction" && state.catalog) {
    const instruction = state.catalog.instructions[screen.instructionId];
    instructionSection = (instruction && instruction.section) || "";
    const steps = visibleSteps(instruction, Boolean(state.unverified[`instruction:${instruction && instruction.id}`]));
    instructionIndex = stepPosition(steps, state.progress, instruction && state.cursor[instruction.id]);
  }
  return backPlan({
    screen: Object.assign({}, screen, { instructionSection }),
    stackDepth: appStack.length || 1,
    introSeen: state.introSeen,
    introStep: state.introStep || 0,
    pickStep: state.step || 0,
    instructionIndex,
    openRoute: state.openRoute || "",
    sheet: Boolean(state.sheet),
    returnTo: state.returnTo || "",
  });
}

function syncBackButton() {
  const button = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.BackButton;
  const plan = currentPlan();
  document.documentElement.dataset.tgBack = plan.type === "none" ? "0" : "1";
  if (!button) return;
  if (plan.type === "none") {
    if (button.hide) button.hide();
  } else if (button.show) button.show();
}

function wireBackButton() {
  const button = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.BackButton;
  if (!button || button.__wired || !button.onClick) return;
  button.onClick(() => goBack());
  button.__wired = true;
}

function navigate(hash, mode) {
  const path = pathFromHash(hash);
  const next = `#${path}`;
  const same = pathFromHash(location.hash) === path && location.hash === next;
  const replace = mode === "replace" || appStack.length === 0;
  if (same) {
    if (!appStack.length) appStack.push(path);
    draw();
    return;
  }
  navLock += 1;
  try {
    if (replace) {
      history.replaceState({ miniapp: true }, "", next);
      if (!appStack.length) appStack.push(path);
      else appStack[appStack.length - 1] = path;
    } else {
      history.pushState({ miniapp: true }, "", next);
      appStack.push(path);
    }
  } finally {
    navLock -= 1;
  }
  syncDeepFact();
  guard();
  draw();
}

function adoptPath(path, reason) {
  if (reason === "pop") {
    if (appStack[appStack.length - 2] === path) appStack.pop();
    else if (appStack[appStack.length - 1] !== path) appStack.splice(0, appStack.length, path);
    return;
  }
  if (appStack[appStack.length - 1] !== path) appStack.push(path);
}

function goBack() {
  const screen = parseRoute(location.hash);
  const plan = currentPlan();
  if (plan.type === "sheet") {
    state.sheet = null;
    draw();
    return;
  }
  if (plan.type === "intro-step") {
    state.introStep = Math.max(0, (state.introStep || 0) - 1);
    draw();
    return;
  }
  if (plan.type === "pick-step") {
    state.step = Math.max(0, (state.step || 0) - 1);
    state.message = "";
    draw();
    return;
  }
  if (plan.type === "instruction-step") {
    const instruction = state.catalog && state.catalog.instructions[screen.instructionId];
    if (instruction) {
      const steps = visibleSteps(instruction, Boolean(state.unverified[`instruction:${instruction.id}`]));
      const index = stepPosition(steps, state.progress, state.cursor[instruction.id]);
      state.cursor[instruction.id] = Math.max(0, index - 1);
    }
    draw();
    return;
  }
  if (plan.type === "route") {
    state.openRoute = "";
    draw();
    return;
  }
  if (plan.type === "history") {
    history.back();
    return;
  }
  if (plan.type === "parent" && plan.path) navigate(plan.path, "replace");
}

function guard() {
  const screen = parseRoute(location.hash);
  if (state.failed || !state.catalog) return;
  if (!state.introSeen && screen.name !== "intro") navigate("/intro");
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
  state.stackDepth = appStack.length || 1;
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
  syncBackButton();
}

function seedPreview(name) {
  state.preview = true;
  const introSteps = { intro: 0, "intro-trust": 1, "intro-sources": 2, "intro-privacy": 3 };
  const intro = Object.prototype.hasOwnProperty.call(introSteps, name);
  const bare = intro || name === "empty";
  const nodate = name === "nodate";
  const china = name === "china";
  state.introStep = intro ? introSteps[name] : 0;
  state.introSeen = !intro;
  const named = new URLSearchParams(location.search).get("startapp") || "";
  state.after = named ? (mapStart(state.catalog, named) || "/trip") : "";
  state.profile = {
    bank_id: bare ? "" : "tbank",
    departure_city_id: bare ? "" : "mow",
    favorite_countries: bare ? [] : ["china", "hong_kong"],
    notify_checklist: true,
    notify_trip: true,
    notify_alerts: false,
    consent_given: !bare,
    onboarding_completed: !bare && name !== "pick" && name !== "onboarding",
    intro_seen: !intro,
    citizenship: "ru",
  };
  state.trip = bare ? null : {
    destination_slug: china ? "china" : "hong_kong",
    departure_city_id: "mow",
    depart_date: china ? "2026-10-31" : nodate ? null : "2026-11-12",
    return_date: china ? "2026-11-14" : nodate ? null : "2026-11-20",
  };
  state.draft = {
    bank_id: state.profile.bank_id,
    departure_city_id: state.profile.departure_city_id,
    destination_slug: bare ? "" : (china ? "china" : "hong_kong"),
    depart_date: china ? "2026-10-31" : nodate || bare ? "" : "2026-11-12",
    return_date: china ? "2026-11-14" : nodate || bare ? "" : "2026-11-20",
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
    intro: "/intro",
    "intro-trust": "/intro",
    "intro-sources": "/intro",
    "intro-privacy": "/intro",
    empty: "/trip",
    nodate: "/trip",
    china: "/trip",
    pick: "/pick",
    onboarding: "/pick",
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

async function markIntro() {
  state.introSeen = true;
  if (!state.profile) state.profile = emptyProfile(true);
  state.profile.intro_seen = true;
  if (state.preview) return;
  const payload = await postJSON("/api/miniapp/intro", {});
  if (payload.profile) state.profile = payload.profile;
  state.introSeen = true;
}

async function finishPick() {
  if (!state.draft.consent) {
    state.message = "Нужно согласие на обработку данных.";
    draw();
    return;
  }
  const profile = {
    bank_id: state.draft.bank_id,
    departure_city_id: state.draft.departure_city_id,
    favorite_countries: [state.draft.destination_slug],
    notify_checklist: state.profile ? state.profile.notify_checklist !== false : true,
    notify_trip: state.profile ? state.profile.notify_trip !== false : true,
    notify_alerts: Boolean(state.profile && state.profile.notify_alerts),
    consent_given: true,
    onboarding_completed: true,
    intro_seen: true,
    citizenship: (state.profile && state.profile.citizenship) || "ru",
  };
  const trip = {
    destination_slug: state.draft.destination_slug,
    departure_city_id: state.draft.departure_city_id,
    depart_date: state.draft.depart_date || null,
    return_date: state.draft.return_date || null,
  };
  const next = afterPick({ deepLink: state.after });
  if (state.preview) {
    state.profile = profile;
    state.trip = trip;
    state.introSeen = true;
    navigate(next);
    return;
  }
  try {
    const payload = await postJSON("/api/miniapp/onboarding", { profile, trip });
    state.profile = payload.profile;
    state.trip = payload.trip;
    state.introSeen = true;
    state.message = "";
    navigate(next);
  } catch (error) {
    state.message = error.message;
    draw();
  }
}

function openPick() {
  state.step = 0;
  state.message = "";
  state.draft.bank_id = (state.profile && state.profile.bank_id) || "";
  state.draft.departure_city_id = (state.trip && state.trip.departure_city_id) || (state.profile && state.profile.departure_city_id) || "";
  state.draft.destination_slug = (state.trip && state.trip.destination_slug) || "";
  state.draft.depart_date = (state.trip && state.trip.depart_date) || "";
  state.draft.return_date = (state.trip && state.trip.return_date) || "";
  state.draft.consent = Boolean(state.profile && state.profile.consent_given);
  navigate("/pick");
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
    goBack();
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
    if (el.dataset.group === "citizenship") target.citizenship = "ru";
    state.message = "";
    if (screen.name === "profile") queueProfileSave();
    draw();
    return;
  }
  if (action === "intro-next") {
    state.introStep = Math.min(3, (state.introStep || 0) + 1);
    draw();
    return;
  }
  if (action === "replay-intro") {
    navigate(beginIntroReplay(state));
    return;
  }
  if (action === "intro-pick" || action === "intro-skip") {
    const choice = action === "intro-pick" ? "pick" : "skip";
    const next = introExit({ action: choice, deepLink: state.after });
    markIntro().then(() => navigate(next)).catch((error) => {
      state.message = error.message;
      draw();
    });
    return;
  }
  if (action === "start-pick") {
    openPick();
    return;
  }
  if (action === "pick-back") {
    goBack();
    return;
  }
  if (action === "pick-next") {
    if (state.step < 2) {
      state.step += 1;
      state.message = "";
      draw();
      return;
    }
    finishPick();
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

window.addEventListener("popstate", () => {
  if (navLock) return;
  adoptPath(pathFromHash(location.hash), "pop");
  syncDeepFact();
  guard();
  draw();
});

window.addEventListener("hashchange", () => {
  if (navLock) return;
  adoptPath(pathFromHash(location.hash), "hash");
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
  wireBackButton();
  try {
    state.catalog = await getJSON("/api/catalog");
  } catch (error) {
    state.failedTitle = "Справочник не открылся";
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
  if (!initData()) {
    state.failedTitle = "Не удалось войти";
    state.failed = "Откройте приложение из Telegram.";
    draw();
    return;
  }
  let serverScreen = "";
  try {
    const session = await postJSON("/api/miniapp/session", {});
    applySession(session);
    serverScreen = session.screen || "";
  } catch (error) {
    state.failedTitle = "Не удалось войти";
    state.failed = error.message;
    draw();
    return;
  }
  const named = params.get("startapp") || params.get("tgWebAppStartParam") || "";
  if (named || serverScreen) state.after = mapStart(state.catalog, named || serverScreen) || "/trip";
  else if (location.hash.startsWith("#/")) {
    const screen = parseRoute(location.hash);
    if (screen.name !== "intro" && screen.name !== "pick") state.after = location.hash.slice(1);
  }
  navigate(bootTarget({
    introSeen: state.introSeen,
    deepLink: state.after,
    hash: location.hash,
  }));
}

boot();
