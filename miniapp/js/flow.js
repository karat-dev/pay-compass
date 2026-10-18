/** Where to go on launch, after the intro, and how a missing date is labeled. */

export function bootTarget({ introSeen, deepLink, hash }) {
  if (!introSeen) return "/intro";
  const path = typeof hash === "string" && hash.startsWith("#/") ? hash.slice(1) : "";
  if (path) return path;
  return deepLink || "/trip";
}

export function introExit({ action, deepLink }) {
  if (action === "pick") return "/pick";
  if (action === "skip") return deepLink || "/guide";
  return deepLink || "/trip";
}

export function afterPick({ deepLink }) {
  return deepLink || "/trip";
}

export function tripWhen(depart) {
  if (!depart) return "Дата не выбрана";
  return "";
}

export function tripCountdown(until) {
  if (until === 0) return "Вылет сегодня";
  if (typeof until === "number" && until > 0) return `До вылета ${until} дн.`;
  if (typeof until === "number" && until < 0) return "Дата вылета уже прошла";
  return "";
}

export function routeForTrip(routes, trip) {
  if (!trip || !trip.destination_slug) return null;
  const origin = trip.departure_city_id || "";
  return (routes || []).find((route) => (
    route.departure_city_id === origin && route.destination_slug === trip.destination_slug
  )) || null;
}

export function searchTicketsUrl({ origin, destination, depart, marker }) {
  if (!/^[A-Z]{3}$/.test(origin || "") || !/^[A-Z]{3}$/.test(destination || "")) return "";
  if (!/^\d+$/.test(String(marker || ""))) return "";
  let date = "";
  if (depart && /^\d{4}-\d{2}-\d{2}$/.test(depart)) {
    const [, month, day] = depart.split("-");
    date = `${day}${month}`;
  }
  return `https://www.aviasales.ru/search/${origin}${date}${destination}1?marker=${marker}`;
}

export function beginIntroReplay(state) {
  state.introStep = 0;
  return "/intro";
}

const TAB_ROOTS = new Set(["trip", "guide", "sos", "profile"]);

function queryFact(screen) {
  if (!screen || !screen.params || typeof screen.params.get !== "function") return "";
  return screen.params.get("fact") || "";
}

export function logicalParent(screen, extra = {}) {
  if (!screen) return "";
  if (screen.name === "search") return extra.returnTo || "/trip";
  if (screen.name === "trip-edit") return "/trip";
  if (screen.name === "country") return "/guide";
  if (screen.name === "section") {
    if (queryFact(screen)) return `/guide/${screen.slug}/${screen.sectionKey}`;
    return `/guide/${screen.slug}`;
  }
  if (screen.name === "instruction") {
    if (screen.instructionSection) return `/guide/${screen.slug}/${screen.instructionSection}`;
    return screen.slug ? `/guide/${screen.slug}` : "/guide";
  }
  if (screen.name === "intro") return extra.introSeen ? "/profile" : "";
  if (screen.name === "pick") return "/trip";
  return "";
}

/** Back stays inside the Mini App. History is used only after an in-app open. */
export function backPlan(input) {
  const screen = input.screen || { name: "trip", params: new URLSearchParams() };
  const stackDepth = input.stackDepth == null ? 1 : input.stackDepth;
  if (input.sheet) return { type: "sheet" };
  if (screen.name === "intro" && (input.introStep || 0) > 0) return { type: "intro-step" };
  if (screen.name === "pick" && (input.pickStep || 0) > 0) return { type: "pick-step" };
  if (screen.name === "instruction" && (input.instructionIndex || 0) > 0) return { type: "instruction-step" };
  if (screen.name === "trip" && input.openRoute) return { type: "route" };
  if (TAB_ROOTS.has(screen.name)) return { type: "none" };
  if (stackDepth > 1) return { type: "history" };
  const path = logicalParent(screen, input);
  if (path) return { type: "parent", path };
  return { type: "none" };
}
