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
